# File-only recovery fixture

A disposable task for the current project-file-only recovery protocol. Clone the repository and run it. No hook, installer, or dependency changes. The historical stage-2 figures in [docs/evals.md](../../docs/evals.md) (5.0 and 13.3 turns) stay historical. This fixture is not a new measurement and does not replace that benchmark.

`grade.py` uses the Python standard library only. It reads `counts.py` and, on the file-only and replay arms, `task_plan.md`. It does not open host session stores.

## Files

| Path | Role |
|------|------|
| `TASK.md` | The only spec the agent should see |
| `checkpoint/` | Committed interruption: `word_count` works, the other two raise `NotImplementedError` |
| `complete/` | A finished workdir `grade.py --self-check` expects to pass |
| `grade.py` | Grader. Do not copy it into the work directory |
| `receipt.template.md` | One redacted receipt per trial |

`checkpoint/task_plan.md` records the interruption:

- Current Phase: `Phase 3`
- Next Step: `Implement line_count and unique_words in counts.py. word_count is already done.`

`checkpoint/findings.md` and `checkpoint/progress.md` follow `templates/`, including the 5-question reboot table.

## Check the fixture

From this directory:

```bash
python3 grade.py --self-check
```

`checkpoint/` is not done: the objective fails, and Phase 3 plus that next step are present. `complete/` passes: the functions match `TASK.md`, Phase 3 is complete, and the current phase has moved on.

## Arms

Keep three tallies. Do not add baseline or replay trials to the file-only numbers. Print failed and inconclusive trials in the same report. An aborted trial is inconclusive and stays in the report.

| Arm | Work directory | Fresh-session prompt | Catchup flags |
|-----|----------------|----------------------|---------------|
| `file-only` | `TASK.md` plus the whole `checkpoint/` | `Continue the work in this directory.` | none |
| `baseline` | `TASK.md` plus `checkpoint/counts.py` only | `Continue the work in this directory.` | none |
| `replay` | Same files as `file-only` | `Continue the work in this directory.` | explicit `--replay` only, and only on this arm |

The file-only arm is the current automatic protocol: planning files are on disk, and the session is not given `--metadata` or `--replay`. The baseline arm is the same partial `counts.py` and `TASK.md` with no `task_plan.md`, `findings.md`, or `progress.md`. Grade that directory on its own. The replay arm is optional. Its results stay out of the file-only tally.

## File-only setup

Run these commands from this directory. The work directory is disposable.

```bash
RUN=$(mktemp -d)
WORKDIR="$RUN/file-only"
mkdir -p "$WORKDIR"
cp TASK.md "$WORKDIR/"
cp checkpoint/task_plan.md checkpoint/findings.md checkpoint/progress.md checkpoint/counts.py "$WORKDIR/"
cp receipt.template.md "$RUN/receipt-file-only.md"
```

Do not copy `grade.py`, this README, or `receipt.template.md` into `$WORKDIR`.

Start a fresh session with that directory as the project. The only user prompt is:

```text
Continue the work in this directory.
```

Do not pass `--metadata` or `--replay`. Do not point the session at local session stores.

## Baseline setup

Use the same shell as the file-only setup so `$RUN` is set.

```bash
BASE="$RUN/baseline"
mkdir -p "$BASE"
cp TASK.md "$BASE/"
cp checkpoint/counts.py "$BASE/"
cp receipt.template.md "$RUN/receipt-baseline.md"
```

`$BASE` has no `task_plan.md`, `findings.md`, or `progress.md`. Use the same prompt. Grade it with `--arm baseline`.

## Live stop

Copying `checkpoint/` is the interruption. To stop a live stage 1 instead, start from `TASK.md` only and stop the session when `task_plan.md` shows both of these, exactly:

```text
## Current Phase

Phase 3
```

```text
## Next Step

Implement line_count and unique_words in counts.py. word_count is already done.
```

Then start the fresh session as in the file-only setup. Do not keep going into `line_count` in the first session.

## Grade

From this directory, after the fresh session stops:

```bash
python3 grade.py "$WORKDIR" --receipt "$RUN/receipt-file-only.md"
python3 grade.py "$BASE" --arm baseline --receipt "$RUN/receipt-baseline.md"
```

Fill the receipt before or after grading. `grade.py` prints `pass`, `fail`, or `inconclusive` on the first line. Exit status is 0, 1, or 2 for those three words.

`file_only_tally: yes` means the trial is a file-only pass or fail. Baseline, replay, and inconclusive trials print `file_only_tally: no` and still appear in the output.

A file-only receipt whose Flags cell contains `--metadata` or `--replay` is inconclusive. A receipt Outcome of `aborted` is inconclusive. Missing `counts.py` or, on the file-only arm, missing `task_plan.md` is inconclusive.

## Receipt fields

Copy `receipt.template.md` once per trial.

| Field | What to record |
|-------|----------------|
| Skill commit or release | `git rev-parse HEAD` of the skill you ran, or the release tag |
| Host | Host name and version, for example the version the host prints |
| Model | Model id the host used |
| OS | `uname -sr`, or the Windows version |
| Flags | Literal extra flags. Empty when there are none |
| Arm | `file-only`, `baseline`, or `replay` |
| Stage-2 turns | Assistant turns in the fresh session only |
| Outcome | `pass`, `fail`, `inconclusive`, or `aborted` |

Redact secrets, home-directory paths, and transcript text. Keep failed, aborted, and inconclusive receipts in the report.

## Replay arm

Use the file-only work directory. The fresh session may be given an explicit `session-catchup.py --replay` for that project. Set the receipt Arm to `replay` and put `--replay` in Flags. Grade without `--arm file-only`:

```bash
cp receipt.template.md "$RUN/receipt-replay.md"
python3 grade.py "$WORKDIR" --arm replay --receipt "$RUN/receipt-replay.md"
```

`grade.py` still does not open session stores. Do not add replay trials to the file-only tally.

## What this does not claim

One small counting task, graded by this script. It does not rerun the 77-cell benchmark, and it does not move the published 5.0 or 13.3 figures.
