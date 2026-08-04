# How to test a booking from a tour page (AS / review)

**Base URL:** `https://review.as.k8s.seeds.no/` (replace host per environment)

## 1. Start from a tour page

Example: [Sognefjord Adventure](https://review.as.k8s.seeds.no/tours/sognefjord-adventure)

1. Set travel start date on `#bookingStartDateVal` (hidden; e.g. `2026-10-26`).
2. Set end date on `#bookingEndDateVal` = start date + `#tourDuration` (in days).
3. Optionally sync the visible `#date` field (`dd.mm.yy - dd.mm.yy` format).
4. Click `#bookNowButton`.
5. Wait for the step-by-step booking wizard (`/booking/booking-details?bookingId=<booking-id>`). Navigation is automatic when clicking Next through steps.

## 2. Contact step

Use a dummy **French** customer with **generic names** (e.g. **John Smith** / **Jane Smith**) and email **`williams.ramos@99x.io`**.

Fill required fields:

- Contact: `#booking_personalTitle` (Mr/Mrs), `#booking_firstName`, `#booking_lastName`, `#booking_country` = France, `#booking_email` = `williams.ramos@99x.io`, `#booking_zip` (not `booking_zipCode`), phone
- Travellers per room: `#guestTitle_0_0` / `#guestTitle_0_1` (title), `#roomInput_0_0_firstName`, `#roomInput_0_0_lastName`, `#roomInput_0_0_nationality` (e.g. French), DOB via `#roomInput_0_0_birthday` (`dd/mm/yyyy`) **and** `#roomInput_0_0_day/month/year` selects

Tick agreement checkboxes (e.g. `#acceptBooking` on payment step), click **Next** / **Proceed**.

See also [How to test AS-1173 payment due date](./How-to-test-AS-1173-payment-due-date.md) for remaining-payment email scenarios.

## 3. Payment step

URL pattern: `/booking/payment?bookingId=<booking-id>`

1. Tick `#acceptBooking` (terms and conditions checkbox).
2. Click **Payment**.
3. Complete payment in the gateway (manual — tester performs card/payment flow).
4. Wait for redirect to `/booking/request-sent?bookingId=<booking-id>`.

**Payment Info:** Click the Payment Info button (class `sidepanel__payment-info--link`) to open a modal with payment conditions (e.g. deposit 10% for default site condition).

Once request-sent is reached, the booking is **no longer Pending**.

## 4. Verify booking in Content Studio

1. Open [Content Studio](https://review.as.k8s.seeds.no/admin/tool/com.enonic.app.contentstudio/main) (requires `/admin` login).
2. Open **Search Panel**, search by **booking ID** from the booking URL.
3. Select the booking → **Edit**.
4. Inspect `booking-payment-condition` x-data (should be populated after fix).

**Saving in Content Studio:** Always **Apply**, click out, **Save**, **Mark as Ready**, **Publish**.

## 5. Change tour payment condition (regression test)

From Content Studio, search **Sognefjord Adventure** tour:

1. Edit → set Payment Condition to **"Deposit 30% + Final 95 days"** (tick correct checkbox).
2. **Apply**, click out, **Save**, **Mark as Ready**, **Publish**.

## 6. Confirm snapshot on finished booking

Return to the **Request Sent** page for the booking created above.

Open **Payment Info** modal again.

**Expected (AS-1172):** Modal still shows the **original** condition (e.g. Deposit 10%) — it must **not** change to Deposit 30%.

## Troubleshooting

If stuck on any step, check for:

- Required **agreement** checkboxes
- **Next**, **Proceed**, **Payment**, **Apply**, or **Close** buttons
