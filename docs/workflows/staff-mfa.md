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
store. Restrict access to deployment operators and keep an encrypted
backup of the key separately from the database backup. Record which
key version goes with each backup and test restoring them together.
The backend validates configured MFA key formats before accepting requests.

> [!WARNING]
> Losing `MFA_ENCRYPTION_KEY` locks out every user with 2FA, including
> administrators. Restoring the factors requires the database backup and its matching key.
> Preserve the exact key, and retain older keys while matching backups
> are recoverable.

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

If no administrator can sign in, an operator with access to the backend
container can reset one account from the deployment CLI. Use a clinic UUID
to constrain account lookup when needed.

```sh
docker compose run --rm backend python -m app.cli mfa reset \
  --email staff@example.test --clinic 00000000-0000-4000-8000-000000000001
```

The command asks for confirmation. Use `--yes` for an explicitly approved
noninteractive reset. The reset removes the authenticator secret, recovery
codes and outstanding challenges, and revokes the account's sessions across
all clinics. If a clinic policy requires MFA for that user, the next sign-in
requires enrollment. The CLI can remove old factors even with a missing or invalid key. Restore the original key if possible, or
configure a new valid key before enrolling users again.

The `auth_mfa_audit` table stores the user ID, event, time and clinic ID
when scoped. A web reset includes the acting staff member's ID. A CLI reset
has a null actor ID and is attributable to the deployment operator through
the deployment's own access logs. Audit rows carry no passwords, keys,
recovery codes or challenge tokens.
