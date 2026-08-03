# Skill evals

An eval-driven test harness for the skills in this repo. It runs a skill against
realistic prompts **with and without the skill**, then grades the output against
assertions — so you can tell whether the skill actually improves results and catch
regressions when you edit it.

The design follows the [agentskills.io eval guide](https://agentskills.io/skill-creation/evaluating-skills)
(per-skill `evals.json`, `with_skill` / `without_skill` runs, `grading.json` +
`benchmark.json`, iteration directories) and borrows the scenario/runner layout from
[dbt-labs/dbt-agent-skills](https://github.com/dbt-labs/dbt-agent-skills/tree/main/evals).

Wired up for **`write-snowflake-dq-tests`** (YAML-output, fully code-graded) and
**`databricks-cost-audit`** / **`databricks-cost-drivers`** (response-graded, via
`--llm-judge`). Adding more skills is a matter of dropping a new suite directory next to
them (see [Adding a suite](#adding-a-suite)).

## Layout

```
evals/
├── README.md                       # this file
├── requirements.txt                # pyyaml + anthropic (use system python3 or a venv)
├── runner.py                       # drives `claude -p` with/without the skill
├── grade.py                        # code- and/or LLM-grades runs against assertions
├── judge.py                        # LLM-judge implementation (forced tool call), used by grade.py
├── .workspace/                     # run outputs (git-ignored)
│   └── write-snowflake-dq-tests/
│       └── iteration-1/
│           ├── <eval-id>/
│           │   ├── with_skill/    { files/, pipeline.yml, timing.json, grading.json, transcript.txt }
│           │   └── without_skill/ { ... }
│           └── benchmark.json
└── write-snowflake-dq-tests/    # the suite (checked in)
    ├── evals.json                  # test cases: prompt, expected_output, files, assertions
    ├── files/                      # input fixtures fed to the agent
    └── expected/golden_pipeline.yml# reference output for human / blind-LLM comparison
```

`evals.json` and the fixtures are the only files you author by hand. `timing.json`,
`grading.json`, and `benchmark.json` are produced by the harness.

## Scope: what each suite actually exercises

`write-snowflake-dq-tests` end-to-end queries live Snowflake, pushes a git branch,
and deploys via the Orchestra MCP server — none of which is deterministic or cheap to
run in a loop. The harness deliberately exercises only the **pipeline-YAML authoring
step** (Step 2 of the skill): the agent is handed a fixture *table inventory* and asked
to emit the data-quality pipeline YAML to `pipeline.yml`. MCP servers are disabled and
the tool set is restricted to file tools, so no run can touch a real warehouse or repo.

`databricks-cost-audit` and `databricks-cost-drivers` follow the same principle but have
no artifact file to grade — a run's answer is a written response, not `pipeline.yml`.
`databricks-cost-audit`'s evals exercise **procedure and communication only**: no Bash
tool is enabled, so the agent can't actually run `scripts/audit.py` against a real
warehouse; the assertions check what it says it would do (ask for missing credentials,
use `--dry-run`, report skipped checks), not real execution. `databricks-cost-drivers`
hands the agent a fixture standing in for the `list_pipeline_runs` MCP call it can't
make (MCP is disabled in the sandbox, same as the Snowflake case), and grades the
materialized ranked table it produces from that data.

This keeps every loop fast and reproducible while covering the part of each skill where
the interesting reasoning happens.

## Setup

You need two things on your machine:

1. **The `claude` CLI** on your `PATH` — the runner drives it headlessly (`claude -p …`).
   Check with `claude --version`; install/upgrade per the [Claude Code docs](https://docs.claude.com/en/docs/claude-code).
   Be signed in (or have `ANTHROPIC_API_KEY` set) so non-interactive runs can authenticate.
   No Orchestra MCP, Snowflake, or git credentials are required — runs are sandboxed to
   file tools with MCP disabled.
2. **`pyyaml`** for the grader, and **`anthropic`** if you'll use `--llm-judge`. Either
   use a `python3` that already has them, or install into a venv:

   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r evals/requirements.txt
   ```

   `--llm-judge` calls the Anthropic API directly (not through the `claude` CLI), so it
   needs `ANTHROPIC_API_KEY` set specifically — a signed-in `claude` CLI session alone
   isn't enough for this one call.

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

# Grade free-text assertions with an LLM judge instead of leaving them `manual`
python3 evals/runner.py databricks-cost-audit --llm-judge
python3 evals/grade.py databricks-cost-audit --llm-judge --judge-model claude-sonnet-5
```

`runner.py` auto-grades each iteration when it finishes, so the usual loop is just the
first command. `grade.py` is there to re-grade after you tweak assertions without
re-spending tokens on runs. `--llm-judge` works with either.

### What a run does

For each eval and each configuration the runner:

1. creates `…/<eval-id>/<config>/` and copies the case's `files` into `…/files/`,
2. shells out to `claude -p` in that directory with MCP disabled and only file tools
   allowed — for `with_skill` the skill's `SKILL.md`, plus the content of any
   `../../references/...` files it links to, is injected via `--append-system-prompt`;
   `without_skill` gets the bare prompt,
3. captures `total_tokens` / `duration_ms` / `total_cost_usd` into `timing.json` and the
   final assistant message into `transcript.txt`,
4. if the suite sets `output_file` (e.g. `write-snowflake-dq-tests`'s `pipeline.yml`),
   expects the agent to have written it. Suites without `output_file` (the databricks
   pair) are graded against `transcript.txt` instead — there's nothing to check for.

A suite can also set an optional `sandbox_note` string in `evals.json`, injected into the
`with_skill` system prompt to describe what the sandbox does and doesn't have (defaults to
the YAML-authoring wording above if omitted).

## Assertions and grading

Each eval lists `assertions` — either plain strings (`"..."`) or objects (`{"text": ...,
"check": ...}`); a plain string is shorthand for `{"text": "..."}`. Three kinds end up
graded differently:

- **Coded** assertions carry a `check` (e.g. `valid_yaml`, `min_task_groups`, `regex`,
  `every_task`) and are graded mechanically by `grade.py` against `output_file` — reliable
  and reusable across iterations. Only meaningful for suites that set `output_file`.
- **Free-text, ungraded** — a plain-string/`text`-only assertion with no `--llm-judge` —
  recorded as `manual` (`passed: null`) for human review.
- **Free-text, LLM-graded** — the same assertions, but with `--llm-judge` passed:
  `judge.py` batches every free-text assertion for a run into one forced tool call
  (`strict: true` + `tool_choice`) against a judge model (default `claude-haiku-4-5`,
  override with `--judge-model`), grading against `transcript.txt` (plus the output file's
  contents, if the suite has one). Recorded as `graded_by: "llm"` with a `rationale`.

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

`grading.json` records PASS/FAIL plus concrete `evidence` per assertion (the judge's
`rationale`, for LLM-graded ones); `benchmark.json` aggregates pass-rate / tokens /
duration per configuration and the **delta** between them. `pass_rate` combines coded and
LLM-graded assertions once `--llm-judge` is used; without it, `pass_rate` is coded-only,
same as before this flag existed.

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
2. Name the suite directory exactly after the skill directory under
   `skills/orchestra/skills/<skill-name>/` — the runner resolves `SKILL.md` from there.
3. If the skill produces a single output file, set `output_file` in `evals.json`
   (defaults to nothing — a suite is response-graded against `transcript.txt` unless it
   opts into a file). If the sandbox's tool/MCP restrictions need explaining to the agent
   (e.g. "you can't actually call the API this skill wraps"), set `sandbox_note`.
4. `python3 evals/runner.py <skill-name>` (add `--llm-judge` if any assertions are
   free-text and you want them graded rather than left `manual`).
