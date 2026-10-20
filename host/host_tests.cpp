// This translation unit exercises the private host policy with synthetic
// modules and SDL events.
#include "host.cpp"

namespace {
unsigned failures = 0;
void Check(bool ok, const char *name) {
  if (!ok) {
    std::fprintf(stderr, "FAIL: %s\n", name);
    ++failures;
  }
}
unsigned sceneFrames = 0;
bool paused = false;
ixion::HostState *state = nullptr;
int Bind(const IxionHost *) { return 0; }
int Preflight(int, char **) { return 0; }
void Activate(int active) { paused = active == 0; }
void *Window() { return nullptr; }
int Inspect(IxionReceipt *r) {
  r->scene_ready = sceneFrames >= 6;
  r->logic_frames = sceneFrames;
  r->audio_paused = paused;
  return 0;
}
int Run(int, char **) {
  for (;;) {
    ++sceneFrames;
    ixion::HostCheckpoint(state, 1, IXION_CHECKPOINT_FRAME_END);
  }
}
IxionApi api{
    sizeof(IxionApi), IXION_ABI_VERSION, 1,        "test", Bind, Run, Activate,
    Window,           Inspect,           Preflight};
} // namespace

int main() {
  using namespace ixion;
  Check(ValidApi(&api, 1), "valid ABI");
  uint32_t truncated = sizeof(uint32_t);
  Check(!ValidApi(reinterpret_cast<const IxionApi *>(&truncated), 1),
        "size prefix before later fields");
  auto wrong = api;
  wrong.abi_version = 1;
  Check(!ValidApi(&wrong, 1), "old ABI rejected");
  wrong = api;
  wrong.preflight = nullptr;
  Check(!ValidApi(&wrong, 1), "missing preflight rejected");
  std::puts("ABI prefix/version/entries: PASS");

  HostState h;
  h.games[0].available = true;
  h.games[0].id = 1;
  h.games[0].label = "mock-dc1";
  h.games[0].api = &api;
  for (Uint32 type :
       {SDL_EVENT_TEXT_INPUT, SDL_EVENT_TEXT_EDITING,
        SDL_EVENT_TEXT_EDITING_CANDIDATES, SDL_EVENT_DROP_FILE,
        SDL_EVENT_DROP_TEXT, SDL_EVENT_DROP_BEGIN, SDL_EVENT_DROP_POSITION,
        SDL_EVENT_CLIPBOARD_UPDATE, SDL_EVENT_USER}) {
    SDL_Event e{};
    e.type = type;
    RouteEvent(h, e);
  }
  Check(h.games[0].events.empty(), "all pointer events discarded");
  SDL_Event key{};
  key.type = SDL_EVENT_KEY_DOWN;
  key.key.key = SDLK_W;
  RouteEvent(h, key);
  SDL_Event focus{};
  focus.type = SDL_EVENT_WINDOW_FOCUS_LOST;
  RouteEvent(h, focus);
  DiscardInput(h.games[0]);
  Check(h.games[0].events.size() == 1 &&
            h.games[0].events.front().type == focus.type,
        "discard input keeps window events");
  Check(!GameById(&h, 2), "absent game id rejected");
  SDL_Event travel{};
  travel.type = SDL_EVENT_KEY_DOWN;
  travel.key.key = SDLK_F10;
  RouteEvent(h, travel);
  Check(h.travelRequested,
        "F10 requests travel without reaching the game queue");
  Travel(h);
  Check(h.active == 0 && h.switches == 0, "single-game travel refused");
  std::puts("pointer queues/input discard/single-game travel: PASS");

  IxionReceipt a{};
  a.audio_paused = 1;
  auto b = a;
  Check(SameReceipt(a, b), "stable receipt");
  b.mode++;
  Check(!SameReceipt(a, b), "mode checked");
  b = a;
  b.character++;
  Check(!SameReceipt(a, b), "character checked");
  b = a;
  b.audio_frames++;
  Check(!SameReceipt(a, b), "audio work checked");
  b = a;
  b.audio_paused = 0;
  Check(!SameReceipt(a, b), "pause failure checked");
  std::puts("mode/character/audio park receipts: PASS");

  h.root = ConvertThreadToFiberEx(nullptr, FIBER_FLAG_FLOAT_SWITCH);
  Check(h.root != nullptr, "root fiber");
  h.games[0].host = &h;
  h.games[0].args = {"test"};
  BuildArgv(h.games[0]);
  state = &h;
  Check(CreateGameFiber(h.games[0]), "game fiber");
  Check(Boot(h) == kExitOk && sceneFrames == 6,
        "five loading checkpoints do not count as boot");
  DeleteFiber(h.games[0].fiber);
  ConvertFiberToThread();
  std::puts("boot waits for completed scene frame: PASS");
  std::printf("host regressions: %s (%u failures)\n",
              failures ? "FAIL" : "PASS", failures);
  return failures ? 1 : 0;
}
