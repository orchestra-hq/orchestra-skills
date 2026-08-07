# Skill evals

An eval-driven test harness for the skills in this repo. It runs a skill against
realistic prompts **with and without the skill**, then grades the output against
assertions — so you can tell whether the skill actually improves results and catch
regressions when you edit it.

The design follows the [agentskills.io eval guide](https://agentskills.io/skill-creation/evaluating-skills)
(per-skill `evals.json`, `with_skill` / `without_skill` runs, `grading.json` +
`benchmark.json`, iteration directories) and borrows the scenario/runner layout from
[dbt-labs/dbt-agent-skills](https://github.com/dbt-labs/dbt-agent-skills/tree/main/evals).

Every suite lives in this flat `evals/` namespace regardless of which plugin its skill
belongs to — `runner.py` resolves a suite name's `SKILL.md` against every known plugin
root (`skills/orchestra/skills/`, `skills/migrate-to-orchestra/skills/`) and requires an
unambiguous match; pass `--plugin` to disambiguate a name collision, or `--skills-root`
to point at a skill tree outside this repo entirely (see [Adding a suite](#adding-a-suite)).

## Layout

```
evals/
├── README.md                       # this file
├── requirements.txt                # pyyaml (use system python3 or a venv)
├── runner.py                       # drives `claude -p` with/without the skill
├── grade.py                        # code-grades generated YAML against assertions
├── validate_live.py                # optional: validates already-generated YAML against
│                                    # the real Orchestra schema via the validate_pipeline
│                                    # MCP tool (credential-gated, skips gracefully without one)
├── _shared_assertions/              # category-level assertion libraries, referenced by
│   ├── definitions.json            # multiple suites via a case's "assertions_ref" — e.g.
│   ├── connections.json            # every *-alerts-to-orchestra suite (Dagster today,
│   ├── alerts.json                 # Airflow/Prefect later) references alerts.json instead
│   └── ...                         # of hand-copying the same 6-destination checks
├── .workspace/                     # run outputs (git-ignored)
│   └── write-snowflake-dq-tests/
│       └── iteration-1/
│           ├── <eval-id>/
│           │   ├── with_skill/    { files/, pipeline.yml, timing.json, grading.json, transcript.txt, validate_live.json }
│           │   └── without_skill/ { ... }
│           └── benchmark.json
└── write-snowflake-dq-tests/    # a suite (checked in)
    ├── evals.json                  # test cases: prompt, expected_output, files, assertions
    ├── files/                      # input fixtures fed to the agent
    └── expected/golden_pipeline.yml# reference output for human / blind-LLM comparison
```

`evals.json`, fixtures, and `_shared_assertions/*.json` are the only files you author by
hand. `timing.json`, `grading.json`, `benchmark.json`, and `validate_live.json` are
produced by the harness.

## Scope: YAML generation only

`write-snowflake-dq-tests` end-to-end queries live Snowflake, pushes a git branch,
and deploys via the Orchestra MCP server — none of which is deterministic or cheap to
run in a loop. The harness deliberately exercises only the **pipeline-YAML authoring
step** (Step 2 of the skill): the agent is handed a fixture *table inventory* and asked
to emit the data-quality pipeline YAML to `pipeline.yml`. MCP servers are disabled and
the tool set is restricted to file tools, so no run can touch a real warehouse or repo.

This keeps the loop fast and reproducible while covering the part of the skill where the
interesting reasoning happens — which tests to infer and how to shape the Orchestra YAML.

## Setup

You need two things on your machine:

1. **The `claude` CLI** on your `PATH` — the runner drives it headlessly (`claude -p …`).
   Check with `claude --version`; install/upgrade per the [Claude Code docs](https://docs.claude.com/en/docs/claude-code).
   Be signed in (or have `ANTHROPIC_API_KEY` set) so non-interactive runs can authenticate.
   No Orchestra MCP, Snowflake, or git credentials are required — runs are sandboxed to
   file tools with MCP disabled.
2. **`pyyaml`** for the grader. Either use a `python3` that already has it (e.g. the
   system interpreter), or install into a venv:

   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r evals/requirements.txt
   ```

Run everything from the **repo root** so the relative paths in `runner.py` resolve.
Each run spends tokens against your Claude account — the full suite is 3 cases × 2
configurations = 6 `claude` invocations.

## Running

```bash
# Run every case, both configurations, into the next iteration dir
python3 evals/runner.py write-snowflake-dq-tests

# One case only / pick configurations / pin a model / reuse an iteration number
python3 evals/runner.py write-snowflake-dq-tests --only ecommerce-full
python3 evals/runner.py write-snowflake-dq-tests --configs with_skill
python3 evals/runner.py write-snowflake-dq-tests --model claude-opus-4-8 --iteration 3

# Grade the latest iteration (or a specific one) and write benchmark.json
python3 evals/grade.py write-snowflake-dq-tests
python3 evals/grade.py write-snowflake-dq-tests --iteration 1
```

`runner.py` auto-grades each iteration when it finishes, so the usual loop is just the
first command. `grade.py` is there to re-grade after you tweak assertions without
re-spending tokens on runs.

### What a run does

For each eval and each configuration the runner:

1. creates `…/<eval-id>/<config>/` and copies the case's `files` into `…/files/`,
2. shells out to `claude -p` in that directory with MCP disabled and only file tools
   allowed — for `with_skill` the skill's `SKILL.md`, plus the content of any
   `../../references/...` files it links to, is injected via `--append-system-prompt`;
   `without_skill` gets the bare prompt,
3. captures `total_tokens` / `duration_ms` / `total_cost_usd` into `timing.json` and the
   final assistant message into `transcript.txt`,
4. expects the agent to have written `pipeline.yml`.

## Assertions and grading

Each eval lists `assertions`. Two kinds:

- **Coded** assertions carry a `check` (e.g. `valid_yaml`, `min_task_groups`, `regex`,
  `every_task`) and are graded mechanically by `grade.py` — reliable and reusable across
  iterations.
- **Free-text** assertions have only `text` and are recorded as `manual` (passed: null)
  for human or LLM review — use these for qualities that don't reduce to a code check.

Coded `check` types (see [`grade.py`](grade.py) for arguments):

| check | what it verifies |
|-------|------------------|
| `valid_yaml` | output parses to a YAML mapping |
| `yaml_eq` / `yaml_present` | a dotted path equals a value / exists |
| `regex` | a pattern appears in the raw text (`min_count`, `ignore_case`) |
| `min_task_groups` | `pipeline` has at least N groups |
| `all_groups_have` | every group carries a given key (e.g. `condition`) |
| `every_task` / `some_task` | a field equals a value across all / at least one task |
| `alerts_status` | an alert fires on a given status (e.g. `FAILED`) |
| `groups_chained` | at least one group has a non-empty `depends_on` |
| `depends_on_edge` | a specific group `depends_on` a specific upstream group (`group`, `upstream`) |
| `no_hardcoded_secret` | no secret-shaped key (`api_key`/`token`/`password`/...) holds a literal value instead of a `${{ ... }}` reference (`extra_keys` optional) |
| `valid_enum` | a field's value across all tasks is one of an allowed set (`field`, `allowed`) |
| `alert_destination_requires` | every alert destination of a given `integration` sets a required `field` (e.g. PAGER_DUTY needs `connection_id`) |

`grading.json` records PASS/FAIL plus concrete `evidence` per assertion; `benchmark.json`
aggregates pass-rate / tokens / duration per configuration and the **delta** between them.

### Shared assertions across suites

A case can pull in one or more category-level assertion files before its own, via
`"assertions_ref": ["definitions", "connections", "alerts"]` — each name resolves to
`_shared_assertions/<name>.json` (`{"category": ..., "assertions": [...]}`, same object
shape as inline assertions). This is what keeps ~50 suites across three source
orchestrators from each hand-copying the same category checks: write `alerts.json` once
against `dagster-alerts-to-orchestra`'s destination schema, and `airflow-alerts-to-orchestra`
/ `prefect-alerts-to-orchestra` reference the same file later, adding only their
orchestrator-specific fixture and a couple of case-specific literals. Shared assertions are
graded ahead of a case's own so `grading.json` reads generic-to-specific.

### Live schema validation (optional)

`grade.py` only checks what a suite's `evals.json` happens to assert — it never confirms
the YAML would actually be accepted by Orchestra. `validate_live.py` closes that gap by
handing an already-generated `pipeline.yml` to the real `validate_pipeline` MCP tool:

```bash
python3 evals/validate_live.py dagster-alerts-to-orchestra --iteration 1
```

It needs `ORCHESTRA_MCP_CONFIG_PATH` set to a file path holding an MCP config that
exposes `orchestra-mcp`'s `validate_pipeline` tool; without it, every case is recorded
`{"status": "skipped"}` and the script exits `0` — it never turns a missing credential
into a hard failure. Locally, point it at a config file you already have. In CI
(`skill-evals-live.yml`), there's no such file on a fresh runner — a preceding step
writes the repo variable `ORCHESTRA_MCP_CONFIG` (the `mcpServers` JSON block itself) out
to a temp file and points `ORCHESTRA_MCP_CONFIG_PATH` at it; leave that repo variable
unset to keep the nightly run a no-op skip. Kept separate from `runner.py`/`grade.py`
because those two are deliberately sandboxed
(`--strict-mcp-config --mcp-config '{"mcpServers":{}}'`) so a generation run can never
reach a live system; validation against the real schema is opt-in and runs only after
generation, never during it.

The `expected/golden_pipeline.yml` reference is **not** diffed mechanically (correct YAML
has many valid shapes). It's the anchor for human review and the blind-LLM comparison the
agentskills guide recommends for holistic quality.

### Interpreting results

The point of the exercise is the **delta** (with_skill − without_skill) in `benchmark.json`:

- **Pass-rate delta > 0** — the skill is adding value; inspect which assertions pass with
  it and fail without to see *what* convention it's enforcing.
- **Pass-rate delta ≈ 0** — either the base model already handles this well (consider
  dropping assertions that always pass in both configs), or the skill isn't helping yet.
- **Token / duration delta** — what the skill costs. A higher pass rate for *fewer* tokens
  is the ideal; a small quality gain for a large token increase may not be worth it.

To improve the skill, feed the failed assertions, the `transcript.txt` of a weak run, and
the current `SKILL.md` to an LLM and ask for targeted edits — then re-run into a fresh
`iteration-N/` and compare. See the
[agentskills iteration loop](https://agentskills.io/skill-creation/evaluating-skills) for
the full method.

## Adding a suite

1. `mkdir evals/<skill-name>` with `evals.json`, `files/`, and optionally `expected/`.
2. Name the suite directory exactly after the skill directory — the runner resolves
   `SKILL.md` by searching every known plugin root (`skills/orchestra/skills/`,
   `skills/migrate-to-orchestra/skills/`) for that name; pass `--plugin` only if the same
   name exists under more than one, or `--skills-root` to test a skill tree outside this repo.
3. Before writing category-shape assertions from scratch, check `_shared_assertions/` for
   an existing file covering the concept (`alerts`, `connections`, `sensors`, ...) and
   reference it via `"assertions_ref": [...]` — add only case-specific literals inline.
4. `python3 evals/runner.py <skill-name>`.
