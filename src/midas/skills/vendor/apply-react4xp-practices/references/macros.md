# Macros

Create and update macros.

Reference: https://developer.enonic.com/docs/xp/stable/cms/macros

## Location and Files

**Descriptor + interfaces** (site layer):
```
site/macros/{macro-name}/
├── {macro-name}.xml       # Descriptor
└── {macro-name}.d.ts      # TypeScript interface
```

**React4XP 6 implementation** (react4xp layer):
```
react4xp/components/macros/{macro-name}/
├── {macro-name}.tsx       # React macro component
└── processor.ts            # Data processor
```

The macro name follows kebab-case (e.g., `image`, `video-embed`).

## Registration

**`react4xp/dataFetcher.ts`:**
```typescript
import { myMacroProcessor } from './components/macros/my-macro/processor';
dataFetcher.addMacro('my-macro', { processor: myMacroProcessor });
```

**`react4xp/componentRegistry.tsx`:**
```typescript
import { MyMacro } from './components/macros/my-macro/my-macro';
componentRegistry.addMacro('my-macro', { View: MyMacro });
```

Note: macros use just the name (no `app.name:` prefix).

## Descriptor Structure (.xml)

```xml
<macro>
    <display-name i18n="macro.macro-name.display-name">Macro Display Name</display-name>
    <description>macro-name</description>
    <form>
        <!-- See descriptor-structure.md -->
        <!-- NOTE: item-set and HtmlArea are NOT allowed here -->
    </form>
</macro>
```

**Constraints:**
- `item-set` elements are **not allowed** in macro config forms.
- `HtmlArea` input type is **not allowed** in macro config forms.

## Interface Structure (.d.ts)

Macros use a single `{PascalName}MacroProps` interface:

```typescript
export interface MacroNameMacroProps {
    field1: string;
    field2: string;
}
```

## Processor Structure (processor.ts)

Macro processors use `MacroProcessorParams` and return props directly (no `componentProps` wrapper).

```typescript
import { Content, NestedRecord } from '@enonic-types/core';
import type { ComponentProcessor, MacroProcessorParams } from '@enonic-types/lib-react4xp/DataFetcher';
import { myImageUrl } from '/lib/99x/extension/portal';
import { getContent } from '/lib/xp/portal';
import { forceArray } from '/lib/99x/util/collections';

export const macroNameMacroProcessor: ComponentProcessor<'io.99x.dfs:macro-name', MacroProcessorParams> = (params) => {
    const { config } = params.macro;
    const content = getContent();

    return {
        // Return props directly — no componentProps wrapper
        field1: config?.field1,
        field2: config?.field2,
    };
};
```

- Macro config fields are accessed via `params.macro.config`.
- Return props **directly** at the top level — no `componentProps` wrapper.
- Macros often access x-data from the current content via `getContent()`.

## React Component Structure (.tsx)

```typescript
import { MacroComponentParams } from '@enonic/react-components';
import React from 'react';
import type { MacroNameMacroProps } from '/site/macros/macro-name/macro-name.d';

export const MacroName = ({ data, children }: MacroComponentParams) => {
    const props = data as unknown as MacroNameMacroProps;

    console.log(props);
    return (
        <div>
            <h1>Macro Name</h1>
        </div>
    );
};
```

- Import `MacroComponentParams` from `@enonic/react-components`.
- Cast `data as unknown as MacroNameMacroProps` to get typed props.
- `children` contains the macro's body text (if any).

## Example

**`image.xml`**
```xml
<macro>
    <display-name i18n="macro.image.display-name">Image</display-name>
    <description>image</description>
    <form>
        <input type="TextLine" name="index">
            <label i18n="macro.image.index">Index</label>
            <occurrences minimum="1" maximum="0" />
            <default>1</default>
        </input>
    </form>
</macro>
```

**`image.d.ts`**
```typescript
export interface ImageMacroProps {
    images: {
        image: string;
        caption: string;
    }[];
}
```

**`processor.ts`**
```typescript
import { Content, NestedRecord } from '@enonic-types/core';
import type { ComponentProcessor, MacroProcessorParams } from '@enonic-types/lib-react4xp/DataFetcher';
import { myImageUrl } from '/lib/99x/extension/portal';
import { getContent } from '/lib/xp/portal';
import { forceArray, getItemsByIndexes } from '/lib/99x/util/collections';
import { getXDataName } from '/lib/99x/util/constants';

export const imageMacroProcessor: ComponentProcessor<'io.99x.dfs:image', MacroProcessorParams> = (params) => {
    const { config } = params.macro;
    const content = getContent();

    return {
        ...getComponentProps(config?.image, content)
    };
};

function getComponentProps(config: NestedRecord, content: Content) {
    const indexes = forceArray(config?.index).map(index => index - 1);
    const macros = content.x?.[getXDataName()]?.macros;
    const images = forceArray(macros?.images);
    const imagesSelected = getItemsByIndexes(images, indexes);

    return {
        images: imagesSelected.map(image => ({
            image: (image.image && myImageUrl(image.image as string, 'width(500)'))?.link,
            caption: image.caption,
        })),
    };
}
```

**`image.tsx`**
```typescript
import { MacroComponentParams } from '@enonic/react-components';
import React from 'react';
import type { ImageMacroProps } from '/site/macros/image/image.d';

export const ImageMacro = ({ data, children }: MacroComponentParams) => {
    const props = data as unknown as ImageMacroProps;

    return (
        <>
            <h2>Image Macro</h2>
            <div>
                {props.images.map((image, index) => (
                    <img src={image.image} alt={image.caption} key={index} />
                ))}
            </div>
        </>
    );
};
```

## i18n Keys

See [i18n.md](./i18n.md) for the full key pattern. Macro keys follow:

```
macro.{name}.display-name
macro.{name}.{field_name}
```
