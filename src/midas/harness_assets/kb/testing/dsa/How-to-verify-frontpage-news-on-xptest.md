# How to verify frontpage news on DSA xptest

## Purpose

Confirm the **Forside nyheter** (`frontpageNews`) part on the public front page after deploy.

## Procedure

1. Open the Norwegian front page: `https://dsa-xptest.enonic.cloud/`
2. Scroll to the **Nyheter** section (class `frontpage-news-part`).
3. Confirm **row 1:** three `.news-card` blocks with images (`col-lg-4`).
4. Confirm **row 2:** three `.news-ticker` items (title link + date, no image).
5. Confirm heading **Nyheter** and link **Les alle nyheter** (unless `hide_heading` is set in CMS).
6. Open English site: `https://dsa-xptest.enonic.cloud/en` — section heading **News**, link **Read all news articles**.

## DOM quick check (browser console)

```js
const s = document.querySelector('.frontpage-news-part')
;({
  imageCards: s?.querySelectorAll('.news-card').length,
  tickers: s?.querySelectorAll('.news-ticker').length
})
// Expect: imageCards 3, tickers 3
```

## Sample data

- **NO base URL:** `https://dsa-xptest.enonic.cloud/`
- **EN base URL:** `https://dsa-xptest.enonic.cloud/en`
- **Production reference layout:** https://www.dsa.no/ (3 image cards + 3 text tickers)
