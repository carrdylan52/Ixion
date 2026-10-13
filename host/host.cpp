// Ixion host: fibers, module loading, event routing, the travel hotkey and receipts.
#include <windows.h>

#include <SDL3/SDL.h>

#include <chrono>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <deque>
#include <mutex>

#include "host.hpp"
#include "ixion_api.h"

namespace ixion {
namespace {

constexpr SIZE_T kFiberStackCommit = 1u << 20;   // 1 MiB committed up front
constexpr SIZE_T kFiberStackReserve = 8u << 20;  // 8 MiB reserved per game fiber
constexpr int kBootTimeoutSeconds = 120;
constexpr uint64_t kHeartbeatFrames = 3600;

std::mutex g_logMutex;
FILE *g_logFile = nullptr;

struct HostState;

// One game: its module, its fiber and the bookkeeping the host keeps for it.
struct Game {
    uint32_t id = 0;
    const char *label = "";
    std::string path;     // module path as given on the command line
    std::wstring fullPath;
    std::vector<std::string> args; // args[0] is the program name
    std::vector<char *> argv;      // NULL-terminated view of args
    HMODULE module = nullptr;
    const IxionApi *api = nullptr;
    LPVOID fiber = nullptr;
    LPVOID resume = nullptr; // the fiber to switch to when the host resumes this game
    std::deque<SDL_Event> events;
    bool checkpointed = false;
    bool parked = false;    // the next return from checkpoint reports that the game was parked
    bool parkValid = false; // a receipt was taken when this game was switched away from
    bool parkOk = false;    // that receipt was filled by the module
    IxionReceipt parkReceipt{};
    bool finished = false;  // run() returned; the game is parked for good
    int exitCode = 0;
    HostState *host = nullptr;
};

struct HostState {
    Options options;
    Game games[2]; // games[0] is Dark Cloud, games[1] is Dark Chronicle
    int active = 0;
    LPVOID root = nullptr;
    IxionHost table{};
    bool quit = false;
    bool travelRequested = false;
    uint32_t switches = 0;
    uint32_t mismatches = 0;
    uint64_t frames = 0;
};

Game *GameById(HostState *h, uint32_t id) {
    if (id < 1 || id > 2) return nullptr;
    return &h->games[id - 1];
}

// Host callbacks receive the HostState as their user pointer.
Game *GameFromUser(void *user, uint32_t id) {
    return GameById(static_cast<HostState *>(user), id);
}

// Converts a narrow command-line string to UTF-16. mingw's main receives ANSI text, so use CP_ACP.
std::wstring ToWide(const std::string &text) {
    if (text.empty()) return std::wstring();
    int count = MultiByteToWideChar(CP_ACP, 0, text.data(), static_cast<int>(text.size()), nullptr, 0);
    std::wstring out(static_cast<size_t>(count), L'\0');
    MultiByteToWideChar(CP_ACP, 0, text.data(), static_cast<int>(text.size()), out.data(), count);
    return out;
}

std::wstring FullPath(const std::string &text) {
    std::wstring wide = ToWide(text);
    DWORD needed = GetFullPathNameW(wide.c_str(), 0, nullptr, nullptr);
    if (needed == 0) return wide;
    std::wstring out(needed, L'\0');
    DWORD written = GetFullPathNameW(wide.c_str(), needed, out.data(), nullptr);
    out.resize(written);
    return out;
}

SDL_Window *WindowOf(const Game &g) {
    return g.api ? static_cast<SDL_Window *>(g.api->window()) : nullptr;
}

// Fills a receipt with the "unknown" defaults, then asks the module to fill what it can.
bool InspectGame(const Game &g, IxionReceipt *out) {
    *out = IxionReceipt{};
    out->size = sizeof(IxionReceipt);
    out->game_id = g.id;
    out->mode = -1;
    out->map = -1;
    out->floor = -1;
    out->character = -1;
    return g.api != nullptr && g.api->inspect(out) == 0;
}

// The fields that must not move while a game is parked.
bool SameReceipt(const IxionReceipt &a, const IxionReceipt &b) {
    return a.logic_frames == b.logic_frames && a.clock_ticks == b.clock_ticks && a.map == b.map &&
           a.floor == b.floor && std::memcmp(a.player_pos, b.player_pos, sizeof a.player_pos) == 0;
}

void LogReceipt(const Game &g, const char *tag, const IxionReceipt &r) {
    LogLine("  %s %s: frames=%llu ticks=%llu mode=%d map=%d floor=%d char=%d pos=(%.3f, %.3f, %.3f) place=\"%s\"",
            g.label, tag, static_cast<unsigned long long>(r.logic_frames),
            static_cast<unsigned long long>(r.clock_ticks), r.mode, r.map, r.floor, r.character,
            r.player_pos[0], r.player_pos[1], r.player_pos[2], r.place);
}

// Takes the receipt of a game that has just been switched away from, at its checkpoint.
void Park(Game &g) {
    g.parkOk = InspectGame(g, &g.parkReceipt);
    g.parkValid = true;
}

void PumpEvents(HostState &h);

// Compares a game that was switched away from with its park receipt. Clears the park record, so a
// game is checked once per park. Returns true if the receipt did not change.
bool CheckPark(HostState &h, Game &g, const char *when) {
    if (!g.parkValid) return true;
    IxionReceipt now{};
    bool nowOk = InspectGame(g, &now);
    bool same = g.parkOk && nowOk && SameReceipt(g.parkReceipt, now);
    if (!same) h.mismatches++;
    LogLine("[%s] %s: %s", g.label, when,
            same ? "receipt unchanged while parked" : "receipt CHANGED while parked");
    g.parkValid = false;
    return same;
}

// Switches to the game's saved fiber. Returns when the game next reaches a checkpoint, or when its
// run() returns. A game that was switched away from is compared against its park receipt first.
void ResumeGame(HostState &h, Game &g) {
    if (g.parkValid) {
        CheckPark(h, g, "resume check");
        g.parked = true;
    }
    SwitchToFiber(g.resume);
}

// Gives the game one routed event at a time to its module. When its queue is empty the host pumps
// SDL first: boot and a game's own loading run before the main loop pumps, and the windows of both
// games belong to the same thread, so an unpumped queue would leave them unanswered to the OS.
int HostPollEvent(void *user, uint32_t gameId, void *sdlEvent) {
    HostState *h = static_cast<HostState *>(user);
    Game *g = GameById(h, gameId);
    if (!g || !sdlEvent) return 0;
    if (g->events.empty()) PumpEvents(*h);
    if (g->events.empty()) return 0;
    *static_cast<SDL_Event *>(sdlEvent) = g->events.front();
    g->events.pop_front();
    return 1;
}

// Called on a game's fiber at a safe point. The host switches to the root fiber; the call returns
// when the host resumes this game, reporting whether the game was parked in between.
int HostCheckpoint(void *user, uint32_t gameId, uint32_t reason) {
    (void)reason;
    HostState *h = static_cast<HostState *>(user);
    Game *g = GameById(h, gameId);
    LPVOID current = GetCurrentFiber();
    if (!g || current == h->root) return 0;
    g->resume = current;
    g->checkpointed = true;
    SwitchToFiber(h->root);
    int parked = g->parked ? 1 : 0;
    g->parked = false;
    return parked;
}

void HostLog(void *user, uint32_t gameId, const char *line) {
    Game *g = GameFromUser(user, gameId);
    LogLine("[%s] %s", g ? g->label : "?", line ? line : "");
}

// Maps an SDL event to the window it belongs to. Returns false for events with no window.
bool EventWindowId(const SDL_Event &ev, SDL_WindowID *id) {
    switch (ev.type) {
    case SDL_EVENT_KEY_DOWN:
    case SDL_EVENT_KEY_UP:
        *id = ev.key.windowID;
        return true;
    case SDL_EVENT_TEXT_EDITING:
        *id = ev.edit.windowID;
        return true;
    case SDL_EVENT_TEXT_EDITING_CANDIDATES:
        *id = ev.edit_candidates.windowID;
        return true;
    case SDL_EVENT_PEN_PROXIMITY_IN:
    case SDL_EVENT_PEN_PROXIMITY_OUT:
        *id = ev.pproximity.windowID;
        return true;
    case SDL_EVENT_PEN_DOWN:
    case SDL_EVENT_PEN_UP:
        *id = ev.ptouch.windowID;
        return true;
    case SDL_EVENT_PEN_BUTTON_DOWN:
    case SDL_EVENT_PEN_BUTTON_UP:
        *id = ev.pbutton.windowID;
        return true;
    case SDL_EVENT_PEN_MOTION:
        *id = ev.pmotion.windowID;
        return true;
    case SDL_EVENT_PEN_AXIS:
        *id = ev.paxis.windowID;
        return true;
    case SDL_EVENT_TEXT_INPUT:
        *id = ev.text.windowID;
        return true;
    case SDL_EVENT_MOUSE_MOTION:
        *id = ev.motion.windowID;
        return true;
    case SDL_EVENT_MOUSE_BUTTON_DOWN:
    case SDL_EVENT_MOUSE_BUTTON_UP:
        *id = ev.button.windowID;
        return true;
    case SDL_EVENT_MOUSE_WHEEL:
        *id = ev.wheel.windowID;
        return true;
    case SDL_EVENT_FINGER_DOWN:
    case SDL_EVENT_FINGER_UP:
    case SDL_EVENT_FINGER_MOTION:
    case SDL_EVENT_FINGER_CANCELED:
        *id = ev.tfinger.windowID;
        return true;
    case SDL_EVENT_DROP_FILE:
    case SDL_EVENT_DROP_TEXT:
    case SDL_EVENT_DROP_BEGIN:
    case SDL_EVENT_DROP_COMPLETE:
    case SDL_EVENT_DROP_POSITION:
        *id = ev.drop.windowID;
        return true;
    default:
        break;
    }
    const Uint32 type = ev.type;
    if (type >= static_cast<Uint32>(SDL_EVENT_WINDOW_FIRST) &&
        type <= static_cast<Uint32>(SDL_EVENT_WINDOW_LAST)) {
        *id = ev.window.windowID;
        return true;
    }
    return false;
}

// The game whose window owns the given SDL window ID, or null.
Game *OwnerOf(HostState &h, SDL_WindowID id) {
    for (Game &g : h.games) {
        SDL_Window *w = WindowOf(g);
        if (w && SDL_GetWindowID(w) == id) return &g;
    }
    return nullptr;
}

// Routes one SDL event. Window events go to the owning game, other events with a window go to the
// game that owns that window, and events without a known window go to the active game. F10 is the
// travel hotkey and goes to no game.
void RouteEvent(HostState &h, const SDL_Event &ev) {
    switch (ev.type) {
    case SDL_EVENT_QUIT:
    case SDL_EVENT_WINDOW_CLOSE_REQUESTED:
        h.quit = true;
        return;
    case SDL_EVENT_KEY_DOWN:
    case SDL_EVENT_KEY_UP:
        if (ev.key.key == SDLK_F10) {
            if (ev.type == SDL_EVENT_KEY_DOWN && !ev.key.repeat) h.travelRequested = true;
            return;
        }
        break;
    default:
        break;
    }
    Game *target = nullptr;
    SDL_WindowID id = 0;
    if (EventWindowId(ev, &id)) target = OwnerOf(h, id);
    if (!target) target = &h.games[h.active];
    target->events.push_back(ev);
}

void PumpEvents(HostState &h) {
    SDL_Event ev;
    while (SDL_PollEvent(&ev)) RouteEvent(h, ev);
}

VOID CALLBACK GameFiberMain(LPVOID param) {
    Game *g = static_cast<Game *>(param);
    int code = g->api->run(static_cast<int>(g->args.size()), g->argv.data());
    g->exitCode = code;
    g->finished = true;
    LogLine("[%s] run() returned %d; the game stays parked", g->label, code);
    for (;;) SwitchToFiber(g->host->root);
}

void BuildArgv(Game &g) {
    g.argv.clear();
    for (std::string &arg : g.args) g.argv.push_back(&arg[0]);
    g.argv.push_back(nullptr);
}

bool LoadGame(HostState &h, Game &g) {
    g.fullPath = FullPath(g.path);
    g.module = LoadLibraryExW(g.fullPath.c_str(), nullptr, LOAD_WITH_ALTERED_SEARCH_PATH);
    if (!g.module) {
        LogLine("[%s] cannot load %s (error %lu)", g.label, g.path.c_str(),
                static_cast<unsigned long>(GetLastError()));
        return false;
    }
    FARPROC proc = GetProcAddress(g.module, "ixion_get_api");
    if (!proc) {
        LogLine("[%s] %s does not export ixion_get_api", g.label, g.path.c_str());
        return false;
    }
    IxionGetApiFn getApi = reinterpret_cast<IxionGetApiFn>(proc);
    g.api = getApi(IXION_ABI_VERSION);
    if (!g.api || g.api->abi_version != IXION_ABI_VERSION || g.api->game_id != g.id) {
        LogLine("[%s] %s does not speak ABI %u for this game", g.label, g.path.c_str(),
                static_cast<unsigned>(IXION_ABI_VERSION));
        return false;
    }
    if (!g.api->bind || !g.api->run || !g.api->activate || !g.api->window || !g.api->inspect) {
        LogLine("[%s] %s is missing required API entries", g.label, g.path.c_str());
        return false;
    }
    if (g.api->bind(&h.table) != 0) {
        LogLine("[%s] bind failed", g.label);
        return false;
    }
    LogLine("[%s] loaded %s (%s)", g.label, g.path.c_str(), g.api->name ? g.api->name : "unnamed");
    return true;
}

bool CreateGameFiber(Game &g) {
    g.fiber = CreateFiberEx(kFiberStackCommit, kFiberStackReserve, FIBER_FLAG_FLOAT_SWITCH,
                            GameFiberMain, &g);
    if (!g.fiber) {
        LogLine("[%s] CreateFiberEx failed (error %lu)", g.label,
                static_cast<unsigned long>(GetLastError()));
        return false;
    }
    g.resume = g.fiber;
    return true;
}

// Runs dc1 to its first checkpoint, then dc2, the same way for both. Each game is parked after its
// boot so the receipts for the later comparison exist, and its audio is paused until it is shown.
ExitCode Boot(HostState &h) {
    for (Game &g : h.games) {
        LogLine("boot: running %s to its first checkpoint", g.label);
        auto started = std::chrono::steady_clock::now();
        ResumeGame(h, g);
        double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
        if (g.finished) {
            LogLine("boot failed: %s returned (code %d) before its first checkpoint", g.label, g.exitCode);
            return kExitGameReturned;
        }
        if (!g.checkpointed) {
            LogLine("boot failed: %s did not checkpoint", g.label);
            return kExitBootFailed;
        }
        if (seconds > kBootTimeoutSeconds) {
            LogLine("boot failed: %s took %.1f s to reach its first checkpoint (limit %d s)", g.label,
                    seconds, kBootTimeoutSeconds);
            return kExitBootFailed;
        }
        Park(g);
        g.api->activate(0);
        LogLine("boot: %s reached its first checkpoint after %.2f s", g.label, seconds);
    }
    return kExitOk;
}

// Shows the start game's window, hides the other, and activates the start game.
void ShowStart(HostState &h) {
    Game &start = h.games[h.active];
    Game &other = h.games[1 - h.active];
    if (SDL_Window *w = WindowOf(start)) {
        SDL_ShowWindow(w);
        SDL_RaiseWindow(w);
    } else {
        LogLine("warning: %s has no window yet", start.label);
    }
    if (SDL_Window *w = WindowOf(other)) SDL_HideWindow(w);
    start.api->activate(1);
    LogLine("active: %s", start.label);
}

// The F10 travel. The active game is already parked at its checkpoint. This switches the windows
// and audio, then leaves the incoming game to be resumed by the main loop.
void Travel(HostState &h) {
    Game &out = h.games[h.active];
    Game &in = h.games[1 - h.active];
    if (in.finished) {
        LogLine("travel refused: %s has already ended", in.label);
        return;
    }
    Park(out);
    out.api->activate(0);
    if (SDL_Window *w = WindowOf(out)) SDL_HideWindow(w);
    if (SDL_Window *w = WindowOf(in)) {
        SDL_ShowWindow(w);
        SDL_RaiseWindow(w);
    } else {
        LogLine("warning: %s has no window", in.label);
    }
    in.api->activate(1);
    in.parked = true; // its checkpoint returns 1 when it is resumed below
    h.switches++;
    LogLine("switch %u: %s -> %s (host frame %llu)", h.switches, out.label, in.label,
            static_cast<unsigned long long>(h.frames));
    if (out.parkOk) {
        LogReceipt(out, "parked", out.parkReceipt);
    } else {
        LogLine("  %s parked: receipt unavailable", out.label);
    }
    IxionReceipt inNow{};
    if (InspectGame(in, &inNow)) {
        LogReceipt(in, "incoming", inNow);
    } else {
        LogLine("  %s incoming: receipt unavailable", in.label);
    }
    h.active = 1 - h.active;
}

int Summary(HostState &h) {
    // The game parked by the last switch is never resumed, so its receipt is checked here instead.
    for (Game &g : h.games) {
        if (&g != &h.games[h.active]) CheckPark(h, g, "end check");
    }
    LogLine("auto-switch summary: %u switches over %llu host frames, %u receipt mismatches", h.switches,
            static_cast<unsigned long long>(h.frames), h.mismatches);
    LogLine("auto-switch %s", h.mismatches == 0 ? "PASS" : "FAIL");
    return h.mismatches == 0 ? kExitOk : kExitMismatch;
}

// The root fiber's loop: route events, travel if asked, resume the active game for one frame.
int MainLoop(HostState &h) {
    const bool autoSwitch = h.options.autoSwitch;
    for (;;) {
        PumpEvents(h);
        if (h.quit) {
            // An acceptance run that is closed early has not tested anything, so it must not pass.
            if (autoSwitch && h.switches < h.options.autoCount) {
                LogLine("auto-switch INCOMPLETE: ended after %u of %u switches", h.switches,
                        h.options.autoCount);
                return kExitIncomplete;
            }
            return kExitOk;
        }
        const bool autoDue = autoSwitch && h.switches < h.options.autoCount && h.frames > 0 &&
                             h.frames % h.options.autoEvery == 0;
        if (h.travelRequested || autoDue) {
            h.travelRequested = false;
            Travel(h);
        }
        ResumeGame(h, h.games[h.active]);
        h.frames++;
        Game &active = h.games[h.active];
        if (active.finished) {
            LogLine("%s ended; quitting", active.label);
            return kExitGameReturned;
        }
        if (autoSwitch && h.switches >= h.options.autoCount) return Summary(h);
        if (h.frames % kHeartbeatFrames == 0) {
            LogLine("heartbeat: host frame %llu, active %s, switches %u",
                    static_cast<unsigned long long>(h.frames), active.label, h.switches);
        }
    }
}

}  // namespace

bool SplitArgs(const std::string &text, std::vector<std::string> *out, std::string *error) {
    out->clear();
    std::string current;
    bool inToken = false;
    bool quoted = false;
    for (char c : text) {
        if (c == '"') {
            quoted = !quoted;
            inToken = true;
            continue;
        }
        if (!quoted && (c == ' ' || c == '\t' || c == '\r' || c == '\n')) {
            if (inToken) out->push_back(current);
            current.clear();
            inToken = false;
            continue;
        }
        current.push_back(c);
        inToken = true;
    }
    if (quoted) {
        if (error) *error = "unclosed double quote in argument string";
        return false;
    }
    if (inToken) out->push_back(current);
    return true;
}

bool LogOpen(const std::string &path) {
    std::lock_guard<std::mutex> lock(g_logMutex);
    g_logFile = std::fopen(path.c_str(), "w");
    return g_logFile != nullptr;
}

void LogLine(const char *fmt, ...) {
    char buffer[2048];
    va_list args;
    va_start(args, fmt);
    std::vsnprintf(buffer, sizeof buffer, fmt, args);
    va_end(args);
    std::lock_guard<std::mutex> lock(g_logMutex);
    std::fputs(buffer, stdout);
    std::fputc('\n', stdout);
    std::fflush(stdout);
    if (g_logFile) {
        std::fputs(buffer, g_logFile);
        std::fputc('\n', g_logFile);
        std::fflush(g_logFile);
    }
}

void Quit(int code) {
    LogLine("ixion exiting with code %d", code);
    {
        std::lock_guard<std::mutex> lock(g_logMutex);
        if (g_logFile) {
            std::fclose(g_logFile);
            g_logFile = nullptr;
        }
    }
    TerminateProcess(GetCurrentProcess(), static_cast<UINT>(code));
    ExitProcess(static_cast<UINT>(code));
}

int RunHost(const Options &options) {
    HostState h;
    h.options = options;

    h.games[0].id = IXION_GAME_DARK_CLOUD;
    h.games[0].label = "dc1";
    h.games[0].path = options.dc1Dll;
    h.games[0].args.push_back("ixion-dc1");
    h.games[0].args.insert(h.games[0].args.end(), options.dc1Args.begin(), options.dc1Args.end());

    h.games[1].id = IXION_GAME_DARK_CHRONICLE;
    h.games[1].label = "dc2";
    h.games[1].path = options.dc2Dll;
    h.games[1].args.push_back("ixion-dc2");
    h.games[1].args.insert(h.games[1].args.end(), options.dc2Args.begin(), options.dc2Args.end());

    for (Game &g : h.games) {
        g.host = &h;
        BuildArgv(g);
        std::string joined;
        for (const std::string &arg : g.args) joined += " [" + arg + "]";
        LogLine("[%s] run args:%s", g.label, joined.c_str());
    }
    h.active = options.startGame == IXION_GAME_DARK_CHRONICLE ? 1 : 0;

    h.table.size = sizeof(IxionHost);
    h.table.abi_version = IXION_ABI_VERSION;
    h.table.user = &h;
    h.table.poll_event = HostPollEvent;
    h.table.checkpoint = HostCheckpoint;
    h.table.log = HostLog;
    h.table.request_travel = nullptr; // reserved for v1

    SDL_SetAppMetadata("Ixion", "hop-v0", "dev.ixion.host");
    if (!SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS)) {
        LogLine("SDL_Init failed: %s", SDL_GetError());
        return kExitStartup;
    }

    h.root = ConvertThreadToFiberEx(nullptr, FIBER_FLAG_FLOAT_SWITCH);
    if (!h.root) {
        LogLine("ConvertThreadToFiberEx failed (error %lu)", static_cast<unsigned long>(GetLastError()));
        return kExitStartup;
    }

    for (Game &g : h.games) {
        if (!LoadGame(h, g)) return kExitStartup;
    }
    for (Game &g : h.games) {
        if (!CreateGameFiber(g)) return kExitStartup;
    }

    const ExitCode booted = Boot(h);
    if (booted != kExitOk) return booted;
    ShowStart(h);
    return MainLoop(h);
}

}  // namespace ixion
