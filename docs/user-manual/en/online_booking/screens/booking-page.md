---
module: online_booking
screen: booking-page
route: /p/booking/[clinicId]
related_endpoints:
  - GET /api/v1/online_booking/public/{clinic_id}/config
  - GET /api/v1/online_booking/public/{clinic_id}/availability
  - GET /api/v1/online_booking/public/{clinic_id}/challenge
  - GET /api/v1/online_booking/public/{clinic_id}/logo
  - POST /api/v1/online_booking/public/{clinic_id}/requests
  - POST /api/v1/online_booking/public/{clinic_id}/confirm
related_permissions: []
related_paths:
  - backend/app/modules/online_booking/frontend/pages/p/booking/[clinicId].vue
  - backend/app/modules/online_booking/frontend/composables/usePublicBooking.ts
  - frontend/server/utils/bookingEmbed.ts
last_verified_commit: 64eb2ee
---
# Public booking page

Patients open this page without an account. It lives on your DentalPin address: `https://<your-dentalpin-address>/p/booking/<clinic id>`. **Public page settings** in [Online requests](requests.md) shows the exact address.

## What patients see

1. Choose the visit type, a day (days without free times are disabled; use the arrows to change week) and a time.
2. Enter first name, last name, email and phone (with the country code outside Spain). If enabled, they also answer "Are you already a patient?" and can add a short comment; the page asks them not to include medical information.
3. Tick the privacy-policy box, complete the ALTCHA check and send. The page then asks them to check their email.
4. The email link opens the same page with a **Confirm request** button. Opening the link does not confirm anything; pressing the button does. The request then waits for reception.

The page uses your logo, main color, title and introduction. It is available in the twelve languages of the application; visitors pick theirs in the selector, and the first guess comes from their browser. Spanish and English use your own title, introduction and visit-type names; other languages show translated standard text and the English visit-type names. If you configured a redirect URL, patients are sent there after sending the request.

## Link to the page

Put the address in a link or button on your website (it opens in a new tab or the same one). Also enter it as **Public page URL** in the settings: confirmation emails link there.

## Embed the page in your website

Use an iframe and list your website in **Websites allowed to embed the page** (one https origin per line, for example `https://www.myclinic.com`, with no path):

```html
<iframe
  src="https://<your-dentalpin-address>/p/booking/<clinic id>"
  title="Request an appointment"
  width="100%"
  height="900"
  style="border:0"
  loading="lazy"
></iframe>
```

Only the listed websites can show the page inside a frame; any other site sees a blank frame. Changes apply within about a minute. Keep **Public page URL** pointing at the DentalPin address, not at your website page: the confirmation link carries a token in the address that an iframe on your site would never receive.

Ask the person who runs your server to keep the booking page reachable from the internet if DentalPin itself is private (see the technical documentation for the exact paths).

## When the page says it is unavailable

The page shows "Online booking is unavailable right now" if booking is disabled, no professional or public URL is configured, or the address is wrong. If the **Privacy policy URL** is empty, the form is shown but cannot be sent.
