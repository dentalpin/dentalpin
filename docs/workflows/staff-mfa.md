---
last_verified_commit: 0000000
---

# Staff MFA operations

The clinic policy is off on existing installations until an administrator
changes it in **Settings → General → Clinic two-factor authentication**.
Generate a dedicated Fernet key in a trusted backend environment.

```sh
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Store the value as `MFA_ENCRYPTION_KEY` in the backend deployment secret
store. Back up that key with the deployment's secrets and restrict access
to operators who can manage authentication. A database backup needs the
matching MFA key to restore staff authenticator access. Activating a clinic
policy requires a valid key.

## Rotate the encryption key

1. Generate a new Fernet key. Retain the current key securely as
   `MFA_PREVIOUS_ENCRYPTION_KEY` and set the new value as
   `MFA_ENCRYPTION_KEY`.
2. Restart the backend workers with both values. In a staged rollout, make
   sure all workers read both keys before traffic can be routed to a worker
   that encrypts with the new key. For a single Compose deployment, stop the
   old backend before starting the replacement.
3. Run the rotation inside the configured backend:
   `docker compose exec backend python -m app.cli mfa rotate-keys`.
   It re-encrypts committed credentials in one transaction and prints the
   count. A failed rotation rolls back the transaction.
4. Wait five minutes after the last worker using the old primary key stops
   issuing challenges, then remove the previous key from runtime
   configuration. Retain it for backups encrypted before the rotation.

Rotating the JWT signing secret does not change the staff TOTP key. Preserve
access to the previous key if a rotation needs to be retried.

## Staff recovery

Staff can sign in with an unused recovery code. An administrator of all the
affected user's clinics can reset their factor under **Settings → People →
Users**. The reset revokes that user's sessions, requires setup at the next
sign-in and leaves an audit record.

The `auth_mfa_audit` table stores the user ID, actor ID, event, time and clinic
ID for a clinic-scoped reset. Its records carry no passwords, authenticator
keys, recovery codes or challenge tokens.
