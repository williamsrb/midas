# Manual Schemes Migration

Use this reference when `xp8migrator` is unavailable, when something it produced needs hand-correcting, or when reading its output to
understand what changed. The transformations below are everything the migrator does on a real XP 7 app (verified against the `app-hmdb`
sample). The migrator is the recommended path — see <https://github.com/enonic/xp8migrator> and
<https://raw.githubusercontent.com/enonic/doc-code/refs/heads/master/docs/upgrade.adoc>.

The migration consists of seven concerns, applied across every descriptor:

1. File extension `.xml` (and `.yml`) → `.yaml`
2. The `site/` directory is renamed and split into `cms/`
3. A new `kind:` field is added to every descriptor based on its location
4. Element / attribute names are renamed to camelCase YAML keys
5. Structural patterns (`<form>`, `<config>`, `<occurrences>`, `<regions>`) are reshaped
6. Special cases for `application.xml`, `site.xml`, `styles.xml`, content types, and `OptionSet`
7. Sibling files (`.js`, `.html`, `.svg`) are copied alongside the new YAML descriptors; the old location is not deleted

---

## 1. File extensions

All descriptor files under `src/main/resources/` with extension `.xml` or `.yml` are renamed to `.yaml`.

## 2. Directory tree: `site/` → `cms/`

The XP 7 `site/` tree is renamed to `cms/`, and `x-data` is renamed to `mixins`. The relocations are:

| XP 7 path                               | XP 8 path                                                   |
|-----------------------------------------|-------------------------------------------------------------|
| `site/site.xml`                         | `cms/site.yaml` (mappings only) + `cms/cms.yaml` (the rest) |
| `site/styles.xml`                       | `cms/style/style.yaml`                                      |
| `site/content-types/<name>/<name>.xml`  | `cms/content-types/<name>/<name>.yaml`                      |
| `site/pages/<name>/<name>.xml`          | `cms/pages/<name>/<name>.yaml`                              |
| `site/parts/<name>/<name>.xml`          | `cms/parts/<name>/<name>.yaml`                              |
| `site/layouts/<name>/<name>.xml`        | `cms/layouts/<name>/<name>.yaml`                            |
| `site/mixins/<name>/<name>.xml`         | `cms/mixins/<name>/<name>.yaml`                             |
| `site/macros/<name>/<name>.xml`         | `cms/macros/<name>/<name>.yaml`                             |
| `site/x-data/<name>/<name>.xml`         | `cms/mixins/<name>/<name>.yaml`                             |
| `site/form-fragments/<name>/<name>.xml` | `cms/form-fragments/<name>/<name>.yaml`                     |

Files that stay in their original location: `application.xml`, `apis/`, `services/`, `webapp/`, `admin/`, `tasks/`, `idprovider/`. They keep
their relative path; only the extension and content change.

## 3. `kind:` field

Every descriptor must declare a `kind:` at the top. The value is determined by the file's location relative to `src/main/resources/`:

| Path                                    | `kind:`            |
|-----------------------------------------|--------------------|
| `enonic.yaml`                           | `"Application"`    |
| `idprovider/idprovider.yaml`            | `"IdProvider"`     |
| `apis/<name>/<name>.yaml`               | `"API"`            |
| `services/<name>/<name>.yaml`           | `"Service"`        |
| `webapp/webapp.yaml`                    | `"WebApp"`         |
| `admin/tools/<name>/<name>.yaml`        | `"AdminTool"`      |
| `admin/extensions/<name>/<name>.yaml`   | `"AdminExtension"` |
| `tasks/<name>/<name>.yaml`              | `"Task"`           |
| `cms/cms.yaml`                          | `"CMS"`            |
| `cms/site.yaml`                         | `"Site"`           |
| `cms/style/style.yaml`                  | `"Style"`          |
| `cms/form-fragments/<name>/<name>.yaml` | `"FormFragment"`   |
| `cms/content-types/<name>/<name>.yaml`  | `"ContentType"`    |
| `cms/mixins/<name>/<name>.yaml`         | `"Mixin"`          |
| `cms/macros/<name>/<name>.yaml`         | `"Macro"`          |
| `cms/layouts/<name>/<name>.yaml`        | `"Layout"`         |
| `cms/pages/<name>/<name>.yaml`          | `"Page"`           |
| `cms/parts/<name>/<name>.yaml`          | `"Part"`           |

`kind:` is mandatory — missing it fails deployment with `Invalid kind "null". Expected "<expected>"`.

## 4. Field renames

XML elements and attributes become camelCase YAML keys:

| XP 7 (XML)                 | XP 8 (YAML)                                                           |
|----------------------------|-----------------------------------------------------------------------|
| `<display-name>`           | `title:` (most descriptors — see below for exceptions)                |
| `<description>`            | `description:`                                                        |
| `<help-text>`              | `helpText:`                                                           |
| `<super-type>`             | `superType:`                                                          |
| `<aspect-ratio>`           | `aspectRatio:`                                                        |
| `<allowContentType>`       | `allowContentType:` (always emitted as an array, even with one entry) |
| `<list-title-expression>`  | `displayNameListExpression:` (and moved out of `<config>` — see §6.4) |
| `<displayNamePlaceholder>` | `displayNamePlaceholder:` (moved out of `<config>` — see §6.4)        |
| `<displayNameExpression>`  | `displayNameExpression:` (moved out of `<config>` — see §6.4)         |

### `displayName` → `title` rename, with exceptions

For most descriptors, the top-level `<display-name>` is renamed to `title:`. **If the XML had no `<display-name>`, add one with the file's
base name** (e.g. `title: "movie"` for a content type whose file is `movie.yaml`).

**Exceptions** — these descriptors do NOT get a `title` field at the top level (and any `displayName`/`<display-name>` present is preserved
as-is):

- `enonic.yaml`
- `cms/cms.yaml`
- `cms/site.yaml`
- `idprovider/idprovider.yaml`
- `cms/style/style.yaml` (per-style `displayName:` is preserved as-is)
- `tasks/<name>/<name>.yaml`
- `webapp/webapp.yaml`

## 5. Structural patterns

### Forms

`<form/>` (empty self-closing) becomes `form: []`.

```xml

<form/>
```

↓

```yaml
form: [ ]
```

`<form>` with children becomes a list of input objects:

```xml

<form>
  <input type="TextLine" name="heading">
    <label>Override heading</label>
  </input>
</form>
```

↓

```yaml
form:
  - type: "TextLine"
    name: "heading"
    label: "Override heading"
    occurrences:
      min: 0
      max: 1
```

The `name` and `type` attributes become keys on the same object. `<label>` becomes `label:`. Note that `occurrences` is always emitted
explicitly — defaults are written out (`min: 0, max: 1`) rather than relying on implicit XP defaults.

### Occurrences

```xml

<occurrences minimum="0" maximum="1"/>
```

↓

```yaml
occurrences:
  min: 0
  max: 1
```

### `<config>` flattening

The `<config>` wrapper is removed; its children are flattened to keys on the input itself:

```xml

<input type="TextLine" name="trailer">
  <label>Youtube Trailer</label>
  <config>
    <regexp>^http(?:s?)://.*$</regexp>
  </config>
</input>
```

↓

```yaml
- type: "TextLine"
  name: "trailer"
  label: "Youtube Trailer"
  regexp: "^http(?:s?)://.*$"
```

`<config>` children that move to the input level include `regexp`, `exclude`, `include`, `allowContentType`, and ComboBox `<option>`
entries.

### `<item-set>`

The `<item-set>` element becomes an input with `type: "ItemSet"` and an `items:` array:

```xml

<item-set name="cast">
  <label>Cast</label>
  <occurrences minimum="0" maximum="0"/>
  <items>
    <input type="ContentSelector" name="actor">...</input>
  </items>
</item-set>
```

↓

```yaml
- type: "ItemSet"
  name: "cast"
  label: "Cast"
  occurrences:
    min: 0
    max: 0
  items:
    - type: "ContentSelector"
      name: "actor"
      ...
```

### Regions

```xml

<regions>
  <region name="left"/>
  <region name="right"/>
</regions>
```

↓

```yaml
regions:
  - "left"
  - "right"
```

Regions become a flat array of strings (just the names).

### ComboBox / RadioButton options

Options inside `<config>` become an `options:` array on the input:

```xml

<input type="ComboBox" name="sorting">
  <config>
    <option value="displayName ASC">Ascending</option>
    <option value="displayName DESC">Descending</option>
  </config>
  <default>displayName ASC</default>
</input>
```

↓

```yaml
- type: "ComboBox"
  name: "sorting"
  options:
    - value: "displayName ASC"
      label: "Ascending"
    - value: "displayName DESC"
      label: "Descending"
  default: "displayName ASC"
```

## 6. Special cases

### 6.1 `application.xml`

The original `<description>` is preserved verbatim. Three fields are imported from `gradle.properties`:

- `title:` ← `appDisplayName`
- `vendorName:` ← `vendorName`
- `vendorUrl:` ← `vendorUrl`

```yaml
kind: "Application"
title: "Headless Movie DB"           # from gradle.properties appDisplayName
description: "Sample application demonstrating XP's headless API"
vendorName: "Enonic"                 # from gradle.properties vendorName
vendorUrl: "https://enonic.com"      # from gradle.properties vendorUrl
```

`enonic.yaml` does NOT receive a `title` derived from the XML's `<display-name>` — instead, the `title:` always comes from
`appDisplayName` in `gradle.properties`.

### 6.2 `site.xml` is split between `cms/site.yaml` and `cms/cms.yaml`

The single `site/site.xml` becomes two YAML files:

- **`cms/site.yaml`** receives only the `<mappings>`:

  ```xml
  <mappings>
    <mapping controller="/controllers/info.js" order="50">
      <match>type:'portal:site'</match>
    </mapping>
  </mappings>
  ```
  ↓
  ```yaml
  kind: "Site"
  mappings:
    - controller: "/controllers/info.js"
      order: 50
      match: "type:'portal:site'"
  ```

  `<mapping controller=... order=...>` and `<match>` collapse into a single object. Order is parsed as an integer.

- **`cms/cms.yaml`** receives the `<x-data>` references (renamed to `mixins`) and the top-level `<form>`:

  ```xml
  <site>
    <x-data name="SoMe" allowContentTypes=".*:person|.*:movie"/>
    <x-data name="spotlight" allowContentTypes="media:image"/>
    <form/>
  </site>
  ```
  ↓
  ```yaml
  kind: "CMS"
  mixins:
    - name: "com.enonic.app.hmdb:SoMe"     # qualified with applicationKey
      allowContentTypes: ".*:person|.*:movie"
      optional: false
    - name: "com.enonic.app.hmdb:spotlight"
      allowContentTypes: "media:image"
      optional: false
  form: []
  ```

  Notes:
    - The `<x-data name="X">` reference is qualified to `<applicationKey>:X`.
    - `optional:` is added with default `false` when the XML didn't specify it.
    - The XML attribute `allowContentTypes` (plural) is preserved as-is (it's a regex string here, not a list).

### 6.3 `site/styles.xml`

```xml

<styles>
  <image name="editor-image-widescreen">
    <display-name i18n="imageStyles.widescreen">Widescreen (16:9)</display-name>
    <aspect-ratio>16:9</aspect-ratio>
  </image>
  <image name="editor-image-portrait">
    <display-name i18n="imageStyles.portrait">Portrait</display-name>
    <aspect-ratio>1:1</aspect-ratio>
    <filter>rounded(1000)</filter>
  </image>
</styles>
```

↓ `cms/style/style.yaml`:

```yaml
kind: "Style"
styles:
  - name: "editor-image-widescreen"
    type: "Image"
    label:
      text: "Widescreen (16:9)"
      i18n: "imageStyles.widescreen"
    aspectRatio: "16:9"
  - name: "editor-image-portrait"
    type: "Image"
    label:
      text: "Portrait"
      i18n: "imageStyles.portrait"
    aspectRatio: "1:1"
    filter: "rounded(1000)"
```

Notes on the migrator output (verified against `app-superhero-blog`):

- The XP 8 path is **`cms/style/style.yaml`** (singular folder + filename), not `cms/styles/image.yaml`. Older docs/examples (including some
  hand-crafted XP 8 apps like `tutorial-intro`) use the plural `cms/styles/image.yaml` shape — those are an older form. The migrator's
  current output is the unified `cms/style/style.yaml`.
- The repeated `<image>` elements collapse into a single `styles:` array with each entry carrying a `type:` discriminator (`"Image"`,
  etc.) — this lets the unified file hold multiple style kinds, not just images.
- `<display-name i18n="...">...</display-name>` becomes a `label: { text, i18n }` object (not a flat `displayName:` string the way other
  Style-related fields are kept). If the XML omitted `i18n=`, only `text:` is present.
- Other fields (`<aspect-ratio>`, `<filter>`, `editor.css`, etc.) are preserved as camelCase keys at the entry level.
- The migrator emits `editor.css: "Please migrate your styles from \"styles/styles.css\" manually"` as a placeholder — the actual CSS isn't
  lifted automatically.

### 6.4 Content type extra fields

For files in `cms/content-types/<name>/<name>.yaml`, three properties are moved out of `<config>` to the top level and one is renamed:

- `displayNamePlaceholder` — top level (was inside `<config>`)
- `displayNameExpression` — top level (was inside `<config>`)
- `listTitleExpression` — top level **and renamed to** `displayNameListExpression`

```xml

<content-type>
  <display-name>Article</display-name>
  <super-type>base:structured</super-type>
  <config>
    <displayNamePlaceholder>Type a title</displayNamePlaceholder>
    <listTitleExpression>title</listTitleExpression>
  </config>
</content-type>
```

↓

```yaml
kind: "ContentType"
title: "Article"
superType: "base:structured"
displayNamePlaceholder: "Type a title"
displayNameListExpression: "title"
```

### 6.5 OptionSet field renames

For any descriptor that contains an input of type `"OptionSet"`, two fields are renamed inside its options:

- `selected:` → `selection:`
- `defaultOption:` → `selected:`

(Yes, the rename chain shifts both fields one position. Apply in this order.)

## 7. Sibling files and cleanup

The migrator copies — but does not move — sibling files (`.js`, `.html`, `.svg`) next to the descriptor into the new `cms/` location. After
running with `-x`:

- `site/parts/heading/heading.xml` → deleted (descriptor migrated)
- `site/parts/heading/heading.js` → still present (leftover)
- `cms/parts/heading/heading.yaml` → new
- `cms/parts/heading/heading.js` → copy of the original

The old `site/` tree is left as a husk of orphaned `.js`, `.html`, and `.svg` files. **Manual cleanup required after the user verifies the
migration:**

```sh
rm -rf src/main/resources/site
```

Run this only after confirming the new `cms/` tree is complete and the controllers under `cms/` match what the new YAML descriptors
reference. (XP 8 looks for the controller `<name>.js` next to its `<name>.yaml`, so the JS must live in `cms/<...>/<name>.js`, not the old
`site/<...>/<name>.js`.)

## What is NOT touched

The migrator never modifies:

- `controllers/` — all controllers, HTML templates
- `i18n/` — `.properties` files
- `import/` — content data
- `assets/` — static files
- `main.js` — app lifecycle script
- `application.svg` — app icon (stays at root)
- `build.gradle`, `gradle.properties`, `gradle/wrapper/*` — build files (handled separately, see SKILL.md)
- `tsconfig.json`, `tsup.config.ts`, etc. — TypeScript / bundler config (handled separately)
- `logback.xml` — logging config (handled separately, see
  <https://raw.githubusercontent.com/enonic/doc-xp/refs/heads/8.0/docs/release/upgrade.adoc>)

## Summary checklist

When migrating by hand, work through each file in this order:

1. Inventory all `.xml` (and `.yml`) descriptors under `src/main/resources/`.
2. For each one, determine the new path (§2) and `kind:` (§3).
3. Convert XML to YAML, applying the field renames (§4) and structural patterns (§5).
4. Apply the special cases (§6) where they apply: `application.xml`, `site.xml`, `styles.xml`, content-type field moves, OptionSet renames.
5. Copy sibling `.js` / `.html` / `.svg` files into the new location.
6. After validating the output, delete the old `site/` tree (§7).
