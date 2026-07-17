# Midas notifications

One-way today (midas -> you), designed to become two-way (you -> midas) later.

## Configuration

```toml
[notify]
enabled = true
events = ["blocked", "awaiting_human", "spec_questions", "answered", "rework"]
slack_webhook = "https://hooks.slack.com/services/T000/B000/XXXX"
whatsapp_phone_id = "123456789012345"   # Meta Cloud API phone-number ID (sender)
whatsapp_to = "4790000000"              # your phone, E.164 without '+'
```

Credentials file (`~/.config/midas/credentials`): `WHATSAPP_TOKEN=<meta access token>`.

Events midas emits:

| Event | When |
|---|---|
| `blocked` | preflight auto-interrupt, or a task blocked in some stage |
| `awaiting_human` | implementation committed; branch ready for your review |
| `spec_questions` | spec judged insufficient; questions posted on Jira |
| `answered` | a question-type task was answered on Jira |
| `rework` | an analyst sent a finished task back (new round) |

## Slack

Create an **Incoming Webhook** (Slack app -> Incoming Webhooks -> Add to a
private channel), paste the URL into `slack_webhook`. Nothing else needed.

## WhatsApp (Meta Cloud API - the safe, free path)

Per the researched guidance: the **official Meta Cloud API** is ban-safe, and
a single-user setup stays far below the free tier (1,000 service
conversations/month; one user talking to midas uses ~30).

Setup:

1. Create a Meta developer account -> app -> add the **WhatsApp** product
   (developers.facebook.com). You get a test sender number and a
   **phone-number ID** -> `whatsapp_phone_id`.
2. Add your own phone as a recipient (test mode) -> `whatsapp_to`.
3. Generate a (long-lived) access token -> `WHATSAPP_TOKEN` in the
   credentials file.

Caveat: Meta only delivers **free-form text** inside a 24-hour window after
the *user's* last message. Practical warm-up: send "hi" to the midas number
in the morning and notifications flow freely all day. Outside the window
Meta requires a pre-approved template message (template support is a later
midas increment).

## The future inbound channel (terrain prepared)

Goal: send commands/questions TO midas from WhatsApp/Slack.

What already exists for it:

- The channel abstraction in `midas/notify.py` (config + credentials are
  shared by both directions).
- Meta side: the same app supports **webhooks** - Meta POSTs every incoming
  WhatsApp message to a URL you register. Slack side: a Slack app with
  event subscriptions does the same.

What the future increment adds:

- `midas listen` - a small webhook receiver (or polling bridge) that maps
  incoming messages to safe commands: `status`, `list`, `task RFD-123`,
  `approve RFD-123`, free-text questions routed to the utility model.
- An allowlist (only `whatsapp_to` / a Slack user id may command midas) and
  a confirmation step for anything that mutates state.

Until then, all interaction stays on this machine's CLI.
