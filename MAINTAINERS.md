# Maintainers

How reviewing and merging works on DentalPin. Short on purpose: this is the bar,
not a process manual. Contributor-facing rules live in [CONTRIBUTING.md](./CONTRIBUTING.md);
the ecosystem policy lives in [COLLABORATORS.md](./COLLABORATORS.md).

## Who

| Maintainer | GitHub | Scope |
|------------|--------|-------|
| Ramon Martinez | @martinezsalmeron | Project lead. Core, governance, releases. Final say. |
| Zoltán Dul | @ZoliQua | Reviews, tests and merges contributor PRs. |

## What a maintainer can merge

- Any PR from a contributor, **modules included**, once you have reviewed and
  tested it and CI is green. If you approve it, it goes in. Nobody second-guesses it.
- Paths listed in [`.github/CODEOWNERS`](./.github/CODEOWNERS) (core, `frontend/app/**`,
  `.github/**`, ADRs, license, security) additionally need the listed owner's review.
  Branch protection enforces this.
- Your own PRs go through another maintainer. You cannot approve yourself.

## What we protect

DentalPin is meant to become the open standard for running a clinic: an operating
system any provider or AI agent can plug into. Four things make that possible, and
every review is first a check that the PR does not erode them.

- **Modular architecture.** Modules are independent, installable, removable. Each
  owns its models, migrations, permissions and UI layer. The boundary is a contract,
  not a suggestion. A PR that reaches across it for convenience is a change request,
  however small the reach.
- **Event bus for cross-module reactions.** Modules react to each other through
  events, not through imports. Direct service-to-service calls only when the target
  is a declared dependency. Every new event goes into `EventType` and the catalog.
- **API first, agent ready.** Every capability lives in a service method, exposed
  through an HTTP endpoint and, when it makes sense for an agent, a `Tool`. The UI
  is a client of that API, never the only place a feature exists. If something can
  only be done by clicking, it is not finished.
- **No tech debt.** Nothing gets merged with the promise of "cleaning up later".
  Later does not come. A PR either does the thing properly or it waits. If a
  shortcut is genuinely unavoidable it is named in the PR description, has a known
  ceiling and a known upgrade path, and the reviewer agrees it is worth it.

## The bar

Ask these before approving. CI covers lint, tests, lockfile drift, manifest
consistency, catalog freshness and docs layout. It does **not** cover the rest.

1. **Tenant isolation.** Every query, tool handler and event consumer filters by
   `clinic_id`. This is the one thing that gets a PR blocked without discussion.
   Grep the diff for `select(` and `.where(` and check each one.
2. **Module boundary.** No imports or FKs across modules unless the target is in
   `manifest.depends`. Cross-module reactions go through the event bus.
3. **Migrations on the module's own branch.** `branch_labels=("<name>",)`, never
   chained through another module. Removable modules ship an uninstall round-trip test.
4. **Permissions.** Every new endpoint has `require_permission(...)`, the permission
   is returned from `get_permissions()`, granted in `role_permissions`, and in
   `frontend/app/config/permissions.ts` if user-facing.
5. **It runs.** Check it out, `docker-compose up`, install the module if needed,
   click through the screens it touches. Automated tests plus a manual visual pass.
   A green CI is not a substitute for opening the browser.
6. **Docs.** New screens have `docs/user-manual/{en,es}/<module>/screens/<slug>.md`.
   New events, permissions and tools are documented per the CLAUDE.md checklist.
   Module `CHANGELOG.md` updated under `## Unreleased`.
7. **Scope.** The PR does what its title says and nothing more. Drive-by refactors,
   new abstractions "for later", new dependencies for something a few lines can do:
   ask for them to be removed or split out.
8. **No tech debt smuggled in.** Silent shortcuts, TODOs without an issue, disabled
   tests, copy-pasted logic, "temporary" flags: change request. See "What we protect".
9. **API first.** Business logic in the service layer, routers thin, no logic that
   exists only in a Vue component. Agent-facing capabilities declared as a `Tool`
   that wraps the service method, filters by `ctx.clinic_id`, and carries the same
   permission string as the HTTP route.

Things that have bitten us more than once, worth a dedicated look:

- Diff far larger than the change suggests: check line endings (CRLF).
- Lazy-loaded relationships accessed in response schemas (`MissingGreenlet`).
- `USelect`/`USelectMenu` with an empty-string value breaks reka-ui. Use `null`.
- Module-layer locale files out of sync with the host locales, or a new locale
  missing from a module layer.
- `frontend/modules.json` rewritten by the running backend during a merge.
- `uv.lock` not regenerated after touching `pyproject.toml`.
- Tests that assume the module is installed in the DB; CI installs every module,
  local setups often do not.

## How to review

- Read the whole diff, not the summary. Use Claude or any other tool to speed it
  up, but the approval is yours, so verify what the tool claims.
- Request changes with a concrete list. One comment per issue, say what to change,
  not just what is wrong. Batch them; a PR should not get ten separate rounds.
- Small fixes you can make yourself (a typo, a missing i18n key, a `null` default):
  push to the contributor's branch if they allow it, say so in the PR, and merge.
  Anything beyond a few lines goes back to the author.
- Do not merge with failing CI. If CI is red for an unrelated reason (flaky job,
  main already broken), say so in the merge comment.
- If the PR reveals a design question (a new cross-module dependency, a new core
  slot, a new external service), stop and open a discussion or ping the lead
  before approving. That is what ADRs are for.

## Merging

- Merge commit (the repo history is merge-based, keep it that way).
- PR title in Conventional Commits, since it becomes the changelog line.
- After merge, close the linked issue if the PR did not do it automatically.
- Do not tag releases. The lead cuts them from the root `CHANGELOG.md`.

## When in doubt

Ask. A question in the PR or a message to the lead costs nothing. A merge that
leaks patient data across clinics costs the project its credibility.
