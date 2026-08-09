# Model-change / fallback event log

Per hard rule 9. Any notice that the model changed mid-task is recorded here **immediately**,
work stops, and the operator is notified before anything resumes.

Each entry must record: timestamp, task and item in progress, model before, model after, and
which output rows had already been written.

---

## Events

**None recorded.**

| Phase | Session model | Model source | Effort | Fallback fired? |
|---|---|---|---|---|
| S (preflight) | Claude Opus 5 (1M context), `claude-opus-5[1m]` | observed from transcript | ultracode — observed, never confirmable (amendment 6) | No |
| 0 (inventory) | Claude Opus 5 (1M context), `claude-opus-5` | `/status` → "Default (Opus 5 with 1M context)"; **Default, not an explicit pin** | ultracode (session-only `/effort`; `settings.json` persists `xhigh`) | **No** |

`switchModelsOnFlag` was verified effective as `false` before Phase 0 analysis began, from
both active setting sources (`p0_preflight_verify.py` → `amendment_8_settings_precedence`).
A flagged request would now pause and offer a choice rather than migrate the session silently.
The correct choice for this task is **retry**, never **switch**.

### Subagent note (Phase 0)

A four-agent mechanical discovery workflow was launched during Phase 0 and **all four agents
failed on a session usage limit before returning anything**. No subagent output reached any
deliverable and no subagent produced a judgement, so no mixed-model labelling occurred. All
Phase 0 discovery was redone in-session via the committed scripts. Recorded here because a
subagent's model is not guaranteed to match the session model and a fallback inside one would
be invisible in this transcript — the conservative reading is that subagents are not used for
any classification pass (A3, A4).

---

*If this file still shows "None recorded" at the end of the task set, no classification pass
was split across models.*
