# KB How-To format — Task Evidence Plan

Use this when creating or updating files under `../../kb/testing`.

## Principles

- **Instrumentation first** — teach *how* to perform an action, not *what happened* on one task.
- **Minimal sample data** — one working example at the end, not a dataset.
- **Stable identifiers** — selectors, field names, menu paths, URL patterns, datatoolbox queries.
- **Environment note** — state which host the steps were verified on; derive others from base URL.

## Template

```markdown
# How to <verb> <object> (<scope>)

**Scope:** `_shared` | `<project>` (e.g. `as`)
**Applies to:** <environments, e.g. review / localhost>
**Related:** [other How-To](./How-to-other.md)

## Prerequisites

- Auth realm if needed (e.g. Content Studio `/admin`, app login)
- Link to `_shared` guide if this builds on generic Enonic steps

## Procedure

1. <Imperative step — what to click, type, or navigate>
2. <Next step with stable selector or CMS path>
3. ...

### Sub-flow (optional)

Use when one guide covers multiple related actions (e.g. open modal vs fill form).

## Pitfalls

- <Common failure, e.g. "page needs referer", "publish media separately">
- <Auth or timing note>

## Sample data (minimal)

| Field | Example |
|-------|---------|
| Base URL | `https://review.example/` |
| ... | one value only where needed |
```

## Examples of good KB topics

**`_shared` (Enonic):**

- Search via datatoolbox
- Filter / select / edit in Content Studio
- Mark as Ready, edit item-sets, change dates, unset selectors

**`<project>` (e.g. AS):**

- Start booking from a tour page
- Check if a tour is bookable
- Select date range / single date on calendar
- Open experience, hotel, save-details, payment-info modals
- Navigate booking steps and fill required fields

## Anti-patterns

- Pasting Jira acceptance criteria or evidence comment text
- Listing every screenshot from one evidence run
- Tables of all emails, bookings, or CMS nodes from a single test session
- Task-specific file names like `How-to-test-AS-1173-only.md` unless the flow is genuinely unique — prefer generic flow names and link task-specific notes in **Pitfalls** or **Related**
