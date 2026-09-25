# Docs sync agent

Instructions for the `RUN_AGENT` task in [`sync-docs.yml`](sync-docs.yml). This task keeps the skills in this repo in line with [orchestra-docs](https://github.com/orchestra-hq/orchestra-docs). It runs when the docs repo merges to `main`, and on a weekly schedule to catch anything the docs trigger missed.

## Steps

1. Clone `orchestra-hq/orchestra-skills` and use it as the working directory. Clone `orchestra-hq/orchestra-docs` next to it, on `main`.
2. Run `python3 scripts/docs_sync.py --docs ../orchestra-docs`.
   - **Exit code 0:** nothing is stale. Stop. Do not open a PR.
   - **Exit code 2:** read the JSON report.
3. Check for an open PR from a `docs-sync/*` branch. If there is one, check out its branch and add to it instead of opening a second PR.
4. Work through the report:
   - **`impacted`:** for each skill file, read the listed docs changes with `git -C ../orchestra-docs diff <docs_range> -- <page>`. Update the skill only where it now says something the docs contradict, or leaves out a new field or behaviour a user writing pipeline YAML would need. Rewording or reordering on the docs side needs no change.
     - A change to `docs/core-concepts/pipelines/schema.mdx` is a pipeline schema change: new or removed `integration` / `integration_job` values, or parameter fields. Put it in `skills/orchestra/references/orchestra/pipeline/yaml-authoring.md`, or in the skill that documents that task type. Never paste the schema in.
   - **`dead_links`:** point each link at the page it moved to. Find it with `git -C ../orchestra-docs log --diff-filter=R --name-status`, or with the docs site's redirects.
   - **`unmapped_docs_changes`:** only look at pages that describe pipeline YAML (fields, triggers, task behaviour, alerting). Skip organisation settings, SSO, guides, templates and the changelog. If a page adds something a skill should cover, update that skill and link the page. The link is what puts the page in the map for future runs.
5. Follow AGENTS.md → "Editing this repository":
   - Shared schema facts go under `skills/orchestra/references/orchestra/`. Do not copy them into `migrate-to-orchestra`.
   - Bump the `version` in each touched plugin's `.claude-plugin/plugin.json` and `.cursor-plugin/plugin.json`.
   - If anything under `skills/orchestra/` changed, also bump `.tessl-plugin/plugin.json`.
   - If a change affects behaviour an eval checks, update that eval under `evals/`.
6. Run `python3 scripts/docs_sync.py --docs ../orchestra-docs --update`. This moves `.docs-sync.json` forward. Always run it, even when the report needed no skill edits, so the next run starts from here.
7. Run `python3 scripts/test_docs_sync.py`, `python3 evals/lint_evals.py` and `python3 skills/orchestra/hooks/test_validate_pipeline.py`. They must all pass.
8. Commit on a new branch `docs-sync/<yyyy-mm-dd>` and open a PR against `main`. Never push to `main` and never merge.

   The PR body lists:
   - the docs range;
   - each skill file changed, with the docs page or schema change that caused it;
   - impacted files you deliberately left unchanged, with a one-line reason each.

   If the only change is the watermark moving forward, still open the PR, titled `[docs-sync] Advance watermark (no skill changes)`.

## Rules

- Only edit files under `skills/`, `evals/`, the plugin manifests and `.docs-sync.json`.
- The docs are the source of truth for product behaviour. If a skill and the docs disagree and you can't tell which is right, leave the skill alone and flag it in the PR body.
- Keep skills written the way they are: workflow and judgement, with links to the docs. Don't turn docs prose into skill text.
- Never add secrets, workspace IDs or customer-specific details.
