# Reference: New Component — Spec Writing Guide

Use this file when the task type is **New Component**.
It defines how to fill the `Suggested Technical Approach`, `Implementation Steps`,
and `Definition of Done` sections of the generated spec document.

---

## Identifying the component

Parse the component type and name from the issue title. Expected pattern:

```
[...] (Backend|Frontend|Fullstack) <ComponentType>: <ComponentName>
```

Examples:
- `(Backend) Part: Info Card` → type=`part`, name=`info-card`
- `(Fullstack) Layout: Article` → type=`layout`, name=`article`
- `(Backend) Content Type: Product` → type=`content-type`, name=`product`
- `(Backend) Macro: Image` → type=`macro`, name=`image`

Component names must be **kebab-case**. Directory name and file name must match exactly.
If the title does not follow this pattern, infer type and name from the description.

---

## File structure by component type

### Part

```
site/parts/{name}/
├── {name}.xml           # Descriptor
└── {name}.d.ts          # TypeScript interfaces: {PascalName}PartData + {PascalName}PartProps

react4xp/components/parts/{name}/
├── {name}.tsx           # React component
└── processor.ts         # Data processor — reads component.config, returns { componentProps }
```

Registration (both files required):
- `react4xp/dataFetcher.ts` → `dataFetcher.addPart(\`${app.name}:{name}\`, { processor })`
- `react4xp/componentRegistry.tsx` → `componentRegistry.addPart('io.99x.{PROJECT}:{name}', { View })`

### Layout

```
site/layouts/{name}/
├── {name}.xml           # Descriptor (includes <regions> block)
└── {name}.d.ts          # TypeScript interface: {PascalName}LayoutProps only (no LayoutData)

react4xp/components/layouts/{name}/
├── {name}.tsx           # React component (uses <Region> for each region)
└── processor.ts         # Reads getContent().data, returns { regions, componentProps }
```

Registration:
- `react4xp/dataFetcher.ts` → `dataFetcher.addLayout(...)`
- `react4xp/componentRegistry.tsx` → `componentRegistry.addLayout(...)`

### Content Type

```
site/content-types/{name}/
├── {name}.xml           # Descriptor
└── {name}.d.ts          # TypeScript interface: {PascalName}Data
```

No React component or processor — content types define the data schema only.

### Macro

```
site/macros/{name}/
├── {name}.xml           # Descriptor (no HtmlArea or item-set — not allowed in macro forms)
└── {name}.d.ts          # TypeScript interface: {PascalName}MacroProps

react4xp/components/macros/{name}/
├── {name}.tsx           # React component
└── processor.ts         # Returns props directly (no componentProps wrapper)
```

Registration:
- `react4xp/dataFetcher.ts` → `dataFetcher.addMacro(...)`
- `react4xp/componentRegistry.tsx` → `componentRegistry.addMacro(...)`

---

## Parsing the schema from the spec

Look for a field table in the issue description:

| Field name | Input type | Config |
|---|---|---|
| title | TextLine | required |
| image | ImageSelector | optional |
| intro | TextArea | optional |

Map each row to the correct Enonic input type in the XML descriptor.
All `name` attributes in the XML must use **snake_case** (e.g. `cta_text`, `hero_image`).

If no field table exists, infer the minimum viable set from the title and acceptance
criteria, and list every assumption explicitly in the spec for dev review.

**TypeScript type mapping:**
- `TextLine`, `TextArea`, `HtmlArea` → `string` in `*Data`; `HtmlArea`/`TextArea` → `ExtendedRichTextData` in `*Props` after `processHtml`
- `ImageSelector` → `string` in both (raw ID in `*Data`, URL after `myImageUrl(...).link` in `*Props`)
- `CheckBox` → `boolean`
- `Long`, `Double` → `number`
- `ContentSelector` (multiple) → `string[]`

---

## i18n

All `<label>`, `<display-name>`, and `<help-text>` elements in XML must have `i18n` attributes.
The `<description>` tag must NOT have `i18n` — it contains only the kebab-case component name.

Key patterns by type:

| Type | Key pattern |
|---|---|
| Part | `part.{name}.display_name` / `part.{name}.{field_name}` / `part.{name}.{field_name}.help_text` |
| Layout | `layout.{name}.display_name` / `layout.{name}.{field_name}` |
| Content Type | `content-type.{name}.display_name` / `content-type.{name}.input.{field_name}` |
| Macro | `macro.{name}.display_name` / `macro.{name}.{field_name}` |

**Both files must always be updated:**
- `i18n/phrases.properties` — English (default/fallback)
- `i18n/phrases_no.properties` — Norwegian

Every key added to one file must be added to the other. Never overwrite or delete existing keys.

---

## Suggested Technical Approach — content to generate

Write the following in the `Suggested Technical Approach` section:

- **Component type and name**: resolved type and kebab-case name
- **Files to create** with exact paths (see structure above for the component type)
- **Schema fields table**: field name (snake_case), Enonic input type, required/optional, TypeScript type in `*Data` and `*Props`
- **Processor strategy**:
  - Part: reads `component.config`, returns `{ componentProps }`
  - Layout: reads `getContent().data`, returns `{ regions, componentProps }`
  - Macro: returns props object directly
- **Registration**: both `dataFetcher.ts` and `componentRegistry.tsx` must be updated
- **i18n keys to add**: list all new keys with their English and Norwegian values (infer Norwegian from context, flag as "translation needed" if uncertain)
- **Assumptions**: list any field, behaviour, or schema detail inferred from incomplete spec

---

## Implementation Steps — content to generate

Write concrete, ordered steps referencing FR numbers:

1. Create `site/{type}/{name}/{name}.xml` — descriptor with all fields from the schema; all labels use `i18n` keys; `<description>` contains kebab-case name as plain text
2. Create `site/{type}/{name}/{name}.d.ts` — `{PascalName}PartData` with raw field types; `{PascalName}PartProps` with processed types (`ExtendedRichTextData` for HtmlArea/TextArea, URL string for images)
3. Create `react4xp/components/{type}/{name}/processor.ts` — reads config/content, processes fields with `processHtml` / `processTextArea` / `myImageUrl`, returns `{ componentProps }` (add `regions` for layouts)
4. Create `react4xp/components/{type}/{name}/{name}.tsx` — destructures `{ component, meta, data, common }` from `ComponentProps<LayoutData>`; casts `data.componentProps as {PascalName}PartProps`; uses `<RichText>` for `ExtendedRichTextData` fields; uses `<Region>` for layout regions
5. Register in `react4xp/dataFetcher.ts` — `dataFetcher.add{Type}(\`${app.name}:{name}\`, { processor: {name}Processor })`
6. Register in `react4xp/componentRegistry.tsx` — `componentRegistry.add{Type}('io.99x.{PROJECT}:{name}', { View: {PascalName} })`
7. Add i18n keys to `i18n/phrases.properties` (English) and `i18n/phrases_no.properties` (Norwegian) — group with one blank line separator, no duplicate keys

---

## Definition of Done checklist to include

- [ ] Descriptor XML created with all fields; all labels have `i18n` attributes; `<description>` is plain kebab-case name
- [ ] `{name}.d.ts` has both `*Data` (raw) and `*Props` (processed) interfaces — no `any`
- [ ] Processor reads from the correct source (`component.config` for parts, `getContent().data` for layouts)
- [ ] HtmlArea/TextArea fields processed with `processHtml` / `processTextArea`; images resolved with `myImageUrl(...).link`
- [ ] React component uses `<RichText>` for `ExtendedRichTextData` fields
- [ ] Registered in both `dataFetcher.ts` and `componentRegistry.tsx`
- [ ] i18n keys added to both `phrases.properties` and `phrases_no.properties`
- [ ] All field assumptions documented and flagged for dev review
