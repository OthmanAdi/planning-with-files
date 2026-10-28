"""Opt-in Claude subagent isolation, independent of cache identity (#348)."""
import json
import unittest
import os
import shutil
import subprocess
import sys
from pathlib import Path
import test_pretool_throttle as throttle


class SkipSubagentTests(unittest.TestCase):
    setUp = throttle.PretoolThrottleTests.setUp
    tearDown = throttle.PretoolThrottleTests.tearDown
    call = throttle.PretoolThrottleTests.call
    def test_skip_raw_agent_before_identity_and_cache(self):
        for route in ('python', 'shell', 'standalone', 'standalone-shell'):
            for event in ('pretool', 'posttool'):
                for payload in ({'agent_id': 'reviewer'}, {'agent_id': 'reviewer', 'session_id': 'bad/id'}, {'agent_id': 'reviewer', 'prompt_id': 'p'}):
                    with self.subTest(route=route, event=event, payload=payload):
                        self.assertEqual('', self.call(event, route, payload=json.dumps(payload), PWF_SKIP_SUBAGENTS='1', PWF_PRETOOL='always'))
                        self.assertEqual([], list(self.cache.iterdir()))

    def test_optin_invalid_input_fails_closed(self):
        for route in ('python', 'shell', 'standalone', 'standalone-shell'):
            for event in ('pretool', 'posttool'):
                for payload in ('broken', '[]', 'null', '{"agent_id":7}'):
                    with self.subTest(route=route, event=event, payload=payload):
                        self.assertEqual('', self.call(event, route, payload=payload, PWF_SKIP_SUBAGENTS='1'))
                        self.assertEqual([], list(self.cache.iterdir()))

    def test_main_agent_type_and_default_keep_context(self):
        for route in ('python', 'shell', 'standalone', 'standalone-shell'):
            for payload in ({'agent_type': 'reviewer'}, {'agent_id': ''}, {}):
                self.assertIn('Throttle plan', self.call('pretool', route, payload=json.dumps(payload), PWF_SKIP_SUBAGENTS='1'))
            self.assertIn('Throttle plan', self.call('pretool', route, payload='{"agent_id":"reviewer"}'))
            self.assertIn('Throttle plan', self.call('pretool', route, payload='{"agent_id":"reviewer"}', PWF_SKIP_SUBAGENTS='true'))

    def test_skip_does_not_consume_parent_nudge(self):
        for route in ('python', 'shell', 'standalone', 'standalone-shell'):
            payload = json.dumps({'session_id': route, 'agent_id': 'reviewer', 'prompt_id': 'p'})
            self.assertEqual('', self.call('posttool', route, payload=payload, PWF_SKIP_SUBAGENTS='1'))
            self.assertIn('Update progress.md', self.call('posttool', route, session=route, PWF_SKIP_SUBAGENTS='1'))


    def test_missing_classifier_fails_closed_before_refusal(self):
        plugin = self.root / 'plugin'
        shutil.copytree(throttle.REPO / 'scripts', plugin / 'scripts')
        (plugin / 'scripts' / 'inject-plan.py').unlink()
        env = os.environ.copy()
        env.update(PWF_SKIP_SUBAGENTS='1', CLAUDE_PLUGIN_ROOT=str(plugin),
                   PLAN_ID='invalid/selection', XDG_CACHE_HOME=str(self.cache))
        for script, events in ((throttle.REPO / 'hooks/claude-hook.sh', ('pre-tool-use', 'post-tool-use')),
                               (plugin / 'scripts/skill-hook.sh', ('--event=pretool', '--event=posttool'))):
            for event in events:
                result = subprocess.run(['sh', str(script), event], cwd=self.root,
                                        env=env, input='{}', text=True, capture_output=True, timeout=60)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual('', result.stdout)
                self.assertEqual([], list(self.cache.iterdir()))

    def test_python_entrypoint_checks_raw_payload_before_selection(self):
        env = os.environ.copy()
        env.update(PWF_SKIP_SUBAGENTS='1', PLAN_ID='invalid/selection',
                   XDG_CACHE_HOME=str(self.cache))
        for event in ('pre-tool-use', 'post-tool-use'):
            for payload in ('{"agent_id":"reviewer"}', 'broken'):
                result = subprocess.run([sys.executable, '-I', str(throttle.REPO / 'scripts/inject-plan.py'),
                                         '--claude-event=' + event], cwd=self.root, env=env,
                                        input=payload, text=True, capture_output=True, timeout=60)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual('', result.stdout)
                self.assertEqual([], list(self.cache.iterdir()))
