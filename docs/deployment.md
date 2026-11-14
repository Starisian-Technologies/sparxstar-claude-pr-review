# Deployment

Consumers follow the reviewed `main` branch:

```yaml
uses: Starisian-Technologies/sparxstar-claude-pr-review/.github/workflows/claude-pr-review.yml@main
```

Owner ruling, 2026-11-14: open a PR for owner review, wait for all reviews to be
submitted, resolve all issues and review threads, and require green CI before
merging. Publish a new release after merge. Releases provide audit history;
consumer references stay on `main`. This overrides prior reviewer tag-pin
guidance. Registry `contract_ref` and third-party action pins are unchanged.

For rollback, revert the offending merge through a reviewed PR on `main`;
publish a new patch release after the revert merges. Existing release tags
must never move.
