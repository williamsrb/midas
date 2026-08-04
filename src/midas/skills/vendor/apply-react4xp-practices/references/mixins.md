# Mixins

Create and update mixins.

Reference: https://developer.enonic.com/docs/xp/stable/cms/mixins

## Location and Files

Files are placed at `/xp/src/main/resources/site/mixins/{mixin-name}/`.
The mixin name follows kebab-case (e.g., `seo`, `author-info`).

For each mixin, generate:
- `{mixin-name}.xml`: Descriptor following the rules below.

## Descriptor Structure (.xml)

```xml
<mixin>
    <display-name i18n="mixin.mixin-name.display-name">Mixin Display Name</display-name>
    <form>
        <!-- See descriptor-structure.md -->
    </form>
</mixin>
```

## Using a Mixin in Another Schema

Reference a mixin inside any `<form>` element:

```xml
<form>
    <input type="TextLine" name="title">
        <label i18n="component.name.title">Title</label>
        <occurrences minimum="1" maximum="1"/>
    </input>
    <mixin name="mixin-name"/>
</form>
```

Mixin fields are **inlined** directly into the parent schema's data — no extra nesting in output.

## Example

```xml
<mixin>
    <display-name i18n="mixin.seo.display-name">SEO</display-name>
    <form>
        <input type="TextLine" name="seoTitle">
            <label i18n="mixin.seo.seoTitle">SEO Title</label>
            <occurrences minimum="0" maximum="1"/>
        </input>
        <input type="TextArea" name="seoDescription">
            <label i18n="mixin.seo.seoDescription">SEO Description</label>
            <occurrences minimum="0" maximum="1"/>
        </input>
    </form>
</mixin>
```

## i18n Keys

See [i18n.md](./references/i18n.md) for the full key pattern. Mixin keys follow:

```
mixin.{name}.display-name
mixin.{name}.{field-name}
```
