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

## Four preconditions. Miss any one and the gate does not run.

**1. The calling repository must be PRIVATE.**
`build-context` refuses to run unless `github.event.repository.private == true`,
and it fails closed — an absent or empty privacy flag counts as not private.
The reason is mechanical, not policy: the job pulls private registry content
into a workflow artifact, and artifacts on a public repo are downloadable by
anyone. On a public repo, gate the job off in your caller (`if:`) so it skips
cleanly instead of failing.

**2. The trigger must be `pull_request`. Never `pull_request_target`.**
The `review` job checks out PR-head code. `pull_request_target` would run it
with a read-write token in the base-repo context. `workflow_call` does not
restrict the invoking event, so this is on you.

**3. Both secrets, passed by name.** Both are declared `required: true`:

```yaml
    secrets:
      ANTHROPIC_API_KEY:             ${{ secrets.ANTHROPIC_API_KEY }}
      COMPOSER_RESOLVER_PRIVATE_KEY: ${{ secrets.COMPOSER_RESOLVER_PRIVATE_KEY }}
```

Passing only the API key fails at startup. Never `secrets: inherit`.

The mint step pairs `COMPOSER_RESOLVER_PRIVATE_KEY` with the **org variable**
`COMPOSER_RESOLVER_CLIENT_ID`, which arrives through the `vars` context — **the
consumer does not pass it.**

**4. Minimum job permissions:** `contents: read` and `pull-requests: write`.
No `actions:` scope — the two jobs hand off a same-run artifact.

---

## Pinning

Published tags read from the live remote 2026-09-10: `v1.0.0`, `v1.1.0`,
`v1.1.1`. **There is no `@v1` moving alias on this repo**, and `@main` is never
permitted.

`@v1.1.1` is the current recommendation: it carries the same `workflow_call`
interface as `v1.1.0` — both inputs, both required secrets, verified identical
— plus the checkout-target security fixes released after it. Parts of the
README still show `@v1.1.0`; both work, and `v1.1.1` is the better pin.

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

Put `sparxstar-specs.yml` at your repo root with flat `specs[]`, `contracts[]`
and `adrs[]` ID arrays. Without it the reviewer still runs, but findings cannot
cite a governing document — that declaration is what turns the reviewer from a
linter into a conformance gate.

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
The composer-resolver App must be *scoped* to every repo the workflow reads —
for this gate that means **both** internal registries as well as the caller.
Installing the App org-wide is not the same as scoping it. This is the
most common misconfiguration on this platform and the error text never says so.

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
