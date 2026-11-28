---
last_verified_commit: 0000000
---
# Online booking requests

An administrator must enable online booking and configure email and a public confirmation page. Availability follows the working hours of the professional chosen in the settings; appointments of other professionals do not block it. If that professional is deactivated or removed from the clinic, the public page stops offering times and taking requests until an administrator chooses an active professional. Booking can always be switched off; the removed professional is then cleared from the settings. The emailed link confirms a request; reception decides whether to accept or reject it. Confirming does not create an appointment.

A confirmed request holds its slot until reception decides or its start time. Before acceptance, the system checks appointments again and reports conflicts for reception to resolve. Rejected and expired requests are deleted after 30 days; contact information on accepted requests is erased after 90 days.

The public page ([booking page](screens/booking-page.md)) is part of DentalPin at `/p/booking/<clinic id>`; link to it or embed it in your website with an iframe. It lets visitors choose a visit type and time, provide contact details and complete ALTCHA. The email link requires selecting “Confirm request”; opening it does not create or confirm an appointment.

The calendar highlights dates with availability and lets visitors move between weeks. Phone and email are required. Authorized staff can edit the logo, color, page text, privacy-policy URL and the websites allowed to embed the page in “Public page settings”.

### Responsive iframe

Allow the host origin in booking settings. The host can resize the iframe after verifying the message origin and sender:

```html
<iframe id="booking" src="https://booking.example/p/booking/CLINIC_UUID" title="Book an appointment"></iframe>
<script>
const frame = document.querySelector('#booking');
window.addEventListener('message', (event) => {
  if (event.origin !== 'https://booking.example' || event.source !== frame.contentWindow) return;
  if (event.data?.type === 'dentalpin:booking:height' && Number.isFinite(event.data.height))
    frame.style.height = `${event.data.height}px`;
});
</script>
```

The parent must send a referrer that includes its origin; if absent or not allowlisted, no height message is sent. Local HTTP origins are accepted only in development.
