# Parts

Create and update parts.

Reference: https://developer.enonic.com/docs/xp/stable/cms/parts

## Location and Files

**Descriptor + interfaces** (site layer):
```
site/parts/{part-name}/
├── {part-name}.xml       # Descriptor
└── {part-name}.d.ts      # TypeScript interfaces
```

**React4XP 6 implementation** (react4xp layer):
```
react4xp/components/parts/{part-name}/
├── {part-name}.tsx       # React component
└── processor.ts          # Data processor
```

The part name follows kebab-case (e.g., `info-card`, `hero`).

## Registration

After creating the files, register the component in both central files.

**`react4xp/dataFetcher.ts`:**
```typescript
import { myPartProcessor } from './components/parts/my-part/processor';
dataFetcher.addPart(`${app.name}:my-part`, { processor: myPartProcessor });
```

**`react4xp/componentRegistry.tsx`:**
```typescript
import { MyPart } from './components/parts/my-part/my-part';
componentRegistry.addPart('io.99x.{PROJECT_SHORT_NAME}:my-part', { View: MyPart });
```

## Descriptor Structure (.xml)

```xml
<part>
    <display-name i18n="part.part-name.display_name">Part Display Name</display-name>
    <description>part-name</description>
    <form>
        <!-- See descriptor-structure.md -->
    </form>
</part>
```

- Use `<form />` (self-closing) when no configuration fields are needed.
- Parts are leaf-nodes: they do **not** support `<regions>`.
- Field `name` attributes must use **snake_case** (e.g. `cta_text`).

## Interface Structure (.d.ts)

Parts require two interfaces:

- `{PascalName}PartData` — raw field values as stored by Enonic (matching XML `name` attributes).
- `{PascalName}PartProps` — processed props the React component receives.

```typescript
import type { ExtendedRichTextData } from '@enonic/react-components';

export interface PartNamePartData {
    title?: string;
    intro?: string;
    image?: string;
}

export interface PartNamePartProps {
    title?: string;
    intro?: ExtendedRichTextData;
    image?: string;
}
```

- Fields with `minimum="0"` in the XML are optional (`?`) in `*Data`.
- `HtmlArea` and `TextArea` fields are typed as `string` in `*Data` and `ExtendedRichTextData` in `*Props` (after `processHtml`).

## Processor Structure (processor.ts)

```typescript
import { Component, NestedRecord, PartComponent } from '@enonic-types/core';
import type { ComponentProcessor, DataFetcher } from '@enonic-types/lib-react4xp/DataFetcher';
import { processTextArea, myImageUrl } from '/lib/99x/extension/portal';
import { processHtml } from '/lib/enonic/react4xp';

export const partNamePartProcessor: ComponentProcessor<'io.99x.dfs:part-name'> = ({ component, dataFetcher }) => {
    const { config } = component as PartComponent;
    return {
        componentProps: getComponentProps(config, component, dataFetcher),
    };
};

function getComponentProps(config: NestedRecord, component: Component, dataFetcher: DataFetcher) {
    return {
        title: config.title,
        intro: config.intro
            ? processHtml({
                value: processTextArea(config.intro as string),
                component,
                dataFetcher,
            })
            : undefined,
        image: (config.image && myImageUrl(config.image as string, 'width(800)'))?.link,
    };
}
```

- Parts read data from `component.config` (the part's own form config).
- Always return `{ componentProps: {...} }`.
- Use `processHtml` from `/lib/enonic/react4xp` for both `HtmlArea` and `TextArea` fields.
- For `TextArea`: wrap with `processTextArea` before passing to `processHtml`.
- Use `myImageUrl` for `ImageSelector` fields — access `.link` for the URL string.

See [fields-processing.md](./fields-processing.md) for all available processing functions.

## React Component Structure (.tsx)

```typescript
import { type ComponentProps, type LayoutData, RichText } from '@enonic/react-components';
import type { PartNamePartProps } from '/site/parts/part-name/part-name.d';

export const PartName = ({ component, meta, data, common }: ComponentProps<LayoutData>) => {
    const props = data.componentProps as PartNamePartProps;

    console.log(props);
    return (
        <div>
            <h1>{props.title}</h1>
        </div>
    );
};
```

- Always destructure `{ component, meta, data, common }` from `ComponentProps<LayoutData>`.
- Cast `data.componentProps as PartNamePartProps` to get typed props.
- Use `<RichText data={props.field} component={component} meta={meta} common={common} />` for `ExtendedRichTextData` fields.

## Example

**`info-card.xml`**
```xml
<part>
    <display-name i18n="part.info-card.display_name">Info Card</display-name>
    <description>info-card</description>
    <form>
        <input type="TextLine" name="title">
            <label i18n="part.info-card.title">Title</label>
            <occurrences minimum="0" maximum="1" />
        </input>
        <input type="TextArea" name="intro">
            <label i18n="part.info-card.intro">Intro</label>
            <occurrences minimum="0" maximum="1" />
        </input>
    </form>
</part>
```

**`info-card.d.ts`**
```typescript
import type { ExtendedRichTextData } from '@enonic/react-components';

export interface InfoCardPartData {
    title?: string;
    intro?: string;
}

export interface InfoCardPartProps {
    title: string;
    intro: ExtendedRichTextData;
}
```

**`processor.ts`**
```typescript
import { Component, NestedRecord, PartComponent } from '@enonic-types/core';
import type { ComponentProcessor, DataFetcher } from '@enonic-types/lib-react4xp/DataFetcher';
import { processTextArea } from '/lib/99x/extension/portal';
import { processHtml } from '/lib/enonic/react4xp';

export const infoCardPartProcessor: ComponentProcessor<'io.99x.dfs:info-card'> = ({ component, dataFetcher }) => {
    const { config } = component as PartComponent;
    return {
        componentProps: getComponentProps(config, component, dataFetcher),
    };
};

function getComponentProps(config: NestedRecord, component: Component, dataFetcher: DataFetcher) {
    return {
        title: config.title,
        intro: processHtml({
            value: processTextArea(config.intro as string),
            component,
            dataFetcher,
        }),
    };
}
```

**`info-card.tsx`**
```typescript
import { type ComponentProps, type LayoutData, RichText } from '@enonic/react-components';
import type { InfoCardPartProps } from '/site/parts/info-card/info-card.d';

export const InfoCardPart = ({ component, meta, data, common }: ComponentProps<LayoutData>) => {
    const props = data.componentProps as InfoCardPartProps;

    return <>
        <h1>{props.title}</h1>
        <RichText
            data={props.intro}
            component={component}
            meta={meta}
            common={common}
            loading="lazy"
        />
    </>;
};
```

## i18n Keys

See [i18n.md](./i18n.md) for the full key pattern. Part keys follow:

```
part.{name}.display_name
part.{name}.{field_name}
part.{name}.{field_name}.help-text
```
