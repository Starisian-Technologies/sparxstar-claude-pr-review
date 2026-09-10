# Deployment

## Deployment model
Deployment is release-by-reference of workflow files in this repository.
Consumer repositories import the workflow by ref:

`Starisian-Technologies/sparxstar-claude-pr-review/.github/workflows/claude-pr-review.yml@<ref>`

## Safe deployment process
1. Open PR with workflow and documentation changes.
2. Validate syntax and governance files.
3. Merge after required reviews.
4. Publish a release tag.
5. Update consumer repositories to the approved tag (required for controlled rollout; see ref guidance below).

## Ref selection guidance
| Use case | Recommended ref | Notes |
|---|---|---|
| Development / initial setup | `@main` | Acceptable for non-production testing; tracks the latest commit. |
| Staging / production | `@vX.Y.Z` | Pin to a release tag to get predictable, auditable behaviour. |

The quick-start example in `README.md` and `examples/consumer-workflow.yml` pins `@v1.1.1`, the current canonical release — not `@main`. An earlier revision of this line said they used `@main` "for simplicity", which contradicted the never-`@main`-in-production rule above and is no longer true of either file.

## Post-deploy verification
- Trigger a test PR in a consumer repository.
- Verify diff retrieval, prompt generation, and comment upsert behavior.
- Confirm no secret leakage in logs.
