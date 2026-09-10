# SETUP — consuming the Claude PR reviewer

**What this repo is.** A reusable workflow that reviews a pull request against
the platform's ADRs, product specs and interface contracts, and posts a single
upserted comment. Three independently-attributed tiers — Spec Conformance,
Contract Seam, ADR Drift — each citing the document ID it judged against.

It **reads** the registries. It never writes back.

> **This file is a router.** The authoritative consumer interface is
> [`README.md`](./README.md) ("Setup & Install") and
> [`docs/consumer-setup.md`](./docs/consumer-setup.md), both written from the
> live workflow. Read them for the full contract; this page covers the four
> things that decide whether the gate runs at all.

> **New repo?** `.github/workflows/standards.yml` in the
> `starisian-technologies-proprietary-license` template already contains a
> correctly-pinned, correctly-gated caller. Start from
> `GOVERNANCE-SETUP.md` there rather than hand-writing one.

---

## Five preconditions. Miss any one and the gate does not run.

Four are yours (the caller). The fifth is org infrastructure, and it is the one
a consumer can satisfy every other item without noticing.

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

> `README.md` and `docs/consumer-setup.md` told consumers they may use
> `pull_request` **and/or `push`**. The live workflow disagrees: the
> `Get PR diff` step exits 1 with "No pull request number found in the
> workflow event payload" whenever the event carries no PR number — which is
> every push. A caller following that guidance got a failing run, not a
> review. Code wins; both lines are corrected in this PR.

**3. Both secrets, passed by name.** Both are declared `required: true`:

```yaml
    secrets:
      ANTHROPIC_API_KEY:             ${{ secrets.ANTHROPIC_API_KEY }}
      COMPOSER_RESOLVER_PRIVATE_KEY: ${{ secrets.COMPOSER_RESOLVER_PRIVATE_KEY }}
```

Passing only the API key fails at startup. Never `secrets: inherit`.

The mint step pairs `COMPOSER_RESOLVER_PRIVATE_KEY` with the variable
`COMPOSER_RESOLVER_CLIENT_ID`, which arrives through the `vars` context — **the
consumer does not pass it.** Organization-scoped is the normal setup, but a
repository-scoped variable resolves through `vars` just as well; the
workflow's own error text names both.

**5. `COMPOSER_RESOLVER_CLIENT_ID` must be set and the App scoped to both
registries.** This is infrastructure, not caller config, and it is the
precondition that bites: `build-context`'s "Validate composer-resolver
configuration" step exits 1 when the variable is empty, before any token is
minted. See [Troubleshooting](#troubleshooting) for the scope half.

**4. Minimum job permissions:** `contents: read` and `pull-requests: write`.
No `actions:` scope — the two jobs hand off a same-run artifact.

---

## Pinning

Published tags read from the live remote 2026-09-10: `v1.0.0`, `v1.1.0`,
`v1.1.1`. **There is no `@v1` moving alias on this repo**, and `@main` is never
permitted.

**Pin `@v1.1.0`.** That is this repo's enforced canon, not just a preference:
`tests/test_workflow_contract.py` asserts it in both `README.md` and the
consumer example, so it is the one pin the repo's own CI defends.

`v1.1.1` exists and carries the checkout-target security fixes released after
`v1.1.0`. Its `on.workflow_call` block is identical — both inputs, both
required secrets, compared directly. So it is technically a drop-in and
arguably the better pin. It is deliberately **not** recommended here, because
recommending it from this page alone would create two competing "current"
pins across documents that route readers to each other.

Promoting `v1.1.1` is a single owner-approved change touching
`README.md`, the consumer example and `test_workflow_contract.py` **together**
— not a line edit in one file.

### `contract_ref` is a different version axis

`contract_ref` names a tag on the **registries**, not on this repo. Default
`v1.0.0`. Only the ref *shape* is validated here; the registry checkout fails
if the tag does not exist. This gate enforces no version floor — that is the
fetch and version gates' job, not the reviewer's.

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

**The job never appears.** Work preconditions 1–4 above in order. Private?
`pull_request`? Both secrets visible? Permissions?

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
