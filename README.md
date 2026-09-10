# SPARXSTAR Claude PR Review

> **Wiring this gate into a repo? Read [`SETUP.md`](./SETUP.md) for the four preconditions that decide whether it runs at all — private repo, `pull_request` trigger, both secrets, permissions. The Setup & Install section below and [`docs/consumer-setup.md`](./docs/consumer-setup.md) are the full interface.**

[![Claude PR Review (Reusable)](https://github.com/Starisian-Technologies/sparxstar-claude-pr-review/actions/workflows/claude-pr-review.yml/badge.svg)](https://github.com/Starisian-Technologies/sparxstar-claude-pr-review/actions/workflows/claude-pr-review.yml)

Centralized reusable GitHub Actions workflow for Claude-powered pull request and commit review to repository specs across Starisian Technologies repositories.

## What this repository provides
- Reusable review workflow: `.github/workflows/claude-pr-review.yml`
- Consumer integration example: `examples/consumer-workflow.yml`
- Governance baseline: contributing, security, support, code ownership, issue/PR templates
- Operational docs for architecture, CI/CD, deployment, and upgrade/rollback
- Platform reference docs injected into review context: `reference/*.md`

## Setup & Install (consuming repositories)

Every identifier below is read from this repo's live `.github/workflows/claude-pr-review.yml` and its actual tags. The detailed companion is [`docs/consumer-setup.md`](docs/consumer-setup.md).

### 0. Prerequisites (do this first — the gate cannot run without it)
This gate mints GitHub App tokens to clone two **private** registries, so org-level setup must exist before any consumer can call it:

- **GitHub App — `composer-resolver` (required).** The mint steps use `actions/create-github-app-token@v3` (`owner: Starisian-Technologies`) to mint installation tokens for `sparxstar-architecture-governance-registry` and `sparxstar-product-specification-registry`. The consuming org must have **composer-resolver** installed and scoped to **both** repos with **Contents: Read** (the gate only reads them — there is no write/push App). Verify in **org Settings → GitHub Apps → composer-resolver → Repository access**. An App existing org-wide is *not* the same as being scoped to these two repos — that mismatch is the most common misconfiguration, and it surfaces at the registry checkout as an opaque `repository not found`, not a clear "scope the App" message.
- **Secrets** (Settings → Secrets and variables → Actions → **Secrets**): `ANTHROPIC_API_KEY` and `COMPOSER_RESOLVER_PRIVATE_KEY`.
- **Variable** (same screen → **Variables**, *not* Secrets): `COMPOSER_RESOLVER_CLIENT_ID` — holds the App **client-id string** (`actions/create-github-app-token@v3` takes `client-id:`; the legacy `app-id` is also accepted, but this workflow passes `client-id`). It must be a **Variable**, not a Secret: the mint reads it via the `vars` context, so a value placed in a Secret slot is invisible to `vars.COMPOSER_RESOLVER_CLIENT_ID` and reads as empty. A missing or misplaced value is **not** a silent failure — the `Validate composer-resolver configuration` step fails fast with an explicit "COMPOSER_RESOLVER_CLIENT_ID variable is not set" error before any token is minted.
- **Who provisions:** App install + org secret/variable creation need org-admin. A missing prerequisite surfaces as "repository not found" or an empty-credential error at the mint/checkout step — not a clear "you forgot to install the App." Check prerequisites first on any auth failure.

### 1. What this gate does
`claude-pr-review.yml` is a reusable workflow that reviews a pull request against the platform's ADRs and product specs. It fetches those contracts from the two private registries, sends the PR diff plus that context to the Anthropic Messages API, and upserts a single review comment with a PASS / FAIL / CONDITIONAL verdict. It is **advisory** — the comment is the deliverable; a FAIL verdict does not fail the job or block merge.

### 2. The `uses:` line and which tag to pin
Pin an **immutable release tag** — the current platform default is **`v1.1.0`**. There is **no `@v1` moving alias** published, so don't pin `@v1` (it won't resolve); `git ls-remote --tags origin` lists the release tags that currently exist. Pin the immutable release tag:

```yaml
uses: Starisian-Technologies/sparxstar-claude-pr-review/.github/workflows/claude-pr-review.yml@v1.1.0
```

Do not reference `@v1` (not published) or `@main` (moving branch). Future releases require a new pin.

### 3. Inputs (`on.workflow_call.inputs`)
- `contract_ref` — *optional* (`required: false`), string, default `v1.0.0`. Git ref (tag) of the ADR + product-spec **registries** to review against. Validated here only for safe ref *shape*; the registry checkout fails if the tag doesn't exist on the registries. This gate does **not** enforce a version floor. The default resolves only if the registries actually carry a `v1.0.0` tag.

No outputs are declared.

### 4. Secrets the consumer passes
Both are declared `required: true`. Pass each **by name**; `secrets: inherit` is not used (pass only the named secrets the workflow needs):

```yaml
    secrets:
      ANTHROPIC_API_KEY:             ${{ secrets.ANTHROPIC_API_KEY }}
      COMPOSER_RESOLVER_PRIVATE_KEY: ${{ secrets.COMPOSER_RESOLVER_PRIVATE_KEY }}
```

The mint step pairs the secret you pass (`COMPOSER_RESOLVER_PRIVATE_KEY`) with the **org variable `COMPOSER_RESOLVER_CLIENT_ID`**, which propagates via the `vars` context — **the consumer does not pass it.**

### 5. Required caller setup
- **Trigger:** `pull_request` (the gate needs PR context and the `review` job reads PR-head code). **Never `pull_request_target`.**
- **Minimum job permissions:** `contents: read` + `pull-requests: write`. No `actions:` scope needed (the two jobs hand off a same-run artifact).
- **Caller repo must be private** — `build-context` refuses to run unless `github.event.repository.private == true`.
- **Required files in the consumer repo:** none. The gate is self-contained.

### 6. Minimal copy-paste caller block
```yaml
# .github/workflows/claude-pr-review.yml  (in your consuming repo)
name: Claude PR Review

on:
  pull_request:
    types: [opened, synchronize, reopened]
  push:

jobs:
  review:
    permissions:
      contents: read
      pull-requests: write
    uses: Starisian-Technologies/sparxstar-claude-pr-review/.github/workflows/claude-pr-review.yml@v1.1.0
    with:
      contract_ref: v1.0.0          # ← must name a tag that exists on the registries
    secrets:
      ANTHROPIC_API_KEY:             ${{ secrets.ANTHROPIC_API_KEY }}
      COMPOSER_RESOLVER_PRIVATE_KEY: ${{ secrets.COMPOSER_RESOLVER_PRIVATE_KEY }}
```

### 7. The sequencing rule (cross-repo)
Secrets don't auto-inherit across the `workflow_call` boundary: this reusable workflow must **declare** a secret under `on.workflow_call.secrets` before a consumer can pass it, and this repo must **re-tag** afterward so the pinned tag contains the declaration. The `v1.1.0` release declares both `ANTHROPIC_API_KEY` and `COMPOSER_RESOLVER_PRIVATE_KEY`, so once that tag is cut, a consumer pinning `@v1.1.0` and passing both is consistent. A future change to the declared secrets requires cutting a new tag (e.g. `v1.1.1`) before consumers can pin it and pass them.

## Workflow behavior
The workflow runs as two jobs to keep the privileged registry credential away from untrusted PR-head code (see [Determinism and safeguards](#determinism-and-safeguards)):

**Job `build-context` (privileged, never checks out PR-head code):**
1. Mints short-lived, least-privilege read tokens (one per registry) from the composer-resolver GitHub App.
2. Checks out the private ADR (`sparxstar-architecture-governance-registry`) and product-spec (`sparxstar-product-specification-registry`) registries at `contract_ref`, plus this repo's `reference/*.md`.
3. Assembles the authoritative ADRs, product specs, and platform reference docs into a trusted-context artifact.

**Job `review` (unprivileged, holds only `ANTHROPIC_API_KEY`):**
4. Loads the PR diff and repo-local context (`AGENTS.md`, `.github/copilot-instructions.md`, selected markdown docs) — reading PR-head files as data only, never executing them.
5. Downloads the trusted-context artifact and builds a deterministic prompt from diff + context.
6. Calls the Anthropic Messages API and upserts a single review comment on the PR.

The reviewer only reads the registries — there is no contract-sync or write-back.

## Determinism and safeguards
- Callers must use the `pull_request` trigger — **never `pull_request_target`**, and not `push`: the `Get PR diff` step exits 1 when the event payload carries no pull request number, so a push run fails before any review is produced. The review job checks out PR-head code, and `pull_request_target` would run it with a read-write token in the base-repo context. `workflow_call` alone does not restrict invocation to these events; unsupported events are rejected at runtime
- **Privilege split (CodeQL hardening):** the composer-resolver GitHub App key — the only credential that can reach private registries — lives solely in the `build-context` job, which never checks out PR-head code. The `review` job checks out PR-head code but holds no App key and only *reads* those files as data (no build/install/script execution); trusted context crosses between jobs via artifact only
- **Private callers only:** the trusted context (private ADR/spec content) is staged as a workflow artifact, which would be downloadable by anyone on a public repository. `build-context` fails fast (before minting any token) unless the caller repository is private
- Diff truncation at 80KB and context truncation at 50KB with explicit notices; authoritative ADR/spec/reference context is placed first so it survives the cap, and trailing repo-local context is truncated first
- Fail-fast handling for unsupported events, empty diffs, missing API key, and unset composer-resolver configuration
- Scoped GitHub token permissions and no credential persistence on checkout

## Governance and standards files
- `CONTRIBUTING.md`
- `SECURITY.md`
- `SUPPORT.md`
- `CHANGELOG.md`
- `CODE_OF_CONDUCT.md`
- `CODEOWNERS`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/ISSUE_TEMPLATE/*.yml`

## Operations documentation
- `docs/consumer-setup.md` — how a consuming repository wires up this gate
- `docs/architecture.md`
- `docs/ci-cd.md`
- `docs/deployment.md`
- `docs/upgrade-rollback.md`
- `docs/security-notes.md` — threat model, controls, and accepted scan findings

## Troubleshooting
### `not our ref` during platform docs checkout
If a remote workflow run (in a caller repo) fails while checking out `.spx-workflow-repo` with `upload-pack: not our ref` (e.g. trying to fetch `refs/pull/<n>/merge`), ensure the reusable workflow is up to date. Current versions resolve the reference-docs checkout ref from `github.job_workflow_sha` — the commit SHA of *this* reusable workflow file, resolved by GitHub itself rather than string-parsed from a ref — so cross-repository calls always pin to a valid commit of this repository. Earlier versions read `github.workflow_ref` (the *caller's* top-level ref, e.g. its PR ref on a `pull_request` run) and later `github.job_workflow_ref` parsed for a tag/branch name; both could, in edge cases, hand `actions/checkout` a ref that only exists in the caller's repository.

### Change diff is empty
Confirm the caller uses `pull_request` (not `push` — it cannot supply a PR number), and that the event includes code changes.

### Claude API request failed
Verify `ANTHROPIC_API_KEY` exists and is valid in repo/org secrets.

### Unexpected review results
Check that caller repository context files are current and relevant.

## Maintenance
Update `.github/workflows/claude-pr-review.yml` and corresponding docs in the same pull request.

Maintained by [Starisian Technologies](https://github.com/Starisian-Technologies).
