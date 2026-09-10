# Architecture

## Purpose
This repository provides a reusable GitHub Actions workflow that performs Claude-based pull request review for consumer repositories.

## Design boundaries
- Central policy workflow: `.github/workflows/claude-pr-review.yml`
- Consumer integration example: `examples/consumer-workflow.yml`
- Human governance docs and templates: repository root + `.github/ISSUE_TEMPLATE/`

## Execution model
1. Consumer repository triggers `pull_request` event.
2. Consumer job calls the reusable workflow in this repository.
3. Workflow fetches PR diff and repository-specific context files.
4. Workflow renders a deterministic prompt and calls Anthropic Messages API.
5. Workflow upserts a single bot PR comment with review output.

## Security boundaries
- API key is sourced only from `ANTHROPIC_API_KEY` secret.
- Diff/comment operations use `GITHUB_TOKEN` with explicit minimum permissions.
- No repository write operations beyond PR comments.

## Failure model
`build-context` is fail-fast, before any token is minted, for:
- A public caller repository
- Unset composer-resolver configuration
- An empty or malformed `contract_ref` (`Validate contract_ref`)

`review` declares `needs: build-context`, so the checks below run only after both App tokens have been minted, the registries checked out and the trusted-context artifact uploaded. They stop the run; they do not make it fail fast:
- Missing PR context
- Empty diff
- Missing or invalid Anthropic API key
- API request failure
