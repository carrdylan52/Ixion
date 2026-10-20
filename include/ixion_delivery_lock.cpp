// Kept in its own translation unit: Windows RECT and the game RECT collide.
#include "ixion_delivery_lock.hpp"
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#else
#include <fcntl.h>
#include <sys/file.h>
#include <unistd.h>
#endif
namespace ixion::delivery {
Lock::Lock(std::filesystem::path path) {
    path += ".lock";
#ifdef _WIN32
    handle_ = reinterpret_cast<std::intptr_t>(CreateFileW(path.c_str(), GENERIC_READ | GENERIC_WRITE, 0,
                nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr));
#else
    handle_ = open(path.c_str(), O_CREAT | O_RDWR | O_CLOEXEC, 0600);
    if (ok() && flock(static_cast<int>(handle_), LOCK_EX | LOCK_NB) != 0) {
        close(static_cast<int>(handle_));
        handle_ = -1;
    }
#endif
}
Lock::~Lock() {
#ifdef _WIN32
    if (ok()) CloseHandle(reinterpret_cast<HANDLE>(handle_));
#else
    if (ok()) close(static_cast<int>(handle_));
#endif
}
} // namespace ixion::delivery
