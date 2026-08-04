# Fields Processing

Functions for processing Enonic XP field data in React4XP 6 processor files.

## Library Imports

```typescript
import { processHtml } from '/lib/enonic/react4xp';
import { myImageUrl, processHTMLField, processTextArea, getLink, myPageUrl } from '/lib/99x/extension/portal';
import { attachmentUrl } from '/lib/xp/portal';
import { get as getContent } from '/lib/xp/content';
import { forceArray } from '/lib/99x/util/collections';
```

---

## `processHtml` — Rich Text Output (React4XP 6)

**Import**: `/lib/enonic/react4xp`

The primary function for producing `ExtendedRichTextData` in React4XP 6. Use for **both** `HtmlArea` and `TextArea` fields. Takes `{ value, component, dataFetcher }`.

```typescript
// HtmlArea field
intro: processHtml({
    value: processHTMLField(config.intro as string),
    component,
    dataFetcher,
})

// TextArea field — wrap with processTextArea first
body: processHtml({
    value: processTextArea(config.body as string),
    component,
    dataFetcher,
})
```

The result is typed as `ExtendedRichTextData` from `@enonic/react-components`. Render it in TSX with `<RichText data={props.field} component={component} meta={meta} common={common} />`.

---

## `processHTMLField` — Pre-process HTML

**Import**: `/lib/99x/extension/portal`

Pre-processes raw HTML content (e.g., resolves internal Enonic links). Pass the result into `processHtml`.

```typescript
text: processHtml({
    value: processHTMLField(config.text as string),
    component,
    dataFetcher,
})
```

---

## `processTextArea` — Pre-process Plain Text

**Import**: `/lib/99x/extension/portal`

Converts newlines in plain text to `<br>` tags. Pass the result into `processHtml` for `TextArea` fields.

```typescript
intro: processHtml({
    value: processTextArea(config.intro as string),
    component,
    dataFetcher,
})
```

---

## `myImageUrl` — Image Processing

**Import**: `/lib/99x/extension/portal`

Use for any `ImageSelector` field. Returns an object with `link`, `alt`, `title`, and other metadata. Access `.link` for the URL string.

```typescript
// Single image URL
image: (config.image && myImageUrl(config.image as string, 'width(800)'))?.link

// With multiple sizes
const image = myImageUrl(config.image as string, 'block(800, 600)');
const imageMedium = myImageUrl(config.image as string, 'block(600, 450)');
const imageSmall = myImageUrl(config.image as string, 'block(400, 300)');

// In props:
image: image && {
    src: image.link,
    srcMedium: imageMedium?.link,
    srcSmall: imageSmall?.link,
    alt: image.alt
}
```

Common crop formats: `'width(1280)'`, `'width(800)'`, `'width(500)'`, `'block(800, 600)'`.

---

## `myPageUrl` — Internal Link URL

**Import**: `/lib/99x/extension/portal`

Use for `ContentSelector` fields that are used as CTA/link destinations.

```typescript
const ctaUrl = config.ctaContent
    ? myPageUrl(config.ctaContent as string)
    : (config.ctaExternalLink as string) || undefined;
```

---

## `getLink` — Link with Metadata

**Import**: `/lib/99x/extension/portal`

Use when you need full link metadata (href + target). Returns an object with `href` and `target`.

```typescript
const ctaContent = data.ctaContent && getContent({ key: data.ctaContent });
const ctaLink = getLink(data.ctaContent, data.ctaExternalLink, undefined, ctaContent);

// In props:
cta: ctaText ? {
    text: ctaText,
    url: ctaLink?.href,
    isExternal: ctaLink?.target === '_blank'
} : undefined
```

---

## `forceArray` — Array Normalization

**Import**: `/lib/99x/util/collections`

Always use when processing fields that may be arrays (`item-set`, multi-value `ContentSelector`, `Tag`). Ensures consistent array format regardless of 0, 1, or many values stored.

```typescript
// Tag or multi-value selector
tags: forceArray(config.tags)

// Item set
items: forceArray(config.items).map((item) => ({
    label: item?.label || '',
    url: item?.url || '',
}))
```

---

## `attachmentUrl` — Video/File URL

**Import**: `/lib/xp/portal`

Use for `MediaSelector` fields pointing to video or file attachments.

```typescript
const internalVideo = config.videoFile && attachmentUrl({ id: config.videoFile as string, type: 'absolute' });
```

---

## Pattern: Video Fields

When a component has video support (internal file + YouTube + Vimeo), derive type and URL as follows:

```typescript
const internalVideo = config.videoFile && attachmentUrl({ id: config.videoFile as string, type: 'absolute' });
const youtubeId = config.youtubeVideoId as string;
const vimeoId = config.vimeoVideoId as string;
const videoType = internalVideo ? 'default' : (youtubeId ? 'youtube' : (vimeoId ? 'vimeo' : undefined));
const videoUrl = internalVideo || youtubeId || vimeoId;
```
