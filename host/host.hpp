// Ixion host: owns SDL, the root fiber, the two game fibers and event routing.
#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "ixion_api.h"

namespace ixion {

// Process exit codes.
enum ExitCode : int {
    kExitOk = 0,
    kExitStartup = 1,      // bad arguments, SDL failure or a module that will not load
    kExitMismatch = 2,     // --auto-switch: a parked game's receipt changed
    kExitBootFailed = 3,   // a game did not reach its first checkpoint in time
    kExitGameReturned = 4, // a game's run() returned
    kExitIncomplete = 5,   // --auto-switch: the program ended before all M switches ran
};

// Command-line options for ixion.exe.
struct Options {
    std::string dc1Dll;
    std::string dc2Dll;
    std::vector<std::string> dc1Args;
    std::vector<std::string> dc2Args;
    uint32_t startGame = IXION_GAME_DARK_CLOUD;
    bool autoSwitch = false;
    uint32_t autoEvery = 0; // host frames between switches
    uint32_t autoCount = 0; // switches before the summary
    std::string logPath;    // optional file that mirrors the log
};

// Splits an argument string on whitespace. Double quotes group words and are removed; backslashes
// are literal so Windows paths work unquoted. Returns false with *error set on an unclosed quote.
bool SplitArgs(const std::string &text, std::vector<std::string> *out, std::string *error);

// Opens the log file mirror. Returns false if the file cannot be created.
bool LogOpen(const std::string &path);

// Writes one line to stdout and to the log file, if open.
#if defined(__GNUC__)
void LogLine(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
#else
void LogLine(const char *fmt, ...);
#endif

// Flushes the log and ends the process with TerminateProcess. Never returns.
[[noreturn]] void Quit(int code);

// Loads both games, boots them, and runs the main loop. Returns the exit code.
int RunHost(const Options &options);

}  // namespace ixion
