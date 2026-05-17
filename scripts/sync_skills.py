#!/usr/bin/env python3
"""Generate Claude and Cursor skill trees from canonical skills/ sources."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"
CLAUDE_OUT = REPO_ROOT / ".claude" / "skills"
CURSOR_OUT = REPO_ROOT / ".cursor" / "skills"

LEGACY_REF_PREFIX = "../../references/orchestra/"
CANONICAL_REF_PREFIX = "../../../references/orchestra/"

CLAUDE_ONLY_START = "<!-- claude-only -->"
CLAUDE_ONLY_END = "<!-- /claude-only -->"
CURSOR_ONLY_START = "<!-- cursor-only -->"
CURSOR_ONLY_END = "<!-- /cursor-only -->"


def discover_skills(skill_filter: str | None) -> list[Path]:
    if not SKILLS_DIR.is_dir():
        raise SystemExit(f"Missing skills directory: {SKILLS_DIR}")

    skills = sorted(path for path in SKILLS_DIR.iterdir() if path.is_dir())
    if skill_filter:
        skills = [path for path in skills if path.name == skill_filter]
        if not skills:
            raise SystemExit(f"Unknown skill: {skill_filter}")
    return skills


def split_frontmatter(content: str) -> tuple[str, str]:
    if not content.startswith("---\n"):
        return "", content

    end = content.find("\n---\n", 4)
    if end == -1:
        return "", content

    frontmatter = content[4:end]
    body = content[end + 5 :]
    return frontmatter, body


def merge_frontmatter(shared: str, overlay: str, *, target: str) -> str:
    if not overlay.strip():
        merged = shared
    else:
        merged_lines: list[str] = []
        shared_lines = [line for line in shared.splitlines() if line.strip()]
        overlay_lines = [line for line in overlay.splitlines() if line.strip()]
        seen_keys: set[str] = set()

        for line in shared_lines + overlay_lines:
            key = line.split(":", 1)[0].strip()
            if key in seen_keys:
                continue
            seen_keys.add(key)
            merged_lines.append(line)
        merged = "\n".join(merged_lines)

    if target == "cursor":
        lines = merged.splitlines()
        disable_value = "true"
        filtered: list[str] = []
        for line in lines:
            key = line.split(":", 1)[0].strip()
            if key == "disable-model-invocation":
                disable_value = line.split(":", 1)[1].strip()
                continue
            filtered.append(line)
        if disable_value != "false":
            filtered.append(f"disable-model-invocation: {disable_value}")
        merged = "\n".join(filtered)

    return merged


def strip_platform_blocks(body: str, *, target: str) -> str:
    if target == "claude":
        keep_start, keep_end = CLAUDE_ONLY_START, CLAUDE_ONLY_END
        drop_start, drop_end = CURSOR_ONLY_START, CURSOR_ONLY_END
    else:
        keep_start, keep_end = CURSOR_ONLY_START, CURSOR_ONLY_END
        drop_start, drop_end = CLAUDE_ONLY_START, CLAUDE_ONLY_END

    def remove_blocks(text: str, start: str, end: str) -> str:
        pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
        return pattern.sub("", text)

    body = remove_blocks(body, drop_start, drop_end)
    body = body.replace(keep_start, "").replace(keep_end, "")
    return body


OVER_QUALIFIED_REF_PREFIX = "../../../../references/orchestra/"


def rewrite_reference_paths(text: str) -> str:
    text = text.replace(OVER_QUALIFIED_REF_PREFIX, CANONICAL_REF_PREFIX)
    return text.replace(LEGACY_REF_PREFIX, CANONICAL_REF_PREFIX)


def read_optional(path: Path) -> tuple[str, str]:
    if not path.is_file():
        return "", ""
    content = path.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter(content)
    return frontmatter, body


def render_skill(skill_dir: Path, *, target: str) -> str:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise SystemExit(f"Missing SKILL.md in {skill_dir}")

    shared_frontmatter, shared_body = split_frontmatter(skill_md.read_text(encoding="utf-8"))
    overlay_frontmatter, overlay_body = read_optional(skill_dir / f"{target}.md")

    body = strip_platform_blocks(shared_body, target=target)
    body = rewrite_reference_paths(body)
    if overlay_body:
        overlay_body = strip_platform_blocks(overlay_body, target=target)
        overlay_body = rewrite_reference_paths(overlay_body)
        body = body.rstrip() + "\n\n" + overlay_body.lstrip()

    frontmatter = merge_frontmatter(shared_frontmatter, overlay_frontmatter, target=target)
    return f"---\n{frontmatter}\n---\n{body}"


def copy_supporting_files(skill_dir: Path, output_dir: Path) -> None:
    for dirname in ("scripts", "references", "templates"):
        source = skill_dir / dirname
        if not source.is_dir():
            continue
        destination = output_dir / dirname
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)


def write_outputs(skill_dir: Path) -> dict[str, str]:
    outputs: dict[str, str] = {}
    for target, output_root in (("claude", CLAUDE_OUT), ("cursor", CURSOR_OUT)):
        rendered = render_skill(skill_dir, target=target)
        output_dir = output_root / skill_dir.name
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "SKILL.md"
        copy_supporting_files(skill_dir, output_dir)
        output_file.write_text(rendered, encoding="utf-8")
        outputs[str(output_file)] = rendered
    return outputs


def read_output_file(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def sync_skills(skill_filter: str | None, *, check: bool) -> int:
    mismatches: list[str] = []

    for skill_dir in discover_skills(skill_filter):
        expected_paths = [
            CLAUDE_OUT / skill_dir.name / "SKILL.md",
            CURSOR_OUT / skill_dir.name / "SKILL.md",
        ]
        if check:
            rendered_by_target = {
                "claude": render_skill(skill_dir, target="claude"),
                "cursor": render_skill(skill_dir, target="cursor"),
            }
            for target, output_path in zip(("claude", "cursor"), expected_paths, strict=True):
                actual = read_output_file(output_path)
                expected = rendered_by_target[target]
                if actual != expected:
                    mismatches.append(str(output_path))
            continue

        write_outputs(skill_dir)

    if check and mismatches:
        print("Generated skill outputs are out of date:", file=sys.stderr)
        for path in mismatches:
            print(f"  - {path}", file=sys.stderr)
        print("Run: python scripts/sync_skills.py", file=sys.stderr)
        return 1

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Exit 1 if outputs are stale")
    parser.add_argument("--skill", help="Sync a single skill by directory name")
    args = parser.parse_args()
    return sync_skills(args.skill, check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
