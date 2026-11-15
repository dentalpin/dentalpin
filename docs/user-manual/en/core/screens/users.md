---
module: core
screen: users
route: /settings/people/users
last_verified_commit: 71402014
---

# Clinic users

Administrators can add staff accounts and manage their access from **Settings → People → Users**.

## Add a staff member

1. Select **New user** and enter the employee's name, email address, and role. You may leave the password blank or enter a temporary one.
2. Dentum creates a one-time setup link and emails it when SMTP delivery is configured. The employee can choose their own password from that link, even if you entered a temporary password.
3. The screen reports whether the email was sent and keeps the link available to copy or share manually. Dentum never includes a password in the email.
4. The employee opens the link, chooses a password, and signs in. The link expires after seven days and can be used once.

## Resend access or reset a password

Use the access-link action on the employee's row. Dentum creates a fresh one-time link and emails it when SMTP is available. You can also copy the link and share it directly. Treat the link like a password: anyone who has it can set the account password.

Email delivery requires an SMTP provider configured for the Dentum instance. See the deployment email runbook if the screen says it could not send the message.
