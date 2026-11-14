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
- An unsupported event (including `pull_request_target`) or invalid PR number
- A missing Anthropic API key
- Unset composer-resolver configuration
- An empty or malformed `contract_ref` (`Validate contract_ref`)

`review` declares `needs: build-context`, so the checks below run only after both App tokens have been minted, the registries checked out and the trusted-context artifact uploaded. They stop the run; they do not make it fail fast:
- Empty diff
- Invalid Anthropic API key
- API request failure
- Incomplete, malformed or empty API response

Concurrency applies to the entire workflow, so a newer run cancels obsolete
context preparation as well as the review. The API call has a 10-second connect
timeout and a 180-second total timeout. Requests are not automatically retried:
an ambiguous timeout may already have incurred API usage.

Missing Anthropic keys produce a successful skip with a warning and job summary; registry fetching and review are skipped. A skip is not a completed review.
