# Security policy

DentalPin holds patient health data. Treat anything that touches
authentication, tenant isolation or clinical records as high severity by
default.

## Reporting a vulnerability

Report privately through
[GitHub Security Advisories](https://github.com/martinezsalmeron/dentalpin/security/advisories/new).
Never open a public issue for a vulnerability.

Expect an acknowledgement within 72 hours. We will tell you what we found,
what we intend to do, and when — and credit you in the advisory unless you
ask us not to.

## Supported versions

The latest release on `main`. There are no long-term support branches yet;
if you run a pinned `DENTALPIN_VERSION`, upgrading is the fix path.

## What we consider a vulnerability

- **Cross-tenant data access.** Any query reaching a row from another
  `clinic_id`. Every multi-tenant table filters on it — a path that skips
  the filter is a breach, not a bug.
- **Permission bypass.** Reaching an endpoint, or an agent tool, without
  the RBAC permission that gates it.
- **Copilot boundary escapes.** The agent re-checks permissions at the
  execution chokepoint and redacts PHI before anything reaches an LLM
  provider. Getting past either is in scope, including prompt injection
  that induces a tool call the calling user could not make themselves.
- Authentication and token handling, stored/reflected XSS, SQL injection,
  SSRF, and unauthenticated access to stored media.

## Out of scope

Findings against `demo.dentalpin.com` that only affect seeded demo data,
missing hardening headers with no demonstrated impact, rate-limit tuning,
and reports from automated scanners with no working proof of concept.
