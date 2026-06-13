# Skill evals

An eval-driven test harness for the skills in this repo. It runs a skill against
realistic prompts **with and without the skill**, then grades the output against
assertions — so you can tell whether the skill actually improves results and catch
regressions when you edit it.

The design follows the [agentskills.io eval guide](https://agentskills.io/skill-creation/evaluating-skills)
(per-skill `evals.json`, `with_skill` / `without_skill` runs, `grading.json` +
`benchmark.json`, iteration directories) and borrows the scenario/runner layout from
[dbt-labs/dbt-agent-skills](https://github.com/dbt-labs/dbt-agent-skills/tree/main/evals).

Currently wired up for **`run-snowflake-quality-tests`** only. Adding more skills is a
matter of dropping a new suite directory next to it (see [Adding a suite](#adding-a-suite)).

## Layout

```
evals/
├── README.md                       # this file
├── requirements.txt                # pyyaml (use system python3 or a venv)
├── runner.py                       # drives `claude -p` with/without the skill
├── grade.py                        # code-grades generated YAML against assertions
├── .workspace/                     # run outputs (git-ignored)
│   └── run-snowflake-quality-tests/
│       └── iteration-1/
│           ├── <eval-id>/
│           │   ├── with_skill/    { files/, pipeline.yml, timing.json, grading.json, transcript.txt }
│           │   └── without_skill/ { ... }
│           └── benchmark.json
└── run-snowflake-quality-tests/    # the suite (checked in)
    ├── evals.json                  # test cases: prompt, expected_output, files, assertions
    ├── files/                      # input fixtures fed to the agent
    └── expected/golden_pipeline.yml# reference output for human / blind-LLM comparison
```

`evals.json` and the fixtures are the only files you author by hand. `timing.json`,
`grading.json`, and `benchmark.json` are produced by the harness.

## Scope: YAML generation only

`run-snowflake-quality-tests` end-to-end queries live Snowflake, pushes a git branch,
and deploys via the Orchestra MCP server — none of which is deterministic or cheap to
run in a loop. The harness deliberately exercises only the **pipeline-YAML authoring
step** (Step 2 of the skill): the agent is handed a fixture *table inventory* and asked
to emit the data-quality pipeline YAML to `pipeline.yml`. MCP servers are disabled and
the tool set is restricted to file tools, so no run can touch a real warehouse or repo.

This keeps the loop fast and reproducible while covering the part of the skill where the
interesting reasoning happens — which tests to infer and how to shape the Orchestra YAML.

## Running

Requires the `claude` CLI on your PATH and `pyyaml` (`pip install -r evals/requirements.txt`,
or just use the system `python3` if it already has pyyaml).

```bash
# Run every case, both configurations, into the next iteration dir
python3 evals/runner.py run-snowflake-quality-tests

# One case only / pick configurations / pin a model / reuse an iteration number
python3 evals/runner.py run-snowflake-quality-tests --only ecommerce-full
python3 evals/runner.py run-snowflake-quality-tests --configs with_skill
python3 evals/runner.py run-snowflake-quality-tests --model claude-opus-4-8 --iteration 3

# Grade the latest iteration (or a specific one) and write benchmark.json
python3 evals/grade.py run-snowflake-quality-tests
python3 evals/grade.py run-snowflake-quality-tests --iteration 1
```

`runner.py` auto-grades each iteration when it finishes, so the usual loop is just the
first command. `grade.py` is there to re-grade after you tweak assertions without
re-spending tokens on runs.

### What a run does

For each eval and each configuration the runner:

1. creates `…/<eval-id>/<config>/` and copies the case's `files` into `…/files/`,
2. shells out to `claude -p` in that directory with MCP disabled and only file tools
   allowed — for `with_skill` the skill's `SKILL.md` is injected via
   `--append-system-prompt`; `without_skill` gets the bare prompt,
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

See [`grade.py`](grade.py) for the full list of `check` types and their arguments.
`grading.json` records PASS/FAIL plus concrete `evidence` per assertion; `benchmark.json`
aggregates pass-rate / tokens / duration per configuration and the **delta** between
them — that delta is the point of the exercise.

The `expected/golden_pipeline.yml` reference is **not** diffed mechanically (correct YAML
has many valid shapes). It's the anchor for human review and the blind-LLM comparison the
agentskills guide recommends for holistic quality.

## Adding a suite

1. `mkdir evals/<skill-name>` with `evals.json`, `files/`, and optionally `expected/`.
2. Name the suite directory exactly after the skill directory under
   `skills/orchestra/skills/<skill-name>/` — the runner resolves `SKILL.md` from there.
3. `python3 evals/runner.py <skill-name>`.
