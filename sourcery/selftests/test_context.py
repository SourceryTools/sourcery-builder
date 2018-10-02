# Test sourcery.context.

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

"""Test sourcery.context."""

import argparse
import io
import locale
import os
import os.path
import sys
import unittest

from sourcery.context import add_common_options, ScriptError, ScriptContext

__all__ = ['ContextTestCase']


class ContextTestCase(unittest.TestCase):

    """Test the ScriptContext class and associated functions."""

    def setUp(self):
        """Set up a context test."""
        self.context = ScriptContext()
        self.cwd = os.getcwd()
        self.save_argv = sys.argv

    def tearDown(self):
        sys.argv = self.save_argv

    def test_add_common_options(self):
        """Test add_common_options."""
        parser = argparse.ArgumentParser()
        add_common_options(parser, os.getcwd())
        args = parser.parse_args([])
        self.assertEqual(args.toplevelprefix,
                         os.path.join(self.cwd, 'install'))
        self.assertEqual(args.logdir,
                         os.path.join(self.cwd, 'logs'))
        self.assertEqual(args.objdir,
                         os.path.join(self.cwd, 'obj'))
        self.assertEqual(args.pkgdir,
                         os.path.join(self.cwd, 'pkg'))
        self.assertEqual(args.srcdir,
                         os.path.join(self.cwd, 'src'))
        self.assertEqual(args.testlogdir,
                         os.path.join(self.cwd, 'testlogs'))
        self.assertFalse(args.verbose)
        self.assertFalse(args.silent)
        args = parser.parse_args(['-i', 'arg1', '-l', 'arg2', '-o', 'arg3',
                                  '-p', 'arg4', '-s', 'arg5', '-T', 'arg6',
                                  '-v'])
        self.assertEqual(args.toplevelprefix,
                         os.path.join(self.cwd, 'arg1'))
        self.assertEqual(args.logdir,
                         os.path.join(self.cwd, 'arg2'))
        self.assertEqual(args.objdir,
                         os.path.join(self.cwd, 'arg3'))
        self.assertEqual(args.pkgdir,
                         os.path.join(self.cwd, 'arg4'))
        self.assertEqual(args.srcdir,
                         os.path.join(self.cwd, 'arg5'))
        self.assertEqual(args.testlogdir,
                         os.path.join(self.cwd, 'arg6'))
        self.assertTrue(args.verbose)
        self.assertFalse(args.silent)
        args = parser.parse_args(['-i', '/arg1', '-l', '/arg2', '-o', '/arg3',
                                  '-p', '/arg4', '-s', '/arg5', '-T', '/arg6',
                                  '--silent'])
        self.assertEqual(args.toplevelprefix, '/arg1')
        self.assertEqual(args.logdir, '/arg2')
        self.assertEqual(args.objdir, '/arg3')
        self.assertEqual(args.pkgdir, '/arg4')
        self.assertEqual(args.srcdir, '/arg5')
        self.assertEqual(args.testlogdir, '/arg6')
        self.assertFalse(args.verbose)
        self.assertTrue(args.silent)

    def test_init(self):
        """Test ScriptContext.__init__."""
        # We can't test more for most attributes than just repeating
        # the assignments in __init__ as assertions.
        self.assertEqual(self.context.orig_script_full,
                         os.path.abspath(sys.argv[0]))
        self.assertEqual(self.context.script_full,
                         os.path.abspath(sys.argv[0]))
        self.assertEqual(self.context.interp, sys.executable)
        self.assertEqual(self.context.script_only,
                         os.path.basename(sys.argv[0]))
        self.assertTrue(os.path.isabs(self.context.sourcery_builder_dir))
        self.assertTrue(os.path.isdir(self.context.sourcery_builder_dir))
        sb_script = os.path.join(self.context.sourcery_builder_dir,
                                 'sourcery-builder')
        sb_readme = os.path.join(self.context.sourcery_builder_dir, 'README')
        sb_run_command = os.path.join(self.context.sourcery_builder_dir,
                                      'build-wrappers', 'run-command')
        self.assertTrue(os.access(sb_script, os.F_OK))
        self.assertTrue(os.access(sb_readme, os.F_OK))
        self.assertTrue(os.access(sb_run_command, os.F_OK))
        self.assertEqual(self.context.script, os.path.basename(sys.argv[0]))
        self.assertFalse(self.context.silent)
        self.assertFalse(self.context.verbose_messages)
        self.assertEqual(self.context.message_file, sys.stderr)
        self.assertFalse(self.context.execute_silent)
        self.assertIs(self.context.environ, os.environ)
        self.assertEqual(self.context.environ_orig, os.environ)
        self.assertIsNot(self.context.environ_orig, os.environ)
        self.assertIs(self.context.flags, sys.flags)
        self.assertEqual(self.context.execve, os.execve)
        self.assertEqual(self.context.setlocale, locale.setlocale)
        self.assertIn('self-test', self.context.commands)
        import sourcery.commands.self_test
        self.assertEqual(self.context.commands['self-test'],
                         sourcery.commands.self_test.Command)
        self.assertIn('gcc', self.context.components)
        import sourcery.components.gcc
        self.assertEqual(self.context.components['gcc'],
                         sourcery.components.gcc.Component)
        # Test loading extra commands and components.
        test_context = ScriptContext(['sourcery.selftests'])
        self.assertIn('self-test', test_context.commands)
        self.assertEqual(test_context.commands['self-test'],
                         sourcery.commands.self_test.Command)
        self.assertIn('null', test_context.commands)
        import sourcery.selftests.commands.null
        self.assertEqual(test_context.commands['null'],
                         sourcery.selftests.commands.null.Command)
        self.assertIn('gcc', test_context.components)
        self.assertEqual(test_context.components['gcc'],
                         sourcery.components.gcc.Component)
        self.assertIn('generic', test_context.components)
        import sourcery.selftests.components.generic
        self.assertEqual(test_context.components['generic'],
                         sourcery.selftests.components.generic.Component)
        # Errors for duplicate commands and components are not tested
        # here, and are expected to be removed to allow for packages
        # with extra commands and components to provide extra Command
        # and Component methods, and to implement those for commands
        # and components that exist in base Sourcery Builder
        # (inheriting from those commands and components).

    def test_build_wrapper_path(self):
        """Test ScriptContext.build_wrapper_path."""
        path = self.context.build_wrapper_path('start-task')
        self.assertEqual(path, os.path.join(self.context.sourcery_builder_dir,
                                            'build-wrappers', 'start-task'))
        self.assertTrue(os.access(path, os.F_OK))

    def test_inform(self):
        """Test ScriptContext.inform."""
        self.context.message_file = io.StringIO()
        self.context.inform('test message')
        output = self.context.message_file.getvalue()
        self.assertIn('test message', output)
        self.assertRegex(output, r'^\[[0-2][0-9]:[0-5][0-9]:[0-6][0-9]\] ')

    def test_inform_start(self):
        """Test ScriptContext.inform_start."""
        self.context.message_file = io.StringIO()
        sys.argv = ['cmd', 'arg1', 'arg2']
        self.context.inform_start()
        output = self.context.message_file.getvalue()
        self.assertIn('%s arg1 arg2 starting...' % self.context.script_only,
                      output)
        self.assertRegex(output, r'^\[[0-2][0-9]:[0-5][0-9]:[0-6][0-9]\] ')

    def test_inform_end(self):
        """Test ScriptContext.inform_end."""
        self.context.message_file = io.StringIO()
        self.context.inform_end()
        output = self.context.message_file.getvalue()
        self.assertIn('... %s complete.' % self.context.script, output)
        self.assertRegex(output, r'^\[[0-2][0-9]:[0-5][0-9]:[0-6][0-9]\] ')

    def test_verbose(self):
        """Test ScriptContext.verbose."""
        self.context.message_file = io.StringIO()
        self.context.verbose('test verbose message')
        output = self.context.message_file.getvalue()
        self.assertEqual(output, '')
        self.context.verbose_messages = True
        self.context.message_file = io.StringIO()
        self.context.verbose('test verbose message')
        output = self.context.message_file.getvalue()
        self.assertEqual(output,
                         '%s: test verbose message\n' % self.context.script)

    def test_warning(self):
        """Test ScriptContext.warning."""
        self.context.message_file = io.StringIO()
        self.context.warning('test warning message')
        output = self.context.message_file.getvalue()
        self.assertEqual(output,
                         ('%s: warning: test warning message\n'
                          % self.context.script))

    def test_error(self):
        """Test ScriptContext.error."""
        self.assertRaisesRegex(ScriptError, 'test error message',
                               self.context.error, 'test error message')
