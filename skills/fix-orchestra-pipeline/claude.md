### Step 5b — Poll PR and auto-retry on merge

**Goal:** Watch the PR and trigger the pipeline rerun automatically once it merges — no manual step from the user.

After sharing the PR URL, emit one status line and then use `ScheduleWakeup` to re-enter this skill at regular intervals:

```
⏳ PR #178 open — polling every 60 s, will auto-trigger pipeline on merge.
```

**Polling loop:**

1. Check PR state:
   ```
   gh pr view {pr_number} --repo {owner/repo} --json state,mergedAt
   ```

2. **If `state == "MERGED"`:** Proceed immediately to Step 6 — trigger `start_pipeline`
   using the original pipeline ID and environment. No confirmation needed (the user
   already approved the fix by merging the PR).

3. **If `state == "CLOSED"` (not merged):** The PR was closed without merging. Report
   this and ask the user how to proceed — do not auto-retry.

4. **If `state == "OPEN"`:** Schedule the next check. Use `ScheduleWakeup` with
   `delaySeconds: 60` while cache is warm (first ~4 checks). After 4 checks with no
   merge, switch to `delaySeconds: 270` to stay within the 5-minute cache window.
   Pass the same `/fix-orchestra-pipeline` invocation as the `prompt` so the next
   wake re-enters the skill with full context.

   Store the PR number, repo, pipeline ID, and environment in the wake-up context by
   encoding them in the prompt string, e.g.:
   ```
   /fix-orchestra-pipeline poll pr=178 repo=owner/repo pipeline_id=123e4567-e89b-12d3-a456-426614174000 env=Production
   ```

**Polling output format** (one line per check, not a full summary):

```
⏳ PR #178 — OPEN (2 min elapsed, next check in 60 s)
⏳ PR #178 — OPEN (3 min elapsed, next check in 60 s)
✅ PR #178 — MERGED — triggering pipeline rerun…
```

**Do not** re-diagnose or re-explain the fix on each poll tick. One line only.
