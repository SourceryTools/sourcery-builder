# Test sourcery.build.

# Copyright 2018-2020 Mentor Graphics Corporation.

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

"""Test sourcery.build."""

import argparse
import contextlib
import glob
import io
import os
import os.path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

from sourcery.build import BuildContext
from sourcery.context import add_common_options, add_parallelism_option, \
    ScriptContext, ScriptError
from sourcery.relcfg import ReleaseConfig, ReleaseConfigTextLoader
from sourcery.rpc import RPCServer
from sourcery.selftests.support import create_files, read_files, \
    redirect_file, parse_makefile

__all__ = ['BuildContextTestCase']


class BuildContextTestCase(unittest.TestCase):

    """Test the BuildContext class."""

    def setUp(self):
        """Set up a BuildContext test."""
        self.context = ScriptContext(['sourcery.selftests'])
        self.tempdir_td = tempfile.TemporaryDirectory()
        self.tempdir = self.tempdir_td.name
        parser = argparse.ArgumentParser()
        add_common_options(parser, self.tempdir)
        add_parallelism_option(parser)
        self.args = parser.parse_args([])
        self.args.build_source_packages = False
        self.relcfg = None
        self.build_context = None

    def setup_rc(self, rc_text_extra=''):
        """Complete test setup.

        Tests require different release configurations using different
        test components, so this part of the setup needs to be
        deferred to this function, called from the individual test
        methods.

        """
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.hosts.set(("x86_64-linux-gnu", '
                       '"x86_64-w64-mingw32"))\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       + rc_text_extra)
        self.relcfg = ReleaseConfig(self.context, relcfg_text,
                                    ReleaseConfigTextLoader(), self.args)
        self.build_context = BuildContext(self.context, self.relcfg, self.args)

    def tearDown(self):
        """Tear down a BuildContext test."""
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

    def temp_file_write(self, name, contents):
        """Write a file in tempdir for this test."""
        with open(self.temp_file(name), 'w', encoding='utf-8') as file:
            file.write(contents)

    def stdout_stderr_read(self):
        """Read the stdout and stderr for this test."""
        return (self.temp_file_read('stdout'), self.temp_file_read('stderr'))

    def test_init(self):
        """Test BuildContext.__init__."""
        self.setup_rc()
        bcontext = self.build_context
        self.assertIs(bcontext.context, self.context)
        self.assertIs(bcontext.relcfg, self.relcfg)
        self.assertEqual(bcontext.logdir,
                         os.path.join(self.args.logdir,
                                      'toolchain-1.0-1-aarch64-linux-gnu'))
        self.assertEqual(bcontext.parallelism, self.args.parallelism)
        self.assertEqual(bcontext.build_objdir,
                         self.relcfg.objdir_path(None, 'build'))
        self.assertTrue(stat.S_ISDIR(os.stat(bcontext.sockdir,
                                             follow_symlinks=False).st_mode))
        self.assertIsInstance(bcontext.server, RPCServer)

    def test_setup_build_dir(self):
        """Test setup_build_dir."""
        self.setup_rc('cfg.add_component("build_test")\n')
        self.build_context.setup_build_dir()
        makefile_name = os.path.join(self.build_context.build_objdir,
                                     'GNUmakefile')
        with open(makefile_name, 'r', encoding='utf-8') as file:
            makefile_text = file.read()
        deps, commands = parse_makefile(makefile_text)
        # Commands are tested in tests of run_build, via running them;
        # mainly verify dependencies here.
        self.assertIn('task-end/x86_64-linux-gnu/all-hosts', deps)
        self.assertIn('task-end/x86_64-w64-mingw32/all-hosts', deps)
        self.assertIn('task-end/x86_64-linux-gnu/first-host', deps)
        self.assertNotIn('task-end/x86_64-w64-mingw32/first-host', deps)
        self.assertNotIn('task-end/x86_64-linux-gnu/other-hosts', deps)
        self.assertIn('task-end/x86_64-w64-mingw32/other-hosts', deps)
        self.assertIn('task-end/init', deps['task-start/x86_64-linux-gnu'])
        self.assertIn('task-end/init', deps['task-start/x86_64-w64-mingw32'])
        self.assertIn('task-end/init', deps['task-start/host-indep'])
        self.assertIn('task-end/x86_64-linux-gnu', deps['task-start/fini'])
        self.assertIn('task-end/x86_64-w64-mingw32', deps['task-start/fini'])
        self.assertIn('task-end/host-indep', deps['task-start/fini'])
        self.assertIn('rm -rf',
                      commands['task-end/x86_64-linux-gnu/all-hosts'][1])

    def test_setup_build_dir_remove(self):
        """Test setup_build_dir removal of existing directory."""
        self.setup_rc('cfg.add_component("build_test")\n')
        os.makedirs(os.path.join(self.build_context.build_objdir, 'x'))
        self.build_context.setup_build_dir()
        dir_contents = sorted(os.listdir(self.build_context.build_objdir))
        self.assertEqual(dir_contents, ['GNUmakefile'])

    def test_wrapper_run_command(self):
        """Test wrapper_run_command."""
        # We can't test much more than repeating the function's logic.
        # The main testing that the generated command does what is
        # intended is in tests of run_build.
        self.setup_rc()
        command = self.build_context.wrapper_run_command('/some/log', 123,
                                                         '/some/dir')
        self.assertEqual(command,
                         [self.context.build_wrapper_path('run-command'),
                          self.context.interp, self.context.script_full,
                          self.build_context.build_objdir, '/some/log',
                          self.build_context.sockdir, '123', '/some/dir'])

    def test_wrapper_start_task(self):
        """Test wrapper_start_task."""
        # We can't test much more than repeating the function's logic.
        # The main testing that the generated command does what is
        # intended is in tests of run_build.
        self.setup_rc()
        command = self.build_context.wrapper_start_task('/some/log', 123)
        self.assertEqual(command,
                         [self.context.build_wrapper_path('start-task'),
                          self.context.interp, self.context.script_full,
                          self.build_context.build_objdir, '/some/log',
                          self.build_context.sockdir, '123'])

    def test_wrapper_end_task(self):
        """Test wrapper_end_task."""
        # We can't test much more than repeating the function's logic.
        # The main testing that the generated command does what is
        # intended is in tests of run_build.
        self.setup_rc()
        command = self.build_context.wrapper_end_task('/some/log', 123)
        self.assertEqual(command,
                         [self.context.build_wrapper_path('end-task'),
                          self.context.interp, self.context.script_full,
                          self.build_context.build_objdir, '/some/log',
                          self.build_context.sockdir, '123'])

    def test_rpc_client_command(self):
        """Test rpc_client_command."""
        # We can't test much more than repeating the function's logic.
        # The main testing that the generated command does what is
        # intended is in tests of run_build.
        self.setup_rc()
        command = self.build_context.rpc_client_command(123)
        self.assertEqual(command,
                         (self.context.script_command()
                          + ['rpc-client', self.build_context.sockdir, '123']))

    def test_task_start(self):
        """Test task_start."""
        self.setup_rc()
        self.context.message_file = io.StringIO()
        self.build_context.task_start('some start text')
        output = self.context.message_file.getvalue()
        self.assertTrue(output.endswith(' some start text start\n'))
        self.assertRegex(output, r'^\[[0-2][0-9]:[0-5][0-9]:[0-6][0-9]\] ')
        self.context.silent = True
        self.context.message_file = io.StringIO()
        self.build_context.task_start('more start text')
        output = self.context.message_file.getvalue()
        self.assertEqual(output, '')

    def test_task_fail_command(self):
        """Test task_fail_command."""
        self.setup_rc()
        self.context.message_file = io.StringIO()
        test_desc = 'test description'
        # Want to test that str() is called for non-string command
        # passed, so don't just pass a string here.
        test_cmd = ('test', 1)
        test_log = self.temp_file('log')
        exp_start = ('%s: warning: test description FAILED\n'
                     "%s: warning: failed command was: ('test', 1)\n"
                     '%s: warning: current log file is: %s '
                     '(last 25 lines shown)\n'
                     '------------------------------------ start '
                     '------------------------------------\n'
                     % (self.context.script, self.context.script,
                        self.context.script, test_log))
        exp_end = ('------------------------------------- end '
                   '-------------------------------------\n')
        num_text = '\n'.join(str(n) for n in range(100))
        num_text_25 = '\n'.join(str(n) for n in range(75, 100))
        # Last 25 lines of log.
        self.context.message_file = io.StringIO()
        self.temp_file_write('log', num_text + '\n')
        self.build_context.task_fail_command(test_desc, test_cmd, test_log)
        output = self.context.message_file.getvalue()
        self.assertEqual(output, '%s%s\n%s' % (exp_start, num_text_25,
                                               exp_end))
        # Last 25 lines of log, no newline.
        self.context.message_file = io.StringIO()
        self.temp_file_write('log', num_text)
        self.build_context.task_fail_command(test_desc, test_cmd, test_log)
        output = self.context.message_file.getvalue()
        self.assertEqual(output, '%s%s\n%s' % (exp_start, num_text_25,
                                               exp_end))
        # Empty log.
        self.context.message_file = io.StringIO()
        self.temp_file_write('log', '')
        self.build_context.task_fail_command(test_desc, test_cmd, test_log)
        output = self.context.message_file.getvalue()
        self.assertEqual(output, '%s\n%s' % (exp_start, exp_end))
        # Non-ASCII text in log.
        self.context.message_file = io.StringIO()
        self.temp_file_write('log', '\u00ff')
        self.build_context.task_fail_command(test_desc, test_cmd, test_log)
        output = self.context.message_file.getvalue()
        self.assertEqual(output, '%s\\xc3\\xbf\n%s' % (exp_start, exp_end))

    def test_task_end(self):
        """Test task_end."""
        self.setup_rc()
        self.context.message_file = io.StringIO()
        self.build_context.task_end('some end text')
        output = self.context.message_file.getvalue()
        self.assertTrue(output.endswith(' some end text end\n'))
        self.assertRegex(output, r'^\[[0-2][0-9]:[0-5][0-9]:[0-6][0-9]\] ')
        self.context.silent = True
        self.context.message_file = io.StringIO()
        self.build_context.task_end('more end text')
        output = self.context.message_file.getvalue()
        self.assertEqual(output, '')

    def test_run_build(self):
        """Test run_build, simple successful build."""
        self.setup_rc('cfg.add_component("build_test")\n'
                      'cfg.multilibs.set((Multilib("build_test", '
                      '"build_test", ()), Multilib("build_test", '
                      '"build_test", ("-mtest",), osdir="test")))\n')
        with self.redirect_stdout_stderr():
            self.build_context.run_build()
        stdout, stderr = self.stdout_stderr_read()
        hosts = self.relcfg.hosts.get()
        host_b0 = hosts[0].build_cfg
        host_b1 = hosts[1].build_cfg
        h0_all_objdir = self.relcfg.objdir_path(host_b0, 'build_test-all')
        h0_all_objdir2 = self.relcfg.objdir_path(host_b0, 'build_test-all2')
        h1_all_objdir = self.relcfg.objdir_path(host_b1, 'build_test-all')
        h1_all_objdir2 = self.relcfg.objdir_path(host_b1, 'build_test-all2')
        self.assertEqual(read_files(h0_all_objdir),
                         (set(),
                          {'out1': 'all-hosts\n',
                           'out2': 'all-hosts-2\n'},
                          {}))
        self.assertEqual(read_files(h0_all_objdir2), (set(), {}, {}))
        self.assertEqual(read_files(h1_all_objdir),
                         (set(),
                          {'out1': 'all-hosts\n',
                           'out2': 'all-hosts-2\n'},
                          {}))
        self.assertEqual(read_files(h1_all_objdir2), (set(), {}, {}))
        first_objdir = self.relcfg.objdir_path(host_b0, 'build_test-first')
        first_objdir2 = self.relcfg.objdir_path(host_b0, 'build_test-first2')
        self.assertEqual(read_files(first_objdir),
                         ({'x', 'x/y'},
                          {'GNUmakefile': 'all:; echo first-host $(X) > out\n',
                           'out': 'first-host Y\n'},
                          {}))
        self.assertEqual(read_files(first_objdir2), ({'x', 'x/y'}, {}, {}))
        other_objdir = self.relcfg.objdir_path(host_b1, 'build_test-other')
        self.assertEqual(read_files(other_objdir),
                         (set(),
                          {'out': 'test python\n'},
                          {}))
        first_objdir_m0 = self.relcfg.objdir_path(
            host_b0, 'build_test-first-aarch64-linux-gnu')
        first_objdir_m1 = self.relcfg.objdir_path(
            host_b0, 'build_test-first-aarch64-linux-gnu-mtest')
        other_objdir_m0 = self.relcfg.objdir_path(
            host_b1, 'build_test-other-aarch64-linux-gnu')
        other_objdir_m1 = self.relcfg.objdir_path(
            host_b1, 'build_test-other-aarch64-linux-gnu-mtest')
        self.assertEqual(read_files(first_objdir_m0),
                         (set(),
                          {'out': 'aarch64-linux-gnu\n'},
                          {}))
        self.assertEqual(read_files(first_objdir_m1),
                         (set(),
                          {'out': 'aarch64-linux-gnu-mtest\n'},
                          {}))
        self.assertEqual(read_files(other_objdir_m0),
                         (set(),
                          {'out': 'test aarch64-linux-gnu\n'},
                          {}))
        self.assertEqual(read_files(other_objdir_m1),
                         (set(),
                          {'out': 'test aarch64-linux-gnu-mtest\n'},
                          {}))
        init_objdir = self.relcfg.objdir_path(None, 'build_test-init')
        host_indep_objdir = self.relcfg.objdir_path(None,
                                                    'build_test-host-indep')
        fini_objdir = self.relcfg.objdir_path(None, 'build_test-fini')
        self.assertEqual(read_files(init_objdir),
                         (set(),
                          {'out': 'init\n'},
                          {}))
        self.assertEqual(read_files(host_indep_objdir),
                         (set(),
                          {'out': 'host-indep\n'},
                          {}))
        self.assertEqual(read_files(fini_objdir),
                         (set(),
                          {'out': 'fini\n'},
                          {}))
        self.assertEqual(stdout, '')
        lines = stderr.splitlines()
        self.assertEqual(len(lines), 36)
        for line in lines:
            self.assertRegex(line,
                             r'^\[[0-2][0-9]:[0-5][0-9]:[0-6][0-9]\] '
                             r'\[00[0-1][0-9]/0018\] /.*(start|end)\Z')
        self.assertIn('[0001/0018]', stderr)
        self.assertIn('[0018/0018]', stderr)
        self.assertIn('/x86_64-linux-gnu/all-hosts start', stderr)
        self.assertIn('/x86_64-w64-mingw32/other-hosts end', stderr)
        self.assertIn('/install-trees-x86_64-linux-gnu/package-input start',
                      stderr)
        self.assertIn('/install-trees-x86_64-w64-mingw32/package-input end',
                      stderr)
        self.assertIn('/x86_64-linux-gnu/package-output start', stderr)
        self.assertIn('/x86_64-w64-mingw32/package-output end', stderr)
        self.assertIn('/x86_64-linux-gnu/package-tar-xz end', stderr)
        self.assertIn('/x86_64-w64-mingw32/package-tar-xz start', stderr)
        self.assertIn('/init/init start', stderr)
        self.assertIn('/init/pkgdir end', stderr)
        self.assertIn('/host-indep/host-indep start', stderr)
        self.assertIn('/fini/fini end', stderr)
        # In this case, the created packages are empty.
        pkg_0 = self.relcfg.pkgdir_path(hosts[0], '.tar.xz')
        pkg_1 = self.relcfg.pkgdir_path(hosts[1], '.tar.xz')
        dir_out = os.path.join(self.tempdir, 'toolchain-1.0')
        subprocess.run(['tar', '-x', '-f', pkg_0], cwd=self.tempdir)
        self.assertEqual(read_files(dir_out),
                         (set(), {}, {}))
        shutil.rmtree(dir_out)
        subprocess.run(['tar', '-x', '-f', pkg_1], cwd=self.tempdir)
        self.assertEqual(read_files(dir_out),
                         (set(), {}, {}))

    def test_run_build_silent(self):
        """Test run_build, simple successful build, silent."""
        self.context.silent = True
        self.setup_rc('cfg.add_component("build_test")\n')
        with self.redirect_stdout_stderr():
            self.build_context.run_build()
        stdout, stderr = self.stdout_stderr_read()
        self.assertEqual(stdout, '')
        self.assertEqual(stderr, '')

    def test_run_build_log(self):
        """Test run_build, simple successful build, command output to log."""
        self.setup_rc('cfg.add_component("build_log")\n')
        with self.redirect_stdout_stderr():
            self.build_context.run_build()
        log = glob.glob(os.path.join(
            self.build_context.logdir,
            '00*-x86_64-linux-gnu-first-host-log.txt'))[0]
        with open(log, 'r', encoding='utf-8') as file:
            log_text = file.read()
        num_text_1 = '\n'.join(str(n) for n in range(10))
        num_text_2 = '\n'.join(str(n) for n in range(10, 20))
        self.assertIn(num_text_1, log_text)
        self.assertIn(num_text_2, log_text)

    def test_run_build_fail_command(self):
        """Test run_build, simple failed build."""
        self.setup_rc('cfg.add_component("build_fail_command")\n')
        with self.redirect_stdout_stderr():
            self.assertRaisesRegex(ScriptError, 'build failed',
                                   self.build_context.run_build)
        stdout, stderr = self.stdout_stderr_read()
        self.assertEqual(stdout, '')
        log = glob.glob(os.path.join(
            self.build_context.logdir,
            '00*-x86_64-linux-gnu-first-host-log.txt'))[0]
        with open(log, 'r', encoding='utf-8') as file:
            log_text = file.read()
        self.assertIn('1\n2\n3\n4\n', log_text)
        self.assertIn('1\n2\n3\n4\n', stderr)

    def test_run_build_fail_command_silent(self):
        """Test run_build, simple failed build, silent."""
        self.context.silent = True
        self.setup_rc('cfg.add_component("build_fail_command")\n')
        with self.redirect_stdout_stderr():
            self.assertRaisesRegex(ScriptError, 'build failed',
                                   self.build_context.run_build)
        stdout, stderr = self.stdout_stderr_read()
        self.assertEqual(stdout, '')
        log = glob.glob(os.path.join(
            self.build_context.logdir,
            '00*-x86_64-linux-gnu-first-host-log.txt'))[0]
        with open(log, 'r', encoding='utf-8') as file:
            log_text = file.read()
        self.assertIn('1\n2\n3\n4\n', log_text)
        # Errors should still appear on stderr even with --silent.
        self.assertIn('1\n2\n3\n4\n', stderr)

    def test_run_build_fail_cd(self):
        """Test run_build, bad cwd for command."""
        self.setup_rc('cfg.add_component("build_fail_cd")\n')
        with self.redirect_stdout_stderr():
            self.assertRaisesRegex(ScriptError, 'build failed',
                                   self.build_context.run_build)

    def test_run_build_fail_python(self):
        """Test run_build, failed Python step."""
        self.setup_rc('cfg.add_component("build_fail_python")\n')
        with self.redirect_stdout_stderr():
            self.assertRaisesRegex(ScriptError, 'build failed',
                                   self.build_context.run_build)
        stdout, stderr = self.stdout_stderr_read()
        self.assertEqual(stdout, '')
        log = glob.glob(os.path.join(
            self.build_context.logdir,
            '00*-x86_64-linux-gnu-first-host-log.txt'))[0]
        with open(log, 'r', encoding='utf-8') as file:
            log_text = file.read()
        self.assertRegex(log_text, 'ValueError.*test failure')
        self.assertRegex(stderr, 'ValueError.*test failure')

    def test_run_build_install_tree(self):
        """Test run_build, implicit install tree creation."""
        self.setup_rc('cfg.add_component("build_install_tree")\n')
        with self.redirect_stdout_stderr():
            self.build_context.run_build()
        hosts = self.relcfg.hosts.get()
        host_b0 = hosts[0].build_cfg
        instdir_def = self.relcfg.install_tree_path(host_b0, 'impl-def')
        instdir_empty = self.relcfg.install_tree_path(host_b0, 'impl-empty')
        instdir_one = self.relcfg.install_tree_path(host_b0, 'impl-one')
        instdir_two = self.relcfg.install_tree_path(host_b0, 'impl-two')
        self.assertEqual(read_files(instdir_def),
                         ({'q'},
                          {'q/a': 'a\n'},
                          {}))
        self.assertEqual(read_files(instdir_empty),
                         (set(),
                          {},
                          {}))
        self.assertEqual(read_files(instdir_one),
                         (set(),
                          {'b': 'b\n'},
                          {}))
        self.assertEqual(read_files(instdir_two),
                         (set(),
                          {'b': 'b\n', 'c': 'c\n'},
                          {}))

    def test_run_build_package(self):
        """Test run_build, nonempty packages built."""
        self.setup_rc('cfg.add_component("build_package")\n'
                      'cfg.source_date_epoch.set(1111199990)\n')
        with self.redirect_stdout_stderr():
            self.build_context.run_build()
        hosts = self.relcfg.hosts.get()
        pkg_0 = self.relcfg.pkgdir_path(hosts[0], '.tar.xz')
        pkg_1 = self.relcfg.pkgdir_path(hosts[1], '.tar.xz')
        dir_out = os.path.join(self.tempdir, 'toolchain-1.0')
        subprocess.run(['tar', '-x', '-f', pkg_0], cwd=self.tempdir)
        self.assertEqual(read_files(dir_out),
                         (set(),
                          {'a1': 'a\n', 'a2': 'a\n', 'a3': 'a\n', 'b': 'b\n'},
                          {'c': 'b'}))
        stat_a1 = os.stat(os.path.join(dir_out, 'a1'))
        self.assertEqual(stat_a1.st_nlink, 3)
        self.assertEqual(stat_a1.st_mtime, 1111199990)
        stat_b = os.stat(os.path.join(dir_out, 'b'))
        self.assertEqual(stat_b.st_nlink, 1)
        self.assertEqual(stat_b.st_mtime, 1111199990)
        shutil.rmtree(dir_out)
        subprocess.run(['tar', '-x', '-f', pkg_1], cwd=self.tempdir)
        self.assertEqual(read_files(dir_out),
                         (set(),
                          {'a1': 'a\n', 'a2': 'a\n', 'a3': 'a\n', 'b': 'b\n',
                           'c': 'b\n'},
                          {}))
        stat_a1 = os.stat(os.path.join(dir_out, 'a1'))
        self.assertEqual(stat_a1.st_nlink, 3)
        self.assertEqual(stat_a1.st_mtime, 1111199990)
        stat_b = os.stat(os.path.join(dir_out, 'b'))
        self.assertEqual(stat_b.st_nlink, 2)
        self.assertEqual(stat_b.st_mtime, 1111199990)

    def test_run_build_src_package(self):
        """Test run_build, source and backup packages built."""
        self.args.build_source_packages = True
        # We need to create dummy source trees, but they do not
        # actually need to come from checking out the given version
        # control locations.
        srcdir = os.path.join(self.tempdir, 'src')
        create_files(srcdir, ['build_src_open-123', 'build_src_closed-456'],
                     {'build_src_open-123/x': 'x',
                      'build_src_closed-456/y': 'y',
                      'build_src_closed-456/.git': 'ignore'},
                     {})
        self.setup_rc('cfg.add_component("build_src_open")\n'
                      'cfg.build_src_open.version.set("123")\n'
                      'cfg.build_src_open.vc.set(TarVC("/dummy"))\n'
                      'cfg.add_component("build_src_closed")\n'
                      'cfg.build_src_closed.version.set("456")\n'
                      'cfg.build_src_closed.vc.set(GitVC("/dummy"))\n'
                      'cfg.source_date_epoch.set(1111199990)\n')
        with self.redirect_stdout_stderr():
            self.build_context.run_build()
        pkg_src = self.relcfg.pkgdir_path(None, '.src.tar.xz')
        pkg_backup = self.relcfg.pkgdir_path(None, '.backup.tar.xz')
        dir_src = os.path.join(self.tempdir,
                               'toolchain-1.0-1-aarch64-linux-gnu')
        dir_backup = os.path.join(self.tempdir,
                                  'toolchain-1.0-1-aarch64-linux-gnu.backup')
        subprocess.run(['tar', '-x', '-f', pkg_src], cwd=self.tempdir)
        self.assertEqual(os.listdir(dir_src), ['build_src_open-1.0-1.tar.xz'])
        subprocess.run(['tar', '-x', '-f', pkg_backup], cwd=self.tempdir)
        self.assertEqual(os.listdir(dir_backup),
                         ['build_src_closed-1.0-1.tar.xz'])
        tar_open = os.path.join(dir_src, 'build_src_open-1.0-1.tar.xz')
        tar_closed = os.path.join(dir_backup, 'build_src_closed-1.0-1.tar.xz')
        self.assertEqual(os.stat(tar_open).st_mtime, 1111199990)
        self.assertEqual(os.stat(tar_closed).st_mtime, 1111199990)
        subprocess.run(['tar', '-x', '-f', tar_open], cwd=self.tempdir)
        subprocess.run(['tar', '-x', '-f', tar_closed], cwd=self.tempdir)
        dir_open = os.path.join(self.tempdir, 'build_src_open-1.0-1')
        dir_closed = os.path.join(self.tempdir, 'build_src_closed-1.0-1')
        self.assertEqual(read_files(dir_open), (set(), {'x': 'x'}, {}))
        self.assertEqual(read_files(dir_closed), (set(), {'y': 'y'}, {}))
        self.assertEqual(os.stat(os.path.join(dir_open, 'x')).st_mtime,
                         1111199990)
        self.assertEqual(os.stat(os.path.join(dir_closed, 'y')).st_mtime,
                         1111199990)
