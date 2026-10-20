# Ixion crossover showcase

Read README.md and docs/SHOWCASE.md first. This branch pins the working crossover
generation. It does not claim compatibility with newer upstream native glTF data.

## Source and data

Adapters live under each port's `port/src`; keep retail `ps2/` source unchanged.
Keep the host ABI plain C and independent of game headers. Build host and both
modules together when changing the ABI.

Disc images, extracted files, converted packs, saves, recordings and local logs
stay outside Git. Use the owner's discs and new output/save folders. Never run a
demo against campaign saves or overwrite an existing extraction.

## Build and test

From a clean root checkout, the portable synthetic test command is:

```sh
python -B -m unittest discover -s tests -p "test_*.py"
```

Retail-data cases skip unless their documented environment variables are set;
report those skips. See docs/SHOWCASE.md for the Windows build and Opar pack recipe.
The complete host requires Windows, SDL3 and the pinned llvm-mingw toolchain.
Run `ixion_fiber_smoke`, `ixion_host_tests`, the ports' focused Ixion tests, and
`--auto-switch 120:20` when changing the modules or pins. A parked-state check
does not qualify audio, controller feel, combat or full campaigns.

Use cached dependencies when available. An offline build needs explicit
FetchContent source directories, vendor headers and an offline Cargo cache;
`FETCHCONTENT_FULLY_DISCONNECTED` alone does not cover every downloader.

## Publication and rollback

There is no deployment service. Publish source changes to the showcase branch
after reviewing the diff, synthetic tests, submodule reachability and secret
scan. Publish nested dependencies before parent pins. Preserve upstream licences.
Never include generated packs in a release or commit.

To reproduce or roll back, check out a recorded root commit, then run
`git submodule update --init --recursive` in an idle checkout and rebuild into a
new directory. Do not use `submodule update --remote` on this pinned candidate.
Local configuration is supplied through launcher arguments or environment
variables; no machine-specific paths belong in tracked files.
