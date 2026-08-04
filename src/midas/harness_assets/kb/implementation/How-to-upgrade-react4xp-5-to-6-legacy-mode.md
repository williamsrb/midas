# How to upgrade an Enonic React4XP 5→6 app in legacy mode (no componentRegistry)

**Scope:** Enonic XP 7.x apps using React4XP 5.x that hand-roll their own asset bridge (no `render()` from `/lib/enonic/react4xp`, no `componentRegistry`/`dataFetcher`) — i.e. React4XP used purely as a client bundler + asset service.
**Applies to:** `messaging-queue-enonic-app` (`io.99x.messagingqueueapp`), and any similarly-structured admin-tool-only XP app.

## Prerequisites

- `~/.claude/kb/offline-reference/react4xp-6.x/docs/react4xp/6.x/legacy-upgrade.md` is the governing doc — the "recommended upgrade" doc is for componentRegistry apps only, don't follow it if the app has none of that.
- Docker dev environment (`make up` / `make full`) with a bind-mounted `xp/` source and a named XP-home volume.

## Procedure

1. **Pin `@enonic/react4xp` to an exact version, not a caret range.** `"^6.0.2"` resolves to `6.1.0` via npm, which requires `react: ^19` — silently breaking a React-18-pinned "Phase A" migration step. Use `"6.0.2"` (no caret) when the goal is React4XP 6.0.x while staying on React 18.
2. **`lib-guillotine` bundles `lib-cache` transitively.** Removing `lib-guillotine` from `build.gradle` without adding `include 'com.enonic.lib:lib-cache:2.2.1'` explicitly leaves any code that does `require('/lib/cache')` broken at runtime with no compile-time signal (XP `include`s aren't transitive). Audit the built JAR after any `include` removal:
   ```bash
   unzip -qo build/libs/<app>-*.jar -d /tmp/scan && grep -rhoE "require\(['\"]/lib/[^'\"]+" /tmp/scan | sed -E "s/require\(['\"]//" | sort -u
   ```
   Every `/lib/xp/<name>` and `/lib/<name>` found must have a matching `include` in `build.gradle`.
3. **Webpack→Rspack CSS swap** (React4XP 6's build pipeline): replace `mini-css-extract-plugin` with `rspack.CssExtractRspackPlugin`, add `esModule: false` to `css-loader` options, add a `woff|woff2|eot|ttf|otf` → `asset/resource` rule, and give `filename`/`chunkFilename` a `[contenthash:9]`. The admin tool controller must read filenames from `stats.components.json` (not hardcode `[name].css`) — verify this before assuming CSS breaks.
4. **XP minor-version bump has a real runtime floor.** `app.systemVersion = "${xpVersion}"` in `build.gradle` becomes an actual OSGi version range (e.g. bumping `xpVersion` to `7.16.7` makes the app require `[7.16.0,8.0.0)`). If the dev sandbox's Docker image is still on an older 7.x (e.g. `7.15.3`), the app installs but logs `WARN ... has an invalid system version range` and **does not fully start** (silent — no admin-tool error page, just a missing `BundleEvent STARTED` for the app bundle). The `leanon/enonic-xp` Docker Hub repo does not publish every patch version — check available tags (`curl -s "https://hub.docker.com/v2/repositories/leanon/enonic-xp/tags?page_size=100"`) and use the newest available tag in the target minor line (tags in the 7.16.x line are `-nodeNN` suffixed only, no bare tag).
5. **A `build.gradle` with commented-out `include "com.enonic.xp:lib-*:${xpVersion}"` lines is not necessarily intentional.** If `main.ts` (or any always-executed entry file) does `import {run} from '/lib/xp/context'` but `lib-context` is commented out, the app throws `ResourceNotFoundException` on every deploy, immediately, on any XP version — a pre-existing latent bug, not something introduced by a React4XP upgrade. Same for `lib-node` if nothing includes it but code requires `/lib/xp/node`. Fix opportunistically during the JAR-scan audit step (see #2) rather than treating it as out of scope.
6. **Verifying a fresh sandbox needs a bootstrap admin user** — a brand-new `xp-home` Docker volume has no users. The setup-wizard "create an Admin User" form has a **client-side username blocklist that rejects any username containing the substring `admin`** (e.g. `testadmin` fails with "Invalid or forbidden username!", `wramos` succeeds). React-controlled inputs on this form don't reliably accept Playwright/browser-automation `form_input` — use `document.getElementById(id)` + the native `HTMLInputElement.prototype.value` setter + dispatch `input`/`change` events via `javascript_exec`, then `.click()` the button element directly once its class no longer includes `disabled`.
7. **Runtime canary for a `require('/lib/cache')` dependency**: call the service via `fetch()` in the browser console (`GET .../_/service/<app>/test-ai-chat?service=claude&message=hi` — check the service's actual param names in its `.ts` source, don't guess). A `500` failure deep in a network call to a real third-party API (`Cannot get property "body" of null`) means the module resolved fine and lib-cache is wired correctly; a `ResourceNotFoundException` naming `/lib/cache` means the include is missing or mis-versioned.

## React 18 → 19 with Semantic UI React: the plan's own findDOMNode check is insufficient

If a migration plan says "verified: semantic-ui-react does NOT use `findDOMNode`, so React 19 is safe modulo `defaultProps`" — **that check is incomplete if it only grepped `semantic-ui-react`'s own source.** `semantic-ui-react@2.1.5` depends on `@fluentui/react-component-ref`, whose `RefFindNode.js` calls `ReactDOM.findDOMNode(this)` in `componentDidMount`/`componentDidUpdate` to resolve a ref for `handleRef`. `findDOMNode` was **fully removed** (not deprecated-but-present) from `react-dom@19` — calling it throws `TypeError: ReactDOM.findDOMNode is not a function` at mount time, with **zero console output** (it surfaces only via a `window` `error` event, not `console.error`, not an unhandled promise rejection) — the whole React tree silently fails to mount, leaving the root container empty.

`RefFindNode`/`react-component-ref` is used internally by `Sidebar`, `Button`, `Input`, `Modal`, `Checkbox`, `Dropdown`, `Portal`, `Sticky`, `TextArea`, `Dimmer`, `Popup`, and `Visibility` (check `grep -rl "RefFindNode\|react-component-ref" node_modules/semantic-ui-react/dist/commonjs/`). If any of these are used anywhere in the app's top-level layout (e.g. a `Sidebar` wrapping the whole page), the **entire app fails to render**, not just the specific component.

**Practical takeaway:** before greenlighting a React 18→19 bump for an app using `semantic-ui-react` 2.x, run this check yourself — don't trust a prior plan's `findDOMNode` verification unless it explicitly covered transitive deps:
```bash
grep -rl 'findDOMNode' node_modules/ 2>/dev/null | grep -v '/umd/\|\.map$\|LICENSE'
```
If `@fluentui/react-component-ref` (or any other transitive dep) shows up, React 19 is not viable via a small prop shim — treat it the same as "Option 2: replace Semantic UI React" in scope, or stay on React 18.

**Debugging technique for "the app renders blank, zero console output" under React 19:** patch `console.error`, `console.warn`, and `window.reportError`, and add a `window.addEventListener('error', ...)` listener *before* triggering the render — React 19 surfaces some uncaught render/commit errors only through the `error` DOM event (via `reportError`), not through `console.error` or a rejected promise. A `read_console_messages`-style tool that only taps `console.*` will show nothing even though a real, fatal `TypeError` occurred.

## Pitfalls

- `npm run check:types:xp` will likely show pre-existing `TS2307: Cannot find module '/lib/<app-lib>/...'` errors for the app's own bundled library (e.g. `messaging-queue-lib`) if that lib ships no `.d.ts` for its submodules. This is unrelated to a React4XP upgrade — don't chase it unless the migration plan explicitly wires `check` into the build gate (most legacy-mode migration plans deliberately leave it unwired mid-migration).
- The Browser pane's `computer` `screenshot` action can fail with "the Browser pane is not displayed" even when navigation/interaction otherwise works — fall back to `get_page_text`, `read_console_messages`, and `read_network_requests` for verification instead of visual screenshots.

## Sample data

| Item | Example |
|---|---|
| Docker Hub tag lookup | `curl -s "https://hub.docker.com/v2/repositories/leanon/enonic-xp/tags?page_size=100"` |
| JAR require-scan | `grep -rhoE "require\(['\"]/lib/[^'\"]+" /tmp/scan \| sed -E "s/require\(\['\"]//" \| sort -u` |
| Admin-tool URL pattern | `http://localhost:<port>/admin/tool/<appName>/<toolName>` |
