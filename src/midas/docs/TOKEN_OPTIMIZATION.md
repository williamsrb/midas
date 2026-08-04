# Token optimization in Midas

Source: an internal PT-BR research note summarizing five videos on reducing
token spend with Claude-family models (translated and evaluated 2026-07-16).
This document records what Midas **adopted**, how, and what was **rejected**
and why.

## Source material, translated (condensed)

1. **Model lineup strategy** - with Fable/Opus/Sonnet/Haiku the choice is a
   capability/speed/cost trade-off. Sonnet 5's new tokenizer consumes ~30%
   more tokens (affects real cost); Fable 5 is capped at 50% of the weekly
   limit on Claude Code plans, so smart delegation to smaller models is
   essential. "Adaptive thinking" lets the model pick its own thinking budget.
2. **"Caveman" output style** - stripping conversational fluff and forcing
   terse technical replies cut output tokens ~31% (Claude Code test) and
   halved cost in an OpenCode test. Output tokens cost far more than input.
3. **Context hygiene** - a polluted context window degrades reasoning and
   raises cost. Use spec-driven prompts, subagents for side quests, /compact
   and /clear, and CLI-output compaction proxies (RTK).
4. **Knowledge graphs (Graphify)** - pre-indexing the repo into a graph and
   querying it instead of re-reading folders (claimed up to 71x savings;
   costs tokens up-front, biggest wins when indexing code only).
5. **10-80-10 orchestration** - the expensive model plans (10%), cheap models
   execute (80%), the expensive model validates (10%). Cap agent count
   (10-15), keep effort at medium to avoid overthinking, use handoff prompts
   to restart long conversations, route simple work to cheaper models.
   Exotic: converting context to PNG (PX Pipe, claimed ~95% savings).

## Adopted in Midas

| Measure | Where | Effect |
|---|---|---|
| **10-80-10 model routing** | `agents.planner_model` (opus) plans, `implementer_model` (sonnet) executes, `validator_model` (sonnet) reviews, `utility_model` (haiku) does glue work (jira fallback, env-detect) | the expensive model only sees the planning stage |
| **Terse output rules** ("caveman light") | `agents.token_saver` appends output-economy rules to every prompt: no preamble/fluff, bullets over prose, targeted file reads | output tokens are the expensive ones; this trims them on every stage |
| **Effort cap / anti-overthinking** | `agents.effort` (low/medium/**high**) maps to a `MAX_THINKING_TOKENS` cap for claude runs; default `medium` | prevents Ultra-effort-style overthinking on routine stages |
| **Subagent cap** | `agents.max_subagents` (default 2) injected into the prompt rules | stops agent-swarm blowups |
| **Fresh context per stage** (handoff pattern) | each pipeline stage is an independent one-shot `claude -p` run fed only `task.md`, `env.json`, `plan.md` | no long-conversation context inflation; the "handoff" is the plan file itself |
| **Spec-driven prompts** | the plan stage produces a tight `plan.md` spec; the implementer receives the spec, not the exploration history | implementer starts with a clean, minimal context |
| **Usage ledger** | every call recorded to `llm-usage.jsonl` (`midas usage`), including hooked interactive sessions | you can only optimize what you measure |

## Adopted later (2026-08-04): the What/How split and RTK

The curated harness changed after this document was first written, and midas now ships the
result. Three additions:

| Technique | How midas ships it |
|---|---|
| **Skill "What" / "How" split** | a `SKILL.md` now carries only the contract - when to use it, decision rules, deliverable - while the procedure lives once in the knowledge base (`kb/implementation/How-to-*.md`, `kb/validation/Quality-gate-*.md`, `kb/testing/<project>/`). Stages stop re-deriving procedure, and a fix to a procedure lands in one place instead of nine |
| **Context budget per stage** | every bundled skill declares what it may read and what it must not. The planner does not read prior rounds; the implementer does not re-read the PRD; triage reads one file and emits one JSON object. Bundled as `kb/implementation/How-to-resolve-task-context.md`, which the budgets delegate to |
| **RTK** (`rtk`) | **reversed from the rejection below.** Compacts noisy shell output (`ls`, `docker ps`, test runners) before it reaches the model, wired through the `rtk-claude.sh` / `rtk-cursor.sh` PreToolUse hooks. Shipped as an `external` CLI item: midas carries the recipe and probe, not the ~10 MB binary. `RTK_DISABLED=1 <cmd>` recovers a hidden field, and `git push` stays denied for both raw and `rtk`-prefixed forms |

Why RTK was reversed: the original objection was that midas' one-shot stages do not
accumulate CLI noise the way interactive sessions do. That is still true of the *planner*,
but the implementer and validator stages run builds, linters and test suites whose output
is exactly what RTK compacts. The binary is also no longer unvetted - it is in daily
interactive use on the curating machine. It stays **optional**, so a machine without it is
`behind`, never `outdated`.

## Evaluated and NOT adopted (for now)

| Technique | Why not |
|---|---|
| **Graphify knowledge graphs** | heavy extra infrastructure per repo; midas tasks touch many small repos where indexing cost would rarely amortize. Revisit if a single big monorepo joins the flow |
| **PNG context compression (PX Pipe)** | fragile/unverified trick; depends on image-input pricing quirks that can change, and hurts auditability of transcripts |
| **OpenRouter / third-party model routing** | company work must stay on approved providers (Anthropic/Cursor subscriptions) |
| **Caveman "Ultra" symbol-compression mode** | savings past the light mode come at the cost of readable transcripts, which midas needs for human validation |

## Practical guidance

- Keep `effort = medium` unless a task genuinely needs deep reasoning; bump
  per-run by editing config, not permanently.
- Prefer `label` pickup mode while trialing: fewer tasks, predictable spend.
- Watch `midas usage --days 30`: if `implement` stages dominate cost, consider
  `implementer_model = "haiku"` for simple content tasks.
- The planner prompt is the only place the expensive model runs - keep task
  descriptions in Jira tight; they are pasted into that context.
