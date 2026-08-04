#!/usr/bin/env python3
"""Cursor hooks: log every Agent chat prompt and result to ../history/ (from this hooks dir)."""

from __future__ import annotations

import fcntl
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HISTORY_ROOT = Path(__file__).resolve().parent.parent / 'history'
STATE_DIR = HISTORY_ROOT / '.state'
STATE_FILE = STATE_DIR / 'pending.json'
ERROR_LOG = STATE_DIR / 'hook-errors.log'


def log_error(message: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    with ERROR_LOG.open('a', encoding='utf-8') as fh:
        fh.write(f'[{stamp}] {message}\n')


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_datetime(dt: datetime) -> str:
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def path_slug(iso_dt: str) -> str:
    return iso_dt.replace(':', '-')


def unique_slug(base_slug: str, day_dir: Path) -> str:
    slug = base_slug
    counter = 1
    while (day_dir / f'{slug}_prompt.md').exists():
        slug = f'{base_slug}_{counter}'
        counter += 1
    return slug


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {'by_generation': {}, 'conversation_stack': {}}
    try:
        data = json.loads(STATE_FILE.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            return {'by_generation': {}, 'conversation_stack': {}}
        data.setdefault('by_generation', {})
        data.setdefault('conversation_stack', {})
        return data
    except Exception as exc:
        log_error(f'load_state failed: {exc}')
        return {'by_generation': {}, 'conversation_stack': {}}


def save_state(state: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix('.tmp')
    with tmp.open('w', encoding='utf-8') as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        json.dump(state, fh, indent=2, sort_keys=True)
        fh.write('\n')
    tmp.replace(STATE_FILE)


def format_attachments(attachments: Any) -> str:
    if not attachments:
        return '_None_'
    lines: list[str] = []
    if isinstance(attachments, list):
        for item in attachments:
            if not isinstance(item, dict):
                lines.append(f'- {item!r}')
                continue
            kind = item.get('type', 'unknown')
            path = item.get('file_path') or item.get('path') or ''
            lines.append(f'- **{kind}**: `{path}`')
    else:
        lines.append(f'- {attachments!r}')
    return '\n'.join(lines) if lines else '_None_'


def format_workspace_roots(roots: Any) -> str:
    if not roots:
        return '_None_'
    if isinstance(roots, list):
        return '\n'.join(f'- `{r}`' for r in roots)
    return f'- `{roots}`'


def write_prompt_file(path: Path, payload: dict[str, Any], iso_dt: str, slug: str) -> None:
    prompt = payload.get('prompt', '')
    body = (
        '---\n'
        f'kind: prompt\n'
        f'iso_datetime: {iso_dt}\n'
        f'path_slug: {slug}\n'
        f'conversation_id: {payload.get("conversation_id", "")}\n'
        f'generation_id: {payload.get("generation_id", "")}\n'
        f'hook_event_name: {payload.get("hook_event_name", "beforeSubmitPrompt")}\n'
        '---\n\n'
        '# Prompt\n\n'
        f'{prompt}\n\n'
        '## Workspace roots\n\n'
        f'{format_workspace_roots(payload.get("workspace_roots"))}\n\n'
        '## Attachments\n\n'
        f'{format_attachments(payload.get("attachments"))}\n'
    )
    path.write_text(body, encoding='utf-8')


def write_result_file(path: Path, text: str, entry: dict[str, Any], payload: dict[str, Any]) -> None:
    body = (
        '---\n'
        f'kind: result\n'
        f'iso_datetime: {entry.get("iso_datetime", "")}\n'
        f'path_slug: {entry.get("slug", "")}\n'
        f'conversation_id: {entry.get("conversation_id", "")}\n'
        f'generation_id: {payload.get("generation_id", entry.get("generation_id", ""))}\n'
        f'hook_event_name: {payload.get("hook_event_name", "")}\n'
        f'status: {payload.get("status", "completed")}\n'
        '---\n\n'
        '# Result\n\n'
        f'{text if text else "_(empty response)_"}\n'
    )
    path.write_text(body, encoding='utf-8')


def register_prompt(payload: dict[str, Any]) -> None:
    now = utc_now()
    iso_dt = iso_datetime(now)
    iso_date = now.strftime('%Y-%m-%d')
    base_slug = path_slug(iso_dt)

    day_dir = HISTORY_ROOT / iso_date
    day_dir.mkdir(parents=True, exist_ok=True)

    slug = unique_slug(base_slug, day_dir)
    prompt_path = day_dir / f'{slug}_prompt.md'
    result_path = day_dir / f'{slug}_result.md'

    write_prompt_file(prompt_path, payload, iso_dt, slug)

    generation_id = str(payload.get('generation_id') or '').strip()
    conversation_id = str(payload.get('conversation_id') or '').strip()
    if not generation_id:
        generation_id = f'no-generation-{slug}'

    entry = {
        'slug': slug,
        'iso_datetime': iso_dt,
        'iso_date': iso_date,
        'prompt_path': str(prompt_path),
        'result_path': str(result_path),
        'conversation_id': conversation_id,
        'generation_id': generation_id,
        'pending': True,
    }

    state = load_state()
    state['by_generation'][generation_id] = entry
    if conversation_id:
        stack = state['conversation_stack'].setdefault(conversation_id, [])
        stack.append(generation_id)
    save_state(state)


def resolve_entry(payload: dict[str, Any]) -> dict[str, Any] | None:
    state = load_state()
    generation_id = str(payload.get('generation_id') or '').strip()
    conversation_id = str(payload.get('conversation_id') or '').strip()

    if generation_id and generation_id in state['by_generation']:
        return state['by_generation'][generation_id]

    if conversation_id:
        stack = state['conversation_stack'].get(conversation_id) or []
        for gid in reversed(stack):
            entry = state['by_generation'].get(gid)
            if entry and entry.get('pending'):
                return entry

    pending = [
        entry for entry in state['by_generation'].values()
        if entry.get('pending')
    ]
    if len(pending) == 1:
        return pending[0]
    if pending:
        pending.sort(key=lambda e: e.get('iso_datetime', ''))
        return pending[-1]
    return None


def mark_complete(generation_id: str | None) -> None:
    if not generation_id:
        return
    state = load_state()
    entry = state['by_generation'].get(generation_id)
    if entry:
        entry['pending'] = False
        save_state(state)


def handle_response(payload: dict[str, Any]) -> None:
    entry = resolve_entry(payload)
    if not entry:
        log_error(f'handle_response: no pending entry for payload keys={list(payload.keys())}')
        return

    text = payload.get('text') or ''
    result_path = Path(entry['result_path'])
    write_result_file(result_path, text, entry, payload)
    mark_complete(str(payload.get('generation_id') or entry.get('generation_id') or ''))


def handle_stop(payload: dict[str, Any]) -> None:
    entry = resolve_entry(payload)
    if not entry:
        return

    result_path = Path(entry['result_path'])
    if result_path.exists() and result_path.stat().st_size > 0:
        mark_complete(str(payload.get('generation_id') or entry.get('generation_id') or ''))
        return

    status = payload.get('status', 'unknown')
    fallback = (
        f'_No assistant text was captured by `afterAgentResponse`. '
        f'Agent loop ended with status `{status}`._'
    )
    write_result_file(result_path, fallback, entry, payload)
    mark_complete(str(payload.get('generation_id') or entry.get('generation_id') or ''))


def main() -> int:
    mode = (sys.argv[1] if len(sys.argv) > 1 else '').strip()
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            payload = {}

        if mode == 'prompt':
            register_prompt(payload)
            sys.stdout.write('{"continue": true}\n')
        elif mode == 'response':
            handle_response(payload)
            sys.stdout.write('{}\n')
        elif mode == 'stop':
            handle_stop(payload)
            sys.stdout.write('{}\n')
        else:
            log_error(f'unknown mode: {mode!r}')
            sys.stdout.write('{}\n')
        return 0
    except Exception:
        log_error(traceback.format_exc())
        if mode == 'prompt':
            sys.stdout.write('{"continue": true}\n')
        else:
            sys.stdout.write('{}\n')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
