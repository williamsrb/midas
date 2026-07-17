"""Outbound notifications: Slack (incoming webhook) and WhatsApp (Meta Cloud API).

Design goal: one-way today (midas -> you), two-way tomorrow. The channel
abstraction below is the "terrain" for future inbound commands - an inbound
webhook receiver can reuse the same config/credentials (see
`midas docs notifications`).

WhatsApp uses the official Meta Cloud API (ban-safe). Free for this use case:
a single-user setup stays far below the 1,000 free service conversations per
month. Token: WHATSAPP_TOKEN in the midas credentials file.
"""

from __future__ import annotations

import requests

from . import logging_setup
from .config import Config, load_credentials

log = logging_setup.get("notify")

GRAPH_API = "https://graph.facebook.com/v21.0"


def send(cfg: Config, event: str, message: str) -> list[str]:
    """Fan a notification out to every configured channel.

    Never raises; returns the list of channels that succeeded.
    """
    if not cfg.notify.enabled or event not in cfg.notify.events:
        return []
    text = f"[midas:{event}] {message}"
    delivered = []
    if cfg.notify.slack_webhook:
        if _send_slack(cfg.notify.slack_webhook, text):
            delivered.append("slack")
    if cfg.notify.whatsapp_phone_id and cfg.notify.whatsapp_to:
        if _send_whatsapp(cfg, text):
            delivered.append("whatsapp")
    if not delivered:
        log.info("notification (no channel delivered): %s", text)
    return delivered


def _send_slack(webhook: str, text: str) -> bool:
    try:
        resp = requests.post(webhook, json={"text": text}, timeout=15)
        if resp.ok:
            return True
        log.error("slack webhook failed: HTTP %s %s", resp.status_code, resp.text[:200])
    except requests.RequestException as exc:
        log.error("slack webhook failed: %s", exc)
    return False


def _send_whatsapp(cfg: Config, text: str) -> bool:
    token = load_credentials().get("WHATSAPP_TOKEN", "")
    if not token:
        log.error("whatsapp configured but WHATSAPP_TOKEN missing from credentials")
        return False
    url = f"{GRAPH_API}/{cfg.notify.whatsapp_phone_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": cfg.notify.whatsapp_to,
        "type": "text",
        "text": {"body": text},
    }
    try:
        resp = requests.post(
            url, json=payload, headers={"Authorization": f"Bearer {token}"}, timeout=15
        )
        if resp.ok:
            return True
        # Outside the 24h service window Meta requires a pre-approved template;
        # documented in `midas docs notifications`.
        log.error("whatsapp send failed: HTTP %s %s", resp.status_code, resp.text[:300])
    except requests.RequestException as exc:
        log.error("whatsapp send failed: %s", exc)
    return False
