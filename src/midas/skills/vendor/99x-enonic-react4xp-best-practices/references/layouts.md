# Layouts

Create and update layouts.

Reference: https://developer.enonic.com/docs/xp/stable/cms/layouts

## Location and Files

**Descriptor + interfaces** (site layer):
```
site/layouts/{layout-name}/
├── {layout-name}.xml       # Descriptor
└── {layout-name}.d.ts      # TypeScript interface
```

**React4XP 6 implementation** (react4xp layer):
```
react4xp/components/layouts/{layout-name}/
├── {layout-name}.tsx       # React layout component
└── processor.ts             # Data processor
```

The layout name follows kebab-case (e.g., `article`, `two-columns`).

## Registration

**`react4xp/dataFetcher.ts`:**
```typescript
import { myLayoutProcessor } from './components/layouts/my-layout/processor';
dataFetcher.addLayout(`${app.name}:my-layout`, { processor: myLayoutProcessor });
```

**`react4xp/componentRegistry.tsx`:**
```typescript
import { MyLayout } from './components/layouts/my-layout/my-layout';
componentRegistry.addLayout('io.99x.{PROJECT_SHORT_NAME}:my-layout', { View: MyLayout });
```

## Descriptor Structure (.xml)

```xml
<layout>
    <display-name i18n="layout.layout-name.display_name">Layout Display Name</display-name>
    <description>layout-name</description>
    <form>
        <!-- Optional config fields. See descriptor-structure.md -->
    </form>
    <regions>
        <region name="region-name" />
    </regions>
</layout>
```

- Add `<regions>` **only when explicitly described** in the task or spec.
- Use `<form />` (self-closing) if no configuration fields are needed.
- Field `name` attributes must use **camelCase**.

## Interface Structure (.d.ts)

Layouts use a single `{PascalName}LayoutProps` interface for the React component props. Unlike parts, there is **no** separate `LayoutData` interface.

```typescript
import type { ExtendedRichTextData } from '@enonic/react-components';

export interface LayoutNameLayoutProps {
    title: string;
    intro: ExtendedRichTextData;
    image?: string;
    text: ExtendedRichTextData;
}
```

- `HtmlArea` and `TextArea` fields are typed as `ExtendedRichTextData` (after `processHtml`).
- `ImageSelector` fields are typed as `string` (the URL after `myImageUrl(...).link`).

## Processor Structure (processor.ts)

Layout processors typically read from the **current content's data** (via `getContent()`), not from the layout's own config. This is because layouts usually render content type fields.

```typescript
import { LayoutComponent, Content, Component } from '@enonic-types/core';
import { getContent } from '/lib/xp/portal';
import type { ComponentProcessor, DataFetcher } from '@enonic-types/lib-react4xp/DataFetcher';
import { myImageUrl, processTextArea } from '/lib/99x/extension/portal';
import { processHtml } from '/lib/enonic/react4xp';

export const layoutNameLayoutProcessor: ComponentProcessor<'io.99x.dfs:layout-name'> = ({ component, dataFetcher }) => {
    const { regions } = component as LayoutComponent;
    const content = getContent();

    return {
        regions,
        componentProps: getComponentProps(content, component, dataFetcher),
    };
};

function getComponentProps(content: Content, component: Component, dataFetcher: DataFetcher) {
    return {
        title: content.data.title,
        intro: processHtml({
            value: processTextArea(content.data.intro as string),
            component,
            dataFetcher,
        }),
        image: (content.data.image && myImageUrl(content.data.image as string, 'width(800)'))?.link,
    };
}
```

- Always return `{ regions, componentProps: {...} }` — both are required.
- Read content data from `getContent().data`, not from `component.config`.
- If the layout has its own form config, read from `(component as LayoutComponent).config` instead.

See [fields-processing.md](./fields-processing.md) for all available processing functions.

## React Component Structure (.tsx)

```typescript
import { Region, RichText } from '@enonic/react-components';
import type { ComponentProps, LayoutData } from '@enonic/react-components';
import type { LayoutNameLayoutProps } from '/site/layouts/layout-name/layout-name.d';

export const LayoutName = ({ component, meta, data, common }: ComponentProps<LayoutData>) => {
    const props = data.componentProps as LayoutNameLayoutProps;

    console.log(props);
    return <>
        <h1>{props.title}</h1>
        <RichText
            data={props.intro}
            component={component}
            meta={meta}
            common={common}
            loading="lazy"
        />
        <div>
            <Region data={component.regions.bottom.components} meta={meta} name="bottom" />
        </div>
    </>;
};
```

- Use `<Region data={component.regions.{name}.components} meta={meta} name="{name}" />` for each region defined in the XML.
- Use `<RichText>` for any `ExtendedRichTextData` field.

## Example

**`article.xml`**
```xml
<layout>
    <display-name i18n="layout.article.display_name">Article</display-name>
    <description>article</description>
    <form />
    <regions>
        <region name="bottom" />
    </regions>
</layout>
```

**`article.d.ts`**
```typescript
import type { ExtendedRichTextData } from '@enonic/react-components';

export interface ArticleLayoutProps {
    title: string;
    intro: ExtendedRichTextData;
    image: string;
    text: ExtendedRichTextData;
}
```

**`processor.ts`**
```typescript
import { LayoutComponent, Content, Component } from '@enonic-types/core';
import { getContent } from '/lib/xp/portal';
import type { ComponentProcessor, DataFetcher } from '@enonic-types/lib-react4xp/DataFetcher';
import { processTextArea, myImageUrl } from '/lib/99x/extension/portal';
import { processHtml } from '/lib/enonic/react4xp';

export const articleLayoutProcessor: ComponentProcessor<'io.99x.dfs:article'> = ({ component, dataFetcher }) => {
    const { regions } = component as LayoutComponent;
    const content = getContent();

    return {
        regions,
        componentProps: getComponentProps(content, component, dataFetcher),
    };
};

function getComponentProps(content: Content, component: Component, dataFetcher: DataFetcher) {
    return {
        title: content.data.title,
        intro: processHtml({
            value: processTextArea(content.data.intro as string),
            component,
            dataFetcher,
        }),
        image: (content.data.image && myImageUrl(content.data.image as string, 'width(500)'))?.link,
        text: processHtml({
            value: content.data.text as string,
            component,
            dataFetcher,
        }),
    };
}
```

**`article.tsx`**
```typescript
import { Region, RichText } from '@enonic/react-components';
import type { ComponentProps, LayoutData } from '@enonic/react-components';
import type { ArticleLayoutProps } from '/site/layouts/article/article.d';

export const ArticleLayout = ({ component, meta, data, common }: ComponentProps<LayoutData>) => {
    const props = data.componentProps as ArticleLayoutProps;

    return <>
        <h1>{props.title}</h1>
        <RichText data={props.intro} component={component} meta={meta} common={common} loading="lazy" />
        {props.image && <img src={props.image} />}
        <RichText data={props.text} component={component} meta={meta} common={common} />
        <div>
            <Region data={component.regions.bottom.components} meta={meta} name="bottom" />
        </div>
    </>;
};
```

## i18n Keys

See [i18n.md](./i18n.md) for the full key pattern. Layout keys follow:

```
layout.{name}.display_name
layout.{name}.{field_name}
```
