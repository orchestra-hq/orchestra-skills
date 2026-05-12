### Step 5b — Poll PR and trigger retry on merge

**Goal:** Watch the PR and trigger the pipeline rerun once it merges.

After sharing the PR URL, emit one status line and keep polling in the same conversation until the PR reaches a terminal state or the user asks to stop:

```
⏳ PR #178 open — checking every 60 s; will trigger the pipeline on merge.
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

4. **If `state == "OPEN"`:** Wait about 60 seconds, then check again. After several
   checks with no merge, widen the interval to about 4–5 minutes. Keep the PR number,
   repo, pipeline ID, and environment in the conversation context so each poll resumes
   the same fix workflow.

**Polling output format** (one line per check, not a full summary):

```
⏳ PR #178 — OPEN (2 min elapsed, next check in 60 s)
⏳ PR #178 — OPEN (3 min elapsed, next check in 60 s)
✅ PR #178 — MERGED — triggering pipeline rerun…
```

**Do not** re-diagnose or re-explain the fix on each poll tick. One line only.
