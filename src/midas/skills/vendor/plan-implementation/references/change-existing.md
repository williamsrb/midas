# Reference: Existing Component Change — Spec Writing Guide

Use this file when the task type is **Existing Component Change**.
It covers both bug fixes and feature additions to components that already exist.

---

## Distinguishing bug fix from feature addition

| Signal | Type |
|---|---|
| Steps to reproduce, expected vs actual behaviour, error messages | Bug fix |
| New field, new visual state, new behaviour, enhanced logic | Feature addition |

A task may combine both. Treat them as separate implementation concerns and
write separate FR entries for each.

---

## Identifying the affected component

The spec description should name the component. Derive candidate file paths based on the component type:

**Part:**
```
site/parts/{name}/{name}.xml
site/parts/{name}/{name}.d.ts
react4xp/components/parts/{name}/{name}.tsx
react4xp/components/parts/{name}/processor.ts
```

**Layout:**
```
site/layouts/{name}/{name}.xml
site/layouts/{name}/{name}.d.ts
react4xp/components/layouts/{name}/{name}.tsx
react4xp/components/layouts/{name}/processor.ts
```

**Content Type / Mixin / X-Data:**
```
site/{type}/{name}/{name}.xml
site/{type}/{name}/{name}.d.ts
```

List the likely affected files in the `Suggested Technical Approach` with a one-line
rationale for each. Not all files necessarily need changes — only include those
actually affected by this task.

---

## What must never change

- **Existing XML field names** — renaming a `name` attribute breaks all existing content in production
- **Existing XML fields removed** — removing a field loses stored content data
- **Existing `*Data` / `*Props` interface properties removed or renamed** — breaks all callers
- **Existing i18n keys renamed or removed** — breaks translated labels across the CMS
- **Existing processor return shape narrowed** — may break React component rendering

---

## Rules for XML schema changes (feature additions)

- New fields go at the **end** of the `<form>` block, before the closing `</form>` tag
- New optional fields must have `<occurrences minimum="0" />`
- New field `name` attributes must use **snake_case**
- All new `<label>`, `<display-name>`, and `<help-text>` elements must have `i18n` attributes
- The `<description>` tag must NOT have `i18n` — plain kebab-case component name only

---

## Rules for TypeScript interface changes

- **`*Data` interface**: add new optional properties (`?`) for new optional XML fields; required fields for required XML fields
- **`*Props` interface**: add processed types — `ExtendedRichTextData` for HtmlArea/TextArea (after `processHtml`), URL `string` for images (after `myImageUrl(...).link`)
- Never remove or rename existing properties — extend only
- Parts have both `{PascalName}PartData` and `{PascalName}PartProps`; layouts have only `{PascalName}LayoutProps`

---

## Rules for processor changes

- Read from the correct source: `component.config` for parts; `getContent().data` for layouts
- Add new field mappings **after** existing ones in `getComponentProps`
- Use `processHtml` + `processTextArea` for TextArea/HtmlArea; use `myImageUrl(...).link` for images
- Processor must always return `{ componentProps }` for parts; `{ regions, componentProps }` for layouts
- Do not change existing property names in the return object

---

## Rules for React component changes

- `data.componentProps` is cast to the `*Props` interface — the cast must remain valid after any interface change
- Use `<RichText>` for any `ExtendedRichTextData` field
- Use `<Region>` for layout regions defined in the XML
- New rendering must handle `undefined` props gracefully (optional fields may not be set)

---

## i18n rules

- New fields require new keys in **both** `i18n/phrases.properties` (English) and `i18n/phrases_no.properties` (Norwegian)
- Key patterns:
  - Part: `part.{name}.{field_name}` / `part.{name}.{field_name}.help_text`
  - Layout: `layout.{name}.{field_name}`
  - Content Type: `content-type.{name}.input.{field_name}`
- Never overwrite or delete existing keys
- Group new keys with existing ones for the same component; separate groups with one blank line

---

## Suggested Technical Approach — content to generate

Write the following in the `Suggested Technical Approach` section:

**For bug fixes:**
- **Root cause hypothesis**: which layer is responsible — XML schema misconfiguration, incorrect processor mapping, wrong field processing, React rendering issue
- **Affected files**: list files with one-line rationale each
- **Minimal change principle**: the fix must touch only what is strictly necessary — no refactoring of unrelated code
- **Similar pattern check**: the implementer should search for the same bug pattern in other components and list findings without auto-fixing

**For feature additions:**
- **Affected files**: list all files that need changes with one-line rationale each
- **Schema delta**: describe new XML fields to add (name, input type, required/optional)
- **Interface delta**: describe new `*Data` / `*Props` properties to add
- **Processor delta**: describe new field mappings to add in `getComponentProps`
- **React delta**: describe new rendering logic or props to use in the component
- **i18n delta**: list new keys needed in both property files

**Shared:**
- **Guillotine/headless impact**: if the processor return shape changes, flag it — downstream API consumers may be affected
- **Registration check**: verify the component is already registered in both `dataFetcher.ts` and `componentRegistry.tsx`; include a note if registration needs updating

---

## Implementation Steps — content to generate

**Bug fix:**

1. Read all affected files to trace the full data flow (XML → `{name}.d.ts` → `processor.ts` → `{name}.tsx`)
2. Identify the exact line(s) causing the bug — document the root cause as a comment before changing anything (reference FR-N)
3. Apply the minimal fix
4. Search for the same pattern in other components — list findings in the spec, do not fix automatically

**Feature addition:**

1. Read all existing component files to understand the current data flow
2. Add new field(s) to `site/{type}/{name}/{name}.xml` — append at end of `<form>`, use `snake_case` names, add `i18n` labels (reference FR-N)
3. Extend `site/{type}/{name}/{name}.d.ts` — add new properties to `*Data` (raw types) and `*Props` (processed types)
4. Extend `react4xp/components/{type}/{name}/processor.ts` — add new field mappings in `getComponentProps` using appropriate processing functions
5. Extend `react4xp/components/{type}/{name}/{name}.tsx` — add rendering for new props; use `<RichText>` for `ExtendedRichTextData`; guard optional fields with conditional rendering
6. Add new i18n keys to `i18n/phrases.properties` (English) and `i18n/phrases_no.properties` (Norwegian)

---

## Definition of Done checklist to include

- [ ] All affected files read before any change was made
- [ ] Root cause documented in the spec (bug fix) or insertion points identified (feature)
- [ ] No existing XML field names removed or renamed
- [ ] New XML fields appended at end of `<form>` with `snake_case` names and `i18n` labels
- [ ] `*Data` / `*Props` interfaces extended — no existing properties removed or renamed
- [ ] Processor mappings added without changing existing return property names
- [ ] React component handles `undefined` for all new optional props
- [ ] i18n keys added to both `phrases.properties` and `phrases_no.properties`
- [ ] Guillotine/headless impact assessed and flagged if applicable
- [ ] No new dependencies introduced without dev approval
