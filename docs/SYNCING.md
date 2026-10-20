> On `showcase-crossover`, use the committed recursive pins. Do not run this
> upstream-sync workflow against the showcase: its data generation and donor
> provenance gates require an explicit migration first. The workflow below
> describes the earlier Hop branches.

# Keeping the port forks in step with upstream

Ixion builds on the community ports without changing them in place. Each port is a submodule on a
fork branch that adds only what Ixion needs:

| Submodule | Fork branch | Upstream | Kazarov fork branch |
|---|---|---|---|
| `games/chronicle` | carrdylan52/Chronicle `ixion` | TheMoonPeople/Chronicle `master` | carrdylan52/Kazarov `ixion-old-layout` |
| `games/chronicletwo` | carrdylan52/ChronicleTwo `ixion` | TheMoonPeople/ChronicleTwo `master` | carrdylan52/Kazarov `ixion` |

Each port's `tools/kazarov` points at its Kazarov fork branch, which adds embedded mode
(`platform/embed.hpp`). Ixion pins exact commits, so nothing breaks when upstream moves; catching up
only brings in upstream's fixes and features. Do it every few weeks or before a milestone.

`tools/sync_upstream.py` does the mechanical part. It never force-pushes, never pushes to
TheMoonPeople, and never opens pull requests.

## The steps

1. **First time in a checkout:** `python tools/sync_upstream.py init`. It checks out the submodules
   on their branches and adds an `upstream` remote to each. Set a git identity in each submodule if
   your global one is not set.
2. **Look:** `python tools/sync_upstream.py status`. Per port: how many commits it is behind, the
   files Ixion changes there, and whether upstream's Kazarov pin is already merged.
3. **Merge:** `python tools/sync_upstream.py merge chronicle` (or `chronicletwo`). By default it
   merges upstream's tip. `--to last-green` merges the newest upstream commit whose "PC builds" CI
   passed (needs the GitHub CLI); `--to <sha>` merges a chosen commit. The script merges upstream's
   Kazarov pin into the Kazarov fork branch first, then upstream into the port, and records the
   merged Kazarov in the port. Nothing is pushed.
4. **If it stops on conflicts:** resolve them by keeping upstream's behaviour and re-applying the
   Ixion seam (the files `status` lists). Never edit `ps2/src`. `git add` the files, `git commit`,
   and rerun the same `merge` command; it carries on from where it stopped.
5. **Build and test, all of these:**
   - the port's own tests (its README), so the standalone game still works;
   - the port's module with `-DIXION_BUILD_PLUGIN=ON -DIXION_API_DIR=<Ixion>/include`, and check that
     it exports only `ixion_get_api` (`llvm-readobj --coff-exports`);
   - the host (`host/build-windows.ps1`), the fiber self-test (`ixion_fiber_smoke.exe`), and
     `ixion.exe ... --auto-switch 120:20` with fresh save folders: it must exit 0 with
     `auto-switch PASS`.
6. **Push:** `python tools/sync_upstream.py push chronicle`. It pushes the Kazarov branch first, then
   the port branch, fast-forward only. A refused push means someone else moved the branch: fetch,
   merge, test again.
7. **Pin:** `python tools/sync_upstream.py bump --push`. It refuses to pin a commit that is not on
   the fork yet, commits "Bump ports: ...", and pushes Ixion.

## When upstream changes Kazarov layout

Chronicle still pins the older Kazarov layout (code under `port/`); ChronicleTwo pins the current
one (`src/cpp/`, `include/`). If upstream Chronicle moves to the current layout, `status` warns and
`merge` stops. Then the port should switch to the `ixion` Kazarov branch: point the port's
`.gitmodules` branch at `ixion`, check out the `ixion` branch (or a commit that merges upstream's
new pin into it) in `tools/kazarov`, rebuild, and change `kazarov_branch` for that port in
`tools/sync_upstream.py`. The `ixion-old-layout` branch then retires.

## Extra push targets

Local mirrors go in `tools/sync.local.json` (ignored by git):

```json
{"mirrors": {"chronicle": "<url>", "chronicletwo": "<url>", "kazarov": "<url>", "ixion": "<url>"}}
```

`push` and `bump --push` push to these too, with the same fast-forward-only rule.
