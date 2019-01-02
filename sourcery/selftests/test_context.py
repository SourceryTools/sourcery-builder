# Test sourcery.context.

# Copyright 2018-2019 Mentor Graphics Corporation.

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
import contextlib
import io
import locale
import os
import os.path
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

from sourcery.context import add_common_options, add_parallelism_option, \
    ScriptError, ScriptContext
from sourcery.relcfg import ReleaseConfigTextLoader
from sourcery.selftests.support import redirect_file

__all__ = ['ContextTestCase']


class ContextTestCase(unittest.TestCase):

    """Test the ScriptContext class and associated functions."""

    def setUp(self):
        """Set up a context test."""
        self.context = ScriptContext()
        self.cwd = os.getcwd()
        self.tempdir_td = tempfile.TemporaryDirectory()
        self.tempdir = self.tempdir_td.name

    def tearDown(self):
        """Tear down a context test."""
        self.tempdir_td.cleanup()

    def temp_file(self, name):
        """Return the name of a temporary file for a test."""
        return os.path.join(self.tempdir, name)

    @contextlib.contextmanager
    def redirect_stdout_stderr(self):
        """Redirect stdout and stderr for code in a 'with' statement."""
        with redirect_file(sys.stdout, self.temp_file('stdout')):
            with redirect_file(sys.stderr, self.temp_file('stderr')):
                yield

    def temp_file_read(self, name):
        """Read a file in tempdir for this test."""
        with open(self.temp_file(name), 'r', encoding='utf-8') as file:
            return file.read()

    def msg_stdout_stderr_read(self):
        """Read the redirected messages, stdout and stderr for this test."""
        return (self.context.message_file.getvalue(),
                self.temp_file_read('stdout'), self.temp_file_read('stderr'))

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

    def test_add_parallelism_option(self):
        """Test add_parallelism_option."""
        parser = argparse.ArgumentParser()
        add_parallelism_option(parser)
        args = parser.parse_args([])
        self.assertEqual(args.parallelism, os.cpu_count())
        args = parser.parse_args(['-j', '1'])
        self.assertEqual(args.parallelism, 1)
        args = parser.parse_args(['-j', '123'])
        self.assertEqual(args.parallelism, 123)

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
        self.assertIs(self.context.execve, os.execve)
        self.assertIs(self.context.setlocale, locale.setlocale)
        self.assertIs(self.context.umask, os.umask)
        self.assertEqual(self.context.package_list, ('sourcery',))
        self.assertIn('self-test', self.context.commands)
        import sourcery.commands.self_test
        self.assertIs(self.context.commands['self-test'],
                      sourcery.commands.self_test.Command)
        self.assertIn('gcc', self.context.components)
        import sourcery.components.gcc
        self.assertIs(self.context.components['gcc'],
                      sourcery.components.gcc.Component)
        # Test loading extra commands and components.
        test_context = ScriptContext(['sourcery.selftests'])
        self.assertEqual(test_context.package_list,
                         ('sourcery', 'sourcery.selftests'))
        self.assertIn('self-test', test_context.commands)
        self.assertIs(test_context.commands['self-test'],
                      sourcery.commands.self_test.Command)
        self.assertIn('null', test_context.commands)
        import sourcery.selftests.commands.null
        self.assertIs(test_context.commands['null'],
                      sourcery.selftests.commands.null.Command)
        self.assertIn('gcc', test_context.components)
        self.assertIs(test_context.components['gcc'],
                      sourcery.components.gcc.Component)
        self.assertIn('generic', test_context.components)
        import sourcery.selftests.components.generic
        self.assertIs(test_context.components['generic'],
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
        self.context.silent = True
        self.context.message_file = io.StringIO()
        self.context.inform('test message')
        output = self.context.message_file.getvalue()
        self.assertEqual(output, '')

    def test_inform_start(self):
        """Test ScriptContext.inform_start."""
        self.context.message_file = io.StringIO()
        self.context.inform_start(['arg1', 'arg2'])
        output = self.context.message_file.getvalue()
        self.assertIn('%s arg1 arg2 starting...' % self.context.script_only,
                      output)
        self.assertRegex(output, r'^\[[0-2][0-9]:[0-5][0-9]:[0-6][0-9]\] ')
        self.context.silent = True
        self.context.message_file = io.StringIO()
        self.context.inform_start(['arg1', 'arg2'])
        output = self.context.message_file.getvalue()
        self.assertEqual(output, '')

    def test_inform_end(self):
        """Test ScriptContext.inform_end."""
        self.context.message_file = io.StringIO()
        self.context.inform_end()
        output = self.context.message_file.getvalue()
        self.assertIn('... %s complete.' % self.context.script, output)
        self.assertRegex(output, r'^\[[0-2][0-9]:[0-5][0-9]:[0-6][0-9]\] ')
        self.context.silent = True
        self.context.message_file = io.StringIO()
        self.context.inform_end()
        output = self.context.message_file.getvalue()
        self.assertEqual(output, '')

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

    def test_execute(self):
        """Test ScriptContext.execute."""
        # Ordinary execution.
        self.context.message_file = io.StringIO()
        with self.redirect_stdout_stderr():
            self.context.execute(['sh', '-c', 'echo a; echo b >&2'])
        output, stdout, stderr = self.msg_stdout_stderr_read()
        self.assertEqual(output, "sh -c 'echo a; echo b >&2'\n")
        self.assertEqual(stdout, 'a\n')
        self.assertEqual(stderr, 'b\n')
        # Making the subprocess silent.
        self.context.message_file = io.StringIO()
        self.context.execute_silent = True
        with self.redirect_stdout_stderr():
            self.context.execute(['sh', '-c', 'echo a; echo b >&2'])
        output, stdout, stderr = self.msg_stdout_stderr_read()
        self.assertEqual(output, "sh -c 'echo a; echo b >&2'\n")
        self.assertEqual(stdout, '')
        self.assertEqual(stderr, '')
        # Specifying a working directory.
        self.context.message_file = io.StringIO()
        self.context.execute_silent = False
        with self.redirect_stdout_stderr():
            self.context.execute(['sh', '-c', 'echo *'], cwd=self.tempdir)
        output, stdout, stderr = self.msg_stdout_stderr_read()
        self.assertEqual(output, ("pushd %s; sh -c 'echo *'; popd\n"
                                  % self.tempdir))
        self.assertEqual(stdout, 'stderr stdout\n')
        self.assertEqual(stderr, '')
        # Not printing the command run.
        self.context.message_file = io.StringIO()
        self.context.silent = True
        with self.redirect_stdout_stderr():
            self.context.execute(['sh', '-c', 'echo *'], cwd=self.tempdir)
        output, stdout, stderr = self.msg_stdout_stderr_read()
        self.assertEqual(output, '')
        self.assertEqual(stdout, 'stderr stdout\n')
        self.assertEqual(stderr, '')
        # Using environment variables.
        self.context.message_file = io.StringIO()
        self.context.environ = dict(self.context.environ)
        self.context.environ['TEST'] = self.tempdir
        with self.redirect_stdout_stderr():
            self.context.execute(['sh', '-c', 'echo $TEST'])
        output, stdout, stderr = self.msg_stdout_stderr_read()
        self.assertEqual(output, '')
        self.assertEqual(stdout, '%s\n' % self.tempdir)
        self.assertEqual(stderr, '')
        # Errors from execute.
        self.assertRaises(subprocess.CalledProcessError, self.context.execute,
                          ['false'])
        self.assertRaises(OSError, self.context.execute, ['true'],
                          cwd=self.temp_file('no-such-directory'))

    def test_script_command(self):
        """Test ScriptContext.script_command."""
        # We can't test much more than repeating the function's logic.
        self.assertEqual(self.context.script_command(),
                         [self.context.interp, '-s', '-E',
                          self.context.script_full])

    def test_exec_self(self):
        """Test ScriptContext.exec_self."""
        # We can't test much more than repeating the function's logic.
        self.context.execve = unittest.mock.MagicMock()
        argv = ['arg1', 'arg2']
        self.context.exec_self(argv)
        self.context.execve.assert_called_once_with(
            self.context.interp, self.context.script_command() + argv,
            self.context.environ)

    def test_clean_environment(self):
        """Test ScriptContext.clean_environment."""
        self.context.setlocale = unittest.mock.MagicMock()
        self.context.umask = unittest.mock.MagicMock()
        self.context.flags = unittest.mock.MagicMock()
        self.context.flags.no_user_site = False
        self.context.flags.ignore_environment = False
        self.context.execve = unittest.mock.MagicMock()
        # Basic test.
        test_env = {'HOME': 'test-home',
                    'LOGNAME': 'test-logname',
                    'SSH_AUTH_SOCK': 'test-sock',
                    'TERM': 'test-term',
                    'USER': 'test-user',
                    'LANG': 'test-lang',
                    'PATH': 'test-path',
                    'PYTHONTEST': 'test-python',
                    'OTHER': 'test-other',
                    'OTHER2': 'test-other2'}
        argv = ['arg1']
        self.context.environ = dict(test_env)
        self.context.clean_environment(argv)
        self.context.setlocale.assert_called_once_with(locale.LC_ALL, 'C')
        self.context.umask.assert_called_once_with(0o022)
        self.context.execve.assert_not_called()
        self.assertEqual(self.context.environ,
                         {'HOME': 'test-home',
                          'LOGNAME': 'test-logname',
                          'SSH_AUTH_SOCK': 'test-sock',
                          'TERM': 'test-term',
                          'USER': 'test-user',
                          'LANG': 'C',
                          'LC_ALL': 'C',
                          'PATH': 'test-path'})
        # Test with re-execution enabled.
        self.context.setlocale.reset_mock()
        self.context.umask.reset_mock()
        self.context.execve.reset_mock()
        self.context.environ = dict(test_env)
        self.context.clean_environment(argv, reexec=True)
        self.context.setlocale.assert_called_once_with(locale.LC_ALL, 'C')
        self.context.umask.assert_called_once_with(0o022)
        self.context.execve.assert_called_once_with(
            self.context.interp, self.context.script_command() + argv,
            self.context.environ)
        self.assertEqual(self.context.environ,
                         {'HOME': 'test-home',
                          'LOGNAME': 'test-logname',
                          'SSH_AUTH_SOCK': 'test-sock',
                          'TERM': 'test-term',
                          'USER': 'test-user',
                          'LANG': 'C',
                          'LC_ALL': 'C',
                          'PATH': 'test-path'})
        # Test with extra variables specified.
        self.context.setlocale.reset_mock()
        self.context.umask.reset_mock()
        self.context.execve.reset_mock()
        self.context.environ = dict(test_env)
        self.context.clean_environment(
            argv,
            extra_vars={'OTHER': 'mod-other',
                        'EXTRA': 'mod-extra',
                        'PATH': 'mod-path',
                        'LD_LIBRARY_PATH': 'mod-ld-library-path'},
            reexec=True)
        self.context.setlocale.assert_called_once_with(locale.LC_ALL, 'C')
        self.context.umask.assert_called_once_with(0o022)
        self.context.execve.assert_called_once_with(
            self.context.interp, self.context.script_command() + argv,
            self.context.environ)
        self.assertEqual(self.context.environ,
                         {'HOME': 'test-home',
                          'LOGNAME': 'test-logname',
                          'SSH_AUTH_SOCK': 'test-sock',
                          'TERM': 'test-term',
                          'USER': 'test-user',
                          'LANG': 'C',
                          'LC_ALL': 'C',
                          'PATH': 'mod-path',
                          'LD_LIBRARY_PATH': 'mod-ld-library-path',
                          'OTHER': 'mod-other',
                          'EXTRA': 'mod-extra'})
        # Test case not needing re-execution.
        self.context.setlocale.reset_mock()
        self.context.umask.reset_mock()
        self.context.execve.reset_mock()
        self.context.environ = dict(test_env)
        self.context.flags.no_user_site = True
        self.context.flags.ignore_environment = True
        self.context.clean_environment(argv, reexec=True)
        self.context.setlocale.assert_called_once_with(locale.LC_ALL, 'C')
        self.context.umask.assert_called_once_with(0o022)
        self.context.execve.assert_not_called()
        self.assertEqual(self.context.environ,
                         {'HOME': 'test-home',
                          'LOGNAME': 'test-logname',
                          'SSH_AUTH_SOCK': 'test-sock',
                          'TERM': 'test-term',
                          'USER': 'test-user',
                          'LANG': 'C',
                          'LC_ALL': 'C',
                          'PATH': 'test-path'})
        # Re-execution needed if no_user_site is False.
        self.context.setlocale.reset_mock()
        self.context.umask.reset_mock()
        self.context.execve.reset_mock()
        self.context.environ = dict(test_env)
        self.context.flags.no_user_site = False
        self.context.clean_environment(argv, reexec=True)
        self.context.setlocale.assert_called_once_with(locale.LC_ALL, 'C')
        self.context.umask.assert_called_once_with(0o022)
        self.context.execve.assert_called_once_with(
            self.context.interp, self.context.script_command() + argv,
            self.context.environ)
        self.assertEqual(self.context.environ,
                         {'HOME': 'test-home',
                          'LOGNAME': 'test-logname',
                          'SSH_AUTH_SOCK': 'test-sock',
                          'TERM': 'test-term',
                          'USER': 'test-user',
                          'LANG': 'C',
                          'LC_ALL': 'C',
                          'PATH': 'test-path'})
        # Re-execution needed if ignore_environment is False.
        self.context.setlocale.reset_mock()
        self.context.umask.reset_mock()
        self.context.execve.reset_mock()
        self.context.environ = dict(test_env)
        self.context.flags.no_user_site = True
        self.context.flags.ignore_environment = False
        self.context.clean_environment(argv, reexec=True)
        self.context.setlocale.assert_called_once_with(locale.LC_ALL, 'C')
        self.context.umask.assert_called_once_with(0o022)
        self.context.execve.assert_called_once_with(
            self.context.interp, self.context.script_command() + argv,
            self.context.environ)
        self.assertEqual(self.context.environ,
                         {'HOME': 'test-home',
                          'LOGNAME': 'test-logname',
                          'SSH_AUTH_SOCK': 'test-sock',
                          'TERM': 'test-term',
                          'USER': 'test-user',
                          'LANG': 'C',
                          'LC_ALL': 'C',
                          'PATH': 'test-path'})
        # Re-execution not needed if ignore_environment is False but
        # there are no PYTHON* variables.
        self.context.setlocale.reset_mock()
        self.context.umask.reset_mock()
        self.context.execve.reset_mock()
        self.context.environ = dict(test_env)
        del self.context.environ['PYTHONTEST']
        self.context.clean_environment(argv, reexec=True)
        self.context.setlocale.assert_called_once_with(locale.LC_ALL, 'C')
        self.context.umask.assert_called_once_with(0o022)
        self.context.execve.assert_not_called()
        self.assertEqual(self.context.environ,
                         {'HOME': 'test-home',
                          'LOGNAME': 'test-logname',
                          'SSH_AUTH_SOCK': 'test-sock',
                          'TERM': 'test-term',
                          'USER': 'test-user',
                          'LANG': 'C',
                          'LC_ALL': 'C',
                          'PATH': 'test-path'})
        # Re-execution needed if different interpreter wanted.
        self.context.setlocale.reset_mock()
        self.context.umask.reset_mock()
        self.context.execve.reset_mock()
        self.context.environ = dict(test_env)
        self.context.flags.no_user_site = True
        self.context.flags.ignore_environment = True
        self.context.interp = sys.executable + '-other'
        self.context.clean_environment(argv, reexec=True)
        self.context.setlocale.assert_called_once_with(locale.LC_ALL, 'C')
        self.context.umask.assert_called_once_with(0o022)
        self.context.execve.assert_called_once_with(
            self.context.interp, self.context.script_command() + argv,
            self.context.environ)
        self.assertEqual(self.context.environ,
                         {'HOME': 'test-home',
                          'LOGNAME': 'test-logname',
                          'SSH_AUTH_SOCK': 'test-sock',
                          'TERM': 'test-term',
                          'USER': 'test-user',
                          'LANG': 'C',
                          'LC_ALL': 'C',
                          'PATH': 'test-path'})
        # Re-execution needed if different script wanted.
        self.context.setlocale.reset_mock()
        self.context.umask.reset_mock()
        self.context.execve.reset_mock()
        self.context.environ = dict(test_env)
        self.context.interp = sys.executable
        self.context.script_full = self.context.orig_script_full + '-other'
        self.context.clean_environment(argv, reexec=True)
        self.context.setlocale.assert_called_once_with(locale.LC_ALL, 'C')
        self.context.umask.assert_called_once_with(0o022)
        self.context.execve.assert_called_once_with(
            self.context.interp, self.context.script_command() + argv,
            self.context.environ)
        self.assertEqual(self.context.environ,
                         {'HOME': 'test-home',
                          'LOGNAME': 'test-logname',
                          'SSH_AUTH_SOCK': 'test-sock',
                          'TERM': 'test-term',
                          'USER': 'test-user',
                          'LANG': 'C',
                          'LC_ALL': 'C',
                          'PATH': 'test-path'})

    def test_main(self):
        """Test ScriptContext.main."""
        context = ScriptContext(['sourcery.selftests'])
        context.setlocale = unittest.mock.MagicMock()
        context.umask = unittest.mock.MagicMock()
        context.flags = unittest.mock.MagicMock()
        context.flags.no_user_site = False
        context.flags.ignore_environment = False
        context.execve = unittest.mock.MagicMock()
        context.called_with_relcfg = unittest.mock.MagicMock()
        test_env = {'HOME': 'test-home',
                    'LOGNAME': 'test-logname',
                    'SSH_AUTH_SOCK': 'test-sock',
                    'TERM': 'test-term',
                    'USER': 'test-user',
                    'LANG': 'test-lang',
                    'PATH': 'test-path',
                    'PYTHONTEST': 'test-python',
                    'OTHER': 'test-other',
                    'OTHER2': 'test-other2'}
        context.environ = dict(test_env)
        # Test generic command execution, no release config.
        context.message_file = io.StringIO()
        context.main(None, ['-i', 'instarg', 'generic', 'arg1'])
        self.assertFalse(context.silent)
        self.assertFalse(context.verbose_messages)
        self.assertEqual(context.script, '%s generic' % context.script_only)
        self.assertIsNone(context.called_with_relcfg)
        self.assertEqual(context.called_with_args.extra, 'arg1')
        self.assertEqual(context.called_with_args.toplevelprefix,
                         os.path.join(self.cwd, 'instarg'))
        self.assertEqual(context.called_with_args.logdir,
                         os.path.join(self.cwd, 'logs'))
        self.assertEqual(context.called_with_args.objdir,
                         os.path.join(self.cwd, 'obj'))
        self.assertEqual(context.called_with_args.pkgdir,
                         os.path.join(self.cwd, 'pkg'))
        self.assertEqual(context.called_with_args.srcdir,
                         os.path.join(self.cwd, 'src'))
        self.assertEqual(context.called_with_args.testlogdir,
                         os.path.join(self.cwd, 'testlogs'))
        self.assertFalse(context.called_with_args.verbose)
        self.assertFalse(context.called_with_args.silent)
        output = context.message_file.getvalue()
        self.assertIn('%s -i instarg generic arg1 starting...'
                      % context.script_only,
                      output)
        self.assertIn('... %s complete.' % context.script, output)
        self.assertRegex(output,
                         r'^\[[0-2][0-9]:[0-5][0-9]:[0-6][0-9]\] '
                         r'.* -i instarg generic arg1 starting\.\.\.\n'
                         r'\[[0-2][0-9]:[0-5][0-9]:[0-6][0-9]\] '
                         r'\.\.\..*complete\.\n\Z')
        context.setlocale.assert_called_with(locale.LC_ALL, 'C')
        context.umask.assert_called_with(0o022)
        context.execve.assert_not_called()
        self.assertEqual(context.environ,
                         {'HOME': 'test-home',
                          'LOGNAME': 'test-logname',
                          'SSH_AUTH_SOCK': 'test-sock',
                          'TERM': 'test-term',
                          'USER': 'test-user',
                          'LANG': 'C',
                          'LC_ALL': 'C',
                          'PATH': 'test-path'})
        # Test --silent.
        context.setlocale.reset_mock()
        context.umask.reset_mock()
        context.execve.reset_mock()
        context.called_with_relcfg = unittest.mock.MagicMock()
        context.environ = dict(test_env)
        context.message_file = io.StringIO()
        context.main(None, ['--silent', 'generic', 'arg1'])
        self.assertTrue(context.silent)
        self.assertFalse(context.verbose_messages)
        self.assertEqual(context.script, '%s generic' % context.script_only)
        self.assertIsNone(context.called_with_relcfg)
        self.assertEqual(context.called_with_args.extra, 'arg1')
        self.assertFalse(context.called_with_args.verbose)
        self.assertTrue(context.called_with_args.silent)
        output = context.message_file.getvalue()
        self.assertEqual(output, '')
        context.setlocale.assert_called_with(locale.LC_ALL, 'C')
        context.umask.assert_called_with(0o022)
        context.execve.assert_not_called()
        self.assertEqual(context.environ,
                         {'HOME': 'test-home',
                          'LOGNAME': 'test-logname',
                          'SSH_AUTH_SOCK': 'test-sock',
                          'TERM': 'test-term',
                          'USER': 'test-user',
                          'LANG': 'C',
                          'LC_ALL': 'C',
                          'PATH': 'test-path'})
        # Test -v.
        context.setlocale.reset_mock()
        context.umask.reset_mock()
        context.execve.reset_mock()
        context.called_with_relcfg = unittest.mock.MagicMock()
        context.environ = dict(test_env)
        context.main(None, ['-v', 'generic', 'arg1'])
        self.assertFalse(context.silent)
        self.assertTrue(context.verbose_messages)
        self.assertEqual(context.script, '%s generic' % context.script_only)
        self.assertIsNone(context.called_with_relcfg)
        self.assertEqual(context.called_with_args.extra, 'arg1')
        self.assertTrue(context.called_with_args.verbose)
        self.assertFalse(context.called_with_args.silent)
        context.setlocale.assert_called_with(locale.LC_ALL, 'C')
        context.umask.assert_called_with(0o022)
        context.execve.assert_not_called()
        self.assertEqual(context.environ,
                         {'HOME': 'test-home',
                          'LOGNAME': 'test-logname',
                          'SSH_AUTH_SOCK': 'test-sock',
                          'TERM': 'test-term',
                          'USER': 'test-user',
                          'LANG': 'C',
                          'LC_ALL': 'C',
                          'PATH': 'test-path'})
        # Test description used for top-level --help.
        context.setlocale.reset_mock()
        context.umask.reset_mock()
        context.execve.reset_mock()
        context.called_with_relcfg = unittest.mock.MagicMock()
        context.environ = dict(test_env)
        help_out = io.StringIO()
        with contextlib.redirect_stdout(help_out):
            self.assertRaises(SystemExit, context.main, None, ['--help'])
        help_text = help_out.getvalue()
        self.assertRegex(help_text, r'generic *Save argument information\.')
        # Test descriptions used for sub-command --help.
        context.setlocale.reset_mock()
        context.umask.reset_mock()
        context.execve.reset_mock()
        context.called_with_relcfg = unittest.mock.MagicMock()
        context.environ = dict(test_env)
        help_out = io.StringIO()
        with contextlib.redirect_stdout(help_out):
            self.assertRaises(SystemExit, context.main, None,
                              ['generic', '--help'])
        help_text = help_out.getvalue()
        self.assertIn('Save argument information.', help_text)
        self.assertTrue(help_text.endswith('Additional description.\n'))
        # Test re-exec when requested by check_script.
        context.setlocale.reset_mock()
        context.umask.reset_mock()
        context.execve.reset_mock()
        context.called_with_relcfg = unittest.mock.MagicMock()
        context.environ = dict(test_env)
        context.main(None, ['reexec', 'arg1'])
        context.setlocale.assert_called_with(locale.LC_ALL, 'C')
        context.umask.assert_called_with(0o022)
        context.execve.assert_called_once_with(
            context.interp,
            context.script_command() + ['reexec', 'arg1'],
            context.environ)
        # Test re-exec not done when not needed.
        context.setlocale.reset_mock()
        context.umask.reset_mock()
        context.execve.reset_mock()
        context.flags.no_user_site = True
        context.flags.ignore_environment = True
        context.called_with_relcfg = unittest.mock.MagicMock()
        context.environ = dict(test_env)
        context.main(None, ['reexec', 'arg1'])
        context.setlocale.assert_called_with(locale.LC_ALL, 'C')
        context.umask.assert_called_with(0o022)
        context.execve.assert_not_called()
        # Test commands using release configs.
        context.setlocale.reset_mock()
        context.umask.reset_mock()
        context.execve.reset_mock()
        context.called_with_relcfg = unittest.mock.MagicMock()
        context.environ = dict(test_env)
        relcfg_text = ('cfg.add_component("generic")\n'
                       'cfg.generic.source_type.set("none")\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        context.main(ReleaseConfigTextLoader(), ['reexec-relcfg', relcfg_text])
        context.setlocale.assert_called_with(locale.LC_ALL, 'C')
        context.umask.assert_called_with(0o022)
        context.execve.assert_not_called()
        self.assertEqual(context.called_with_relcfg.build.get().name,
                         'x86_64-linux-gnu')
        self.assertEqual(context.environ,
                         {'HOME': 'test-home',
                          'LOGNAME': 'test-logname',
                          'SSH_AUTH_SOCK': 'test-sock',
                          'TERM': 'test-term',
                          'USER': 'test-user',
                          'LANG': 'C',
                          'LC_ALL': 'C',
                          'PATH': 'test-path',
                          'SOURCE_DATE_EPOCH': str(
                              context.called_with_relcfg.source_date_epoch.get(
                              ))})
        self.assertEqual(context.script_full, context.orig_script_full)
        self.assertEqual(context.interp, sys.executable)
        # Test release config setting environment variables.
        context.setlocale.reset_mock()
        context.umask.reset_mock()
        context.execve.reset_mock()
        context.called_with_relcfg = unittest.mock.MagicMock()
        context.environ = dict(test_env)
        relcfg_text = ('cfg.add_component("generic")\n'
                       'cfg.generic.source_type.set("none")\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       'cfg.env_set.set({"OTHER": "rc-other"})\n')
        context.main(ReleaseConfigTextLoader(), ['reexec-relcfg', relcfg_text])
        context.setlocale.assert_called_with(locale.LC_ALL, 'C')
        context.umask.assert_called_with(0o022)
        context.execve.assert_not_called()
        self.assertEqual(context.called_with_relcfg.build.get().name,
                         'x86_64-linux-gnu')
        self.assertEqual(context.environ,
                         {'HOME': 'test-home',
                          'LOGNAME': 'test-logname',
                          'SSH_AUTH_SOCK': 'test-sock',
                          'TERM': 'test-term',
                          'USER': 'test-user',
                          'LANG': 'C',
                          'LC_ALL': 'C',
                          'PATH': 'test-path',
                          'OTHER': 'rc-other',
                          'SOURCE_DATE_EPOCH': str(
                              context.called_with_relcfg.source_date_epoch.get(
                              ))})
        self.assertEqual(context.script_full, context.orig_script_full)
        self.assertEqual(context.interp, sys.executable)
        # Test release config forcing re-exec by setting script_full.
        context.setlocale.reset_mock()
        context.umask.reset_mock()
        context.execve.reset_mock()
        context.called_with_relcfg = unittest.mock.MagicMock()
        context.environ = dict(test_env)
        relcfg_text = ('cfg.add_component("generic")\n'
                       'cfg.generic.source_type.set("none")\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       'cfg.script_full.set("%s-other")\n'
                       % context.script_full)
        context.main(ReleaseConfigTextLoader(), ['reexec-relcfg', relcfg_text])
        context.setlocale.assert_called_with(locale.LC_ALL, 'C')
        context.umask.assert_called_with(0o022)
        context.execve.assert_called_once_with(
            context.interp,
            context.script_command() + ['reexec-relcfg', relcfg_text],
            context.environ)
        self.assertEqual(context.called_with_relcfg.build.get().name,
                         'x86_64-linux-gnu')
        self.assertEqual(context.environ,
                         {'HOME': 'test-home',
                          'LOGNAME': 'test-logname',
                          'SSH_AUTH_SOCK': 'test-sock',
                          'TERM': 'test-term',
                          'USER': 'test-user',
                          'LANG': 'C',
                          'LC_ALL': 'C',
                          'PATH': 'test-path',
                          'SOURCE_DATE_EPOCH': str(
                              context.called_with_relcfg.source_date_epoch.get(
                              ))})
        self.assertEqual(context.script_full,
                         '%s-other' % context.orig_script_full)
        self.assertEqual(context.interp, sys.executable)
        context.script_full = context.orig_script_full
        # Test release config forcing re-exec by setting interp.
        context.setlocale.reset_mock()
        context.umask.reset_mock()
        context.execve.reset_mock()
        context.called_with_relcfg = unittest.mock.MagicMock()
        context.environ = dict(test_env)
        relcfg_text = ('cfg.add_component("generic")\n'
                       'cfg.generic.source_type.set("none")\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       'cfg.interp.set("%s-other")\n'
                       % context.interp)
        context.main(ReleaseConfigTextLoader(), ['reexec-relcfg', relcfg_text])
        context.setlocale.assert_called_with(locale.LC_ALL, 'C')
        context.umask.assert_called_with(0o022)
        context.execve.assert_called_once_with(
            context.interp,
            context.script_command() + ['reexec-relcfg', relcfg_text],
            context.environ)
        self.assertEqual(context.called_with_relcfg.build.get().name,
                         'x86_64-linux-gnu')
        self.assertEqual(context.environ,
                         {'HOME': 'test-home',
                          'LOGNAME': 'test-logname',
                          'SSH_AUTH_SOCK': 'test-sock',
                          'TERM': 'test-term',
                          'USER': 'test-user',
                          'LANG': 'C',
                          'LC_ALL': 'C',
                          'PATH': 'test-path',
                          'SOURCE_DATE_EPOCH': str(
                              context.called_with_relcfg.source_date_epoch.get(
                              ))})
        self.assertEqual(context.script_full, context.orig_script_full)
        self.assertEqual(context.interp, '%s-other' % sys.executable)
