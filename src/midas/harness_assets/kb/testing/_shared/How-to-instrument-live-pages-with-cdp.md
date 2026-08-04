# How to instrument live pages with CDP for evidence

**Scope:** `_shared`
**Applies to:** any site under browser automation with a Chrome DevTools Protocol channel
(`cursor-ide-browser` → `browser_cdp`; Playwright CDP session works the same)
**Related:** [How-to-use-content-studio-xp8.md](./How-to-use-content-studio-xp8.md)

## Purpose

Prove hover, responsive and motion behaviour that a plain screenshot cannot reach, and turn
DOM facts (hrefs, computed styles, current URL) into a capturable image.

## Hover states

Two different mechanisms — pick by what the component uses.

**CSS `:hover` only** (colour, underline, background): force the pseudo-state so it survives
a screenshot, since a real pointer cannot be parked while capturing.

```js
// CDP, in order
CSS.enable
DOM.getDocument            → root nodeId
DOM.querySelector          → nodeId of the element
CSS.forcePseudoState       { nodeId, forcedPseudoClasses: ['hover'] }
// capture, then clear with forcedPseudoClasses: []
```
Read the effect with `CSS.getComputedStyleForNode` (or `Runtime.evaluate` +
`getComputedStyle`) **before and after** so the report can state the actual values.

**React `onMouseEnter` / `onFocus`** (state change, e.g. swapping an image panel):
`forcePseudoState` does nothing — React needs a real event. Dispatch `mouseover` **with a
`relatedTarget` that is a sibling element**, not `document.body`:

```js
row.dispatchEvent(new MouseEvent('mouseover', { bubbles: true, relatedTarget: otherRow }))
```
With `relatedTarget: document.body` React's synthetic `mouseenter` is often computed as
"already inside" and the handler never fires. Verify the state actually changed (class,
`src`, panel height) before capturing — do not assume the dispatch worked.

## Viewport / responsive

```js
Emulation.setDeviceMetricsOverride { width: 390, height: 844, deviceScaleFactor: 2, mobile: true }
// capture
Emulation.clearDeviceMetricsOverride
```
Always clear it — a leftover override silently poisons every later desktop capture.

## Motion

- Reduced motion: `Emulation.setEmulatedMedia { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] }`,
  then assert the animation stopped (`getAnimations().length`, or `playState`).
- Auto-scrolling / marquee: sample the moving value twice with a delay and show it changed:
  ```js
  const t1 = getComputedStyle(el).transform; await new Promise(r => setTimeout(r, 600));
  [t1, getComputedStyle(el).transform]
  ```
  `element.getAnimations()` gives `animationName`, `duration`, `iterations`, `playState` —
  better proof than a still image.

## Making DOM facts capturable

A screenshot of a page cannot show an `href` or a `target`. Build a small overlay from the
**live DOM** and screenshot that, so the image is self-evidencing:

```js
const box = document.createElement('div')
box.setAttribute('style', 'position:fixed;inset:0;z-index:99999;background:#fff;padding:16px;overflow:auto')
box.innerHTML = '<p>Live DOM of ' + location.href + '</p>' + tableBuiltFromQuerySelectorAll
document.body.appendChild(box)
```
Same trick for navigation proof: after a click, inject a fixed banner containing
`location.href` and capture it, since the embedded browser screenshot has no address bar.
Keep the values **read from the page** — never hand-typed.

## Pitfalls

- `Input.*` CDP methods are denied in the Cursor embedded browser; use the dedicated
  `browser_click` / `browser_type` tools or `Runtime.evaluate` + `dispatchEvent`.
- Screenshots taken via `browser_take_screenshot` with a path land under
  `/tmp/cursor/screenshots/<the path you asked for>` — copy them to the real evidence folder
  before flattening, or the folder stays empty.
- Content Studio's page-editor surface is an iframe; snapshots do not see inside it. Use
  `Runtime.evaluate` against `iframe.contentDocument` (same origin) or drive the outer panel.
- Overlays and injected banners must be removed (or the tab reloaded) before the next capture.

## Sample data (minimal)

| Thing | Example |
|-------|---------|
| Mobile viewport | 390 × 844, `deviceScaleFactor: 2` |
| Hover-transition sample delay | 600 ms |
