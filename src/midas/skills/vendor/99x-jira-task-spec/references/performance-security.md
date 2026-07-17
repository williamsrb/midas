# Reference: Performance / Security — Spec Writing Guide

Use this file when the task type is **Performance / Security**.
These tasks are high-risk: a change that improves one metric can introduce
regressions elsewhere. The spec must document the root cause before any
implementation approach is suggested.

---

## Reading the spec for root cause details

Before writing the approach, extract:

| Detail | Where to look |
|---|---|
| **Metric or vulnerability** | Description: LCP, TTI, bundle size, CVE ID, XSS vector, N+1 query, secrets exposure |
| **Affected code path** | Description or comments: which component, controller, query, or endpoint |
| **Baseline / threshold** | Numbers or conditions that define the problem (e.g. "LCP > 4s on mobile") |
| **Acceptance condition** | What "fixed" looks like (e.g. "LCP < 2.5s", "no `dangerouslySetInnerHTML` on user input") |

If any of these are missing, mark them as gaps in the spec.

---

## Performance patterns in Enonic React4xp

**Server-side caching** — wrap expensive controller calls with `cacheLib`:
```typescript
import { newCache } from '/lib/cache';
const cache = newCache({ size: 100, expire: 3600 });
export function getData(key: string) {
  return cache.get(key, () => fetchFromSource(key));
}
```
The TTL value must be documented and justified in the spec — the dev must validate it
against content update frequency before implementation.

**Guillotine queries** — over-fetching causes slow responses:
- Trim queries to only the fields the component actually renders
- Add `first`/`after` pagination on list queries
- Eliminate N+1 patterns (queries inside loops)

**React rendering** — client-side performance:
- Replace anonymous functions in JSX props with named/memoized references
- Images must have `loading="lazy"` and explicit `width`/`height`
- Large lists require windowing — flag as a significant architectural change

---

## Security patterns in Enonic React4xp

**Input sanitisation:**
- Any value from user input or external APIs rendered in the DOM is untrusted
- Never use `dangerouslySetInnerHTML` unless the value is explicitly sanitised server-side
- Flag every existing `dangerouslySetInnerHTML` found in affected files

**Secrets exposure:**
- Locate every `log.*` call in affected files
- Verify none log request headers, config values, or response bodies from authenticated endpoints
- Credentials and API keys must come from `app.config` — never from hardcoded values or env vars read at runtime in JS

**Dependency vulnerabilities:**
- Identify the vulnerable package and version from the CVE reference in the spec
- Check if a patched version exists — note it in the spec
- Verify compatibility with the current React4xp version — note the result
- List the update in the Implementation Steps — **do not apply it automatically**; the dev must approve

**Content Security Policy:**
- Do not change CSP headers directly
- If the fix requires whitelisting a new external domain, flag it for the dev

---

## Suggested Technical Approach — content to generate

Write the following in the `Suggested Technical Approach` section:

- **Root cause**: state the exact metric/vulnerability and the specific code path responsible
- **Affected files**: list the files in scope (controllers, lib files, `.tsx` components, queries)
- **Approach type**: which lever applies — caching, query trimming, React rendering, sanitisation, dependency update, secrets audit
- **Risk**: describe what could regress if the fix is applied incorrectly
- **Out of scope**: list related areas that will NOT be touched to keep the change surgical
- **Gaps**: any missing baseline data, CVE details, or acceptance conditions the dev must provide

---

## Implementation Steps — content to generate

Write concrete, ordered steps referencing FR numbers:

**Performance:**
1. Document the current baseline metric (from spec) and the target threshold
2. Identify the exact lines responsible for the bottleneck (reference FR-N)
3. Apply the targeted fix (caching / query trim / lazy loading / memoization)
4. Document TTL rationale or pagination parameters chosen
5. Note any components or queries that were inspected but left unchanged

**Security:**
1. Identify and document the vulnerable code path (reference FR-N)
2. Apply the minimal fix (sanitisation, log scrubbing, config-based credentials)
3. Search for the same pattern in related files — list findings, do not fix automatically
4. For dependency updates: list package, current version, target version, and compatibility notes — do not run `npm install`
5. Flag any CSP or architecture changes needed for dev action

---

## Definition of Done checklist to include

- [ ] Root cause identified and documented in the spec
- [ ] Change is surgical — no unrelated refactoring
- [ ] If caching added: TTL choice documented and ready for dev validation
- [ ] If Guillotine query changed: only required fields fetched; pagination added where applicable
- [ ] If dependency update: compatibility verified and listed — not applied automatically
- [ ] No new `dangerouslySetInnerHTML` introduced
- [ ] No secrets, credentials, or API keys in log statements
- [ ] Similar patterns in other files listed in the report (not auto-fixed)
