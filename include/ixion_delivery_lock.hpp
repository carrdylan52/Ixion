// Cross-process lock for an Ixion ledger or cursor. The empty .lock file stays
// on disk; the OS releases ownership on crash. Never unlink a shared lock.
#pragma once
#include <cstdint>
#include <filesystem>
namespace ixion::delivery {
class Lock {
public:
    explicit Lock(std::filesystem::path path);
    ~Lock();
    bool ok() const { return handle_ != -1; }
    Lock(const Lock &) = delete;
    Lock &operator=(const Lock &) = delete;
private:
    std::intptr_t handle_ = -1;
};
} // namespace ixion::delivery
