# General Conventions

General conventions and best practices for Enonic React4XP 6 projects.

## File Naming

- All component names use **kebab-case** (e.g., `info-card`, `hero-banner`).
- The directory name and file name must match exactly.

## Folder Structure

All XP schema resources are placed under `/xp/src/main/resources/`:

```
xp/src/main/resources/
├── i18n/
│   ├── phrases.properties           # Default/fallback translations (usually in English)
│   └── phrases_no.properties        # Norwegian translations
├── react4xp/
│   ├── dataFetcher.ts               # Register all component processors here
│   ├── componentRegistry.tsx        # Register all React components here
│   └── components/
│       ├── pages/{name}/
│       │   ├── {name}.tsx           # React page component
│       │   └── processor.ts         # Data processor (returns regions)
│       ├── layouts/{name}/
│       │   ├── {name}.tsx           # React layout component
│       │   └── processor.ts         # Data processor (returns regions + componentProps)
│       ├── parts/{name}/
│       │   ├── {name}.tsx           # React part component
│       │   └── processor.ts         # Data processor (returns componentProps)
│       └── macros/{name}/
│           ├── {name}.tsx           # React macro component
│           └── processor.ts         # Data processor (returns props directly)
└── site/
    ├── content-types/{name}/
    │   ├── {name}.xml               # Descriptor
    │   └── {name}.d.ts             # TypeScript interface ({PascalName}Data)
    ├── x-data/{name}/
    │   ├── {name}.xml               # Descriptor
    │   └── {name}.d.ts             # TypeScript interface  ({PascalName}XData)
    ├── mixins/{name}/
    │   ├── {name}.xml               # Descriptor
    │   └── {name}.d.ts             # TypeScript interface  ({PascalName}MixinData)
    ├── parts/{name}/
    │   ├── {name}.xml               # Descriptor
    │   └── {name}.d.ts             # TypeScript interfaces ({PascalName}PartData + {PascalName}PartProps)
    ├── layouts/{name}/
    │   ├── {name}.xml               # Descriptor
    │   └── {name}.d.ts             # TypeScript interface ({PascalName}LayoutData + {PascalName}LayoutProps)
    ├── macros/{name}/
    │   ├── {name}.xml               # Descriptor
    │   └── {name}.d.ts             # TypeScript interface ({PascalName}MacroProps)
    └── pages/{name}/
        └── {name}.xml               # Descriptor
```

## React4XP 6 Data Flow

1. A request hits Enonic XP (`site/app.ts` or `site/component.ts`).
2. `dataFetcher.ts` routes it to the matching `processor.ts`.
3. The processor fetches config/content, transforms it, and returns `componentProps` (and `regions` for pages/layouts).
4. `componentRegistry.tsx` maps the component key to its React component.
5. The React component receives `{ component, meta, data, common }` and reads `data.componentProps` for its typed props.

## Registering a New Component

Every new component requires two registration steps.

**1. Add to `react4xp/dataFetcher.ts`:**
```typescript
import { myPartProcessor } from './components/parts/my-part/processor';
dataFetcher.addPart(`${app.name}:my-part`, { processor: myPartProcessor });
```

**2. Add to `react4xp/componentRegistry.tsx`:**
```typescript
import { MyPart } from './components/parts/my-part/my-part';
componentRegistry.addPart('io.99x.{PROJECT_SHORT_NAME}:my-part', { View: MyPart });
```

Use `addPart`, `addLayout`, `addPage`, or `addMacro` as appropriate.

## TypeScript Interface Naming

Each component type uses a specific interface naming convention:

| Component | Data interface | Props interface |
|---|---|---|
| Content type | `{PascalName}Data` | — |
| Part | `{PascalName}PartData` | `{PascalName}PartProps` |
| Layout | — | `{PascalName}LayoutProps` |
| Macro | — | `{PascalName}MacroProps` |

- `*Data` interfaces reflect the raw fields from the Enonic form (what Enonic stores).
- `*Props` interfaces reflect what the React component receives (processed types).
- `HtmlArea` fields are typed as `string` in `*Data` and `ExtendedRichTextData` (from `@enonic/react-components`) in `*Props`.

## Field Naming in XML

All `name` attributes on `<input>` and `<item-set>` elements must use **`snake_case`** (e.g., `first_name`, `contact_email`, `cta_text`).

## i18n

All `<label>`, `<display-name>`, and `<help-text>` elements must use `i18n` attributes.

The `<description>` tag must **NOT** have an `i18n` attribute — it must contain only the component name (kebab-case) as plain text.

See [i18n.md](./i18n.md) for full key patterns and property file management.
