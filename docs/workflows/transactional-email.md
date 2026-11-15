# Transactional email for Dentum

This runbook configures SMTP delivery for staff invitations and access recovery. It does not create employee mailboxes; those are provisioned separately in the chosen mailbox provider.

## SMTP settings

Configure these values in the production environment used by `docker-compose.prod.yml` or `docker-compose.coolify.yml`:

```dotenv
EMAIL_ENABLED=true
EMAIL_PROVIDER=smtp
EMAIL_SMTP_HOST=<provider submission host>
EMAIL_SMTP_PORT=587
EMAIL_SMTP_TLS=true
EMAIL_SMTP_USER=<verified sender mailbox or SMTP username>
EMAIL_SMTP_PASSWORD=<provider app password or SMTP secret>
EMAIL_FROM_ADDRESS=noreply@dentum.online
EMAIL_FROM_NAME=Dentum
PUBLIC_URL=https://dentum.online
```

In Coolify, set `FRONTEND_URL=https://dentum.online`; the Compose file maps it to the backend's `PUBLIC_URL`.

Use the provider's SMTP submission endpoint and credentials. Do not use an employee's personal password. If the provider requires SSL-on-connect, configure a provider that supports STARTTLS on port 587 or update the SMTP transport settings for its documented port.

## Domain authentication

Add the exact DNS records supplied by the selected mail provider:

- SPF authorizes the provider to send for `dentum.online`. Keep one SPF TXT record and merge authorized senders into it rather than publishing multiple SPF records.
- DKIM publishes the provider's signing key under the selector it specifies.
- DMARC starts with a reporting policy, then can be tightened after legitimate messages pass SPF or DKIM alignment.

Do not guess SPF or DKIM values; they are provider-specific. Mailbox hosting may also require MX records and a `mail` host record. The Dentum application itself only needs authenticated SMTP submission and does not need inbound MX records to send invitations.

## Staff access messages

When an administrator creates a user without setting a password, Dentum creates a one-time password setup link and emails it. The same action on an existing user sends a fresh password reset link. Links expire after seven days and are single-use. If SMTP is unavailable, the user screen indicates this and leaves the link available for manual sharing.

System email currently does not send passwords. Staff set their own password from the one-time link.
