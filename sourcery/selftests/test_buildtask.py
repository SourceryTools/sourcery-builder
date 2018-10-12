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
from sourcery.buildtask import BuildCommand, BuildMake, BuildPython
from sourcery.context import add_common_options, add_parallelism_option, \
    ScriptContext, ScriptError
from sourcery.makefile import command_to_make
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
