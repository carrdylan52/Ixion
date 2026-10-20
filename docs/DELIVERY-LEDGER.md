# One-item delivery ledger (round 8: consumed history binding)

The launcher owns a JSON-lines ledger shared by both games. It delivers DC1
Regular Water (native ID 145) when an installed encounter spawn in the imported
DC1 room is counted dead in DC2. The selected native enemy and every authored
DC1 roster spawn are eligible. This is a narrow, opt-in prototype. No retail save layout
or Ixion ABI changes are involved.

Initialize a **new disposable** run folder once:

```powershell
python -B tools/ledger.py --ledger <run>\ledger.jsonl --dc1-save <run>\dc1-saves
```

The run folder must be empty (or absent) and the DC1 save root must be a new
folder strictly inside it (`save == run` is refused by Python and C++); an existing campaign save root is refused. Initialization
writes the cursor, the independently sealed consumed high-water file, the sealed
ledger and, last, `<run>\ixion-disposable-run.json`
(`{"version":2,"ledger_format":2,"ledger":<id>}`). Delivery is enabled only while that marker
binds both the ledger ID and ledger format v2: the host refuses `--ledger` without it, DC2 refuses to append
unless its own `--save` root lies inside the run folder, and DC1 refuses to
consume unless its cursor (save root) does. Each refusal is logged.

For standalone games, set `IXION_LEDGER` to that absolute ledger path and pass
DC1 `--save` the initialized root. For Hop, pass the host `--ledger <file>` and
the same DC1 save root in `--dc1-args`. Both private DLLs inherit the path. The
ledger tool refuses to overwrite existing state. Keep both progress files with
the disposable run; do not restore or copy older progress over newer state.

The header contains **version 2**, a random ledger identity, and the absolute
recipient cursor path. Every delivery line has exactly `seq`, `source_game`,
`source_event`, `item`, and `created`. Sequences start at 1 and are contiguous;
the only allowed source is `dc2`, and the only allowed item is 145. The last
line is always the trailer `{"end":<record count>,"fnv1a64":"<16 hex>"}`, an
FNV-1a 64 checksum of every byte before it. A cut at any line boundary removes
the trailer and an edit breaks the checksum; both refuse delivery.

**Version 1 ledgers cannot be continued, appended to or consumed**, including
R2 and R4 files with intact markers and already-consumed cursors. R2 could
label a native fallback death as the requested donor; its records cannot
distinguish that case from a real donor death. Both ports log a refusal before
any ledger/cursor write or grant: `legacy ledger version 1 has ambiguous kill
attribution; refusing append/consume; initialize a fresh disposable run (no
migration)`. Unknown versions also refuse. The launcher writes version 2 only
in a fresh disposable folder and never upgrades or overwrites existing files.
Every playtest launch uses a fresh disposable ledger. Start a new run; do not
change an old header or rebuild its checksum to bypass this refusal. Even an
apparently correctly attributed version 1 donor/native record is refused.
Cursor format remains version 1. The disposable marker is now version 2 and
must explicitly name ledger format 2 and the same ledger ID. A version-1
marker is refused even if the ledger header is changed to 2 and its checksum
is recomputed, including mixed historical/current records and an already
consumed cursor. The refusal is logged as `legacy disposable-run marker version
1 lacks ledger v2 binding; refusing append/consume; initialize a fresh disposable
run (no migration)`. Missing, malformed, unsupported or mismatched bindings
also refuse before append, cursor writes or grants. Earlier v2 ledgers created
with v1 markers likewise require a fresh run; the launcher never upgrades them.

Delivery records retain their five-field schema and stable event encoding;
there is no per-record version discriminator. The independent run marker is
the format-eligibility boundary. The checksum detects damage and unresealed
edits, not malicious authorship. Reheadering/resealing a legacy ledger while
retaining its original marker and cursor cannot authorize delivery. Coordinated
edits/forgery of two or more state files, including ledger plus high-water or
both progress files, and copying history into another authorized run are outside
this prototype's threat boundary. This is not a cryptographic provenance guarantee.

**The final at-most-once boundary covers ordinary play, reloads, relaunches,
crashes, and any single-file state edit**, including a ledger edit with a
recomputed public checksum, a cursor rollback, or a resealed high-water edit.
Loss is allowed; duplicate grants for one world kill in one run are not.
Coordinated multi-file forgery is out of scope. History commitments rely on
SHA-256 collision resistance; neither the digest nor the file seals prove authorship.
The independent
high-water snapshot is `<ledger path>.consumed.jsonl` (for example,
`<run>\ledger.jsonl.consumed.jsonl`), beside the ledger rather than inside the save
root. Its first line has exactly `version:2`, `ledger`, `seq`, `prefix_sha256`
and `events_sha256`;
the second is `{"end":<same seq>,"fnv1a64":<checksum of first line including newline>}`.
The prefix digest covers records 1 through `seq`, including all five fields,
serialized as compact JSON with ASCII-sorted keys and one LF after each record.
The event digest covers the consumed `source_event` set in ASCII lexical order,
one event plus LF per entry (event syntax excludes LF). The header and the
unconsumed tail are excluded. Both zero-prefix digests are SHA-256 of empty bytes.
The launcher initializes this version-2 snapshot to zero before publishing authorization. DC1 replaces
the complete checksummed snapshot using the existing durable temp/rename writer,
under the existing ledger and cursor locks. No additional lock is needed: every
reader/writer of this snapshot already holds the ledger lock. It records reserved
consumption, which can precede an actual grant and deliberately permit loss.

Before deduping or appending, DC2 validates this snapshot against the current
ledger ID/count and recomputes both consumed-history digests. DC1 performs the
same check before any progress write or grant. A renamed consumed event, changed
creation time, or other consumed-record edit refuses even when the ledger's own
checksum has been correctly recomputed. Both production paths log `consumed
history mismatch; refusing append/consume (edited ledger or high-water)` and
make no append, progress write or grant. The genuine marker/cursor/high-water
are unchanged. Ordinary new records after high-water remain eligible; equivalent
JSON whitespace/key order changes preserve canonical history.

DC1 also validates both progress files against this ledger ID and record count.
Missing, malformed, damaged or foreign high-water state refuses
without recreating it. Earlier runs without this file require a fresh disposable
run, as do round-7 version-1 snapshots without history bindings; there is no
migration. The two sequence values must agree. A lower cursor
with an intact higher snapshot, or a lower snapshot with an intact higher cursor,
logs `ixion ledger refused: consumed high-water disagrees with cursor; refusing
replay (rollback or interrupted commit)` and makes no writes or grants. This
includes a correctly resealed single-file high-water rollback. No automatic
repair lowers progress or silently reauthorizes delivery. Rolling back both
files at once remains outside the agreed boundary.

The event is a **stable world-kill identity**:
`kill:<ledger id>:<donor room>:<dungeon>:<floor>:e<encounter slot>:<native|dc1-<donor id>>`.
It has no process nonce and no room generation, so a relaunch with the same
version 2 ledger, a reload of a pre-kill DC2 save, or a respawn-then-kill dedupes to
`added=0` and never grants twice. The ledger id is part of the key and dedupe
is per ledger, so a fresh ledger (a new run) grants the same kill again. Two
packs of the same donor room on the same floor collapse to one kill (a loss,
never a duplicate). Spawn zero keeps the R2 `e0:dc1-<id>` event encoding inside
the new format; this is not permission to continue an R2 ledger. The
extra authored spawn N uses `eN:dc1-<id>`. The identity comes from the saved
installed roster key, checked against the actor's pointer and incarnation,
or from the actually installed native encounter. It never reads the requested
donor option, so changing an unrelated roster member cannot re-grant a kill.

ThinkHost snapshots the immutable kill at its real count seam, before NONE
and donor cleanup. A bounded FIFO retains 32 events including the active retry;
overflow logs `ixion ledger LOST delivery: kill queue overflow` without replacing
an earlier event. Retirement/departure cannot erase a queued event, and two
deaths between boundaries both survive. Despawn and retirement alone are not
producers. The post-frame main loop drains one event per frame in every game
loop, independently of the current room sample. A busy lock, unreadable ledger
or failed commit is retried up to 300 attempts per head, then logged as `LOST`;
retrying dedupes an append that did publish. Process exit can still lose
unpublished queued events. The queue is in memory, not a durable outbox.

Roster kill memory remains scoped to its native `CMonsterMan::Initialize`
floor lifetime. Retirement/reinstall in the same lifetime skips killed donors;
a population reset may spawn them again and pay native rewards. Water dedupe
remains scoped to the ledger across those lifetimes, so those re-kills add no
Water records. Mid-visit Initialize calls also reset native reward memory;
that pre-existing lifetime policy is unchanged here.

The ledger is logically append-only: an atomic replacement preserves all old
bytes and publishes exactly one extra complete record. Both ports use their
existing durable `FilesWrite` (exclusive temporary file, flush, rename and
write-through/directory sync). OS-held `.lock` files serialize processes and
release on crash; the lock path stays on disk. The launcher uses exclusive
initial publication and syncs each file. A partially initialized run refuses
delivery.

DC1 checks at the top of the town frame loop, after initialization and before
the frame or town loop starts, at most once per 30 game frames. It takes the
ledger lock then the cursor lock and holds both through both progress writes and the native grant. The
cursor is `ixion-delivery.cursor.json` next to the saves under the chosen root.
The ledger is bound to that one recipient location, rather than allowing every
save root to start its own cursor. Missing, malformed, mismatched or ahead-of-
ledger cursor state refuses delivery; a missing sidecar never means zero.

For each delivery, `seq` must exceed **both** progress values. DC1 commits the
**high-water snapshot (sequence and both history digests together), then the
cursor, then calls `CDngStatusData::GetItem`**. There is no separate digest write
or grant window: the complete history binding is in the first atomic publication.
Both files must therefore be durable before the real gate writes native inventory.
This provides **at-most-once** grant, not a transactional exactly-once save update:

- Before the high-water publication, a crash or failed write can retry safely.
- After high-water publication but before cursor publication, the mismatch
  refuses all further consumption, losing this delivery (and blocking later
  ones in this disposable run). Start a fresh run; never reset either file.
- After both publications but before grant, or after grant but before a native
  save, the sequence stays consumed and may be lost; it is never granted again.
- A write that publishes but reports failure grants nothing in that call. On
  restart it follows the same persisted-state rules above.

The native gate can also lose an item when overflow is already full; the
cursor is never rewound and the loss is logged as `ixion ledger LOST item`. Logs count inventory copies before/after instead
of trusting that gate's return value. Save using DC1's normal save flow to keep
the item across restarting; the ledger does not auto-save the game.

The cursor and independent high-water jointly retain dedupe across all slots
in the root. Loading an older retail save may lose the reward and will not
redeliver it. Deleting either progress file refuses delivery; rolling back
only one cannot re-grant. Rolling back both together, coordinated multi-file
forgery, copying an inventory to another save, and cloud-save restores of both
progress files are outside this prototype's guarantee. Saving the
granted Water into two DC1 slots of the same disposable root forks it across
timelines (the native save cannot see the sidecar); it stays inside one
disposable run folder. Re-killing the same enemy in a new session with the
same ledger is not a new delivery. There is no weapon crosswalk, gilda transfer, inventory debit,
gate-key grant, durable outbox, multi-recipient distribution, or campaign migration.

`include/ixion_delivery.hpp`, `include/ixion_delivery_lock.hpp`/`.cpp`, and
`tests/ixion_delivery_test.cpp` are canonical. The ports vendor identical copies
under `port/src` and `port/src/tests` so standalone builds require no Ixion ABI
dependency. Keep those copies synchronized when changing the protocol.
