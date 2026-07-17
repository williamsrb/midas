# Descriptor Structure

Form field types and structure for Enonic XP schema descriptors (.xml files).

Reference: https://developer.enonic.com/docs/xp/stable/cms/schemas/input-types

## Universal Input Wrapper

All input types share this structure:

```xml
<input type="InputTypeName" name="fieldname">
    <label i18n="component.name.fieldname">Display Label</label>
    <help-text i18n="component.name.fieldname.help-text">Optional help text</help-text>
    <occurrences minimum="0" maximum="1"/>
    <default>optional default value</default>
    <config>
        <!-- type-specific config -->
    </config>
</input>
```

- `maximum="0"` means unlimited occurrences.
- All `label` and `help-text` elements must use `i18n` attributes. See [i18n.md](./i18n.md).
- All `name` attributes must use `snake_case` (e.g., `first_name`, `cta_text`).

---

## Input Types

### TextLine
Single-line text input.

```xml
<input type="TextLine" name="title">
    <label i18n="component.name.title">Title</label>
    <occurrences minimum="1" maximum="1"/>
    <config>
        <max-length>256</max-length>
        <show-counter>true</show-counter>
        <regexp>^[A-Za-z]+$</regexp>
    </config>
</input>
```

TypeScript type: `string`

### TextArea
Multi-line plain text input.

```xml
<input type="TextArea" name="description">
    <label i18n="component.name.description">Description</label>
    <occurrences minimum="0" maximum="1"/>
    <config>
        <max-length>2000</max-length>
        <show-counter>true</show-counter>
    </config>
</input>
```

TypeScript type: `string`

### HtmlArea
Rich text editor. **Not allowed in macro config forms.**

```xml
<input type="HtmlArea" name="text">
    <label i18n="component.name.text">Text</label>
    <occurrences minimum="0" maximum="1"/>
    <config>
        <include>Bold | Italic | Underline | Subscript | Superscript | Undo | Redo</include>
    </config>
</input>
```

- `exclude`: space-separated tool names to remove, or `*` for all.
- `include`: space-separated tool names to add; `|` creates a separator.
- `allowHeadings`: space-separated subset of `h1`–`h6`; default is all.

TypeScript type: `string` (raw HTML) in `*Data` interfaces; `ExtendedRichTextData` from `@enonic/react-components` in `*Props` interfaces.

### Long
Integer number input.

```xml
<input type="Long" name="count">
    <label i18n="component.name.count">Count</label>
    <occurrences minimum="1" maximum="1"/>
    <config>
        <min>0</min>
        <max>100</max>
    </config>
</input>
```

TypeScript type: `number`

### Double
Decimal number input.

```xml
<input type="Double" name="price">
    <label i18n="component.name.price">Price</label>
    <occurrences minimum="0" maximum="1"/>
    <config>
        <min>0</min>
        <max>9999.99</max>
    </config>
</input>
```

TypeScript type: `number`

### CheckBox
Boolean checkbox.

```xml
<input type="CheckBox" name="featured">
    <label i18n="component.name.featured">Featured</label>
    <config>
        <alignment>left</alignment>
    </config>
</input>
```

- `alignment`: `left` | `right` | `top` | `bottom`. Default: `left`.
- Do not set `<occurrences>` — it's always `minimum="0" maximum="1"`.

TypeScript type: `boolean`

### RadioButton
Single-select from a fixed list.

```xml
<input type="RadioButton" name="status">
    <label i18n="component.name.status">Status</label>
    <occurrences minimum="1" maximum="1"/>
    <config>
        <option value="draft" i18n="component.name.status.draft">Draft</option>
        <option value="published" i18n="component.name.status.published">Published</option>
    </config>
    <default>draft</default>
</input>
```

TypeScript type: `string` (use a union type when values are known, e.g. `'draft' | 'published'`)

### ComboBox
Dropdown, supports multiple selections.

```xml
<input type="ComboBox" name="category">
    <label i18n="component.name.category">Category</label>
    <occurrences minimum="1" maximum="1"/>
    <config>
        <option value="news">News</option>
        <option value="blog">Blog</option>
        <option value="event">Event</option>
    </config>
    <default>news</default>
</input>
```

TypeScript type: `string` (single) or `string[]` (multiple)

### Tag
Free-text tags with autocomplete.

```xml
<input type="Tag" name="tags">
    <label i18n="component.name.tags">Tags</label>
    <occurrences minimum="0" maximum="0"/>
</input>
```

TypeScript type: `string[]`

### Date
Date picker.

```xml
<input type="Date" name="publishDate">
    <label i18n="component.name.publishDate">Publish Date</label>
    <occurrences minimum="0" maximum="1"/>
    <default>now</default>
</input>
```

- Default: ISO format `yyyy-MM-dd`, or relative (`now`, `+1year -12days`).

TypeScript type: `string`

### DateTime
Date + time picker.

```xml
<input type="DateTime" name="eventTime">
    <label i18n="component.name.eventTime">Event Time</label>
    <occurrences minimum="0" maximum="1"/>
    <config>
        <timezone>true</timezone>
    </config>
</input>
```

TypeScript type: `string`

### Time
Time picker.

```xml
<input type="Time" name="startTime">
    <label i18n="component.name.startTime">Start Time</label>
    <occurrences minimum="0" maximum="1"/>
    <default>09:00</default>
</input>
```

TypeScript type: `string`

### GeoPoint
Geographic coordinate picker.

```xml
<input type="GeoPoint" name="location">
    <label i18n="component.name.location">Location</label>
    <occurrences minimum="0" maximum="1"/>
</input>
```

TypeScript type: `string` (stored as `"lat,lon"`)

### ContentSelector
Reference to any content node.

```xml
<input type="ContentSelector" name="relatedArticles">
    <label i18n="component.name.relatedArticles">Related Articles</label>
    <occurrences minimum="0" maximum="0"/>
    <config>
        <allowContentType>${app}:article</allowContentType>
        <allowPath>${site}/*</allowPath>
        <treeMode>false</treeMode>
    </config>
</input>
```

TypeScript type: `string` (single) or `string[]` (multiple)

### ImageSelector
Reference to an image (`media:image`).

```xml
<input type="ImageSelector" name="image">
    <label i18n="component.name.image">Image</label>
    <occurrences minimum="0" maximum="1"/>
    <config>
        <allowPath>*</allowPath>
        <treeMode>false</treeMode>
    </config>
</input>
```

TypeScript type: `string`

### MediaSelector
Reference to a media node.

```xml
<input type="MediaSelector" name="document">
    <label i18n="component.name.document">Document</label>
    <occurrences minimum="0" maximum="1"/>
    <config>
        <allowContentType>media:archive</allowContentType>
        <allowPath>${site}/*</allowPath>
    </config>
</input>
```

TypeScript type: `string`

### AttachmentUploader
Upload file(s) as attachments on the content node.

```xml
<input type="AttachmentUploader" name="files">
    <label i18n="component.name.files">Files</label>
    <occurrences minimum="0" maximum="0"/>
</input>
```

TypeScript type: `string[]`

---

## Grouping Elements

### field-set
Visual grouping only — does not affect data structure.

```xml
<field-set>
    <label i18n="component.name.metadata">Metadata</label>
    <items>
        <input type="Tag" name="tags">
            <label i18n="component.name.tags">Tags</label>
            <occurrences minimum="0" maximum="0"/>
        </input>
    </items>
</field-set>
```

### item-set
Repeatable group of fields. Produces object (single) or array (multiple) in stored data. **Not allowed in macro config forms.**

```xml
<item-set name="links">
    <label i18n="component.name.links">Links</label>
    <occurrences minimum="0" maximum="0"/>
    <items>
        <input type="TextLine" name="label">
            <label i18n="component.name.links.label">Label</label>
            <occurrences minimum="1" maximum="1"/>
        </input>
        <input type="TextLine" name="url">
            <label i18n="component.name.links.url">URL</label>
            <occurrences minimum="1" maximum="1"/>
        </input>
    </items>
</item-set>
```

TypeScript type:
```typescript
links?: {
    label: string;
    url: string;
}[];
```

### option-set
Conditional blocks with single-select (radio) or multi-select (checkbox) modes.

```xml
<option-set name="block">
    <label i18n="component.name.block">Block</label>
    <occurrences minimum="0" maximum="0"/>
    <options minimum="1" maximum="1">
        <option name="quote">
            <label i18n="component.name.block.quote">Quote</label>
            <items>
                <input type="TextArea" name="quote">
                    <label i18n="component.name.block.quote.text">Quote text</label>
                    <occurrences minimum="1" maximum="1"/>
                </input>
            </items>
        </option>
        <option name="image">
            <label i18n="component.name.block.image">Image</label>
            <items>
                <input type="ImageSelector" name="image">
                    <label i18n="component.name.block.image.selector">Image</label>
                    <occurrences minimum="1" maximum="1"/>
                </input>
            </items>
        </option>
    </options>
</option-set>
```

- `<options minimum="1" maximum="1">` → single-select (radio buttons).
- `<options minimum="0" maximum="0">` → multi-select (checkboxes), unlimited.

### mixin reference
Inline fields from a mixin file.

```xml
<mixin name="mixin-name"/>
```

Fields are inlined directly into the parent form's data — no nesting in output.

---

## Additional Input Types

### ContentTypeFilter
Selector for choosing a content type.

```xml
<input type="ContentTypeFilter" name="content_type_filter">
    <label i18n="component.name.content_type_filter">Content Type Filter</label>
    <occurrences minimum="0" maximum="1"/>
    <config>
        <context>true</context>
    </config>
</input>
```

TypeScript type: `string`

### CustomSelector
Selector with a customizable data source (e.g., external API or service).

```xml
<input type="CustomSelector" name="custom_selector">
    <label i18n="component.name.custom_selector">Custom Selector</label>
    <occurrences minimum="0" maximum="1"/>
    <config>
        <service>my-custom-selector</service>
        <param value="sortBy">length</param>
    </config>
</input>
```

TypeScript type: `string` (single) or `string[]` (multiple)
