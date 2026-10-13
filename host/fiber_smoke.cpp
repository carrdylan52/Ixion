// Fiber self-test for the Ixion host: no games and no SDL. Root fiber, two game fibers, and a
// nested fiber under game B that checkpoints on its own. Checks resume order and that the x87 and
// SSE rounding modes set differently in each fiber survive every switch.
#include <windows.h>

#include <xmmintrin.h>

#include <cstdio>
#include <string>

namespace {

constexpr SIZE_T kStackCommit = 64u << 10;
constexpr SIZE_T kStackReserve = 1u << 20;
constexpr int kRounds = 64;

// x87 rounding bits (control word bits 10-11). MXCSR keeps the same encoding in bits 13-14.
constexpr unsigned kNear = 0x0000u;
constexpr unsigned kDown = 0x0400u;
constexpr unsigned kUp = 0x0800u;
constexpr unsigned kChop = 0x0C00u;

struct Slot {
    LPVOID fiber = nullptr;
    LPVOID resume = nullptr; // where the root continues this slot next
};

LPVOID g_root = nullptr;
Slot g_a;
Slot g_b;
LPVOID g_nested = nullptr;
std::string g_trace;

[[noreturn]] void Fail(const char *what) {
    std::printf("fiber smoke: FAIL: %s (trace so far: %s)\n", what, g_trace.c_str());
    std::fflush(stdout);
    ExitProcess(1);
}

void SetFp(unsigned rc) {
    unsigned short cw = 0;
    __asm__ volatile("fnstcw %0" : "=m"(cw));
    cw = static_cast<unsigned short>((cw & ~0x0C00u) | rc);
    __asm__ volatile("fldcw %0" : : "m"(cw));
    _mm_setcsr((_mm_getcsr() & ~0x6000u) | (rc << 3));
}

void CheckFp(unsigned rc, char who) {
    unsigned short cw = 0;
    __asm__ volatile("fnstcw %0" : "=m"(cw));
    const unsigned csr = _mm_getcsr();
    if ((cw & 0x0C00u) != rc || (csr & 0x6000u) != (rc << 3)) {
        std::printf("fiber smoke: FP state of %c changed across a switch (cw=%04x mxcsr=%08x)\n", who,
                    static_cast<unsigned>(cw), csr);
        Fail("floating-point control state");
    }
}

// Records the yield and switches to the root. The owner's resume target is updated so the root
// later resumes the fiber that actually yielded (the nested fiber, when it yields for game B).
void Checkpoint(Slot &owner, unsigned rc, char tag) {
    owner.resume = GetCurrentFiber();
    g_trace.push_back(tag);
    SwitchToFiber(g_root);
    CheckFp(rc, tag);
}

VOID CALLBACK FiberA(LPVOID) {
    for (;;) {
        SetFp(kUp);
        Checkpoint(g_a, kUp, 'A');
    }
}

VOID CALLBACK NestedFiber(LPVOID) {
    for (;;) {
        SetFp(kChop);
        Checkpoint(g_b, kChop, 'N');
        // Hand control back to game B. It continues after its SwitchToFiber(nested) call.
        SwitchToFiber(g_b.fiber);
        CheckFp(kChop, 'N');
    }
}

VOID CALLBACK FiberB(LPVOID) {
    g_nested = CreateFiberEx(kStackCommit, kStackReserve, FIBER_FLAG_FLOAT_SWITCH, NestedFiber, nullptr);
    if (!g_nested) Fail("CreateFiberEx (nested)");
    for (;;) {
        SetFp(kDown);
        Checkpoint(g_b, kDown, 'B');
        // Run the nested fiber until it yields to the root and then hands back to us.
        SwitchToFiber(g_nested);
        CheckFp(kDown, 'B');
    }
}

void Resume(Slot &slot) {
    SwitchToFiber(slot.resume);
}

}  // namespace

int main() {
    g_root = ConvertThreadToFiberEx(nullptr, FIBER_FLAG_FLOAT_SWITCH);
    if (!g_root) Fail("ConvertThreadToFiberEx");
    SetFp(kNear);

    g_a.fiber = CreateFiberEx(kStackCommit, kStackReserve, FIBER_FLAG_FLOAT_SWITCH, FiberA, nullptr);
    g_b.fiber = CreateFiberEx(kStackCommit, kStackReserve, FIBER_FLAG_FLOAT_SWITCH, FiberB, nullptr);
    if (!g_a.fiber || !g_b.fiber) Fail("CreateFiberEx");
    g_a.resume = g_a.fiber;
    g_b.resume = g_b.fiber;

    // Round r: A yields once; then B yields once, directly on even rounds and through the nested
    // fiber on odd rounds. The trace must read A,B,A,N,A,B,A,N,... in that order.
    for (int r = 0; r < kRounds; ++r) {
        Resume(g_a);
        CheckFp(kNear, 'R');
        if (g_trace.size() != static_cast<size_t>(2 * r + 1) || g_trace.back() != 'A') Fail("resume order (A)");
        Resume(g_b);
        CheckFp(kNear, 'R');
        const char want = (r % 2 == 0) ? 'B' : 'N';
        if (g_trace.size() != static_cast<size_t>(2 * r + 2) || g_trace.back() != want) {
            Fail("resume order (B or nested N)");
        }
    }

    std::printf("fiber smoke: PASS (%d rounds, %zu switches, floating-point state intact in root, A, B and nested fiber)\n",
                kRounds, g_trace.size());
    std::fflush(stdout);
    return 0;
}
