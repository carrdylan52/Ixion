#!/usr/bin/env python3
"""Build a local Opar demo pack from an owner's extracted DC1 files."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def prepare(data: Path, output: Path) -> None:
    data, output = data.resolve(), output.resolve()
    sources = [data / p for p in (
        "dun/mpd_pack/d01inter.mpd", "dun/d01inter.cfg",
        "dun/monstor/e104a.chr", "dun/monstor/e104a.stb")]
    for source in sources:
        if not source.is_file():
            raise ValueError(f"Missing raw DC1 source: {source}")
    if output.exists():
        raise ValueError("Choose a new output directory; existing packs are never replaced")
    if output.is_relative_to(data) or data.is_relative_to(output):
        raise ValueError("Keep the output separate from extracted source data")
    tools = Path(__file__).resolve().parent
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=output.name + ".staging-", dir=output.parent) as temporary:
        staging = Path(temporary)
        packs = staging / "packs"
        packs.mkdir()
        subprocess.run([
            sys.executable, "-B", str(tools / "room_converter.py"), "convert",
            "--pack", str(sources[0]), "--cfg", str(sources[1]),
            "--output", str(packs / "room-d01inter"), "--room", "d01inter",
            "--spawn", "0,0,0", "--enemy-spawn", "93.508744096,0,0",
            "--exit", "249.356651,0,0", "--scale", "1.5584790682688"
        ], check=True, stdout=subprocess.DEVNULL)
        subprocess.run([
            sys.executable, "-B", str(tools / "monster_converter.py"), "convert",
            "--dc1-pack", str(sources[2]), "--output", str(packs / "opar-r1-overlay")
        ], check=True, stdout=subprocess.DEVNULL)
        script = packs / "opar-r1-overlay/data/dungeon/monster/ix_e104a.stb"
        shutil.copyfile(sources[3], script)
        staging.rename(output)
    print(f"Prepared Opar and room packs: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dc1-raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        prepare(args.dc1_raw, args.output)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Opar preparation failed: {error}\n")
