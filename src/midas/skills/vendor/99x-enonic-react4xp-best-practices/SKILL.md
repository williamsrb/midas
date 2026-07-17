---
name: 99x-enonic-react4xp-best-practices
description: Apply when writing, reviewing, or generating any Enonic React4XP 6 code. Contains binding conventions for this project — file naming, folder structure, XML schemas, TypeScript patterns, processor and React component standards, and component registration. Always read before creating or editing parts, layouts, content types, x-data, mixins, or macros in an Enonic project. Never generate Enonic code without consulting this skill first. Installed for Cursor IDE from git.seeds.no/seeds/enonic-skills.
compatibility: Claude Code, Cursor
---

## Cursor IDE

Adapted from [git.seeds.no/seeds/enonic-skills](https://git.seeds.no/seeds/enonic-skills). Read reference files under `references/` with the **Read** tool before generating or editing Enonic React4XP code.

# Enonic React4XP 6 Best Practices

Apply these rules when writing or reviewing Enonic React4XP 6 code.

## General Conventions
See [general-conventions.md](./references/general-conventions.md) for:
- General conventions and best practices for Enonic React4XP 6 projects, including file naming, folder structure, React4XP 6 data flow, and component registration in `dataFetcher.ts` and `componentRegistry.tsx`.

## Content Types
See [content-types.md](./references/content-types.md) for:
- Content type structure and best practices

## X-Data
See [x-data.md](./references/x-data.md) for:
- X-data structure and best practices

## Mixins
See [mixins.md](./references/mixins.md) for:
- Mixin structure and best practices

## Parts
See [parts.md](./references/parts.md) for:
- Part structure and best practices

## Layouts
See [layouts.md](./references/layouts.md) for:
- Layout structure and best practices

## Macros
See [macros.md](./references/macros.md) for:
- Macro structure and best practices

## Fields Processing

See [fields-processing.md](./references/fields-processing.md) for:
- Internal library functions for processing images, links, HTML, TextArea, arrays, and video fields in controllers.

## Development Guidelines

See [development-guidelines.md](./references/development-guidelines.md) for:
- Runtime constraints and anti-patterns (e.g. forbidden libs in background tasks)

## When to load each reference

| Task involves             | Read these files                                                     |
|---------------------------|----------------------------------------------------------------------|
| Creating/editing a part   | `general-conventions.md`, `parts.md`, `fields-processing.md`        |
| Creating/editing a layout | `general-conventions.md`, `layouts.md`, `fields-processing.md`      |
| Content type or schema    | `content-types.md`, `mixins.md`                                      |
| X-data fields             | `x-data.md`, `mixins.md`                                             |
| Macro development         | `macros.md`, `general-conventions.md`                                |
| Any new component         | `general-conventions.md` + type-specific file                        |
| Any descriptor XML        | `descriptor-structure.md`                                            |
| Background tasks          | `development-guidelines.md`                                          |

Always read `general-conventions.md` first. It contains cross-cutting rules that apply to every other file.
