# Model-change / fallback event log

Per hard rule 9. Any notice that the model changed mid-task is recorded here **immediately**,
work stops, and the operator is notified before anything resumes.

Each entry must record: timestamp, task and item in progress, model before, model after, and
which output rows had already been written.

---

## Events

**None recorded.**

| Phase | Session model observed | Fallback fired? |
|---|---|---|
| S (preflight) | Claude Opus 5 (1M context), `claude-opus-5[1m]` | No |

---

*If this file still shows "None recorded" at the end of the task set, no classification pass
was split across models.*
