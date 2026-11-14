"""Execute the workflow's guards without network calls or credentials."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


WORKFLOW = (Path(__file__).resolve().parents[1] /
            '.github/workflows/claude-pr-review.yml').read_text()


def step_script(name):
    step = WORKFLOW.split(f'      - name: {name}\n', 1)[1]
    step = step.split('\n      - name:', 1)[0]
    return textwrap.dedent(step.split('        run: |\n', 1)[1])


class ReviewGuardsTests(unittest.TestCase):
    def test_preflight_accepts_only_pr_events_with_key_and_positive_number(self):
        cases = [
            ('pull_request', '42', 'test-key', True),
            ('pull_request_target', '42', 'test-key', False),
            ('workflow_dispatch', '', 'test-key', False),
            ('push', '', 'test-key', False),
            ('pull_request', '0', 'test-key', False),
            ('pull_request', 'abc', 'test-key', False),
            ('pull_request', '42', '', True),
        ]
        for event, number, key, valid in cases:
            with self.subTest(event=event, number=number, key_present=bool(key)):
                result = subprocess.run(
                    ['bash', '-c', step_script('Validate review request')],
                    env={**os.environ, 'EVENT_NAME': event, 'PR_NUMBER': number,
                         'ANTHROPIC_API_KEY': key, 'GITHUB_OUTPUT': '/dev/null',
                         'GITHUB_STEP_SUMMARY': '/dev/null'}, capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, valid, result.stdout)

    def test_preflight_precedes_registry_token_minting(self):
        self.assertLess(WORKFLOW.index('- name: Validate review request'),
                        WORKFLOW.index('- name: Mint ADR read token'))

    def test_complete_response_joins_text_blocks_and_rejects_bad_results(self):
        script = 'set -euo pipefail\nif ! jq -er' + step_script(
            'Run Claude review').split('if ! jq -er', 1)[1]
        cases = [
            ({'type': 'message', 'stop_reason': 'end_turn', 'content': [
                {'type': 'thinking', 'thinking': 'ignored'},
                {'type': 'text', 'text': 'First'},
                {'type': 'text', 'text': 'Second'}]}, 'First\nSecond\n'),
            ({'type': 'message', 'stop_reason': 'max_tokens', 'content': [
                {'type': 'text', 'text': 'Partial PASS'}]}, None),
            ({'type': 'message', 'stop_reason': 'end_turn', 'content': [
                {'type': 'text', 'text': ' \n '}]}, None),
            ({'type': 'message', 'stop_reason': 'end_turn', 'content': []}, None),
            ({'type': 'error'}, None),
            ('not JSON', None),
        ]
        for payload, expected in cases:
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as d:
                Path(d, 'response.json').write_text(
                    payload if isinstance(payload, str) else json.dumps(payload))
                result = subprocess.run(['bash', '-c', script], cwd=d,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, expected is not None)
                if expected is not None:
                    self.assertEqual(Path(d, 'review.txt').read_text(), expected)

    def test_generated_output_symlinks_are_rejected_without_touching_target(self):
        script = step_script('Run Claude review')
        script = 'set -euo pipefail\n' + script.split(
            '# PR checkouts may contain tracked symlinks.', 1)[1].split(
            "cat > prompt_template.txt", 1)[0]
        for name in ('prompt_template.txt', 'prompt.txt', 'request.json', 'review.txt'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as d:
                target = Path(d, 'target'); target.write_text('untouched')
                Path(d, name).symlink_to(target)
                result = subprocess.run(['bash', '-c', script], cwd=d,
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(target.read_text(), 'untouched')

    def test_api_has_finite_connect_and_total_timeout(self):
        self.assertIn('--connect-timeout 10 --max-time 180', WORKFLOW)
        # Avoid implicit paid POST retries after an ambiguous timeout.
        self.assertNotIn('--retry-all-errors', WORKFLOW)


if __name__ == '__main__':
    unittest.main()
