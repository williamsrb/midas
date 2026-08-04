# Reference: API Integration — Spec Writing Guide

Use this file when the task type is **API Integration**.
It defines how to fill the `Suggested Technical Approach`, `Implementation Steps`,
and `Definition of Done` sections of the generated spec document.

---

## Reading the spec for API details

Before writing the approach, extract from the issue description:

| Detail | Where to look |
|---|---|
| **Base URL** | Description or comments |
| **Endpoints** | List of paths and HTTP methods |
| **Auth mechanism** | Bearer token, API key header, OAuth client credentials, Basic auth, or none |
| **Access token endpoint** | Any endpoint called to obtain a short-lived token before consuming other endpoints |
| **Request payload** | Fields and types sent by the app |
| **Response shape** | Fields the component actually needs (ignore the rest) |
| **Error cases** | What the UI should show when the API fails |

For each item not found in the spec, note it as a **gap** in the spec document.
The implementation must use safe fallbacks for every gap.

---

## Architecture rules to reflect in the spec

### 1. API configuration belongs in `site.xml`

All API URLs and credentials must be configured as site settings, not as `app.config` keys.
Add a dedicated `<field-set>` to `xp/src/main/resources/site/site.xml` for each integration.

```xml
<field-set>
    <label i18n="site.{integration-name}.label">{Integration Display Name}</label>
    <items>
        <input type="TextLine" name="{integration_name}_base_url">
            <label i18n="site.{integration-name}.base_url">Base URL</label>
            <occurrences minimum="1" maximum="1"/>
        </input>
        <input type="TextLine" name="{integration_name}_api_key">
            <label i18n="site.{integration-name}.api_key">API Key</label>
            <occurrences minimum="1" maximum="1"/>
        </input>
        <!-- Add one input per credential or config value -->
    </items>
</field-set>
```

- Field names use **snake_case** prefixed with the integration name (e.g. `shopify_base_url`, `shopify_api_key`)
- All `<label>` elements must have `i18n` attributes; add keys to both `phrases.properties` and `phrases_no.properties`
- The values are read at runtime via `getSiteConfig()` from `/lib/xp/portal` — never hardcoded

### 2. Integration lib location

All integration code lives under:

```
xp/src/main/resources/lib/99x/modules/api/{integration-name}/
├── types.ts        — TypeScript interfaces for request/response shapes
├── client.ts       — Reads site config, builds auth headers, exposes performRequest wrapper
└── {domain}.ts     — Domain functions grouped by concern (e.g. products.ts, auth.ts)
```

The processor imports from this lib. The React component **never** receives credentials, tokens, or raw API responses — only the already-transformed, display-ready props.

### 3. HTTP requests use `performRequest`

All HTTP calls must go through:

```typescript
import { performRequest } from '/lib/99x/extension/http-client';
```

Never use `/lib/http-client` directly. `performRequest` provides the project-standard
error handling, logging, and response normalisation.

### 4. Cache frequently-called endpoints

Endpoints that are called on every page render and return stable data (e.g. access tokens,
product catalogues, configuration payloads) must be wrapped with `/lib/cache` to avoid
performance degradation:

```typescript
import { newCache } from '/lib/cache';

const tokenCache = newCache({ size: 1, expire: 3500 }); // expire slightly before token TTL

export function getAccessToken(): string | null {
    return tokenCache.get('token', () => fetchAccessToken());
}
```

- The cache TTL must be documented in the spec with a rationale (e.g. "3500s — token TTL is 3600s")
- Flag the TTL choice for dev validation against the actual token expiry or data staleness tolerance
- Only cache read-only data — never cache mutation responses

### 5. Credentials must never reach React

The processor maps API data to display-safe props. It must never include:
- API keys, tokens, or credentials in any prop
- Raw API response objects that may contain sensitive fields
- Internal IDs or implementation details not needed for rendering

If the React component accidentally receives a credential through `componentProps`,
flag it explicitly in the spec as a security risk.

---

## Suggested Technical Approach — content to generate

Write the following in the `Suggested Technical Approach` section:

- **Integration name**: the kebab-case name used for the lib folder and site.xml field-set prefix
- **`site.xml` changes**: list each new field to add inside a new `<field-set>` (field name, input type, label)
- **i18n keys to add**: `site.{integration-name}.*` keys for both `phrases.properties` and `phrases_no.properties`
- **Files to create**:
  - `lib/99x/modules/api/{name}/types.ts` — typed interfaces for all request/response shapes (no `any`)
  - `lib/99x/modules/api/{name}/client.ts` — reads site config via `getSiteConfig()`, exposes auth headers; uses `performRequest` from `/lib/99x/extension/http-client`
  - `lib/99x/modules/api/{name}/{domain}.ts` — one file per domain; each function returns typed result or `null` on failure
- **Cache strategy**: identify which endpoints need caching; document the TTL and rationale for each
- **Processor changes**: which processor(s) call the lib and how the response maps to `componentProps`
- **React component changes**: what the component renders and what fallback it shows when data is absent
- **Security contract**: confirm that no credentials or sensitive fields flow into any React prop
- **Spec gaps**: list any missing API details that must be clarified before or during implementation

---

## Implementation Steps — content to generate

Write concrete, ordered steps referencing FR numbers:

1. Add a `<field-set>` to `site.xml` with all config fields for the integration (base URL, credentials); add `i18n` keys to both `phrases.properties` and `phrases_no.properties` (FR-N)
2. Create `lib/99x/modules/api/{name}/types.ts` — TypeScript interfaces for every request and response shape the integration uses
3. Create `lib/99x/modules/api/{name}/client.ts` — read site config via `getSiteConfig()`; build the auth header or token logic; use `performRequest` from `/lib/99x/extension/http-client`; wrap any token-fetch in a `newCache` block with documented TTL if applicable
4. Create `lib/99x/modules/api/{name}/{domain}.ts` — domain functions that call `client.ts`; wrap every call in try/catch; log errors with `log.error()`; return `null` on any failure
5. Update the processor to call the domain function, handle `null` response, map only display-safe fields to `componentProps` — no credentials in the returned object
6. Update/create the React component to render the data and a meaningful fallback when props indicate empty or failed state

---

## Definition of Done checklist to include

- [ ] API config fields added to `site.xml` inside a dedicated `<field-set>` — no hardcoded URLs or credentials anywhere in the code
- [ ] `i18n` keys added to both `phrases.properties` and `phrases_no.properties` for all new site.xml labels
- [ ] Integration lib created at `lib/99x/modules/api/{name}/` with `types.ts`, `client.ts`, and domain file(s)
- [ ] All HTTP calls go through `performRequest` from `/lib/99x/extension/http-client`
- [ ] Frequently-called endpoints (e.g. access token) wrapped with `newCache`; TTL documented and flagged for dev validation
- [ ] Every domain function returns `null` on failure — processor never throws to React
- [ ] No credentials, tokens, or raw API fields passed as React component props
- [ ] React component renders a meaningful fallback when data is absent
- [ ] Response types are explicit TypeScript interfaces — no `any`
- [ ] All spec gaps documented and flagged for dev review
