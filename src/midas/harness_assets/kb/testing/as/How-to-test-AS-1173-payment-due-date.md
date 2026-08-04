# How to test AS-1173 — payment due date

**Base URL:** `https://review.as.k8s.seeds.no/`  
**Related:** [How to test a booking from a tour page](./How-to-test-a-booking-from-a-tour-page.md)

## Goal

Verify `{final_payment_due_date}` in the **`remainingPaymentEmail`** clamps to **today** when the countback date is in the past. Fixed `paymentDueDate.endDate` must not be clamped.

## Pick travel dates first (mandatory)

Anchor **today on review** (e.g. 2026-06-24). Run the matrix before booking.

### Payment conditions (review)

| Condition | Deposit | Final due | Travel availability |
|-----------|---------|-----------|-------------------|
| `deposit-30-final-95-days` | 30% | travel − **95** days | 2026-01-01 – **2026-09-30** |
| `due-date-20-on-2026-11-20` | 20% | fixed **2026-11-20** | **2026-10-01** – 2026-12-31 |
| Site default | 10% | travel − **65** days | fallback |

### Tours

| Tour | Slug |
|------|------|
| Sognefjord Adventure | `sognefjord-adventure` |
| Oslo-Bergen | `oslo-bergen-and-fjord-experience` |

### Date selection matrix (T = today)

| Intent | Tour | Travel start | Payment at booking |
|--------|------|--------------|-------------------|
| **`remainingPaymentEmail` (AS-1173)** | Sognefjord | **Aug 15** (&lt;95d in deposit-30 avail) | **Full** total |
| 30% modal — future due | Sognefjord | **Sep 28** (≥95d, ≤ Sep 30) | 30% deposit |
| Site default modal | Sognefjord | **Oct 26** | 10% deposit |
| Fixed date modal | Oslo-Bergen | **Oct 26** | 20% deposit |

**Do not** use a deposit booking for the remaining-payment email test — deposit CF sends `confirmedEmail` (`confirmedEmailSent`), not `remainingPaymentEmail`.

## Trigger `remainingPaymentEmail`

Template: **`remainingPaymentEmail`**. Outlook search: **`outstanding`**. Flag: **`confirmedLastMinuteEmailSent`** (not `confirmedEmailSent`).

**Code path** (`captureAndRecordPayment` in `bookings/index.js`):

1. Booking must be **full payment** at Flywire (`transaction.deposit = false`, `status = Complete`).
2. On Tourplan **CF**, `numericPriceTotal` (from Tourplan) must be **greater than** the captured/reserved amount.
3. Then `remainingPayment > 0` → `remainingPaymentEmail`.

**Manual Tourplan price edit is valid** to force the bump if the live quote does not exceed the reserved amount.

| Tourplan vs reserved | Email | Flag |
|---------------------|-------|------|
| Total **&gt;** reserved (full pay) | `remainingPaymentEmail` | `confirmedLastMinuteEmailSent` |
| Total **&lt;** reserved | `creditPaymentEmail` | `confirmedLastMinuteEmailSent` |
| Deposit CF (any Tourplan total) | `confirmedEmail` | `confirmedEmailSent` |

## Payment Info modal

Click `.sidepanel__payment-info--link` → loads in `#experienceModal`.

| Case | Modal | Due in copy |
|------|-------|-------------|
| Full pay (&lt;95d on deposit-30) | Less than 65 days | N/A |
| 30% More65 | More than 65 days | travel − 95 days |
| 10% site default | More than 65 days | travel − 65 days |
| 20% fixed | More than 65 days | **Nov 20, 2026** |

## Booking wizard

- Generic contact: **John Smith** / **Jane Smith**, `williams.ramos@99x.io`, France
- Zip field: `#booking_zip` (not `booking_zipCode`)
- Travellers: `#guestTitle_0_0`, `#roomInput_0_0_birthday` + day/month/year selects

## Evidence

`~/.cursor/prds/AS-1173/evidence/` — plan: `~/.cursor/plans/AS-1173-evidence-plan.md`

## Sample data (T = 2026-06-24)

| Scenario | Tour | Travel | Pay at booking |
|----------|------|--------|----------------|
| Remaining email | Sognefjord | 2026-08-15 | Full |
| 30% modal | Sognefjord | 2026-09-28 | 30% |
| Site default | Sognefjord | 2026-10-26 | 10% |
| Fixed 20% | Oslo-Bergen | 2026-10-26 | 20% |
| Tourplan bump example | — | — | Reserved 2415 → set **2500+** |
