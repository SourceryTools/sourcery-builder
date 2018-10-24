# Test sourcery.buildtask.

# Copyright 2018 Mentor Graphics Corporation.

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation; either version 2.1 of the
# License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public
# License along with this program; if not, see
# <https://www.gnu.org/licenses/>.

"""Test sourcery.buildtask."""

import argparse
import tempfile
import unittest

from sourcery.build import BuildContext
from sourcery.buildcfg import BuildCfg
from sourcery.buildtask import BuildCommand, BuildMake, BuildPython, BuildTask
from sourcery.context import add_common_options, add_parallelism_option, \
    ScriptContext, ScriptError
from sourcery.fstree import FSTreeEmpty
from sourcery.makefile import command_to_make
from sourcery.pkghost import PkgHost
from sourcery.relcfg import ReleaseConfig, ReleaseConfigTextLoader

__all__ = ['BuildStepTestCase']


class BuildStepTestCase(unittest.TestCase):

    """Test the BuildStep class and subclasses."""

    def setUp(self):
        """Set up a BuildStep test."""
        self.context = ScriptContext()
        self.tempdir_td = tempfile.TemporaryDirectory()
        self.tempdir = self.tempdir_td.name
        parser = argparse.ArgumentParser()
        add_common_options(parser, self.tempdir)
        add_parallelism_option(parser)
        self.args = parser.parse_args([])
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        self.relcfg = ReleaseConfig(self.context, relcfg_text,
                                    ReleaseConfigTextLoader(), self.args)
        self.build_context = BuildContext(self.context, self.relcfg, self.args)

    def tearDown(self):
        """Tear down a BuildStep test."""
        self.tempdir_td.cleanup()

    def test_command(self):
        """Test BuildCommand."""
        log = 'test-log'
        fail_message = 'test-fail-message'
        test_cwd = 'test-cwd'
        # Leave it to tests of BuildContext to verify the exact
        # wrapper invocation generated, and that commands do get
        # executed properly.
        expect_wrapper_none = command_to_make(
            self.context,
            self.build_context.wrapper_run_command(log, fail_message, ''))
        expect_wrapper_cwd = command_to_make(
            self.context,
            self.build_context.wrapper_run_command(log, fail_message,
                                                   test_cwd))
        command = BuildCommand(self.context, ['x', "a$b"])
        self.assertEqual(str(command), "x 'a$b'")
        self.assertEqual(command.make_string(
            self.build_context, log, fail_message, {}),
                         "%s x 'a$$b'" % expect_wrapper_none)
        command = BuildCommand(self.context, ['x', "a$b"], test_cwd)
        self.assertEqual(str(command), "x 'a$b'")
        self.assertEqual(command.make_string(
            self.build_context, log, fail_message, {}),
                         "%s x 'a$$b'" % expect_wrapper_cwd)
        self.assertEqual(command.make_string(
            self.build_context, log, fail_message,
            {'Z': 'x$y', 'A': 'q'}),
                         "%s env A=q 'Z=x$$y' x 'a$$b'" % expect_wrapper_cwd)

    def test_command_errors(self):
        """Test BuildCommand errors."""
        self.assertRaisesRegex(ScriptError, 'newline in command',
                               BuildCommand, self.context, ['x', 'a\nb'])

    def test_make(self):
        """Test BuildMake."""
        log = 'test-log'
        fail_message = 'test-fail-message'
        test_cwd = 'test-cwd'
        expect_wrapper_none = command_to_make(
            self.context,
            self.build_context.wrapper_run_command(log, fail_message, ''))
        expect_wrapper_cwd = command_to_make(
            self.context,
            self.build_context.wrapper_run_command(log, fail_message,
                                                   test_cwd))
        command = BuildMake(self.context, ['all', "a$b"])
        self.assertEqual(str(command), "$(MAKE) all 'a$b'")
        self.assertEqual(command.make_string(
            self.build_context, log, fail_message, {}),
                         "%s $(MAKE) all 'a$$b'" % expect_wrapper_none)
        command = BuildMake(self.context, ['all', "a$b"], test_cwd)
        self.assertEqual(str(command), "$(MAKE) all 'a$b'")
        self.assertEqual(command.make_string(
            self.build_context, log, fail_message, {}),
                         "%s $(MAKE) all 'a$$b'" % expect_wrapper_cwd)
        self.assertEqual(command.make_string(
            self.build_context, log, fail_message,
            {'Z': 'x$y', 'A': 'q'}),
                         "%s env A=q 'Z=x$$y' $(MAKE) all 'a$$b'"
                         % expect_wrapper_cwd)

    def test_make_errors(self):
        """Test BuildMake errors."""
        self.assertRaisesRegex(ScriptError, 'newline in command',
                               BuildMake, self.context, ['all', 'a\nb'])

    def test_python(self):
        """Test BuildPython."""
        log = 'test-log'
        fail_message = 'test-fail-message'
        expect_wrapper = command_to_make(
            self.context,
            self.build_context.wrapper_run_command(log, fail_message, ''))
        expect_rpc = command_to_make(
            self.context,
            self.build_context.rpc_client_command(1))
        command = BuildPython(self.context, self.test_python, [1, '2'])
        self.assertRegex(str(command), r"^python: .*\(1, '2'\)\Z")
        self.assertEqual(command.make_string(
            self.build_context, log, fail_message, {}),
                         '%s %s' % (expect_wrapper, expect_rpc))

    def test_python_env(self):
        """Test BuildPython with environment variables specified."""
        log = 'test-log'
        fail_message = 'test-fail-message'
        expect_wrapper = command_to_make(
            self.context,
            self.build_context.wrapper_run_command(log, fail_message, ''))
        expect_rpc = command_to_make(
            self.context,
            self.build_context.rpc_client_command(1))
        command = BuildPython(self.context, self.test_python, [1, '2'])
        self.assertRegex(str(command), r"^python: .*\(1, '2'\)\Z")
        # Environment variables are useless for Python steps, but are
        # specified at task level and apply to subtasks unless
        # overridden, so may be present for such a step anyway.
        self.assertEqual(command.make_string(
            self.build_context, log, fail_message, {'A': 'B'}),
                         '%s env A=B %s' % (expect_wrapper, expect_rpc))


class BuildTaskTestCase(unittest.TestCase):

    """Test the BuildTask class."""

    def setUp(self):
        """Set up a BuildTask test."""
        self.context = ScriptContext()
        self.context.environ = dict(self.context.environ)
        for key in ('A', 'B', 'C', 'D'):
            if key in self.context.environ:
                del self.context.environ[key]
        self.tempdir_td = tempfile.TemporaryDirectory()
        self.tempdir = self.tempdir_td.name
        parser = argparse.ArgumentParser()
        add_common_options(parser, self.tempdir)
        add_parallelism_option(parser)
        self.args = parser.parse_args([])
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        self.relcfg = ReleaseConfig(self.context, relcfg_text,
                                    ReleaseConfigTextLoader(), self.args)
        self.build_context = BuildContext(self.context, self.relcfg, self.args)

    def tearDown(self):
        """Tear down a BuildStep test."""
        self.tempdir_td.cleanup()

    def test_init(self):
        """Test BuildTask.__init__."""
        top_task = BuildTask(self.relcfg, None, '', True)
        self.assertEqual(top_task.relcfg, self.relcfg)
        self.assertEqual(top_task.context, self.context)
        sub_task = BuildTask(self.relcfg, top_task, 'b', True)
        sub2_task = BuildTask(self.relcfg, sub_task, 'c', False)
        BuildTask(self.relcfg, sub_task, 'd', False)
        BuildTask(self.relcfg, sub2_task, 'sub_a', False)
        BuildTask(self.relcfg, sub2_task, 'sub_b', False)
        # The full details of how dependencies are set up for subtasks
        # are verified in tests of record_deps.
        deps = {}
        top_task.record_deps(deps)
        self.assertIn('task-end/b/c/sub_a', deps['task-start/b/c/sub_b'])
        self.assertIn('task-start/b/c/sub_b', deps['task-end/b/c/sub_b'])
        self.assertIn('task-end/b/c/sub_b', deps['task-end/b/c'])
        self.assertIn('task-start/b/c', deps['task-start/b/c/sub_a'])

    def test_init_errors(self):
        """Test errors from BuildTask.__init__."""
        self.assertRaisesRegex(ScriptError, 'invalid build task name',
                               BuildTask, self.relcfg, None, '/b', True)
        self.assertRaisesRegex(ScriptError, 'top-level task has nonempty name',
                               BuildTask, self.relcfg, None, 'b', True)
        top_task = BuildTask(self.relcfg, None, '', True)
        self.assertRaisesRegex(ScriptError, 'empty task name not at top level',
                               BuildTask, self.relcfg, top_task, '', True)
        top_task.finalize()
        self.assertRaisesRegex(ScriptError,
                               '__init__ called after finalization',
                               BuildTask, self.relcfg, top_task, 'b', True)
        top_task = BuildTask(self.relcfg, None, '', True)
        sub_task = BuildTask(self.relcfg, top_task, 'b', True)
        self.assertRaisesRegex(ScriptError,
                               'duplicate task name: /b',
                               BuildTask, self.relcfg, top_task, 'b', True)
        sub2_task = BuildTask(self.relcfg, sub_task, 'c', False)
        self.assertRaisesRegex(ScriptError,
                               'duplicate task name: /b/c',
                               BuildTask, self.relcfg, sub_task, 'c', True)
        # Errors from _add_subtask are errors from __init__ as far as
        # BuildTask users are concerned, so test them here.
        sub2_task.add_command(['test', 'command'])
        self.assertRaisesRegex(ScriptError,
                               'task /b/c has both commands or Python steps '
                               'and subtasks',
                               BuildTask, self.relcfg, sub2_task, 'd', False)
        sub3_task = BuildTask(self.relcfg, sub_task, 'd', False)
        sub3_task.add_make(['test', 'make'], '/test-cwd')
        self.assertRaisesRegex(ScriptError,
                               'task /b/d has both commands or Python steps '
                               'and subtasks',
                               BuildTask, self.relcfg, sub3_task, 'e', False)
        sub4_task = BuildTask(self.relcfg, sub_task, 'e', False)
        sub4_task.add_python(int, ())
        self.assertRaisesRegex(ScriptError,
                               'task /b/e has both commands or Python steps '
                               'and subtasks',
                               BuildTask, self.relcfg, sub4_task, 'f', False)

    def test_add_command(self):
        """Test add_command."""
        # For all the various ways of adding commands, the details of
        # the commands making their way through to the Makefile are
        # verified in tests of makefile_text.
        top_task = BuildTask(self.relcfg, None, '', False)
        top_task.add_command(['test', 'cmd'])
        top_task.add_command(['test', 'cmd2'])
        top_task.add_command(['test', 'cmd3'], cwd='/some/where')

    def test_add_command_errors(self):
        """Test errors from add_command."""
        top_task = BuildTask(self.relcfg, None, '', False)
        top_task.finalize()
        self.assertRaisesRegex(ScriptError,
                               'add_command called after finalization',
                               top_task.add_command, ['test'])
        top_task = BuildTask(self.relcfg, None, '', False)
        sub_task = BuildTask(self.relcfg, top_task, 'b', True)
        sub2_task = BuildTask(self.relcfg, top_task, 'c', False)
        BuildTask(self.relcfg, sub2_task, 'd', False)
        self.assertRaisesRegex(ScriptError,
                               'task /c has both commands and subtasks',
                               sub2_task.add_command, ['test'])
        self.assertRaisesRegex(ScriptError,
                               'parallel task /b has commands',
                               sub_task.add_command, ['test'])

    def test_add_python(self):
        """Test add_python."""
        top_task = BuildTask(self.relcfg, None, '', False)
        top_task.add_python(int, ())
        top_task.add_python(int, [1])

    def test_add_python_errors(self):
        """Test errors from add_python."""
        top_task = BuildTask(self.relcfg, None, '', False)
        top_task.finalize()
        self.assertRaisesRegex(ScriptError,
                               'add_python called after finalization',
                               top_task.add_python, int, ())
        top_task = BuildTask(self.relcfg, None, '', False)
        sub_task = BuildTask(self.relcfg, top_task, 'b', True)
        sub2_task = BuildTask(self.relcfg, top_task, 'c', False)
        BuildTask(self.relcfg, sub2_task, 'd', False)
        self.assertRaisesRegex(ScriptError,
                               'task /c has both Python steps and subtasks',
                               sub2_task.add_python, int, ())
        self.assertRaisesRegex(ScriptError,
                               'parallel task /b has Python steps',
                               sub_task.add_python, int, ())

    def test_add_empty_dir(self):
        """Test add_empty_dir."""
        top_task = BuildTask(self.relcfg, None, '', False)
        top_task.add_empty_dir('/some/where')
        top_task.add_empty_dir('/some/other')

    def test_add_empty_dir_errors(self):
        """Test errors from add_empty_dir."""
        top_task = BuildTask(self.relcfg, None, '', False)
        top_task.finalize()
        self.assertRaisesRegex(ScriptError,
                               'add_empty_dir called after finalization',
                               top_task.add_empty_dir, '/testdir')
        top_task = BuildTask(self.relcfg, None, '', False)
        sub_task = BuildTask(self.relcfg, top_task, 'b', True)
        sub2_task = BuildTask(self.relcfg, top_task, 'c', False)
        BuildTask(self.relcfg, sub2_task, 'd', False)
        self.assertRaisesRegex(ScriptError,
                               'task /c has both commands and subtasks',
                               sub2_task.add_empty_dir, '/testdir')
        self.assertRaisesRegex(ScriptError,
                               'parallel task /b has commands',
                               sub_task.add_empty_dir, '/testdir')

    def test_add_empty_dir_parent(self):
        """Test add_empty_dir_parent."""
        top_task = BuildTask(self.relcfg, None, '', False)
        top_task.add_empty_dir_parent('/some/where')
        top_task.add_empty_dir_parent('/some/other')

    def test_add_empty_dir_parent_errors(self):
        """Test errors from add_empty_dir_parent."""
        top_task = BuildTask(self.relcfg, None, '', False)
        top_task.finalize()
        self.assertRaisesRegex(ScriptError,
                               'add_empty_dir_parent called after '
                               'finalization',
                               top_task.add_empty_dir_parent, '/testdir')
        top_task = BuildTask(self.relcfg, None, '', False)
        sub_task = BuildTask(self.relcfg, top_task, 'b', True)
        sub2_task = BuildTask(self.relcfg, top_task, 'c', False)
        BuildTask(self.relcfg, sub2_task, 'd', False)
        self.assertRaisesRegex(ScriptError,
                               'task /c has both commands and subtasks',
                               sub2_task.add_empty_dir_parent, '/testdir')
        self.assertRaisesRegex(ScriptError,
                               'parallel task /b has commands',
                               sub_task.add_empty_dir_parent, '/testdir')

    def test_add_make(self):
        """Test add_make."""
        top_task = BuildTask(self.relcfg, None, '', False)
        top_task.add_make(['test', 'arg'], '/some/where')

    def test_add_make_errors(self):
        """Test errors from add_make."""
        top_task = BuildTask(self.relcfg, None, '', False)
        top_task.finalize()
        self.assertRaisesRegex(ScriptError,
                               'add_make called after finalization',
                               top_task.add_make, ['test'], '/testdir')
        top_task = BuildTask(self.relcfg, None, '', False)
        sub_task = BuildTask(self.relcfg, top_task, 'b', True)
        sub2_task = BuildTask(self.relcfg, top_task, 'c', False)
        BuildTask(self.relcfg, sub2_task, 'd', False)
        self.assertRaisesRegex(ScriptError,
                               'task /c has both commands and subtasks',
                               sub2_task.add_make, ['test'], '/testdir2')
        self.assertRaisesRegex(ScriptError,
                               'parallel task /b has commands',
                               sub_task.add_make, ['test'], '/testdir3')

    def test_env_set(self):
        """Test env_set."""
        top_task = BuildTask(self.relcfg, None, '', False)
        top_task.env_set('A', 'B')
        top_task.env_set('C', 'D')
        top_task.finalize()
        self.assertEqual(top_task.get_full_env()['A'], 'B')
        self.assertEqual(top_task.get_full_env()['C'], 'D')
        # ':' and '=' are OK in variable values (although '=' is not
        # OK in names and ':' is not OK in values when prepending).
        top_task = BuildTask(self.relcfg, None, '', False)
        top_task.env_set('PATH', 'A=B:C=D')
        top_task.finalize()
        self.assertEqual(top_task.get_full_env()['PATH'], 'A=B:C=D')
        top_task = BuildTask(self.relcfg, None, '', False)
        top_task.env_set('A', 'B')
        top_task.env_set('A', 'C')
        top_task.finalize()
        self.assertEqual(top_task.get_full_env()['A'], 'C')

    def test_env_set_errors(self):
        """Test errors from env_set."""
        top_task = BuildTask(self.relcfg, None, '', False)
        top_task.finalize()
        self.assertRaisesRegex(ScriptError,
                               'env_set called after finalization',
                               top_task.env_set, 'A', 'B')
        top_task = BuildTask(self.relcfg, None, '', False)
        self.assertRaisesRegex(ScriptError,
                               'bad character in environment variable setting',
                               top_task.env_set, 'A=', 'B')
        self.assertRaisesRegex(ScriptError,
                               'bad character in environment variable setting',
                               top_task.env_set, 'A\nB', 'B')
        self.assertRaisesRegex(ScriptError,
                               'bad character in environment variable setting',
                               top_task.env_set, 'A', 'B\nC')
        top_task.env_prepend('PATH', 'X')
        self.assertRaisesRegex(ScriptError,
                               'variable PATH both set and prepended to',
                               top_task.env_set, 'PATH', 'Y')

    def test_env_prepend(self):
        """Test env_prepend."""
        top_task = BuildTask(self.relcfg, None, '', False)
        self.context.environ['B'] = 'orig_B'
        top_task.env_prepend('A', 'A1')
        top_task.env_prepend('A', 'A2')
        top_task.env_prepend('B', 'B1')
        top_task.env_prepend('B', 'B2=B3')
        top_task.env_prepend('C', 'C1')
        top_task.finalize()
        self.assertEqual(top_task.get_full_env()['A'], 'A2:A1')
        self.assertEqual(top_task.get_full_env()['B'], 'B2=B3:B1:orig_B')
        self.assertEqual(top_task.get_full_env()['C'], 'C1')

    def test_env_prepend_errors(self):
        """Test errors from env_prepend."""
        top_task = BuildTask(self.relcfg, None, '', False)
        top_task.finalize()
        self.assertRaisesRegex(ScriptError,
                               'env_prepend called after finalization',
                               top_task.env_prepend, 'A', 'B')
        top_task = BuildTask(self.relcfg, None, '', False)
        self.assertRaisesRegex(ScriptError,
                               'bad character in environment variable setting',
                               top_task.env_prepend, 'A=', 'B')
        self.assertRaisesRegex(ScriptError,
                               'bad character in environment variable setting',
                               top_task.env_prepend, 'A\nB', 'B')
        self.assertRaisesRegex(ScriptError,
                               'bad character in environment variable setting',
                               top_task.env_prepend, 'A', 'B\nC')
        self.assertRaisesRegex(ScriptError,
                               'bad character in environment variable setting',
                               top_task.env_prepend, 'A', 'B:C')
        top_task.env_set('A', 'B')
        self.assertRaisesRegex(ScriptError,
                               'variable A both set and prepended to',
                               top_task.env_prepend, 'A', 'C')

    def test_get_full_env(self):
        """Test get_full_env."""
        top_task = BuildTask(self.relcfg, None, '', False)
        self.context.environ['A'] = 'orig_A'
        self.context.environ['B'] = 'orig_B'
        sub1_task = BuildTask(self.relcfg, top_task, 'a', False)
        sub1_task.env_set('B', 'B1')
        sub1_task.env_set('C', 'C1')
        sub1_task.env_prepend('D', 'D1')
        sub2_task = BuildTask(self.relcfg, sub1_task, 'b', False)
        sub2_task.env_prepend('A', 'A2')
        sub2_task.env_prepend('B', 'B2')
        sub2_task.env_prepend('C', 'C2')
        sub2_task.env_prepend('D', 'D2')
        sub3_task = BuildTask(self.relcfg, sub2_task, 'c', False)
        sub3_task.env_prepend('A', 'A3')
        sub3_task.env_set('B', 'B3')
        sub3_task.env_set('C', 'C3')
        top_task.finalize()
        env = top_task.get_full_env()
        self.assertEqual(env, {})
        env = sub1_task.get_full_env()
        self.assertEqual(env, {'B': 'B1', 'C': 'C1', 'D': 'D1'})
        env = sub2_task.get_full_env()
        self.assertEqual(env, {'A': 'A2:orig_A', 'B': 'B2:B1', 'C': 'C2:C1',
                               'D': 'D2:D1'})
        env = sub3_task.get_full_env()
        self.assertEqual(env, {'A': 'A3:A2:orig_A', 'B': 'B3', 'C': 'C3',
                               'D': 'D2:D1'})

    def test_get_full_env_errors(self):
        """Test errors from get_full_env."""
        top_task = BuildTask(self.relcfg, None, '', False)
        self.assertRaisesRegex(ScriptError,
                               'get_full_env called before finalization',
                               top_task.get_full_env)

    def test_depend(self):
        """Test depend."""
        top_task = BuildTask(self.relcfg, None, '', True)
        sub1_task = BuildTask(self.relcfg, top_task, 'a', False)
        deps = {}
        top_task.record_deps(deps)
        self.assertNotIn('task-end/b', deps['task-start/a'])
        # Dependencies may be created before or after the task being
        # depended on has been created.
        sub1_task.depend('/b')
        deps = {}
        top_task.record_deps(deps)
        self.assertIn('task-end/b', deps['task-start/a'])
        BuildTask(self.relcfg, top_task, 'c', False)
        sub1_task.depend('/c')
        deps = {}
        top_task.record_deps(deps)
        self.assertIn('task-end/c', deps['task-start/a'])

    def test_depend_errors(self):
        """Test errors from depend."""
        top_task = BuildTask(self.relcfg, None, '', True)
        sub1_task = BuildTask(self.relcfg, top_task, 'a', False)
        BuildTask(self.relcfg, top_task, 'b', False)
        top_task.finalize()
        self.assertRaisesRegex(ScriptError,
                               'depend called after finalization',
                               sub1_task.depend, '/b')

    def test_depend_install(self):
        """Test depend_install."""
        top_task = BuildTask(self.relcfg, None, '', True)
        sub1_task = BuildTask(self.relcfg, top_task, 'a', False)
        dep_pkg = PkgHost(self.context, 'x86_64-pc-linux-gnu')
        dep_build = BuildCfg(self.context, 'aarch64-linux-gnu')
        sub1_task.depend_install(dep_pkg, 'test-pkg')
        deps = {}
        top_task.record_deps(deps)
        self.assertIn('install-trees/x86_64-pc-linux-gnu/test-pkg',
                      deps['task-start/a'])
        sub1_task.depend_install(dep_build, 'test-build')
        deps = {}
        top_task.record_deps(deps)
        self.assertIn('install-trees/aarch64-linux-gnu/test-build',
                      deps['task-start/a'])

    def test_depend_install_errors(self):
        """Test errors from depend_install."""
        top_task = BuildTask(self.relcfg, None, '', True)
        sub1_task = BuildTask(self.relcfg, top_task, 'a', False)
        top_task.finalize()
        dep_pkg = PkgHost(self.context, 'x86_64-pc-linux-gnu')
        self.assertRaisesRegex(ScriptError,
                               'depend_install called after finalization',
                               sub1_task.depend_install, dep_pkg, 'test')

    def test_provide_install(self):
        """Test provide_install."""
        top_task = BuildTask(self.relcfg, None, '', True)
        sub1_task = BuildTask(self.relcfg, top_task, 'a', False)
        prov_pkg = PkgHost(self.context, 'x86_64-pc-linux-gnu')
        prov_build = BuildCfg(self.context, 'aarch64-linux-gnu')
        sub1_task.provide_install(prov_pkg, 'test-pkg')
        sub1_task.provide_install(prov_build, 'test-build')
        deps = {}
        top_task.record_deps(deps)
        self.assertIn('task-end/a',
                      deps['install-trees/x86_64-pc-linux-gnu/test-pkg'])
        self.assertIn('task-end/a',
                      deps['install-trees/aarch64-linux-gnu/test-build'])

    def test_provide_install_errors(self):
        """Test errors from provide_install."""
        top_task = BuildTask(self.relcfg, None, '', True)
        sub1_task = BuildTask(self.relcfg, top_task, 'a', False)
        prov_pkg = PkgHost(self.context, 'x86_64-pc-linux-gnu')
        prov_build = BuildCfg(self.context, 'aarch64-linux-gnu')
        tree = FSTreeEmpty(self.context)
        top_task.finalize()
        self.assertRaisesRegex(ScriptError,
                               'provide_install called after finalization',
                               sub1_task.provide_install, prov_pkg, 'test')
        top_task = BuildTask(self.relcfg, None, '', True)
        sub1_task = BuildTask(self.relcfg, top_task, 'a', False)
        sub1_task.provide_install(prov_pkg, 'test-pkg')
        self.assertRaisesRegex(ScriptError,
                               'install tree x86_64-pc-linux-gnu/test-pkg '
                               'already provided',
                               sub1_task.provide_install, prov_pkg, 'test-pkg')
        top_task.declare_implicit_install(prov_build, 'test-2')
        top_task.contribute_implicit_install(prov_pkg, 'test-3', tree)
        top_task.define_implicit_install(prov_build, 'test-4', tree)
        self.assertRaisesRegex(ScriptError,
                               'install tree aarch64-linux-gnu/test-2 '
                               'already declared',
                               sub1_task.provide_install, prov_build, 'test-2')
        self.assertRaisesRegex(ScriptError,
                               'install tree x86_64-pc-linux-gnu/test-3 '
                               'already contributed to',
                               sub1_task.provide_install, prov_pkg, 'test-3')
        self.assertRaisesRegex(ScriptError,
                               'install tree aarch64-linux-gnu/test-4 '
                               'already defined',
                               sub1_task.provide_install, prov_build, 'test-4')

    def test_declare_implicit_install(self):
        """Test declare_implicit_install."""
        top_task = BuildTask(self.relcfg, None, '', True)
        sub1_task = BuildTask(self.relcfg, top_task, 'a', False)
        impl_pkg = PkgHost(self.context, 'x86_64-pc-linux-gnu')
        impl_build = BuildCfg(self.context, 'aarch64-linux-gnu')
        tree = FSTreeEmpty(self.context)
        sub1_task.declare_implicit_install(impl_pkg, 'test-pkg')
        sub1_task.declare_implicit_install(impl_build, 'test-build')
        # declare_implicit_install may be called after
        # contribute_implicit_install.
        sub1_task.contribute_implicit_install(impl_pkg, 'test2-pkg', tree)
        sub1_task.declare_implicit_install(impl_pkg, 'test2-pkg')
        top_task.finalize()
        deps = {}
        top_task.record_deps(deps)
        # The details of tasks set up for implicitly created install
        # trees are tested in tests of finalize.
        self.assertIn('task-end/install-trees-x86_64-pc-linux-gnu/test-pkg',
                      deps['install-trees/x86_64-pc-linux-gnu/test-pkg'])
        self.assertIn('task-end/install-trees-aarch64-linux-gnu/test-build',
                      deps['install-trees/aarch64-linux-gnu/test-build'])

    def test_declare_implicit_install_errors(self):
        """Test errors from declare_implicit_install."""
        top_task = BuildTask(self.relcfg, None, '', True)
        sub1_task = BuildTask(self.relcfg, top_task, 'a', False)
        impl_pkg = PkgHost(self.context, 'x86_64-pc-linux-gnu')
        impl_build = BuildCfg(self.context, 'aarch64-linux-gnu')
        tree = FSTreeEmpty(self.context)
        top_task.finalize()
        self.assertRaisesRegex(ScriptError,
                               'declare_implicit_install called after '
                               'finalization',
                               sub1_task.declare_implicit_install, impl_pkg,
                               'test')
        top_task = BuildTask(self.relcfg, None, '', True)
        sub1_task = BuildTask(self.relcfg, top_task, 'a', False)
        sub1_task.declare_implicit_install(impl_pkg, 'test-pkg')
        self.assertRaisesRegex(ScriptError,
                               'install tree x86_64-pc-linux-gnu/test-pkg '
                               'already declared',
                               sub1_task.declare_implicit_install, impl_pkg,
                               'test-pkg')
        top_task.provide_install(impl_build, 'test-2')
        top_task.define_implicit_install(impl_pkg, 'test-3', tree)
        self.assertRaisesRegex(ScriptError,
                               'install tree aarch64-linux-gnu/test-2 '
                               'already provided',
                               sub1_task.declare_implicit_install, impl_build,
                               'test-2')
        self.assertRaisesRegex(ScriptError,
                               'install tree x86_64-pc-linux-gnu/test-3 '
                               'already defined',
                               sub1_task.declare_implicit_install, impl_pkg,
                               'test-3')

    def test_contribute_implicit_install(self):
        """Test contribute_implicit_install."""
        top_task = BuildTask(self.relcfg, None, '', True)
        sub1_task = BuildTask(self.relcfg, top_task, 'a', False)
        impl_pkg = PkgHost(self.context, 'x86_64-pc-linux-gnu')
        impl_build = BuildCfg(self.context, 'aarch64-linux-gnu')
        tree = FSTreeEmpty(self.context)
        # contribute_implicit_install may be called either before or
        # after declare_implicit_install.
        sub1_task.declare_implicit_install(impl_pkg, 'test-pkg')
        sub1_task.declare_implicit_install(impl_build, 'test-build')
        sub1_task.contribute_implicit_install(impl_pkg, 'test-pkg', tree)
        sub1_task.contribute_implicit_install(impl_build, 'test-build', tree)
        sub1_task.contribute_implicit_install(impl_pkg, 'test2-pkg', tree)
        sub1_task.contribute_implicit_install(impl_build, 'test2-build', tree)
        sub1_task.declare_implicit_install(impl_pkg, 'test2-pkg')
        sub1_task.declare_implicit_install(impl_build, 'test2-build')
        # contribute_implicit_install may be called more than once for
        # the same install tree.
        sub1_task.contribute_implicit_install(impl_build, 'test-build', tree)
        sub1_task.contribute_implicit_install(impl_pkg, 'test2-pkg', tree)
        top_task.finalize()
        deps = {}
        top_task.record_deps(deps)
        # The details of tasks set up for implicitly created install
        # trees are tested in tests of finalize.
        self.assertIn('task-end/install-trees-x86_64-pc-linux-gnu/test-pkg',
                      deps['install-trees/x86_64-pc-linux-gnu/test-pkg'])
        self.assertIn('task-end/install-trees-x86_64-pc-linux-gnu/test2-pkg',
                      deps['install-trees/x86_64-pc-linux-gnu/test2-pkg'])
        self.assertIn('task-end/install-trees-aarch64-linux-gnu/test-build',
                      deps['install-trees/aarch64-linux-gnu/test-build'])
        self.assertIn('task-end/install-trees-aarch64-linux-gnu/test2-build',
                      deps['install-trees/aarch64-linux-gnu/test2-build'])

    def test_contribute_implicit_install_errors(self):
        """Test errors from contribute_implicit_install."""
        top_task = BuildTask(self.relcfg, None, '', True)
        sub1_task = BuildTask(self.relcfg, top_task, 'a', False)
        impl_pkg = PkgHost(self.context, 'x86_64-pc-linux-gnu')
        impl_build = BuildCfg(self.context, 'aarch64-linux-gnu')
        tree = FSTreeEmpty(self.context)
        top_task.finalize()
        self.assertRaisesRegex(ScriptError,
                               'contribute_implicit_install called after '
                               'finalization',
                               sub1_task.contribute_implicit_install, impl_pkg,
                               'test', tree)
        top_task = BuildTask(self.relcfg, None, '', True)
        sub1_task = BuildTask(self.relcfg, top_task, 'a', False)
        top_task.provide_install(impl_build, 'test-2')
        top_task.define_implicit_install(impl_pkg, 'test-3', tree)
        self.assertRaisesRegex(ScriptError,
                               'install tree aarch64-linux-gnu/test-2 '
                               'already provided',
                               sub1_task.contribute_implicit_install,
                               impl_build, 'test-2', tree)
        self.assertRaisesRegex(ScriptError,
                               'install tree x86_64-pc-linux-gnu/test-3 '
                               'already defined',
                               sub1_task.contribute_implicit_install, impl_pkg,
                               'test-3', tree)

    def test_define_implicit_install(self):
        """Test define_implicit_install."""
        top_task = BuildTask(self.relcfg, None, '', True)
        sub1_task = BuildTask(self.relcfg, top_task, 'a', False)
        impl_pkg = PkgHost(self.context, 'x86_64-pc-linux-gnu')
        impl_build = BuildCfg(self.context, 'aarch64-linux-gnu')
        tree = FSTreeEmpty(self.context)
        sub1_task.define_implicit_install(impl_pkg, 'test-pkg', tree)
        sub1_task.define_implicit_install(impl_build, 'test-build', tree)
        top_task.finalize()
        deps = {}
        top_task.record_deps(deps)
        # The details of tasks set up for implicitly created install
        # trees are tested in tests of finalize.
        self.assertIn('task-end/install-trees-x86_64-pc-linux-gnu/test-pkg',
                      deps['install-trees/x86_64-pc-linux-gnu/test-pkg'])
        self.assertIn('task-end/install-trees-aarch64-linux-gnu/test-build',
                      deps['install-trees/aarch64-linux-gnu/test-build'])

    def test_define_implicit_install_errors(self):
        """Test errors from define_implicit_install."""
        top_task = BuildTask(self.relcfg, None, '', True)
        sub1_task = BuildTask(self.relcfg, top_task, 'a', False)
        impl_pkg = PkgHost(self.context, 'x86_64-pc-linux-gnu')
        impl_build = BuildCfg(self.context, 'aarch64-linux-gnu')
        tree = FSTreeEmpty(self.context)
        top_task.finalize()
        self.assertRaisesRegex(ScriptError,
                               'define_implicit_install called after '
                               'finalization',
                               sub1_task.define_implicit_install, impl_pkg,
                               'test', tree)
        top_task = BuildTask(self.relcfg, None, '', True)
        sub1_task = BuildTask(self.relcfg, top_task, 'a', False)
        sub1_task.provide_install(impl_pkg, 'test-pkg')
        self.assertRaisesRegex(ScriptError,
                               'install tree x86_64-pc-linux-gnu/test-pkg '
                               'already provided',
                               sub1_task.define_implicit_install, impl_pkg,
                               'test-pkg', tree)
        top_task.declare_implicit_install(impl_build, 'test-2')
        top_task.contribute_implicit_install(impl_pkg, 'test-3', tree)
        top_task.define_implicit_install(impl_build, 'test-4', tree)
        self.assertRaisesRegex(ScriptError,
                               'install tree aarch64-linux-gnu/test-2 '
                               'already declared',
                               sub1_task.define_implicit_install, impl_build,
                               'test-2', tree)
        self.assertRaisesRegex(ScriptError,
                               'install tree x86_64-pc-linux-gnu/test-3 '
                               'already contributed to',
                               sub1_task.define_implicit_install, impl_pkg,
                               'test-3', tree)
        self.assertRaisesRegex(ScriptError,
                               'install tree aarch64-linux-gnu/test-4 '
                               'already defined',
                               sub1_task.define_implicit_install, impl_build,
                               'test-4', tree)

    def test_start_name(self):
        """Test start_name."""
        top_task = BuildTask(self.relcfg, None, '', True)
        sub1_task = BuildTask(self.relcfg, top_task, 'a', False)
        sub2_task = BuildTask(self.relcfg, sub1_task, 'b', False)
        self.assertEqual(top_task.start_name(), 'task-start')
        self.assertEqual(sub1_task.start_name(), 'task-start/a')
        self.assertEqual(sub2_task.start_name(), 'task-start/a/b')
        top_task.finalize()
        self.assertEqual(top_task.start_name(), 'task-start')
        self.assertEqual(sub1_task.start_name(), 'task-start/a')
        self.assertEqual(sub2_task.start_name(), 'task-start/a/b')

    def test_end_name(self):
        """Test end_name."""
        top_task = BuildTask(self.relcfg, None, '', True)
        sub1_task = BuildTask(self.relcfg, top_task, 'a', False)
        sub2_task = BuildTask(self.relcfg, sub1_task, 'b', False)
        self.assertEqual(top_task.end_name(), 'task-end')
        self.assertEqual(sub1_task.end_name(), 'task-end/a')
        self.assertEqual(sub2_task.end_name(), 'task-end/a/b')
        top_task.finalize()
        self.assertEqual(top_task.end_name(), 'task-end')
        self.assertEqual(sub1_task.end_name(), 'task-end/a')
        self.assertEqual(sub2_task.end_name(), 'task-end/a/b')

    def test_log_name(self):
        """Test log_name."""
        top_task = BuildTask(self.relcfg, None, '', False)
        sub1_task = BuildTask(self.relcfg, top_task, 'z', False)
        sub1_task.add_command(['echo', 'z'])
        sub2_task = BuildTask(self.relcfg, top_task, 'a', False)
        sub2_task.add_command(['echo', 'a'])
        sub3_task = BuildTask(self.relcfg, top_task, 'c', False)
        sub4_task = BuildTask(self.relcfg, sub3_task, 'd', False)
        sub4_task.add_command(['echo', 'd'])
        top_task.finalize()
        self.assertEqual(sub1_task.log_name(), '0001-z-log.txt')
        self.assertEqual(sub2_task.log_name(), '0002-a-log.txt')
        self.assertEqual(sub4_task.log_name(), '0003-c-d-log.txt')

    def test_log_name_errors(self):
        """Test errors from log_name."""
        top_task = BuildTask(self.relcfg, None, '', False)
        sub1_task = BuildTask(self.relcfg, top_task, 'z', False)
        sub1_task.add_command(['echo', 'z'])
        self.assertRaisesRegex(ScriptError,
                               'log_name called before finalization',
                               sub1_task.log_name)

    def test_record_deps(self):
        """Test record_deps."""
        # Test serial and parallel tasks, and implicit dependencies,
        # without install trees.
        top_task = BuildTask(self.relcfg, None, '', True)
        sub_task_a = BuildTask(self.relcfg, top_task, 'a', True)
        sub_task_b = BuildTask(self.relcfg, top_task, 'b', False)
        BuildTask(self.relcfg, top_task, 'x', False)
        sub_task_y = BuildTask(self.relcfg, top_task, 'y', False)
        sub_task_y.depend('/x')
        BuildTask(self.relcfg, sub_task_a, 'c', True)
        BuildTask(self.relcfg, sub_task_a, 'd', False)
        BuildTask(self.relcfg, sub_task_b, 'e', True)
        BuildTask(self.relcfg, sub_task_b, 'f', False)
        deps = {}
        top_task.record_deps(deps)
        # Only verify the sets of dependencies, not their order.
        for key in deps:
            deps[key] = set(deps[key])
        self.assertEqual(deps,
                         {'task-start': set(),
                          'task-end': {'task-start', 'task-end/a',
                                       'task-end/b', 'task-end/x',
                                       'task-end/y'},
                          'task-start/a': {'task-start'},
                          'task-end/a': {'task-start/a', 'task-end/a/c',
                                         'task-end/a/d'},
                          'task-start/b': {'task-start'},
                          'task-end/b': {'task-start/b', 'task-end/b/e',
                                         'task-end/b/f'},
                          'task-start/x': {'task-start'},
                          'task-end/x': {'task-start/x'},
                          'task-start/y': {'task-start', 'task-end/x'},
                          'task-end/y': {'task-start/y'},
                          'task-start/a/c': {'task-start/a'},
                          'task-end/a/c': {'task-start/a/c'},
                          'task-start/a/d': {'task-start/a'},
                          'task-end/a/d': {'task-start/a/d'},
                          'task-start/b/e': {'task-start/b'},
                          'task-end/b/e': {'task-start/b/e'},
                          'task-start/b/f': {'task-start/b', 'task-end/b/e'},
                          'task-end/b/f': {'task-start/b/f'}})
        # Test case with install trees, depended on or provided.
        top_task = BuildTask(self.relcfg, None, '', True)
        sub_task_a = BuildTask(self.relcfg, top_task, 'a', True)
        sub_task_b = BuildTask(self.relcfg, top_task, 'b', False)
        test_pkg = PkgHost(self.context, 'x86_64-pc-linux-gnu')
        test_build = BuildCfg(self.context, 'aarch64-linux-gnu')
        sub_task_a.depend_install(test_pkg, 'test1')
        sub_task_a.depend_install(test_build, 'test2')
        sub_task_b.provide_install(test_pkg, 'test1')
        sub_task_b.provide_install(test_build, 'test2')
        deps = {}
        top_task.record_deps(deps)
        for key in deps:
            deps[key] = set(deps[key])
        self.assertEqual(deps,
                         {'task-start': set(),
                          'task-end': {'task-start', 'task-end/a',
                                       'task-end/b'},
                          'task-start/a': {
                              'task-start',
                              'install-trees/x86_64-pc-linux-gnu/test1',
                              'install-trees/aarch64-linux-gnu/test2'},
                          'task-end/a': {'task-start/a'},
                          'task-start/b': {'task-start'},
                          'task-end/b': {'task-start/b'},
                          'install-trees/x86_64-pc-linux-gnu/test1': {
                              'task-end/b'},
                          'install-trees/aarch64-linux-gnu/test2': {
                              'task-end/b'}})

    def test_finalize(self):
        """Test finalize."""
        # Task numbers are tested via tests of log_name, dependencies
        # via tests of record_deps, and the effect of no longer being
        # able to call various functions via tests of those functions.
        # Thus, what needs testing here is the tasks for implicitly
        # created install trees.
        top_task = BuildTask(self.relcfg, None, '', True)
        sub1_task = BuildTask(self.relcfg, top_task, 'a', False)
        sub2_task = BuildTask(self.relcfg, top_task, 'b', False)
        sub3_task = BuildTask(self.relcfg, top_task, 'c', False)
        sub4_task = BuildTask(self.relcfg, top_task, 'd', False)
        impl_pkg = PkgHost(self.context, 'x86_64-pc-linux-gnu')
        impl_build = BuildCfg(self.context, 'aarch64-linux-gnu')
        sub2_task.provide_install(impl_pkg, 'b-pkg')
        sub3_task.provide_install(impl_build, 'c-build')
        sub4_task.provide_install(impl_build, 'd-build')
        tree_pkg = self.relcfg.install_tree_fstree(impl_pkg, 'b-pkg')
        tree_build = self.relcfg.install_tree_fstree(impl_build, 'c-build')
        tree2_build = self.relcfg.install_tree_fstree(impl_build, 'd-build')
        sub1_task.declare_implicit_install(impl_pkg, 'test-pkg')
        sub1_task.declare_implicit_install(impl_build, 'test-build')
        sub1_task.contribute_implicit_install(impl_build, 'test-build',
                                              tree_build)
        sub1_task.contribute_implicit_install(impl_build, 'test-build',
                                              tree2_build)
        sub1_task.define_implicit_install(impl_pkg, 'test2-pkg', tree_pkg)
        top_task.finalize()
        deps = {}
        top_task.record_deps(deps)
        for key in deps:
            deps[key] = set(deps[key])
        self.assertEqual(deps,
                         {'task-start': set(),
                          'task-end': {
                              'task-start', 'task-end/a', 'task-end/b',
                              'task-end/c', 'task-end/d',
                              'task-end/install-trees-aarch64-linux-gnu',
                              'task-end/install-trees-x86_64-pc-linux-gnu'},
                          'task-start/a': {'task-start'},
                          'task-end/a': {'task-start/a'},
                          'task-start/b': {'task-start'},
                          'task-end/b': {'task-start/b'},
                          'task-start/c': {'task-start'},
                          'task-end/c': {'task-start/c'},
                          'task-start/d': {'task-start'},
                          'task-end/d': {'task-start/d'},
                          'task-start/install-trees-aarch64-linux-gnu': {
                              'task-start'},
                          'task-end/install-trees-aarch64-linux-gnu': {
                              'task-start/install-trees-aarch64-linux-gnu',
                              'task-end/install-trees-aarch64-linux-gnu/'
                              'test-build'},
                          'task-start/install-trees-x86_64-pc-linux-gnu': {
                              'task-start'},
                          'task-end/install-trees-x86_64-pc-linux-gnu': {
                              'task-start/install-trees-x86_64-pc-linux-gnu',
                              'task-end/install-trees-x86_64-pc-linux-gnu/'
                              'test-pkg',
                              'task-end/install-trees-x86_64-pc-linux-gnu/'
                              'test2-pkg'},
                          'task-start/install-trees-aarch64-linux-gnu/'
                          'test-build': {
                              'task-start/install-trees-aarch64-linux-gnu',
                              'install-trees/aarch64-linux-gnu/c-build',
                              'install-trees/aarch64-linux-gnu/d-build'},
                          'task-end/install-trees-aarch64-linux-gnu/'
                          'test-build': {
                              'task-start/install-trees-aarch64-linux-gnu/'
                              'test-build'},
                          'task-start/install-trees-x86_64-pc-linux-gnu/'
                          'test-pkg': {
                              'task-start/install-trees-x86_64-pc-linux-gnu'},
                          'task-end/install-trees-x86_64-pc-linux-gnu/'
                          'test-pkg': {
                              'task-start/install-trees-x86_64-pc-linux-gnu/'
                              'test-pkg'},
                          'task-start/install-trees-x86_64-pc-linux-gnu/'
                          'test2-pkg': {
                              'task-start/install-trees-x86_64-pc-linux-gnu',
                              'install-trees/x86_64-pc-linux-gnu/b-pkg'},
                          'task-end/install-trees-x86_64-pc-linux-gnu/'
                          'test2-pkg': {
                              'task-start/install-trees-x86_64-pc-linux-gnu/'
                              'test2-pkg'},
                          'install-trees/aarch64-linux-gnu/c-build': {
                              'task-end/c'},
                          'install-trees/aarch64-linux-gnu/d-build': {
                              'task-end/d'},
                          'install-trees/x86_64-pc-linux-gnu/b-pkg': {
                              'task-end/b'},
                          'install-trees/aarch64-linux-gnu/test-build': {
                              'task-end/install-trees-aarch64-linux-gnu/'
                              'test-build'},
                          'install-trees/x86_64-pc-linux-gnu/test-pkg': {
                              'task-end/install-trees-x86_64-pc-linux-gnu/'
                              'test-pkg'},
                          'install-trees/x86_64-pc-linux-gnu/test2-pkg': {
                              'task-end/install-trees-x86_64-pc-linux-gnu/'
                              'test2-pkg'}})

    def test_finalize_errors(self):
        """Test errors from finalize."""
        top_task = BuildTask(self.relcfg, None, '', True)
        sub1_task = BuildTask(self.relcfg, top_task, 'a', True)
        self.assertRaisesRegex(ScriptError,
                               'finalize called for non-top-level task /a',
                               sub1_task.finalize)
        impl_pkg = PkgHost(self.context, 'x86_64-pc-linux-gnu')
        tree = FSTreeEmpty(self.context)
        sub1_task.contribute_implicit_install(impl_pkg, 'test-pkg', tree)
        self.assertRaisesRegex(ScriptError,
                               'install tree x86_64-pc-linux-gnu/test-pkg '
                               'never declared',
                               top_task.finalize)
