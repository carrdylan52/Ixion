#!/usr/bin/env python3
"""Keep the Ixion port forks in step with upstream.

Ixion builds on TheMoonPeople/Chronicle and TheMoonPeople/ChronicleTwo through forks whose
`ixion` branches add only the module build, and on TheMoonPeople/Kazarov through fork branches
that add embedded mode. This script does the mechanical part of catching those branches up with
upstream; a person or an agent resolves conflicts, builds and tests (docs/SYNCING.md).

Commands (run from anywhere inside the Ixion checkout):

  init                      check out submodules on their branches and add `upstream` remotes
  status                    how far each fork branch is behind upstream, and what Ixion pins
  merge GAME [--to REF]     merge upstream (or REF, or `last-green`) into GAME's Kazarov branch,
                            then into GAME's ixion branch; stops on conflicts
  push GAME                 fast-forward push GAME's Kazarov branch, then its ixion branch
  bump [--push]             pin Ixion to the pushed heads of both forks and commit

GAME is `chronicle` or `chronicletwo`. Nothing here force-pushes, pushes anywhere upstream, or
opens pull requests. Extra push targets (for example local mirrors) go in tools/sync.local.json:

  {"mirrors": {"chronicle": "<url>", "chronicletwo": "<url>", "kazarov": "<url>", "ixion": "<url>"}}
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

KAZAROV_UPSTREAM = "https://github.com/TheMoonPeople/Kazarov.git"
GAMES = {
    "chronicle": {
        "path": "games/chronicle",
        "upstream": "https://github.com/TheMoonPeople/Chronicle.git",
        "upstream_repo": "TheMoonPeople/Chronicle",
        "upstream_branch": "master",
        "branch": "ixion",
        "kazarov_branch": "ixion-old-layout",
        "ci_workflow": "PC builds",
    },
    "chronicletwo": {
        "path": "games/chronicletwo",
        "upstream": "https://github.com/TheMoonPeople/ChronicleTwo.git",
        "upstream_repo": "TheMoonPeople/ChronicleTwo",
        "upstream_branch": "master",
        "branch": "ixion",
        "kazarov_branch": "ixion",
        "ci_workflow": "PC builds",
    },
}
FORBIDDEN_PUSH = "themoonpeople"


class Stop(Exception):
    pass


def git(repo, *args, check=True, quiet=False):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise Stop(f"git {' '.join(args)} failed in {repo}:\n{r.stderr.strip() or r.stdout.strip()}")
    return r.stdout.strip() if r.returncode == 0 or not quiet else ""


def ok(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True).returncode == 0


def root():
    here = Path(__file__).resolve().parent
    top = git(here, "rev-parse", "--show-toplevel")
    return Path(top)


def local_config(top):
    p = top / "tools" / "sync.local.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def short(sha):
    return sha[:10] if sha else "-"


def paths(top, name):
    g = GAMES[name]
    game = top / g["path"]
    return g, game, game / "tools" / "kazarov"


def ensure_remote(repo, name, url):
    have = git(repo, "remote").split()
    if name not in have:
        git(repo, "remote", "add", name, url)
    elif git(repo, "remote", "get-url", name) != url:
        git(repo, "remote", "set-url", name, url)


def ensure_branch(repo, branch):
    """Put the checkout on `branch`, creating it from origin if needed, without moving HEAD."""
    head = git(repo, "rev-parse", "HEAD")
    if git(repo, "rev-parse", "--abbrev-ref", "HEAD") == branch:
        return
    if ok(repo, "rev-parse", "--verify", f"refs/heads/{branch}"):
        if git(repo, "rev-parse", branch) != head:
            raise Stop(f"{repo}: local {branch} is at {short(git(repo, 'rev-parse', branch))} but the checkout "
                       f"is at {short(head)}; check out {branch} by hand and decide which is right")
        git(repo, "switch", "-q", branch)
    else:
        git(repo, "switch", "-q", "-c", branch, head)
        if ok(repo, "rev-parse", "--verify", f"refs/remotes/origin/{branch}"):
            git(repo, "branch", "-q", f"--set-upstream-to=origin/{branch}", branch)


def require_clean(repo):
    if git(repo, "status", "--porcelain", "--untracked-files=no"):
        raise Stop(f"{repo} has uncommitted changes; commit or stash them first")


def require_identity(repo):
    if not ok(repo, "var", "GIT_COMMITTER_IDENT"):
        raise Stop(f"{repo} has no git identity; set user.name and user.email (git config) before merging")


def kazarov_layout(repo, ref):
    """'old' when Kazarov keeps its code under port/, 'new' when it has src/cpp/."""
    if ok(repo, "cat-file", "-e", f"{ref}:src/cpp"):
        return "new"
    if ok(repo, "cat-file", "-e", f"{ref}:port/platform"):
        return "old"
    return "unknown"


def fetch_commit(repo, sha):
    if ok(repo, "cat-file", "-e", f"{sha}^{{commit}}"):
        return
    for remote in ("upstream", "origin"):
        if ok(repo, "fetch", "-q", remote, sha):
            return
    raise Stop(f"{repo}: cannot fetch Kazarov commit {sha} from upstream or origin")


def last_green(g):
    if not shutil.which("gh"):
        raise Stop("--to last-green needs the GitHub CLI (gh)")
    out = subprocess.run(["gh", "run", "list", "-R", g["upstream_repo"], "--branch", g["upstream_branch"],
                          "--workflow", g["ci_workflow"], "--status", "success", "-L", "1",
                          "--json", "headSha"], capture_output=True, text=True)
    runs = json.loads(out.stdout or "[]") if out.returncode == 0 else []
    if not runs:
        raise Stop(f"no successful '{g['ci_workflow']}' run found on {g['upstream_repo']} {g['upstream_branch']}")
    return runs[0]["headSha"]


def resolve_target(game, g, to):
    if to in (None, "", "tip"):
        return git(game, "rev-parse", f"upstream/{g['upstream_branch']}")
    if to == "last-green":
        sha = last_green(g)
        fetch_commit(game, sha)
        return sha
    if not ok(game, "rev-parse", "--verify", f"{to}^{{commit}}"):
        git(game, "fetch", "-q", "upstream", to, check=False)
    return git(game, "rev-parse", f"{to}^{{commit}}")


def kazarov_pin(game, ref):
    line = git(game, "ls-tree", ref, "tools/kazarov")
    return line.split()[2] if line else None


# --- commands ------------------------------------------------------------------------------------

def cmd_init(top, args):
    git(top, "submodule", "update", "--init", "--recursive")
    for name in GAMES:
        g, game, kz = paths(top, name)
        ensure_branch(game, g["branch"])
        ensure_remote(game, "upstream", g["upstream"])
        ensure_branch(kz, g["kazarov_branch"])
        ensure_remote(kz, "upstream", KAZAROV_UPSTREAM)
        print(f"{name}: {g['branch']} at {short(git(game, 'rev-parse', 'HEAD'))}, "
              f"Kazarov {g['kazarov_branch']} at {short(git(kz, 'rev-parse', 'HEAD'))}")


def cmd_status(top, args):
    for name in GAMES:
        g, game, kz = paths(top, name)
        if not (game / ".git").exists():
            print(f"{name}: not checked out; run init")
            continue
        git(game, "fetch", "-q", "origin")
        git(game, "fetch", "-q", "upstream")
        git(kz, "fetch", "-q", "origin", check=False)
        git(kz, "fetch", "-q", "upstream", check=False)
        up = f"upstream/{g['upstream_branch']}"
        pinned = git(top, "ls-tree", "HEAD", g["path"]).split()[2]
        head = git(game, "rev-parse", "HEAD")
        fork = git(game, "rev-parse", f"origin/{g['branch']}", check=False, quiet=True)
        base = git(game, "merge-base", head, up)
        behind = git(game, "rev-list", "--count", f"{head}..{up}")
        ours = git(game, "diff", "--name-only", base, head).splitlines()
        print(f"== {name}  ({g['upstream_repo']} {g['upstream_branch']})")
        print(f"   Ixion pins {short(pinned)}; local {g['branch']} {short(head)}; fork {short(fork)}")
        print(f"   upstream tip {short(git(game, 'rev-parse', up))}; {behind} commits behind; "
              f"based on {short(base)}")
        print(f"   files Ixion changes in this port ({len(ours)}): {', '.join(ours)}")
        up_pin = kazarov_pin(game, up)
        kz_head = git(kz, "rev-parse", "HEAD")
        line = f"   Kazarov {g['kazarov_branch']} {short(kz_head)}; upstream pins {short(up_pin)}"
        if up_pin:
            try:
                fetch_commit(kz, up_pin)
                if ok(kz, "merge-base", "--is-ancestor", up_pin, kz_head):
                    line += " (already merged)"
                else:
                    line += f" ({git(kz, 'rev-list', '--count', f'{kz_head}..{up_pin}')} commits to merge)"
                if kazarov_layout(kz, up_pin) != kazarov_layout(kz, kz_head):
                    line += ("\n   WARNING: upstream now pins the other Kazarov layout; the embedded-mode "
                             "changes must move to the matching fork branch (docs/SYNCING.md)")
            except Stop as e:
                line += f" ({e})"
        print(line)
        if pinned != head:
            print("   note: Ixion's pin differs from the local branch; run bump after pushing")


def cmd_merge(top, args):
    g, game, kz = paths(top, args.game)
    require_clean(game)
    require_clean(kz)
    require_identity(game)
    require_identity(kz)
    if ok(game, "rev-parse", "-q", "--verify", "MERGE_HEAD") or ok(kz, "rev-parse", "-q", "--verify", "MERGE_HEAD"):
        raise Stop("a merge is already in progress; finish it with `git commit` (or `git merge --abort`) first")
    ensure_branch(game, g["branch"])
    ensure_branch(kz, g["kazarov_branch"])
    git(game, "fetch", "-q", "upstream")
    git(kz, "fetch", "-q", "upstream", check=False)
    target = resolve_target(game, g, args.to)
    print(f"{args.game}: merging upstream {short(target)} into {g['branch']}")

    pin = kazarov_pin(game, target)
    if pin:
        fetch_commit(kz, pin)
        if ok(kz, "merge-base", "--is-ancestor", pin, "HEAD"):
            print(f"  Kazarov: upstream pin {short(pin)} already in {g['kazarov_branch']}")
        else:
            if kazarov_layout(kz, pin) != kazarov_layout(kz, "HEAD"):
                raise Stop(f"upstream {args.game} now pins the other Kazarov layout ({short(pin)}); "
                           "move embedded mode to the matching fork branch first (docs/SYNCING.md)")
            r = subprocess.run(["git", "-C", str(kz), "merge", "--no-edit", "-m",
                                f"Merge upstream Kazarov {short(pin)} into {g['kazarov_branch']}", pin],
                               capture_output=True, text=True)
            if r.returncode != 0:
                conflicts = git(kz, "diff", "--name-only", "--diff-filter=U").splitlines()
                raise Stop(f"Kazarov merge stopped with conflicts in {kz}:\n  " + "\n  ".join(conflicts) +
                           f"\nResolve them, `git -C {kz} commit`, then rerun this merge.")
            print(f"  Kazarov: merged {short(pin)} -> {short(git(kz, 'rev-parse', 'HEAD'))}")

    if ok(game, "merge-base", "--is-ancestor", target, "HEAD"):
        print(f"  {args.game}: already contains {short(target)}")
    else:
        r = subprocess.run(["git", "-C", str(game), "merge", "--no-ff", "--no-commit", target],
                           capture_output=True, text=True)
        # The game always records our merged Kazarov, not upstream's pin.
        git(game, "add", "tools/kazarov")
        conflicts = [p for p in git(game, "diff", "--name-only", "--diff-filter=U").splitlines()
                     if p != "tools/kazarov"]
        if conflicts:
            raise Stop(f"{args.game} merge stopped with conflicts in {game}:\n  " + "\n  ".join(conflicts) +
                       f"\nResolve them (keep upstream's behaviour, re-apply the Ixion seam), `git -C {game} add` "
                       f"them and `git -C {game} commit`. tools/kazarov is already staged.")
        if r.returncode != 0 and not git(game, "diff", "--cached", "--name-only"):
            raise Stop(f"{args.game} merge failed:\n{r.stderr.strip()}")
        git(game, "commit", "-q", "-m", f"Merge upstream {short(target)} into {g['branch']}")
        print(f"  {args.game}: merged -> {short(git(game, 'rev-parse', 'HEAD'))}")
    if git(game, "status", "--porcelain", "--", "tools/kazarov"):
        git(game, "add", "tools/kazarov")
        git(game, "commit", "-q", "-m", f"Move tools/kazarov to {short(git(kz, 'rev-parse', 'HEAD'))}")
        print("  recorded the merged Kazarov in the port")
    print("Next: build and test both games and the host (docs/SYNCING.md), then `push "
          f"{args.game}` and `bump --push`.")


def safe_push(repo, remote_or_url, branch):
    url = remote_or_url if "://" in remote_or_url or "@" in remote_or_url else git(repo, "remote", "get-url", remote_or_url)
    if FORBIDDEN_PUSH in url.lower():
        raise Stop(f"refusing to push to {url}: Ixion never pushes upstream")
    if not branch.startswith("ixion") and branch != "main":
        raise Stop(f"refusing to push branch {branch}")
    r = subprocess.run(["git", "-C", str(repo), "push", remote_or_url, f"{branch}:refs/heads/{branch}"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise Stop(f"push of {branch} to {url} was refused (not a fast-forward?):\n{r.stderr.strip()}")
    print(f"  pushed {branch} {short(git(repo, 'rev-parse', branch))} -> {url}")


def cmd_push(top, args):
    g, game, kz = paths(top, args.game)
    mirrors = local_config(top).get("mirrors", {})
    require_clean(game)
    require_clean(kz)
    safe_push(kz, "origin", g["kazarov_branch"])
    if mirrors.get("kazarov"):
        safe_push(kz, mirrors["kazarov"], g["kazarov_branch"])
    safe_push(game, "origin", g["branch"])
    if mirrors.get(args.game):
        safe_push(game, mirrors[args.game], g["branch"])


def cmd_bump(top, args):
    require_identity(top)
    msg = []
    for name in GAMES:
        g, game, _ = paths(top, name)
        head = git(game, "rev-parse", "HEAD")
        git(game, "fetch", "-q", "origin")
        if not ok(game, "merge-base", "--is-ancestor", head, f"origin/{g['branch']}"):
            raise Stop(f"{name} {short(head)} is not pushed to its fork yet; run `push {name}` first")
        pinned = git(top, "ls-tree", "HEAD", g["path"]).split()[2]
        if pinned != head:
            git(top, "add", g["path"])
            msg.append(f"{name} {short(head)}")
    if not msg:
        print("Ixion already pins the current fork heads")
    else:
        git(top, "commit", "-q", "-m", "Bump ports: " + ", ".join(msg))
        print(f"committed {short(git(top, 'rev-parse', 'HEAD'))}: Bump ports: {', '.join(msg)}")
    if args.push:
        branch = git(top, "rev-parse", "--abbrev-ref", "HEAD")
        safe_push(top, "origin", branch)
        mirror = local_config(top).get("mirrors", {}).get("ixion")
        if mirror:
            safe_push(top, mirror, branch)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("status")
    m = sub.add_parser("merge")
    m.add_argument("game", choices=sorted(GAMES))
    m.add_argument("--to", help="upstream commit or ref to merge, or `last-green` (default: upstream tip)")
    p = sub.add_parser("push")
    p.add_argument("game", choices=sorted(GAMES))
    b = sub.add_parser("bump")
    b.add_argument("--push", action="store_true")
    args = ap.parse_args()
    top = root()
    try:
        {"init": cmd_init, "status": cmd_status, "merge": cmd_merge, "push": cmd_push, "bump": cmd_bump}[args.cmd](top, args)
    except Stop as e:
        print(f"stopped: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
