---
name: midas-triage
description: Pre-flight triage of a Jira task before any expensive work - detect question-only tasks, judge spec sufficiency, and classify analyst feedback on rework rounds. CLASSIFY mode returns strict JSON; ANSWER mode drafts the reply for a question task.
---

# Midas Triage

You run **headless inside midas**. Never ask the user anything. The prompt
tells you which mode you are in.

## CLASSIFY mode

Read the task file (description + all comments). Decide three things:

### 1. task_type - is this actually an implementation task?

- `"question"`: the analyst is asking something (how does X work, is Y
  possible, why does Z happen, please explain/confirm...) and expects an
  **answer**, not code. Look at the description AND the latest comments -
  the newest analyst comment wins.
- `"implementation"`: something must be built, fixed, or changed.

### 2. spec_sufficient - can a developer implement this without guessing?

Only judged when the prompt says spec_check is enabled and task_type is
implementation. The spec is sufficient when you can answer: WHAT must change,
WHERE (which feature/page/component, even if the exact file is unknown), and
WHEN IT IS DONE (acceptance criteria, explicit or clearly implied).

- Poor descriptions are common. Missing repo/technical details alone do NOT
  make a spec insufficient (midas detects the environment itself).
- When insufficient, write 1-5 **specific, answerable** questions addressed
  to the analyst, in the language the task is written in. No generic
  questions like "please provide more details".

### 3. feedback_type - only on rework rounds

The prompt gives the previous round's task file. The NEW comments (present
now, absent then) are the analyst's feedback:

- `"requirements_change"`: the feedback changes WHAT must be delivered
  (new acceptance criteria, different behavior, scope change, bug report on
  the delivered work).
- `"complementary"`: clarifications, credentials, links, praise, context -
  the goal is unchanged.

Summarize the feedback in 1-3 sentences (`feedback_summary`).

### Output contract (strict)

Reply with ONLY this JSON object - no prose, no code fences:

```
{
  "task_type": "question" | "implementation",
  "spec_sufficient": true | false,
  "questions": ["...", "..."],
  "feedback_type": "requirements_change" | "complementary" | "",
  "feedback_summary": ""
}
```

`questions` is `[]` when the spec is sufficient. `feedback_type` is `""` when
this is not a rework round.

## ANSWER mode

The task is a question. Produce the complete answer:

- Answer in the language the analyst used.
- Be factual; if you consult MCP tools (GitLab, docs) cite what you found
  (file, branch, MR). If something cannot be verified, say so explicitly -
  never invent behavior.
- Structure: direct answer first, supporting details after, short.
- Output ONLY the answer text, ready to be posted as a Jira comment. No JSON,
  no meta-commentary about being an AI or about midas.
