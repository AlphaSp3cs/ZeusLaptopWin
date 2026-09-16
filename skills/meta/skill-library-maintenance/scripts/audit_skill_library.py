#!/usr/bin/env python3
"""Audit a Hermes skill library.

Reports, per skill: size, description, dangling references, orphaned support
files, and TRANSITIVE reachability. Also profiles H2 section sizes so you can
see which sections make a megaskill big before deciding what to extract.

Usage:
    python3 audit_skill_library.py [SKILLS_ROOT] [--profile SKILL_NAME]

Defaults SKILLS_ROOT to the platform Hermes skills dir.

Key design notes (learned the hard way):
  * Dangling checks match only LINKED refs -- `references/x.md` inside
    backticks or a markdown link. A bare filename mentioned in PROSE (e.g.
    "no such file as validate_go_setups.py exists") must NOT count as a link,
    or every honest "this does not exist" note reports as a broken ref.
  * Reachability is TRANSITIVE. After you extract sections into references/,
    files are named one hop out, and a naive direct-mention check reports
    false orphans.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Linked refs only: inside backticks, or as a markdown link target.
LINKED_REF = re.compile(
    r"`((?:references|scripts|templates)/[A-Za-z0-9_.\-]+\.[A-Za-z0-9]+)`"
    r"|\]\(((?:references|scripts|templates)/[A-Za-z0-9_.\-]+\.[A-Za-z0-9]+)\)"
)
SUBDIRS = ("references", "scripts", "templates")


def default_root() -> Path:
    if os.name == "nt":
        return Path(os.environ["LOCALAPPDATA"]) / "hermes" / "skills"
    return Path.home() / ".local" / "share" / "hermes" / "skills"


def linked_refs(text: str) -> set[str]:
    return {a or b for a, b in LINKED_REF.findall(text)}


def on_disk(skill_dir: Path) -> set[str]:
    out = set()
    for sub in SUBDIRS:
        d = skill_dir / sub
        if d.is_dir():
            out |= {f"{sub}/{f.name}" for f in d.iterdir() if f.is_file()}
    return out


def reachable(skill_dir: Path) -> set[str]:
    """Walk SKILL.md -> references/*.md -> ... collecting every linked file."""
    seen: set[str] = set()
    frontier = ["SKILL.md"]
    while frontier:
        cur = frontier.pop()
        if cur in seen:
            continue
        seen.add(cur)
        f = skill_dir / cur
        if not f.exists() or f.suffix != ".md":
            continue
        frontier.extend(linked_refs(f.read_text(encoding="utf-8", errors="replace")))
    seen.discard("SKILL.md")
    return seen


def profile_sections(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    cur, buf, rows = "_preamble", [], []
    for line in text.splitlines():
        if line.startswith("## "):
            rows.append((cur, len("\n".join(buf))))
            cur, buf = line.strip(), []
        else:
            buf.append(line)
    rows.append((cur, len("\n".join(buf))))
    rows.sort(key=lambda r: -r[1])
    total = sum(r[1] for r in rows) or 1
    print(f"\nSection profile: {path}  ({total}c, {len(rows)} H2 sections)")
    run = 0
    for name, size in rows:
        run += size
        print(f"  {size:6d}c {100*size/total:5.1f}%  cum{100*run/total:6.1f}%  {name[:70]}")
    print("\n  Sections that are pure LOOKUP material (pitfall catalogs, file")
    print("  indexes, error tables) are extraction candidates -> references/.")


def main() -> int:
    args = [a for a in sys.argv[1:]]
    profile_target = None
    if "--profile" in args:
        i = args.index("--profile")
        profile_target = args[i + 1]
        del args[i:i + 2]
    root = Path(args[0]).expanduser() if args else default_root()

    if not root.is_dir():
        print(f"ERROR: skills root not found: {root}")
        return 2

    print(f"=== SKILL LIBRARY AUDIT: {root} ===\n")
    total_chars = 0
    problems = 0

    for skill_md in sorted(root.rglob("SKILL.md")):
        d = skill_md.parent
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        total_chars += len(text)

        refs = linked_refs(text)
        dangling = sorted(r for r in refs if not (d / r).exists())
        reach = reachable(d)
        unreachable = sorted(on_disk(d) - reach)
        # also flag refs that are reachable-but-missing anywhere in the graph
        deep_dangling = sorted(r for r in reach if not (d / r).exists())

        desc_m = re.search(r"^description:\s*(.+)$", text, re.M)
        desc = desc_m.group(1).strip() if desc_m else "!! MISSING"

        bad = bool(dangling or unreachable or deep_dangling) or not desc_m
        if bad:
            problems += 1
        flag = "!! " if bad else "OK "

        print(f"{flag}{d.name:38s} {len(text):7d}c  refs:{len(refs):3d}")
        print(f"     desc: {desc[:70]}")
        if len(desc) > 60 and desc_m:
            print(f"     WARN: description {len(desc)}c > 60c budget; index truncates at 57c")
        if dangling:
            print(f"     DANGLING (linked from SKILL.md): {dangling}")
        if deep_dangling:
            print(f"     DANGLING (linked deeper in graph): {deep_dangling}")
        if unreachable:
            print(f"     UNREACHABLE (on disk, nothing links to it): {unreachable}")

    print(f"\n--- total always-loaded skill text: {total_chars}c across "
          f"{len(list(root.rglob('SKILL.md')))} skills")
    print(f"--- skills with problems: {problems}")
    if total_chars > 100_000:
        print("--- NOTE: >100KB resident. Profile the largest skills and extract")
        print("    lookup-only sections with --profile <skill-name>.")

    if profile_target:
        for skill_md in root.rglob("SKILL.md"):
            if skill_md.parent.name == profile_target:
                profile_sections(skill_md)
                break
        else:
            print(f"\nERROR: no skill named {profile_target!r}")
            return 2

    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
