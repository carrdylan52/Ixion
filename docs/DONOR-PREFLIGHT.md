# Separate donor preflight — tooling companion

This is a **tooling-only companion**, not a migrated-engine release. The branch
adds a read-only source preflight and its tests. It does not modify game code,
submodule pins, extracted data or saves, and it makes no new build or gameplay
acceptance claim. Its public base retains the older showcase generation.

The preflight was developed against the separate current-upstream migration
checkpoint: Ixion `6b86c760`, Chronicle `cd88c80e`, ChronicleTwo `bb6e948f`.
Those migration commits are **not included** in this public companion branch;
the original migration continues separately without rebasing or replacing it.
The public showcase C1 pin has the same donor manifest and copied helpers, so
this standalone tooling can also be checked against that already-public source.

## Validate the separate donor

When working on the migration, keep the active ChronicleTwo engine at its migration pin. C1's
`IXION_DC2_SOURCE_DIR` is a provenance input, not the active engine checkout:
`port/ixdc2` compiles its private copies, not translation units from that path.
Use a separate donor checkout at the full `donor_commit` recorded in C1's
unchanged `port/ixdc2/helpers.json`:
`87cf4efa4ed17c4f075a03a4efdbca0303cac670`.

The donor must already exist locally. Provision it separately; the preflight
never fetches, checks out, rewrites or repairs dependencies. A detached checkout
is supported. Keep the recorded files unmodified, with LF helper snippets as
required by the existing archive gate. Do not repin or regenerate the manifest
or `helpers.inc` to make a newer donor pass.

Run from the Ixion root (Python 3 and Git required):

```powershell
$ErrorActionPreference = 'Stop'
$Donor = 'D:/source/ChronicleTwo-donor-87cf4efa'
$DonorJson = python -B ./tools/check_crossover_donor.py --donor "$Donor"
if ($LASTEXITCODE -ne 0) { throw 'Donor preflight failed; do not configure C1' }
$DonorConfig = ($DonorJson -join "`n") | ConvertFrom-Json
if ([string]::IsNullOrWhiteSpace($DonorConfig.cmake_argument)) {
    throw 'Donor preflight did not return a CMake argument'
}
```

This verifies the exact donor revision, HEAD/index blobs and working source
bytes for all recorded snippets **and the math source**, snippet hashes, and
copied helper equality. Unrelated untracked files are not provenance inputs.
It prints JSON only on success, including one `cmake_argument` carrying the
verified absolute donor path. Pass that value as a single argument, including
when the path contains spaces; do not use `Invoke-Expression` or split it.

For the C1 configure step, append it to the existing cached Windows-toolchain
arguments. The following assumes `$C1Build` is a **new, unused** build directory
and `$CachedC1Args` already contains the correct toolchain, explicit
`FETCHCONTENT_SOURCE_DIR_*` paths and cached `KZ_PORT_VENDOR_DIRS`. Preflight all
vendor headers: Kazarov's `file(DOWNLOAD)` is independent of FetchContent.

```powershell
if (Test-Path -LiteralPath $C1Build) { throw 'Use a new C1 build directory' }
if (-not $CachedC1Args) { throw 'Provide the complete cached dependency arguments' }
$env:CARGO_NET_OFFLINE = 'true'
$ConfigureArgs = @('-S', './games/chronicle', '-B', $C1Build) + $CachedC1Args + @(
    '-DFETCHCONTENT_FULLY_DISCONNECTED=ON',
    '-DFETCHCONTENT_UPDATES_DISCONNECTED=ON',
    '-DIXION_BUILD_PLUGIN=ON',
    "-DIXION_API_DIR:PATH=$((Resolve-Path ./include).Path)",
    $DonorConfig.cmake_argument
)
cmake @ConfigureArgs
if ($LASTEXITCODE -ne 0) { throw 'C1 configure failed' }
```

Re-run preflight immediately before configuring if the donor changes. This
recipe does not select or modify dependency pins, provision caches, or qualify
the migration. It does not bypass C1's existing `check_symbols.py` archive and
linked-binary gates; those must still run unchanged during the build.

Source-only regression check:

```text
python -B -m unittest discover -s tests -p "test_crossover_donor.py" -v
python -B -m unittest discover -s tests -p "test_*.py"
```

A preflight pass removes only the donor configuration blocker. Required next
qualification remains both standalone/module builds, donor/archive and negative
symbol gates, focused Ridepod/collision tests, export/import checks, host
regressions, fiber smoke and renderer-off/async Hop checks with new output
directories and disposable saves. Do not reuse the showcase's retained receipts
as acceptance of this migration.
