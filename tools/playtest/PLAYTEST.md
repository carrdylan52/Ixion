# Crossover demo guide

This source branch provides a 29-mode launcher. It does not include a playable
asset package. Build the binaries and generate local packs from your discs as
described in [SHOWCASE.md](../../docs/SHOWCASE.md). The Opar recipe prepares two
packs. With both games' data and staged binaries, the supplied recipe supports
**Inspect, Hop, Opar, Ridepod, NativeDC1 and NativeDC2**. The remaining 23 modes
have source implementations but no complete published pack recipe. They need
additional local packs and are labeled in the menu. The table below is an
inventory of experiments, not a claim that all are reproducible from the helper.

Run `Play-Crossover.cmd -PackageRoot <local-package> -Dc1Data <data> -Dc2Data <data>`
for the menu, or `Play-Ixion.ps1 -Mode Opar` with the same arguments for Opar.
`IXION_DC1_DATA` and `IXION_DC2_DATA` are alternative data-path settings.
Use `-DryRun` to inspect any mode. Missing inputs stop before launch.

Every launch uses a fresh run/save directory under the package's `runs/` (or
`-RunRoot`). Never copy campaign saves there. Session logs stay in that directory;
Hop also writes its ledger and cursor. Existing ledgers cannot be reset/migrated.

Left stick moves, right stick turns the camera, Cross confirms/attacks and Circle
locks on. At the yellow leave-room prompt, press Cross. Native startup prompts
may require confirmation. In DC1, Select+Start opens the developer menu.

## Experiments and known limits

The observations below describe the pinned crossover candidate's earlier bounded
local tests. They are not a complete gameplay acceptance or current-upstream result.

| Pick | Choice | What to try / present limit |
|---|---|---|
| 1 | Cave chest and atmosphere | Open the chest; imported Atla/progression and gate policy remain incomplete. |
| 2 | Empty imported cave | Walk its walls and leave at the marker. |
| 3 | Hop ledger | Kill the native rat with Cross, then F10 to Dark Cloud's cave. Confirm its floor/intro prompts and wait for **Regular Water acquired**. One kill pays once. |
| 4 | Opar | Approach his spit/flop; Ghost-style/effect parity is not implied. |
| 5 | Ghost | Watch movement and fight; the35% vanish branch remains unobserved. |
| 6 | Werewolf | Boss-tier180HP experiment; clean-duel balance remains unqualified. |
| 7 | Floor-3 roster | Fifteen mixed DC1 monsters. Same-floor kills are remembered; a new native floor lifetime resets them. |
| 8 | Mimic pair | Confirm near the chest to reveal e35a; King Mimic reveal was not established. |
| 9 | Skinned King Mimic | Watch posed/textured motion; death/drop coverage remains open. |
| 10 | Toan combo | Lock on and tap Cross for DC1 timing; jump-slam is available. |
| 11 | Toan charged burst | Hold and release Cross. Shot records exist; burst hit/damage is unqualified. |
| 12 | Toan in Palm Brinks | Walk near the shop; town body has no Dagger. |
| 13 | Goro hammer/smash | Tap for combo; hold and release for charged smash. Integrated damage43 is logged. |
| 14 | Ungaga combo/charge | Tap for three hits; hold and release for shots. Integrated charge hits are logged; long walk-pose freeze remains open. |
| 15 | Xiao slingshot | Circle, then Cross. Integrated native hit4 is logged; sling band is rigid, miss/wall coverage open. |
| 16 | Monica Opar event | Confirm event11000 dialogue; use native transformation menu if needed. This route has no enemy fight. |
| 17 | Monica faithful goo | Cross spits, Square lunges, Circle aims. Damage11 on friendly is policy; counter-spit proof used injected hit/roll. |
| 18 | Random floor4242 | Walk seeded DC1 layout with its monsters/atmosphere. This roster selects nine of15 authored spawns; full entrance-to-exit walk remains unqualified. |
| 19 | Norune in DC2 Georama | Place Macho/Laura/Paige houses and walk to villagers. Laura dialogue is proven; old Macho replay misses on merged runtime. Routes lack villager collision. |
| 20 | Empty Dran arena | Walk and leave. Arena tile collapse proof used a separate test stimulus. |
| 21 | Dran fight | Walk in, dodge fireballs and collapsing tiles. Launcher uses normal life/damage; qualified kills used debug life20/scale4. A normal-balance kill was not run. No intro/death cutscene. |
| 22 | Ridepod in imported cave | R3 mounts/dismounts; encounter is0 as proven. |
| 23 | Ridepod in Dark Cloud | Walk into a wall; Cross punches, hold Square for twin guns. Requires a converted textured multipart pack. No full energy/upgrade/HUD/sound parity. |
| 24 | DC2 Shed in Norune | Select enters Georama, Triangle opens menu, Cross places Shed. The sidecar writes on SAVE-screen entry; cancelling is not transactional. Each launcher session is fresh, so it does not reload a previous launch. |
| 25 | Vanguard in Dark Cloud | Approach and fight. Approved texture/control/program-validator fixes are integrated. Kill proof used a test sword; optional effects/sounds are stubs. |
| 26 | Second imported room | Walk timber steps; no campaign/progression claim. |
| 27 | Native Dark Cloud | Fresh Norune session, separate from live saves. |
| 28 | Native Dark Chronicle | Boot/language selection, separate from live saves. |
| 29 | Opar with DC1 sounds | Listen for spit/step/flop/death/hurt. Recorded PCM differs from sound-off; listening/mixer parity remains unqualified. |

## Suggested tour

Opar → Goro smash → Monica goo → Dran arena → Georama → Ridepod in DC1.
Prepare each mode's required packs first and use a new launch for each stop.
For the Hop ledger demo, kill the native rat in DC2, press F10, confirm DC1's
floor/intro prompts and wait for Regular Water. The once-only delivery protocol
is bounded to disposable sessions; it does not provide merged campaign saves.

Physical F10/controller feel and audible output remain unqualified. Screenshots
and automated travel do not establish them. To report an issue, include the
mode, source pins, exact error and relevant log excerpt; keep personal paths,
assets and saves out of public reports.
