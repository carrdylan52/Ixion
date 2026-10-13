/* Ixion host <-> game module ABI.
 *
 * Each game (Dark Cloud, Dark Chronicle) is built as a shared library that exports exactly one
 * symbol, ixion_get_api. Everything else in the module -- game globals, its private copy of
 * Kazarov, its renderer, mixer and clock -- stays hidden inside it. The host (ixion.exe) loads
 * both modules, runs each game on its own fiber, and switches between them only when a game
 * reaches a checkpoint (the end of a graphics frame).
 *
 * Only plain C types cross this boundary: no C++ objects, no STL, no exceptions, no game pointers
 * and no graphics handles. Memory is never freed on the other side. SDL objects (SDL_Event,
 * SDL_Window *) are the one exception, because host and modules load the same SDL3 shared library.
 */
#ifndef IXION_API_H
#define IXION_API_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define IXION_ABI_VERSION 1u

#if defined(_WIN32)
#define IXION_EXPORT __declspec(dllexport)
#else
#define IXION_EXPORT __attribute__((visibility("default")))
#endif

/* Game identifiers. */
enum {
    IXION_GAME_DARK_CLOUD = 1,     /* Chronicle */
    IXION_GAME_DARK_CHRONICLE = 2, /* ChronicleTwo */
};

/* Why a game reached a checkpoint. */
enum {
    IXION_CHECKPOINT_FRAME_END = 1, /* after a completed graphics frame has been presented */
    IXION_CHECKPOINT_BOOT = 2,      /* reserved: before the first frame */
};

/* A snapshot of where a game is, for logs and for checking that a parked game did not move.
 * Fields a module cannot fill stay -1 (or 0 for counters). */
typedef struct IxionReceipt {
    uint32_t size;          /* sizeof(IxionReceipt), set by the caller */
    uint32_t game_id;
    uint64_t logic_frames;  /* frames the game's own loop has completed */
    uint64_t clock_ticks;   /* the module's Kazarov clock tick count */
    int32_t  mode;          /* game-specific top-level mode, -1 if unknown */
    int32_t  map;           /* game-specific current map or scene number, -1 if unknown */
    int32_t  floor;         /* dungeon floor, -1 outside dungeons or if unknown */
    int32_t  character;     /* active playable character, -1 if unknown */
    float    player_pos[3]; /* active character's world position, all 0 if unknown */
    char     place[48];     /* a human-readable place name if the module knows one, else "" */
} IxionReceipt;

/* A request to travel, from a game or from the host. Reserved for v1 (stations); the v0 hotkey
 * travel does not use it. */
typedef struct IxionTravel {
    uint32_t size;
    uint32_t to_game;
    char     destination[64]; /* the destination module's own startup jump, e.g. "town:10" */
} IxionTravel;

/* Services the host gives a module. Every callback receives the host's user pointer and the
 * calling module's game id. */
typedef struct IxionHost {
    uint32_t size;        /* sizeof(IxionHost) */
    uint32_t abi_version; /* IXION_ABI_VERSION */
    void    *user;

    /* Fills *sdl_event (an SDL_Event) with the next event the host routed to this module and
     * returns 1, or returns 0 when the module's queue is empty. Modules must not call
     * SDL_PollEvent, SDL_PumpEvents or SDL_WaitEvent* themselves. */
    int (*poll_event)(void *user, uint32_t game_id, void *sdl_event);

    /* Called by the module on its own fiber at a safe point. The host may switch to the other
     * game here; the call returns when this module is resumed. Returns 1 if the module was parked
     * (another game ran in between, so the module must rebase its clocks and frame pacing),
     * 0 if it continued straight on. */
    int (*checkpoint)(void *user, uint32_t game_id, uint32_t reason);

    /* One line of log text (no newline needed). */
    void (*log)(void *user, uint32_t game_id, const char *line);

    /* Reserved for v1: a game asks to travel. May be null in v0. */
    void (*request_travel)(void *user, uint32_t game_id, const IxionTravel *travel);
} IxionHost;

/* What a module offers the host. */
typedef struct IxionApi {
    uint32_t    size;        /* sizeof(IxionApi) */
    uint32_t    abi_version; /* IXION_ABI_VERSION */
    uint32_t    game_id;
    const char *name;        /* "Dark Cloud" or "Dark Chronicle" */

    /* Gives the module the host's services. Called once, before run. Returns 0 on success. */
    int (*bind)(const IxionHost *host);

    /* Runs the game with these command-line arguments (argv[0] is a program name). Called once,
     * on the fiber the host made for this game. It normally never returns while the program
     * runs; if it does, the value is the game's exit code. */
    int (*run)(int argc, char **argv);

    /* Called by the host on its own fiber while this module is parked: active != 0 just before the
     * module is resumed as the visible game, 0 just after it was switched away from. The module
     * pauses or resumes its audio output and releases mouse capture here. It must not render,
     * pump events or advance game state. */
    void (*activate)(int active);

    /* The module's SDL_Window *, or null before the game has opened its window. */
    void *(*window)(void);

    /* Fills *out (out->size set by the caller) and returns 0, or returns nonzero if unavailable. */
    int (*inspect)(IxionReceipt *out);
} IxionApi;

/* The module's only export. Returns null if the module does not speak this ABI version. */
typedef const IxionApi *(*IxionGetApiFn)(uint32_t abi_version);
IXION_EXPORT const IxionApi *ixion_get_api(uint32_t abi_version);

#ifdef __cplusplus
}
#endif

#endif /* IXION_API_H */
