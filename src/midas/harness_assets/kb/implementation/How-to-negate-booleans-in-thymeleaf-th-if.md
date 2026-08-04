# How to negate booleans in Thymeleaf `th:if`

**Scope:** `_shared`  
**Applies to:** Enonic XP Thymeleaf templates under `src/main/resources/**/*.html`  
**Related:** `~/.cursor/rules/enonic-thymeleaf-negation.mdc`, VET-1197 (duplicate external-link anchors)

## Prerequisites

- Editing a Thymeleaf fragment or part/layout view that branches on a boolean (e.g. `useTarget`, visibility flags).
- Prefer checking live HTML when two mutually exclusive branches might both render.

## Procedure

1. Never put JS-style `!` inside a **single** `${...}` compound expression.
2. Split operands into separate `${}` and use Thymeleaf `not`:

```html
<a data-th-if="${obj.url} and ${not obj.useTarget}" ...>
```

3. Or keep branches exclusive with `th:if` / `th:unless` (no compound negation):

```html
<a data-th-if="${obj.useTarget}" ...>
<a data-th-unless="${obj.useTarget}" ...>
```

4. When changing an existing `th:unless` to a compound `th:if`, re-verify with content where the negated flag is **true** (e.g. external link with `useTarget: true`).

## Forbidden

```html
<!-- BAD: ! inside one ${} does not negate reliably -->
<a data-th-if="${obj.url and !obj.useTarget}" ...>
<div data-th-if="${item.visible and !item.hidden}" ...>
```

XP Thymeleaf can treat `${a and !b}` as truthy when `a` is set, so the negation never applies. Result: both branches render (duplicate links/labels).

## Pitfalls

- Replacing a working `th:unless` with `${a and !b}` “cleanup” introduces silent duplicates.
- Only one of an external/internal link pair must render; AC for `target="_blank"` fails if the plain duplicate remains clickable.
- Safe split-`${}` examples elsewhere in vetinst: `analysis-full-view.html`, `shortcutblock.html`, `banner-medium.html`.
