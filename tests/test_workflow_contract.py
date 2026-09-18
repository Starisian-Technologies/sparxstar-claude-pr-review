from pathlib import Path
import re
import unittest


class WorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        cls.workflow = (repo_root / ".github/workflows/claude-pr-review.yml").read_text(encoding="utf-8")
        cls.readme = (repo_root / "README.md").read_text(encoding="utf-8")
        cls.docs_ci_cd = (repo_root / "docs/ci-cd.md").read_text(encoding="utf-8")
        cls.consumer_example = (repo_root / "examples/consumer-workflow.yml").read_text(encoding="utf-8")
        cls.consumer_setup = (repo_root / "docs/consumer-setup.md").read_text(encoding="utf-8")
        cls.setup_md = (repo_root / "SETUP.md").read_text(encoding="utf-8")

    def _assert_claude_workflow_pinned_to(self, text: str, expected_ref: str) -> None:
        # Extract every `uses: …/claude-pr-review.yml@<ref>` pin and assert each
        # resolves to exactly expected_ref. \S+ stops at whitespace, so trailing
        # spaces, CRLF line endings, and inline comments (…@v1 # note) are all
        # handled, and the @v1.0.0-contains-@v1 substring trap is avoided.
        refs = re.findall(r"claude-pr-review\.yml@(\S+)", text)
        self.assertTrue(refs, "no claude-pr-review.yml@<ref> pin found")
        for ref in refs:
            self.assertEqual(ref, expected_ref)

    def test_reusable_workflow_requires_anthropic_api_key(self) -> None:
        self.assertIn("workflow_call:", self.workflow)
        self.assertIn("ANTHROPIC_API_KEY:", self.workflow)
        self.assertIn("required: true", self.workflow)

    def test_reusable_workflow_declares_contract_ref_input(self) -> None:
        self.assertIn("inputs:", self.workflow)
        self.assertIn("contract_ref:", self.workflow)
        # Default is the immutable release tag, not the moving major alias.
        self.assertIn("default: v1.0.0", self.workflow)

    def test_reusable_workflow_requires_composer_resolver_private_key(self) -> None:
        self.assertIn("COMPOSER_RESOLVER_PRIVATE_KEY:", self.workflow)

    def test_workflow_validates_resolver_config_before_minting(self) -> None:
        self.assertIn("COMPOSER_RESOLVER_CLIENT_ID variable is not set", self.workflow)
        self.assertIn("COMPOSER_RESOLVER_PRIVATE_KEY secret is not set", self.workflow)
        validate = self.workflow.index("Validate composer-resolver configuration")
        mint = self.workflow.index("Mint ADR read token")
        self.assertLess(validate, mint)

    def test_workflow_mints_scoped_registry_read_tokens(self) -> None:
        # SHA-pinned, not @v3: these steps run a third-party action while holding
        # the App private key, and a major tag can be moved by its owner.
        #
        # Assert the COMPLETE list of refs, not merely that a SHA appears
        # somewhere. An earlier version checked `assertIn(<sha>)` plus
        # `assertNotIn("@v3\n")`, which one pinned step satisfied on behalf of
        # both — and which `@v3 # comment` slipped past entirely.
        app_token_refs = re.findall(
            r"actions/create-github-app-token@(\S+)", self.workflow
        )
        self.assertEqual(
            app_token_refs,
            ["bcd2ba49218906704ab6c1aa796996da409d3eb1", "bcd2ba49218906704ab6c1aa796996da409d3eb1"],
            "both privileged mint steps must pin the verified commit SHA; "
            f"found {app_token_refs}",
        )
        self.assertIn("client-id: ${{ vars.COMPOSER_RESOLVER_CLIENT_ID }}", self.workflow)
        self.assertIn("private-key: ${{ secrets.COMPOSER_RESOLVER_PRIVATE_KEY }}", self.workflow)
        self.assertIn("repositories: sparxstar-architecture-governance-registry", self.workflow)
        self.assertIn("repositories: sparxstar-product-specification-registry", self.workflow)

    def test_workflow_checks_out_registries_with_minted_tokens_at_resolved_shas(self) -> None:
        self.assertIn("repository: Starisian-Technologies/sparxstar-architecture-governance-registry", self.workflow)
        self.assertIn("repository: Starisian-Technologies/sparxstar-product-specification-registry", self.workflow)
        self.assertIn("token: ${{ steps.adr-token.outputs.token }}", self.workflow)
        self.assertIn("token: ${{ steps.spec-token.outputs.token }}", self.workflow)
        # The contract_ref is resolved to immutable commit SHAs via the GitHub API
        # before any checkout; the checkout steps use those SHAs, not the raw input.
        self.assertIn("Resolve contract ref SHAs", self.workflow)
        self.assertIn("ref: ${{ steps.contract-shas.outputs.adr-sha }}", self.workflow)
        self.assertIn("ref: ${{ steps.contract-shas.outputs.spec-sha }}", self.workflow)
        # Checkout-target resolution must not fall back to PR head refs in the privileged workflow.
        self.assertNotIn("github.event.pull_request.head.repo.full_name", self.workflow)
        self.assertNotIn("github.event.pull_request.head.sha", self.workflow)
        self.assertNotIn("falling back to PR head SHA", self.workflow)

    def test_contract_ref_sha_resolution_url_encodes_ref(self) -> None:
        # contract_ref validation allows '/' (e.g. release/1.2 branch names),
        # but the GitHub API path requires such refs to be percent-encoded or
        # the slash is read as a path separator and the lookup 404s.
        resolve_start = self.workflow.index("resolve_ref_sha() {")
        resolve_end = self.workflow.index("\n          }", resolve_start)
        resolve_body = self.workflow[resolve_start:resolve_end]
        self.assertIn("urllib.parse.quote", resolve_body)
        self.assertIn("safe='-._~'", resolve_body)
        self.assertIn("gh api \"repos/$repo/commits/$encoded_ref\"", resolve_body)

    def test_contract_ref_is_validated_before_checkout(self) -> None:
        self.assertIn("Validate contract_ref", self.workflow)
        self.assertIn("CONTRACT_REF: ${{ inputs.contract_ref }}", self.workflow)
        self.assertIn("[A-Za-z0-9][A-Za-z0-9._/-]*", self.workflow)
        # Plus Git's own ref-name rules (rejects .lock, //, trailing /, ..).
        self.assertIn("git check-ref-format --allow-onelevel", self.workflow)
        # The raw input must not flow directly into a checkout ref.
        self.assertNotIn("ref: ${{ inputs.contract_ref }}", self.workflow)
        validate = self.workflow.index("Validate contract_ref")
        adr_checkout = self.workflow.index("Checkout ADR registry")
        self.assertLess(validate, adr_checkout)

    def test_registry_content_is_loaded_into_spec_context(self) -> None:
        # build-context assembles per-tier files from registry clones; the review
        # job reads them via collect_tier fallback paths in the trusted-context artifact.
        self.assertIn("tier_adrs.txt", self.workflow)
        self.assertIn("tier_specs.txt", self.workflow)
        self.assertIn(".spx-trusted-context/tier_specs.txt", self.workflow)
        self.assertIn(".spx-trusted-context/tier_adrs.txt", self.workflow)

    def _job_blocks(self) -> tuple[str, str]:
        # build-context is defined before review; slice the file at the two
        # 2-space-indented job headers.
        a_start = self.workflow.index("\n  build-context:")
        b_start = self.workflow.index("\n  review:")
        self.assertLess(a_start, b_start)
        return self.workflow[a_start:b_start], self.workflow[b_start:]

    def test_workflow_is_split_into_two_jobs(self) -> None:
        self.assertIn("\n  build-context:", self.workflow)
        self.assertIn("\n  review:", self.workflow)
        _, review = self._job_blocks()
        self.assertIn("needs: build-context", review)

    def test_privileged_job_holds_app_key_and_never_checks_out_pr_head(self) -> None:
        build_context, _ = self._job_blocks()
        # The App key and token minting live in the privileged job...
        self.assertIn("actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1", build_context)
        self.assertIn("secrets.COMPOSER_RESOLVER_PRIVATE_KEY", build_context)
        self.assertIn("actions/upload-artifact", build_context)
        # ...which must never resolve or check out untrusted PR-head code.
        self.assertNotIn("Resolve checkout target", build_context)
        self.assertNotIn("steps.checkout_target.outputs.ref", build_context)

    def test_build_context_refuses_public_caller(self) -> None:
        build_context, _ = self._job_blocks()
        self.assertIn("Guard against public caller repository", build_context)
        self.assertIn("github.event.repository.private", build_context)
        # The guard must run before any token is minted AND before any private
        # content is fetched — it is the first gate, failing the job outright.
        guard = build_context.index("Guard against public caller repository")
        mint = build_context.index("Mint ADR read token")
        fetch = build_context.index("Checkout ADR registry")
        self.assertLess(guard, mint)
        self.assertLess(guard, fetch)
        # The guard is the first step in the job — no other `- name:` precedes it.
        self.assertEqual(
            build_context.index("      - name:"),
            build_context.index("      - name: Guard against public caller repository"),
        )

    def test_all_checkouts_disable_credential_persistence(self) -> None:
        checkouts = self.workflow.count("uses: actions/checkout@v5")
        persist_false = self.workflow.count("persist-credentials: false")
        self.assertGreaterEqual(checkouts, 4)
        self.assertEqual(checkouts, persist_false)

    def test_trusted_context_loaded_before_repo_local(self) -> None:
        _, review = self._job_blocks()
        # The trusted context artifact (.spx-trusted-context) is downloaded and
        # referenced before repo-local AGENTS.md is read into repo_context.txt.
        trusted = review.index(".spx-trusted-context")
        repo_local = review.index("AGENTS.md")
        self.assertLess(trusted, repo_local)

    def test_resolve_checkout_target_never_falls_back_to_pr_head(self) -> None:
        _, review = self._job_blocks()
        # The checkout target must never reference the untrusted PR-head repo or
        # SHA — not even as a fallback. Fail-closed means exiting with an error,
        # never silently using an attacker-controllable ref.
        self.assertNotIn("github.event.pull_request.head.repo", review)
        self.assertNotIn("github.event.pull_request.head.sha", review)
        # Also guard against the specific intermediate variable names used in the
        # previous fallback implementation, catching aliased access patterns.
        self.assertNotIn("PR_HEAD_REPO_FULL_NAME", review)
        self.assertNotIn("PR_HEAD_SHA", review)

    def test_unprivileged_review_job_has_no_app_key_and_only_consumes_artifact(self) -> None:
        _, review = self._job_blocks()
        # The job that checks out untrusted PR-head code...
        self.assertIn("ref: ${{ steps.checkout_target.outputs.ref }}", review)
        # ...must not hold the App key or mint tokens...
        self.assertNotIn("actions/create-github-app-token", review)
        self.assertNotIn("COMPOSER_RESOLVER_PRIVATE_KEY", review)
        # ...and receives trusted context only via artifact (never re-fetched).
        self.assertIn("actions/download-artifact", review)
        self.assertNotIn("Checkout ADR registry", review)
        self.assertNotIn("Checkout product-spec registry", review)

    def test_workflow_has_required_permissions(self) -> None:
        self.assertIn("permissions:", self.workflow)
        self.assertIn("contents: read", self.workflow)
        self.assertIn("pull-requests: write", self.workflow)

    def test_diff_step_has_fail_fast_guards(self) -> None:
        start_marker = "- name: Get PR diff"
        end_marker = "\n      - name:"
        start = self.workflow.index(start_marker)
        end = self.workflow.index(end_marker, start + len(start_marker))
        diff_step = self.workflow[start:end]
        self.assertIn("No pull request number found", diff_step)
        self.assertIn("PR diff is empty", diff_step)
        self.assertIn("set -euo pipefail", diff_step)

    def test_diff_truncation_is_capped_and_flagged(self) -> None:
        start_marker = 'if [ "$(wc -c < pr.diff)" -gt 80000 ]; then'
        end_marker = 'echo "truncated=false" >> "$GITHUB_OUTPUT"'
        start = self.workflow.index(start_marker)
        end = self.workflow.index(end_marker, start) + len(end_marker)
        diff_block = self.workflow[start:end]
        self.assertIn('echo "truncated=true" >> "$GITHUB_OUTPUT"', diff_block)
        self.assertIn('data.decode("utf-8")', diff_block)

    def test_three_tier_context_steps_present(self) -> None:
        self.assertIn("Load three-tier context", self.workflow)
        self.assertIn("tier_specs.txt", self.workflow)
        self.assertIn("tier_contracts.txt", self.workflow)
        self.assertIn("tier_adrs.txt", self.workflow)

    def test_tier_paths_match_artifact_layout(self) -> None:
        self.assertIn(".sparxstar/specs/agent", self.workflow)
        self.assertIn(".sparxstar/contracts", self.workflow)
        self.assertIn(".sparxstar/adrs", self.workflow)

    def test_tier_truncation_is_capped_per_tier(self) -> None:
        self.assertIn("truncate_to_bytes", self.workflow)
        self.assertIn("25000", self.workflow)  # spec tier cap
        self.assertIn("20000", self.workflow)  # contracts and adrs tier cap
        self.assertIn('data.decode("utf-8")', self.workflow)

    def test_declaration_step_reads_sparxstar_specs_yml(self) -> None:
        self.assertIn("Read repo declaration", self.workflow)
        self.assertIn("sparxstar-specs.yml", self.workflow)
        self.assertIn("specs_ids", self.workflow)
        self.assertIn("contracts_ids", self.workflow)
        self.assertIn("adrs_ids", self.workflow)

    def test_prompt_has_three_named_passes(self) -> None:
        self.assertIn("PASS 1 — SPEC CONFORMANCE", self.workflow)
        self.assertIn("PASS 2 — CONTRACT SEAM CHECK", self.workflow)
        self.assertIn("PASS 3 — ADR DRIFT DETECTION", self.workflow)

    def test_prompt_template_substitution_is_allowlisted(self) -> None:
        self.assertIn('"${DIFF}": Path("pr.diff").read_text(encoding="utf-8")', self.workflow)
        self.assertIn('"${TIER_SPECS}": safe_read("tier_specs.txt",', self.workflow)
        self.assertIn('"${TIER_CONTRACTS}": safe_read("tier_contracts.txt",', self.workflow)
        self.assertIn('"${TIER_ADRS}": safe_read("tier_adrs.txt",', self.workflow)
        self.assertIn('"${PLATFORM_REF}": safe_read("platform_ref.txt",', self.workflow)
        self.assertIn('"${REPO_CONTEXT}": safe_read("repo_context.txt",', self.workflow)
        # Full allowlist pattern — all 13 tokens must be present
        self.assertIn(
            "DIFF|TIER_SPECS|TIER_CONTRACTS|TIER_ADRS|PLATFORM_REF|REPO_CONTEXT|REPO|PR_TITLE|PR_NUMBER|TRUNCATION_LINE|SPECS_IDS|CONTRACTS_IDS|ADRS_IDS",
            self.workflow,
        )

    def test_platform_ref_is_injected_into_prompt(self) -> None:
        self.assertIn("${PLATFORM_REF}", self.workflow)
        self.assertIn("PLATFORM REFERENCE", self.workflow)

    def test_prompt_substitution_validates_no_leftover_tokens(self) -> None:
        # Guard must scan the template (before substitution), not the rendered
        # prompt — diff/spec content can contain ${FOO} that false-positive.
        self.assertIn('leftover = re.findall(r"\\$\\{[A-Z_]+\\}", template)', self.workflow)
        self.assertIn("Unsubstituted template variables in prompt template", self.workflow)

    def test_artifact_download_step_present_with_continue_on_error(self) -> None:
        self.assertIn("Download spec artifact", self.workflow)
        self.assertIn("actions/download-artifact@v4", self.workflow)
        self.assertIn("continue-on-error: true", self.workflow)

    def test_build_context_writes_per_tier_files(self) -> None:
        build_context, _ = self._job_blocks()
        # build-context writes three per-tier files so the review job can fall
        # back to registry content without PyYAML when no fetch-specs artifact
        # is present. trusted_context.txt is no longer written or uploaded.
        self.assertIn("tier_adrs.txt", build_context)
        self.assertIn("tier_specs.txt", build_context)
        self.assertIn("platform_ref.txt", build_context)
        # All three files must be included in the artifact upload.
        upload = build_context.index("Upload trusted context")
        self.assertIn("tier_adrs.txt", build_context[upload:])
        self.assertIn("tier_specs.txt", build_context[upload:])
        self.assertIn("platform_ref.txt", build_context[upload:])

    def test_fetch_specs_artifact_extracted_to_isolated_dir(self) -> None:
        _, review = self._job_blocks()
        # Artifact must land in an isolated directory, never the repo root,
        # so PR-head .sparxstar/ files cannot inject into the tier context.
        self.assertIn("path: .spx-specs-artifact", review)
        self.assertIn(".spx-specs-artifact/.sparxstar/specs/agent", review)
        self.assertIn(".spx-specs-artifact/.sparxstar/contracts", review)
        self.assertIn(".spx-specs-artifact/.sparxstar/adrs", review)

    def test_tier_files_fall_back_to_registry_artifact(self) -> None:
        _, review = self._job_blocks()
        # collect_tier must fall back to .spx-trusted-context/ tier files when
        # fetch-specs artifact is absent or empty.
        self.assertIn(".spx-trusted-context/tier_specs.txt", review)
        self.assertIn(".spx-trusted-context/tier_adrs.txt", review)

    def test_platform_ref_sourced_from_build_context_artifact(self) -> None:
        _, review = self._job_blocks()
        # Platform reference docs live in the privileged build-context job;
        # the review job must read them from the artifact, never re-fetch.
        self.assertIn(".spx-trusted-context/platform_ref.txt", review)
        self.assertNotIn(".spx-workflow-repo/reference", review)

    def test_declaration_uses_stdlib_only_no_pyyaml(self) -> None:
        self.assertNotIn("pip install pyyaml", self.workflow)
        self.assertNotIn("import yaml", self.workflow)
        # Line-based stdlib parser — handles blank lines between list items.
        self.assertIn("extract_ids", self.workflow)
        self.assertIn("splitlines", self.workflow)
        self.assertNotIn("re.search(rf", self.workflow)

    def test_review_comment_is_upserted_with_single_marker(self) -> None:
        self.assertIn('COMMENT_MARKER="<!-- claude-pr-review-comment -->"', self.workflow)
        self.assertIn('issues/${PR_NUMBER}/comments', self.workflow)
        self.assertIn('issues/comments/${EXISTING_COMMENT_ID}', self.workflow)
        self.assertIn('gh pr comment "$PR_NUMBER"', self.workflow)

    def test_readme_documents_required_permissions_and_secret(self) -> None:
        self.assertIn("ANTHROPIC_API_KEY", self.readme)
        self.assertIn("contents: read", self.readme)
        self.assertIn("pull-requests: write", self.readme)

    def test_consumer_example_keeps_required_permissions_and_secret(self) -> None:
        self.assertIn("contents: read", self.consumer_example)
        self.assertIn("pull-requests: write", self.consumer_example)
        self.assertIn("ANTHROPIC_API_KEY", self.consumer_example)

    def test_consumer_example_has_fetch_specs_job(self) -> None:
        self.assertIn("fetch-specs:", self.consumer_example)
        self.assertIn("fetch-specs.yml", self.consumer_example)
        self.assertIn("needs: fetch-specs", self.consumer_example)

    def test_consumer_example_pins_immutable_tag_and_passes_resolver_secret(self) -> None:
        # Platform convention: pin the immutable release tag, not @v1 or @main.
        self._assert_claude_workflow_pinned_to(self.consumer_example, "v1.1.1")
        self.assertIn("COMPOSER_RESOLVER_PRIVATE_KEY: ${{ secrets.COMPOSER_RESOLVER_PRIVATE_KEY }}", self.consumer_example)
        self.assertIn("contract_ref: v1.0.0", self.consumer_example)

    def test_readme_pins_immutable_tag_and_documents_resolver_requirements(self) -> None:
        self._assert_claude_workflow_pinned_to(self.readme, "v1.1.1")
        self.assertIn("COMPOSER_RESOLVER_PRIVATE_KEY", self.readme)
        self.assertIn("COMPOSER_RESOLVER_CLIENT_ID", self.readme)
        self.assertIn("contract_ref", self.readme)

    def test_consumer_setup_doc_pins_same_immutable_tag(self) -> None:
        # docs/consumer-setup.md carries its own copy-paste caller. Unasserted,
        # it could drift back to an older tag while README and the example
        # stayed current, and CI would stay green — which is how the pin got
        # out of step across this repo's docs in the first place.
        self._assert_claude_workflow_pinned_to(self.consumer_setup, "v1.1.1")

    def test_setup_router_pins_same_immutable_tag(self) -> None:
        # SETUP.md recommends a pin in prose rather than a `uses:` line, so it
        # is checked by content: the recommended tag must be the current one,
        # and the superseded tag must not still be presented as the pin.
        self.assertIn("**Pin `@v1.1.1`.**", self.setup_md)
        self.assertNotIn("**Pin `@v1.1.0`.**", self.setup_md)

    def test_ci_cd_doc_matches_permission_contract(self) -> None:
        self.assertIn("contents: read", self.docs_ci_cd)
        self.assertIn("pull-requests: write", self.docs_ci_cd)
        self.assertIn("ANTHROPIC_API_KEY", self.docs_ci_cd)

    def test_ci_cd_doc_documents_resolver_and_contract_ref(self) -> None:
        self.assertIn("COMPOSER_RESOLVER_PRIVATE_KEY", self.docs_ci_cd)
        self.assertIn("COMPOSER_RESOLVER_CLIENT_ID", self.docs_ci_cd)
        self.assertIn("contract_ref", self.docs_ci_cd)

    def test_api_call_does_not_discard_the_error_body(self) -> None:
        # curl -f makes curl exit non-zero on HTTP >= 400 *and* throw the
        # response body away. With it, a revoked key, a retired model id, a
        # rate limit and an outage all reached the log as one hardcoded
        # sentence about the API key, and the real cause could not be read
        # off the job at all. Regression guard: the request must keep the
        # body so the status handler has something to report.
        start = self.workflow.index("api.anthropic.com/v1/messages")
        call = self.workflow[start - 400 : self.workflow.index("review.txt", start)]
        self.assertNotIn("curl -sf", call)
        self.assertIn("-o response.json", call)
        self.assertIn("-w '%{http_code}'", call)

    def test_api_failure_distinguishes_auth_from_other_causes(self) -> None:
        # The point of keeping the body: an operator must be able to tell
        # "rotate the secret" from "this has nothing to do with the secret"
        # without re-running anything.
        self.assertIn("HTTP_STATUS", self.workflow)
        # The API's own words, not ours.
        self.assertIn(".error.type", self.workflow)
        self.assertIn(".error.message", self.workflow)
        # Only 401/403 may advise rotating the key.
        self.assertIn("401|403)", self.workflow)
        rotate = [ln for ln in self.workflow.splitlines() if "rotate" in ln.lower()]
        self.assertTrue(rotate, "no rotation guidance found")
        for line in rotate:
            self.assertNotIn("404", line)
            self.assertNotIn("429", line)
        # A 404 is a request fault and must say so.
        self.assertIn("Rotating the API key will not fix this", self.workflow)

    def test_model_id_is_named_in_the_not_found_diagnostic(self) -> None:
        # A 404 is most often the model id, so the diagnostic has to print
        # which id was asked for; otherwise the next operator guesses too.
        self.assertIn('CLAUDE_MODEL="claude-sonnet-4-6"', self.workflow)
        self.assertIn('--arg model "${CLAUDE_MODEL}"', self.workflow)
        self.assertIn("Requested model: ${CLAUDE_MODEL}", self.workflow)


if __name__ == "__main__":
    unittest.main()
