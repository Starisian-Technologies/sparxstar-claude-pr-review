# SETUP — consuming the Claude PR reviewer

**What this repo is.** A reusable workflow that reviews a pull request against
the platform's ADRs, product specs and interface contracts, and posts a single
upserted comment. Three independently-attributed tiers — Spec Conformance,
Contract Seam, ADR Drift — each citing the document ID it judged against.

It **reads** the registries. It never writes back.

> **This file is a router.** The authoritative consumer interface is
> [`README.md`](./README.md) ("Setup & Install") and
> [`docs/consumer-setup.md`](./docs/consumer-setup.md), both written from the
> live workflow. Read them for the full contract; this page covers the five
> things that decide whether the gate runs at all.

> **New repo?** The `starisian-technologies-proprietary-license` template is
> gaining a correctly-pinned, credential-gated caller
> (`.github/workflows/standards.yml`) and a setup checklist
> (`GOVERNANCE-SETUP.md`). Both are on that repo's open governance-wiring PR,
> **not yet on its default branch** — check there before hand-writing a
> caller, and prefer them once merged.

---

## Five preconditions. Miss any one and the gate does not run.

Four are yours (the caller). The fifth is org infrastructure — the one a
consumer can miss while satisfying all four others, which is exactly why it is
the one that bites.

**1. The calling repository must be PRIVATE.**
`build-context` refuses to run unless `github.event.repository.private == true`,
and it fails closed — an absent or empty privacy flag counts as not private.
The reason is mechanical, not policy: the job pulls private registry content
into a workflow artifact, and artifacts on a public repo are downloadable by
anyone. On a public repo, gate the job off in your caller (`if:`) so it skips
cleanly instead of failing.

**2. The trigger must be `pull_request`. Never `pull_request_target`, and —
despite what the companion docs say — not `push` either.**
The `review` job checks out PR-head code. `pull_request_target` would run it
with a read-write token in the base-repo context. `workflow_call` does not
restrict the invoking event, so this is on you.

> The live workflow rejects pushes: `Get PR diff` exits 1 with "No pull
> request number found in the workflow event payload" whenever the event
> carries no PR number — which is every push. Four places told consumers
> otherwise, and all four are corrected in this PR: `README.md`'s
> determinism note, its troubleshooting line, and — the one that actually
> gets copied — the `push:` trigger in the **copy-paste caller block**, plus
> `docs/ci-cd.md`'s "use both triggers for complete coverage".
> `docs/consumer-setup.md` never carried the push guidance; an earlier
> revision of this note wrongly named it.

**3. Both secrets, passed by name.** Both are declared `required: true`:

```yaml
    secrets:
      ANTHROPIC_API_KEY:             ${{ secrets.ANTHROPIC_API_KEY }}
      COMPOSER_RESOLVER_PRIVATE_KEY: ${{ secrets.COMPOSER_RESOLVER_PRIVATE_KEY }}
```

Passing only the API key fails at startup — that one is mechanical.

`secrets: inherit` is a separate matter: GitHub Actions permits it, and it
would work here. The platform forbids it anyway, as least-privilege policy —
a caller passes only the named secrets a workflow declares, never its whole
secret store. Treat it as a rule you follow, not a thing that breaks.

The mint step pairs `COMPOSER_RESOLVER_PRIVATE_KEY` with the variable
`COMPOSER_RESOLVER_CLIENT_ID`, which arrives through the `vars` context — **the
consumer does not pass it.** Organization-scoped is the normal setup, but a
repository-scoped variable resolves through `vars` just as well; the
workflow's own error text names both.

**4. Minimum job permissions:** `contents: read` and `pull-requests: write`.
No `actions:` scope — the two jobs hand off a same-run artifact.

**5. `COMPOSER_RESOLVER_CLIENT_ID` must be set, and the App scoped to both
registries.** `build-context`'s "Validate composer-resolver configuration"
step exits 1 when the variable is empty, before any token is minted; an App
that is installed but not *scoped* fails later, at ref resolution.

The variable half a repository admin can fix (a repo-scoped variable resolves
through `vars` perfectly well). **The App scoping half needs an org owner** —
that is the part no amount of caller-side configuration reaches. See
[Troubleshooting](#troubleshooting).

---

## Pinning

Published tags read from the live remote 2026-09-10: `v1.0.0`, `v1.1.0`,
`v1.1.1`. **There is no `@v1` moving alias on this repo**, and `@main` is never
permitted.

**Pin `@v1.1.1`.** It carries the checkout-target security fixes released
after `v1.1.0`, and its `on.workflow_call` block is identical — both inputs,
both required secrets, compared directly — so it is a drop-in.

This is the repo's canon, not just this page's preference: `README.md`, the
consumer example in `examples/` and `tests/test_workflow_contract.py` are all
promoted to `v1.1.1` in this PR, together. An earlier revision of this page
recommended `v1.1.0` because that was what the tests then asserted, which had
the perverse effect of steering new consumers onto the older security posture
while naming the newer tag as the fixed one. Promoting all four at once
removes the contradiction rather than documenting it.

### `contract_ref` is a different version axis

`contract_ref` names a tag on the **registries**, not on this repo. Default
`v1.0.0`. Only the ref *shape* is validated at input.

If the tag does not exist, the failure comes from the **`Resolve contract ref
SHAs`** step — `::error::Unable to resolve contract_ref '<ref>' in ADR
registry` — which runs *before* either checkout, because the workflow resolves
the ref to an immutable commit SHA first so the tag cannot move underneath the
job. Don't go looking at the checkout steps.

This gate enforces no version floor — that is the fetch and version gates'
job, not the reviewer's.

Both the ADR registry and the product-spec registry currently carry `v1.0.0`
and `v1.0.1`, so either resolves. Do not bump `contract_ref` in the same reflex
as the `uses:` pin; they move independently.

---

## Declaring what governs your repo

Put `sparxstar-specs.yml` at your repo root. Without it the reviewer still
runs, but findings cannot cite a governing document — that declaration is what
turns the reviewer from a linter into a conformance gate.

**The shape is a list of maps with `id:` keys, and the parser is strict:**

```yaml
specs:
  - id: rlc-games
contracts:
  - id: cross-repo-lineage-node-contract
adrs:
  - id: ADR-011
```

It is a regex parser, not a YAML engine. Two shapes that look reasonable are
**silently ignored** — no error, just `(none declared)`:

- `specs: [rlc-games]` — the section header must be `specs:` with nothing
  after it, so an inline array is never even entered.
- `- rlc-games` — a bare scalar list item. Only `- id: <value>` is matched.

A declaration in either of those shapes leaves the repo reading as governed
while the reviewer sees nothing. Check a run's log for the declared IDs after
you first fill this in.

It is read from the pull request's **base** commit, never the PR head, so a PR
cannot widen the scope it is reviewed against by editing the file in the same
PR. Parsing is a stdlib regex parser, not a full YAML engine — keep the shape
flat.

Look every ID up before writing it. An ID that does not resolve is worse than
an empty list: the repo reads as governed when it is not.

---

## Troubleshooting

**`repository not found` right after a token minted successfully.** The mint
proves the App exists and the key is valid; it proves nothing about **scope**.
The composer-resolver App must be *scoped* to the two repos this gate reads —
`sparxstar-architecture-governance-registry` and
`sparxstar-product-specification-registry` — with Contents: Read. Installing
the App org-wide is not the same as scoping it. This is the most common
misconfiguration on this platform and the error text never says so.

**The App does not need access to your own repo.** The two mint steps scope
their tokens to the registries by name, and the PR-head checkout uses the
default `GITHUB_TOKEN` with `persist-credentials: false` — no App credential
is involved. Adding the caller to the App's repository access grants
cross-repo reach this gate never uses.

**The job never appears.** Work all five preconditions above in order.
Private? `pull_request`? Both secrets visible? Permissions? And the one
that is not caller config: is `COMPOSER_RESOLVER_CLIENT_ID` set, and is the
App scoped to both registries?

**A secret error at startup.** Secrets do not cross `workflow_call`
automatically. Open your caller and this repo's `on.workflow_call.secrets`
block at the tag you pinned, in the same sitting, and compare the exact names.

---

## Credentials

Defined once, in the Cross-Repo Access Standard:

> `sparxstar-product-specification-registry` →
> `specs/_platform/SPARXSTAR-CROSS-REPO-ACCESS-STANDARD.md`

Do not restate the mint block in your repo. Link to it.

---

## Related

| You need | Go to |
|---|---|
| Wiring a brand-new repo, end to end | `starisian-technologies-proprietary-license` → `GOVERNANCE-SETUP.md` |
| Full consumer interface for this gate | [`README.md`](./README.md), [`docs/consumer-setup.md`](./docs/consumer-setup.md) |
| ADRs and invariants | `sparxstar-architecture-governance-registry` → `SETUP.md` |
| Product specs | `sparxstar-product-specification-registry` → `SETUP.md` |
| Interface contracts | `sparxstar-contracts-registry` → `SETUP.md` |
| Lint/style enforcement | `sparxstar-code-conformance` → `SETUP.md` |
