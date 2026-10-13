// ixion.exe: runs Dark Cloud and Dark Chronicle as two modules in one process.
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>

#include "host.hpp"

namespace {

void PrintUsage(FILE *out) {
    std::fputs(
        "usage: ixion --dc1 <dll> --dc2 <dll> [options]\n"
        "  --dc1 <dll>          Dark Cloud module (ixion_c1.dll)\n"
        "  --dc1-args \"<args>\"  arguments for Dark Cloud (data, save, window, jump)\n"
        "  --dc2 <dll>          Dark Chronicle module (ixion_c2.dll)\n"
        "  --dc2-args \"<args>\"  arguments for Dark Chronicle\n"
        "  --start dc1|dc2      game shown first (default dc1)\n"
        "  --auto-switch N:M    switch every N host frames, M times, then exit 0 if no parked\n"
        "                       game's receipt changed, 2 otherwise\n"
        "  --log <file>         also write the log to this file\n"
        "F10 travels between the games. Quit with the window close button.\n",
        out);
}

// Parses a decimal count made only of digits (no sign, no spaces). Returns false otherwise.
bool ParseCount(const std::string &text, unsigned long long *value) {
    if (text.empty() || text.find_first_not_of("0123456789") != std::string::npos) return false;
    *value = std::strtoull(text.c_str(), nullptr, 10);
    return true;
}

bool ParseAutoSwitch(const std::string &text, ixion::Options *options) {
    size_t colon = text.find(':');
    if (colon == std::string::npos) return false;
    unsigned long long every = 0;
    unsigned long long count = 0;
    if (!ParseCount(text.substr(0, colon), &every) || !ParseCount(text.substr(colon + 1), &count)) {
        return false;
    }
    if (every == 0 || count == 0 || every > UINT32_MAX || count > UINT32_MAX) return false;
    options->autoSwitch = true;
    options->autoEvery = static_cast<uint32_t>(every);
    options->autoCount = static_cast<uint32_t>(count);
    return true;
}

}  // namespace

int main(int argc, char **argv) {
    ixion::Options options;
    bool haveDc1 = false;
    bool haveDc2 = false;

    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        const bool hasValue = i + 1 < argc;
        if (arg == "--help" || arg == "-h") {
            PrintUsage(stdout);
            return 0;
        } else if (arg == "--dc1" && hasValue) {
            options.dc1Dll = argv[++i];
            haveDc1 = true;
        } else if (arg == "--dc2" && hasValue) {
            options.dc2Dll = argv[++i];
            haveDc2 = true;
        } else if ((arg == "--dc1-args" || arg == "--dc2-args") && hasValue) {
            std::vector<std::string> words;
            std::string error;
            if (!ixion::SplitArgs(argv[++i], &words, &error)) {
                std::fprintf(stderr, "ixion: %s: %s\n", arg.c_str(), error.c_str());
                return ixion::kExitStartup;
            }
            std::vector<std::string> &target = arg == "--dc1-args" ? options.dc1Args : options.dc2Args;
            target = words;
        } else if (arg == "--start" && hasValue) {
            const std::string value = argv[++i];
            if (value == "dc1") {
                options.startGame = 1;
            } else if (value == "dc2") {
                options.startGame = 2;
            } else {
                std::fprintf(stderr, "ixion: --start takes dc1 or dc2\n");
                return ixion::kExitStartup;
            }
        } else if (arg == "--auto-switch" && hasValue) {
            if (!ParseAutoSwitch(argv[++i], &options)) {
                std::fprintf(stderr, "ixion: --auto-switch takes N:M with N and M positive\n");
                return ixion::kExitStartup;
            }
        } else if (arg == "--log" && hasValue) {
            options.logPath = argv[++i];
        } else {
            std::fprintf(stderr, "ixion: unknown or incomplete option: %s\n", arg.c_str());
            PrintUsage(stderr);
            return ixion::kExitStartup;
        }
    }

    if (!haveDc1 || !haveDc2) {
        PrintUsage(stderr);
        return ixion::kExitStartup;
    }
    if (!options.logPath.empty() && !ixion::LogOpen(options.logPath)) {
        std::fprintf(stderr, "ixion: cannot open log file %s\n", options.logPath.c_str());
        return ixion::kExitStartup;
    }

    ixion::Quit(ixion::RunHost(options));
}
