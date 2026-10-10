"""PreToolUse repeats only a newly visible plan view (issue #312)."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

@unittest.skipUnless(shutil.which('sh'), 'requires POSIX sh')
class PretoolThrottleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='pwf-pretool-')
        self.root = Path(self.tmp.name)
        self.plan = self.root / 'task_plan.md'
        self.plan.write_text('# Throttle plan\n' + ''.join('line %s\n' % i for i in range(60)), encoding='utf-8')
        (self.root / 'progress.md').write_text('# Progress\n', encoding='utf-8')
        self.cache = self.root / 'cache'
        self.cache.mkdir()
    def tearDown(self):
        self.tmp.cleanup()
    def call(self, event, route='python', session='alpha', payload=None, **extra):
        env = os.environ.copy()
        for name in list(env):
            if name.startswith('PWF_') or name in ('PLAN_ID', 'PLANNING_DISABLED', 'PYTHON_BIN'):
                env.pop(name)
        env.update(XDG_CACHE_HOME=str(self.cache), CLAUDE_PLUGIN_ROOT=str(REPO), PWF_TRUSTED_PYTHON=sys.executable)
        env.update(extra)
        if payload is None:
            payload = json.dumps({'session_id': session}) if session else '{}'
        if route in ('python', 'shell'):
            env['PWF_FAST_PATH'] = '0' if route == 'shell' else '1'
            names = {'userprompt':'user-prompt-submit','pretool':'pre-tool-use','precompact':'pre-compact','session':'session-start','posttool':'post-tool-use'}
            cmd = ['sh', str(REPO/'hooks/claude-hook.sh'), names[event]]
        else:
            env['PWF_FAST_PATH'] = '0' if route == 'standalone-shell' else '1'
            cmd = ['sh', str(REPO/'scripts/skill-hook.sh'), '--event='+event]
        result = subprocess.run(cmd, cwd=self.root, env=env, input=payload, text=True, capture_output=True, timeout=180)
        self.assertEqual(0, result.returncode, result.stderr)
        return result.stdout
    def test_prompt_seeds_exact_pretool_view_all_routes(self):
        for route in ('python','shell','standalone','standalone-shell'):
            with self.subTest(route=route):
                self.assertIn('Throttle plan', self.call('userprompt', route, session=route))
                self.assertEqual('', self.call('pretool', route, session=route))
                self.assertEqual('', self.call('pretool', route, session=route))
    def test_changed_view_refreshes_once_and_outside_view_does_not(self):
        self.assertIn('Throttle plan', self.call('pretool'))
        self.assertEqual('', self.call('pretool'))
        before = self.plan.stat()
        self.plan.write_text(self.plan.read_text().replace('line 1\n','LINE 1\n'), encoding='utf-8')
        os.utime(self.plan, ns=(before.st_atime_ns,before.st_mtime_ns))
        self.assertIn('LINE 1', self.call('pretool'))
        self.assertEqual('', self.call('pretool'))
        self.plan.write_text(self.plan.read_text().replace('line 59','changed beyond view'), encoding='utf-8')
        self.assertEqual('', self.call('pretool'))
    def test_recovery_and_prompt_seed(self):
        self.call('pretool')
        self.assertEqual('', self.call('pretool'))
        self.call('precompact')
        self.assertIn('Throttle plan', self.call('pretool'))
        self.assertIn('Throttle plan', self.call('session'))
        self.assertEqual('', self.call('pretool'))
        self.assertIn('Throttle plan', self.call('userprompt'))
        self.assertEqual('', self.call('pretool'))
    def test_sessions_do_not_suppress_each_other(self):
        self.assertIn('Throttle plan',self.call('pretool', session='alpha'))
        self.assertIn('Throttle plan',self.call('pretool', session='beta'))
        self.assertEqual('',self.call('pretool',session='alpha'))
    def test_missing_identity_and_broken_cache_repeat(self):
        for _ in range(2):
            self.assertIn('Throttle plan', self.call('pretool', session=None))
        broken = self.cache/'pwf-pretool'; broken.write_text('keep')
        for _ in range(2):
            self.assertIn('Throttle plan', self.call('pretool'))
        self.assertEqual('keep',broken.read_text())
    def test_always_optout(self):
        self.call('userprompt')
        for _ in range(2):
            self.assertIn('Throttle plan',self.call('pretool',PWF_PRETOOL='always'))
    def test_tamper_is_checked_even_if_visible_head_is_unchanged(self):
        (self.root/'.plan-attestation').write_text(hashlib.sha256(self.plan.read_bytes()).hexdigest())
        self.assertIn('Throttle plan', self.call('pretool'))
        self.plan.write_text(self.plan.read_text()+'tamper outside head\n')
        for _ in range(2):
            self.assertIn('PLAN TAMPERED', self.call('pretool'))

    def test_native_identity_overrides_inherited_identity_and_malformed_repeats(self):
        self.call('pretool', session='alpha')
        self.assertIn('Throttle plan', self.call('pretool', session='beta', PWF_SESSION_ID='alpha'))
        for payload in ('{}', 'null', '{broken', '{"session_id":"../bad"}'):
            for _ in range(2):
                self.assertIn('Throttle plan', self.call('pretool', payload=payload, PWF_SESSION_ID='alpha'))

    def test_agents_and_prompt_ids_are_separate_and_routes_agree(self):
        alpha = json.dumps({'session_id':'shared','agent_id':'a','prompt_id':'p1'})
        beta = json.dumps({'session_id':'shared','agent_id':'b','prompt_id':'p1'})
        next_turn = json.dumps({'session_id':'shared','agent_id':'a','prompt_id':'p2'})
        self.assertIn('Throttle plan',self.call('pretool',payload=alpha))
        self.assertEqual('',self.call('pretool',route='standalone',payload=alpha))
        self.assertIn('Throttle plan',self.call('pretool',payload=beta))
        self.assertIn('Throttle plan',self.call('pretool',payload=next_turn))
        no_prompt=json.dumps({'session_id':'shared','agent_id':'a'})
        for _ in range(2):
            self.assertIn('Throttle plan',self.call('pretool',payload=no_prompt))

    def test_plan_switch_overwrites_view_slot_even_for_identical_content(self):
        other = self.root/'other'; other.mkdir()
        (other/'task_plan.md').write_bytes(self.plan.read_bytes())
        self.call('pretool')
        self.assertEqual('',self.call('pretool'))
        self.assertIn('Throttle plan',self.call('pretool',PWF_PLAN_ROOT=str(other)))
        self.assertIn('Throttle plan',self.call('pretool'))

    def test_rendering_mode_and_truncation_are_part_of_the_view(self):
        self.call('pretool')
        self.assertIn('Throttle plan',self.call('pretool',PWF_INJECT='smart'))
        self.assertEqual('',self.call('pretool',PWF_INJECT='smart'))
        self.plan.write_text('# Throttle plan\n'+''.join('line %s\n'%i for i in range(29)))
        self.assertIn('truncated=false',self.call('pretool'))
        self.plan.write_text(self.plan.read_text()+'outside head\n')
        self.assertIn('truncated=true',self.call('pretool'))

    def test_refused_prompt_does_not_seed_and_clears_old_context(self):
        self.call('pretool')
        (self.root/'progress.md').write_bytes(b'x'*(1048576+1))
        self.assertEqual('',self.call('userprompt'))
        self.assertIn('Throttle plan',self.call('pretool'))

    def test_private_cache_bad_slot_fails_toward_repeated_output(self):
        self.call('pretool')
        slot=next((self.cache/'pwf-pretool').iterdir())
        slot.write_bytes(b'x'*129)
        for _ in range(2):
            self.assertIn('Throttle plan',self.call('pretool'))
        self.assertEqual(b'x'*129,slot.read_bytes())
        slot.unlink()
        target=self.root/'keep-me'; target.write_text('keep')
        try:
            os.link(target,slot)
        except OSError:
            self.skipTest('hard links unavailable')
        for _ in range(2):
            self.assertIn('Throttle plan',self.call('pretool'))
        self.assertEqual('keep',target.read_text())

    def test_linked_cache_root_is_not_followed(self):
        target=self.root/'target';target.mkdir()
        try:
            (self.cache/'pwf-pretool').symlink_to(target,target_is_directory=True)
        except OSError:
            self.skipTest('symlinks unavailable')
        for _ in range(2):
            self.assertIn('Throttle plan',self.call('pretool'))
        self.assertEqual([],list(target.iterdir()))

    def test_always_does_not_bypass_attestation_or_disabled_mode(self):
        (self.root/'.plan-attestation').write_text('0'*64)
        self.assertIn('PLAN TAMPERED',self.call('pretool',PWF_PRETOOL='always'))
        self.assertEqual('',self.call('pretool',PWF_PRETOOL='always',PLANNING_DISABLED='1'))

    def test_posttool_reminder_still_rearms_each_prompt(self):
        self.call('userprompt')
        self.assertEqual('',self.call('pretool'))
        self.assertIn('Update progress.md',self.call('posttool'))
        self.assertEqual('',self.call('posttool'))
        self.call('userprompt')
        self.assertIn('Update progress.md',self.call('posttool'))

    def test_autonomous_and_gated_keep_their_existing_pretool_policy(self):
        for mode in ('autonomous','gated'):
            (self.root/'.mode').write_text(mode)
            self.assertEqual('',self.call('pretool'))
            self.assertIn('requires attested plan',self.call('userprompt'))
            (self.root/'.plan-attestation').write_text(hashlib.sha256(self.plan.read_bytes()).hexdigest())
            self.assertIn('Throttle plan',self.call('userprompt'))
            self.assertEqual('',self.call('pretool'))
            (self.root/'.mode').unlink()
            self.assertIn('Throttle plan',self.call('pretool'))
            (self.root/'.plan-attestation').unlink()

    def test_failed_or_missing_python_cache_helper_repeats_shell_output(self):
        copy=self.root/'plugin-copy'
        shutil.copytree(REPO/'scripts',copy/'scripts')
        helper=copy/'scripts/inject-plan.py'
        helper.write_text('raise SystemExit(3)\n')
        for _ in range(2):
            self.assertIn('Throttle plan',self.call('pretool',route='shell',CLAUDE_PLUGIN_ROOT=str(copy)))
        helper.unlink()
        for _ in range(2):
            self.assertIn('Throttle plan',self.call('pretool',route='shell',CLAUDE_PLUGIN_ROOT=str(copy)))

    def test_recovery_with_missing_plan_invalidates_the_previous_view(self):
        original=self.plan.read_bytes()
        for route,events in (('python',('session','userprompt','precompact')),('shell',('session','userprompt','precompact')),('standalone',('userprompt','precompact')),('standalone-shell',('userprompt','precompact'))):
            for event in events:
                with self.subTest(route=route,event=event):
                    session=route+'-'+event
                    self.assertIn('Throttle plan',self.call('pretool',route=route,session=session))
                    self.plan.unlink()
                    self.call(event,route=route,session=session)
                    self.plan.write_bytes(original)
                    self.assertIn('Throttle plan',self.call('pretool',route=route,session=session))
