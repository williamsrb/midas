# How to align NIFS matches and table-form endpoints (NTB)

## Scope
Applies to `football` (Enonic XP 7.15, CommonJS) — `lib/ntf/request-tables.js`, `getLastFiveMatchesNTB`, and any future code that zips NIFS "matches" and NIFS "table" API responses together by index.

## Prerequisites
- Two NIFS/NTB endpoints in play: `/stages/{id}/matches/?teamId=…` and `/stages/{id}/table/` (team `lastSixMatches`).
- No auth header is required to read these endpoints for verification.

## Pitfall (confirmed against live data)
The two NIFS endpoints do **not** share a sort order:
- `/stages/{id}/matches/?teamId=…` → **descending** by `timestamp` (newest first).
- `/stages/{id}/table/` → `lastSixMatches` / `allPreviousMatches` → **ascending** (oldest → newest).

Zipping them by raw index (or by an offset like `arr.length - n + i`) silently misaligns letters and match IDs — this caused NTF-1227 (FORM letters showing correct results, but each linking to the wrong match).

Also: NIFS round numbers are **not** chronological — postponed matches break round order (e.g. round 1 played after round 4). Never sort by `round` as a proxy for chronology; always sort by `timestamp`.

## Procedure
1. Filter matches to played (`matchStatusId == 1`).
2. Sort ascending by `timestamp`: `.sort((a, b) => a.timestamp - b.timestamp)`.
3. Take the last N with `slice(-n)` rather than offset arithmetic against the unsliced array.
4. Zip with the table endpoint's form array by index — both are now oldest→newest, so no reversal is needed.
5. Guard the case where fewer played matches exist than form codes (index yields `undefined` → push the entry with `ntb_match_id: null`; don't throw). Views already render a `<span>` instead of a link in that case.

## Sample data (Eliteserien 2026, stage 700911, Sarpsborg 08 ntb_main_team_id 5043)
- `lastSixMatches: "2,1,1,1,3,1"` → last five `1,1,1,3,1` = V V V U V.
- Correct chronological match order after sorting: rounds 10, 11, 13, 14, 15.
- Buggy unsorted zip previously picked rounds 5, 1, 4, 3, 2 (the *oldest* played matches, reversed) — exact match with the support-reported wrong link.
