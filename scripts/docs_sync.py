"""Report which skill files are behind orchestra-docs.

Run by the `orchestra/sync-docs.yml` pipeline's agent before it edits anything
(see orchestra/sync-docs.md). Deterministic and cheap, so the agent only spends
effort when something a skill depends on actually changed.

- Docs: a skill file depends on every docs page it links to
  (https://docs.getorchestra.io/docs/<path>). Changes are read from
  `git diff <watermark>..HEAD -- docs/` in an orchestra-docs checkout.
- Dead links: linked pages missing from the docs checkout (moved/renamed pages).

Pipeline schema changes arrive the same way: docs/core-concepts/pipelines/schema.mdx
is regenerated from the published JSON schema, and skills link to it.

Usage:
    python3 scripts/docs_sync.py --docs <orchestra-docs checkout>           # report; exit 2 if anything is stale
    python3 scripts/docs_sync.py --docs <orchestra-docs checkout> --update  # move watermark to docs HEAD
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WATERMARK = ROOT / ".docs-sync.json"
DOCS_LINK = re.compile(r"https://docs\.getorchestra\.io/docs/([A-Za-z0-9_\-/.]+)")


def link_to_page(path):
    """`core-concepts/pipelines/schema/#x` -> `docs/core-concepts/pipelines/schema` (extension-less)."""
    return "docs/" + path.split("#")[0].rstrip("/.")


def page_key(docs_file):
    """`docs/a/b.mdx` or `docs/a/b/index.mdx` -> `docs/a/b`, the same key link_to_page produces."""
    key = re.sub(r"\.mdx?$", "", docs_file)
    return key[: -len("/index")] if key.endswith("/index") else key


def dependency_map():
    """{docs page key: [skill files linking to it]} across both plugins."""
    deps = {}
    for f in sorted((ROOT / "skills").rglob("*.md")):
        rel = str(f.relative_to(ROOT))
        for link in set(DOCS_LINK.findall(f.read_text())):
            deps.setdefault(link_to_page(link), []).append(rel)
    return deps


def changed_docs(docs_dir, since):
    out = subprocess.run(
        ["git", "-C", docs_dir, "diff", "--name-only", f"{since}..HEAD", "--", "docs/"],
        capture_output=True, text=True, check=True,
    ).stdout
    return [p for p in out.splitlines() if re.search(r"\.mdx?$", p)]


def docs_pages(docs_dir):
    out = subprocess.run(["git", "-C", docs_dir, "ls-files", "docs/"], capture_output=True, text=True, check=True).stdout
    return {page_key(p) for p in out.splitlines() if re.search(r"\.mdx?$", p)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", required=True, help="path to an orchestra-docs checkout at the commit to sync to")
    ap.add_argument("--update", action="store_true", help="record docs HEAD as synced")
    args = ap.parse_args()

    since = json.loads(WATERMARK.read_text())["docs_sha"]
    head = subprocess.run(["git", "-C", args.docs, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()

    if args.update:
        WATERMARK.write_text(json.dumps({"docs_sha": head}, indent=2) + "\n")
        print(f"watermark -> {head}")
        return 0

    deps = dependency_map()
    pages = docs_pages(args.docs)
    impacted, unmapped = {}, []
    for docs_file in changed_docs(args.docs, since):
        skills = deps.get(page_key(docs_file))
        if not skills:
            unmapped.append(docs_file)
        for s in skills or []:
            impacted.setdefault(s, []).append(docs_file)

    report = {
        "docs_range": f"{since}..{head}",
        "impacted": impacted,  # skill file -> changed docs pages it links to
        "unmapped_docs_changes": unmapped,  # changed pages no skill links to — review for new YAML features only
        "dead_links": {k: v for k, v in deps.items() if k not in pages},  # linked pages that no longer exist
    }
    print(json.dumps(report, indent=2))
    return 2 if impacted or report["dead_links"] else 0


if __name__ == "__main__":
    sys.exit(main())
