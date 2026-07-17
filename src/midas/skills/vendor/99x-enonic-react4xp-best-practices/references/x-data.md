# X-Data

Create and update x-data schemas.

Reference: https://developer.enonic.com/docs/xp/stable/cms/x-data

## Location and Files

Files are placed at `/xp/src/main/resources/site/x-data/{x-data-name}/`.
The x-data name follows kebab-case (e.g., `social-media`, `macros`).

For each x-data, generate:
- `{x-data-name}.xml`: Descriptor following the rules below.

## Descriptor Structure (.xml)

```xml
<x-data>
    <display-name i18n="x-data.x-data-name.display_name">X-Data Display Name</display-name>
    <form>
        <!-- See descriptor-structure.md -->
    </form>
</x-data>
```

## Activating X-Data in site.xml

X-data must be activated in `site.xml`:

```xml
<!-- Apply to all content types -->
<x-data name="x-data-name"/>

<!-- Apply only to specific content types (regex) -->
<x-data name="x-data-name" allowContentTypes="^com\.example\.app:article$"/>

<!-- Make it optional (user enables per content item) -->
<x-data name="x-data-name" optional="true"/>
```

## Example

```xml
<x-data>
    <display-name i18n="x-data.macros.display_name">Macros</display-name>
    <form>
        <item-set name="images">
            <label i18n="x-data.macros.item-set.images">Images</label>
            <occurrences minimum="0" maximum="0" />
            <items>
                <input type="ImageSelector" name="image">
                    <label i18n="x-data.macros.images.image">Image</label>
                    <occurrences minimum="1" maximum="1"/>
                    <config>
                        <allowPath>*</allowPath>
                        <treeMode>false</treeMode>
                    </config>
                </input>
                <input type="TextLine" name="caption">
                    <label i18n="x-data.macros.images.caption">Caption</label>
                    <occurrences minimum="0" maximum="1" />
                </input>
            </items>
        </item-set>
    </form>
</x-data>
```

## i18n Keys

See [i18n.md](./references/i18n.md) for the full key pattern. X-data keys follow:

```
x-data.{name}.display_name
x-data.{name}.{field-name}
x-data.{name}.item-set.{item-set-name}
x-data.{name}.{item-set-name}.{field-name}
```
