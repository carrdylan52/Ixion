// Exercise the actual DLL boundary without booting a renderer or accessing any
// game data/save.
#include "ixion_api.h"
#include <cstdio>
#include <windows.h>

int Poll(void *, uint32_t, void *) { return 0; }
int Checkpoint(void *, uint32_t, uint32_t) { return 0; }

int main(int argc, char **argv) {
  if (argc != 3)
    return 2; // DLL, disposable save root
  HMODULE module =
      LoadLibraryExA(argv[1], nullptr, LOAD_WITH_ALTERED_SEARCH_PATH);
  if (!module) {
    std::printf("load failed: %lu\n", GetLastError());
    return 1;
  }
  auto get =
      reinterpret_cast<IxionGetApiFn>(GetProcAddress(module, "ixion_get_api"));
  if (!get || get(1))
    return 1;
  const auto *api = get(IXION_ABI_VERSION);
  if (!api || api->size < sizeof(IxionApi))
    return 1;
  uint32_t shortHost = 4;
  if (api->bind(reinterpret_cast<const IxionHost *>(&shortHost)) == 0)
    return 1;
  IxionHost host{sizeof(IxionHost), IXION_ABI_VERSION, nullptr, Poll,
                 Checkpoint,        nullptr,           nullptr};
  if (api->bind(&host) != 0)
    return 1;
  char name[] = "probe";
  char data[] = "--data";
  char save[] = "--save";
  char absent[] = "Z:/ixion-hop-r3-nonexistent-data";
  char *args[] = {name, data, absent, save, argv[2], nullptr};
  if (api->preflight(5, args) == 0)
    return 1;
  const int code = api->run(
      5, args); // even a preflight/run race returns; no setup UI or std::exit
  std::printf("actual dc%u DLL: old ABI/short host rejected; missing-data run "
              "returned %d\n",
              api->game_id, code);
  return code == 3 ? 0 : 1;
}
