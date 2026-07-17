# Content Types

Create and update content types.

Reference: https://developer.enonic.com/docs/xp/stable/cms/content-types

## Location and Files

The files need to be placed on `/xp/src/main/resources/site/content-types/{content-type-name}`.
The content type name need to follow the pattern kebab-case. For example, when you create the content type `Info Box`, the name will be `info-box`.

For each content type, you need to generate these files:
- `{content-type-name}.xml`: This file will contain the complete descriptor of content type, following the rules from this doc.
- `{content-type-name}.d.ts`: This file will contain an interface describing all fields from content type.

### Descriptor Structure (.xml)

The descriptor file (.xml) need to be created following these rules:

- The file will follow this example:

```
<content-type>
    <display-name i18n="content-type.content-type-name.display-name">contnt-type-display-name</display-name>
    <display-name-expression>${content-type-title-field}</display-name-expression>
    <description>content-type-name</description>
    <super-type>base:structured</super-type>
    <form>
        <!-- See these docs on ./descriptor-structure.md -->
    </form>
</content-type>
```

- All label fields needs to be translated in i18n files. Check details about this on [i18n.md](./references/i18n.md)

### Interface Structure (.d.ts)

The interface file (.d.ts) need to be created following these rules:

```
export interface ContentTypeNameData {
    formField1: type;
    formField2: type;
    // ...
}
```
