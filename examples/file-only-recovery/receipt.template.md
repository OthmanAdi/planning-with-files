# File-only recovery receipt

Copy this file once per trial. Fill every row. Redact secrets, home-directory paths, and transcript text. Keep the file when the trial fails, is aborted, or is inconclusive. Do not drop those trials from the report.

| Field | Value |
|-------|-------|
| Skill commit or release | |
| Host | |
| Model | |
| OS | |
| Flags | |
| Arm | |
| Stage-2 turns | |
| Outcome | |

`Arm` is `file-only`, `baseline`, or `replay`.

`Flags` is the literal flag list for that trial. Leave it empty when there are none. A `file-only` trial that records `--metadata` or `--replay` is inconclusive.

`Outcome` is `pass`, `fail`, `inconclusive`, or `aborted`. `aborted` stays in the report as inconclusive.

`Stage-2 turns` counts assistant turns in the fresh session only.
