# How to verify FORM column on elite tabell (ntf)

**Scope:** `ntf`
**Applies to:** `elite.ntf.seeds.no`, club NTF hosts (`*.ntf.seeds.no`), production club `/tabell`
**Related:** none

## Prerequisites

- Public page — no auth
- NIFS stage id for the league season (Eliteserien 2026 example: `700911`)
- Optional: ImageMagick `mogrify` if capturing Jira evidence screenshots

## Procedure

1. Open `<base>/tabell` (tournament: all FORM letters are `<a>`; club host: only the local club row uses `<a>`, other clubs use `<span>`).
2. Selectors (rendered HTML):
   - Row: `tr.table__row` (own club: `tr.table__row--active`)
   - Team name: `span.table__typo--full` (not `table__team-name`)
   - FORM cell: `td.table__form`
   - Letters: `a.team-form.team-form--win|--lose|--draw` (or `span.team-form…` on club hosts for other clubs)
   - Letter text: translated `V` / `T` / `U`
3. Confirm five letters per club and that tournament-site `href`s may point at **production club** domains (`https://www.<club>/resultater/kamp?id=…`) — the id is what matters.
4. Cross-check every letter against NIFS:

```bash
curl -s "<BASE>/tabell" -o /tmp/tabell.html
curl -s "https://api.nifs.no/stages/<STAGE_ID>/matches/" -o /tmp/all.json
python3 - <<'EOF'
import json, re
allm = {m['id']: m for m in json.load(open('/tmp/all.json'))}
rows = re.findall(r'<tr class="table__row[^"]*">.*?</tr>', open('/tmp/tabell.html', encoding='utf-8').read(), re.S)
letter_of = {'team-form--win': 'V', 'team-form--lose': 'T', 'team-form--draw': 'U'}
bad, checked = [], 0
for r in rows:
    n = re.search(r'table__typo--full[^>]*>\s*([^<]+)', r)
    forms = re.findall(r'<a class="team-form\s*([^"]*)"[^>]*href="([^"]*)"[^>]*>\s*([^<\s]+)', r)
    if not forms or not n: continue
    team = n.group(1).strip(); key = team.split()[0]
    if team.startswith('Bodø') or team.startswith('Bod'): key = 'Bodø'
    if team.startswith('Ham'): key = 'HamKam'
    if team.startswith('KFUM'): key = 'KFUM'
    ids = [u.split('id=')[-1] for _, u, _ in forms]
    for (cls, _, letter), mid in zip(forms, ids):
        checked += 1
        m = allm.get(int(mid))
        if not m: bad.append((team, mid, 'id not in stage')); continue
        home, away = m['homeTeam']['name'], m['awayTeam']['name']
        hs, as_ = m['result']['homeScore90'], m['result']['awayScore90']
        if home == team or home.startswith(team) or team.startswith(home) or home.startswith(key):
            is_home = True
        elif away == team or away.startswith(team) or team.startswith(away) or away.startswith(key):
            is_home = False
        else:
            is_home = key in home
        gf, ga = (hs, as_) if is_home else (as_, hs)
        exp = 'V' if gf > ga else ('T' if gf < ga else 'U')
        got = letter_of.get(cls.strip(), letter.strip())
        if exp != got:
            bad.append((team, mid, f'letter {got} but {home} {hs}-{as_} {away} => {exp}'))
    ts = [allm[int(i)]['timestamp'] for i in ids if int(i) in allm]
    if ts != sorted(ts): bad.append((team, '-', 'FORM not chronological'))
    def involves(x):
        h, a = x['homeTeam']['name'], x['awayTeam']['name']
        return (h == team or a == team or h.startswith(team) or a.startswith(team)
                or team.startswith(h) or team.startswith(a)
                or h.startswith(key) or a.startswith(key))
    played = sorted([x for x in allm.values() if x.get('matchStatusId') == 1 and involves(x)],
                    key=lambda x: x['timestamp'])
    if [str(x['id']) for x in played[-5:]] != ids:
        bad.append((team, '-', 'not the five most recent played'))
print(f'letters checked: {checked}\nMISMATCHES: {len(bad)}')
for b in bad: print('  ', b)
EOF
```

5. Expect `MISMATCHES: 0` and `letters checked: 80` for a full 16-club Eliteserien table.

## Pitfalls

- Table model cache ~6 minutes (`tableCache` expire 360 in `lib/tasks/tableView.js`) — wait after deploy before judging.
- Club production hosts deploy per installation; old FORM ids on production do not prove the fixed build is wrong.
- Some production club `/resultater/kamp?id=…` pages return “Match not found”; use NIFS `https://api.nifs.no/matches/<id>` for the score when landing pages fail.
- FORM order is by **timestamp**, not round number (postponed fixtures can sit in the last five out of round order).
- Regex must use `table__typo--full` and `tr class="table__row` (active row has an extra class).

## Sample data (minimal)

| Field | Example |
|-------|---------|
| Base URL | `https://elite.ntf.seeds.no` |
| Club host | `https://bra.ntf.seeds.no` |
| Stage id | `700911` (Eliteserien 2026) |
