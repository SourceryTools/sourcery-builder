# Test sourcery.build.

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

"""Test sourcery.build."""

import argparse
import contextlib
import os
import os.path
import stat
import sys
import tempfile
import unittest

from sourcery.build import BuildContext
from sourcery.context import add_common_options, add_parallelism_option, \
    ScriptContext
from sourcery.relcfg import ReleaseConfig, ReleaseConfigTextLoader
import sourcery.rpc
from sourcery.selftests.support import read_files, redirect_file, \
    parse_makefile

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

    def stdout_stderr_read(self):
        """Read the stdout and stderr for this test."""
        return (self.temp_file_read('stdout'), self.temp_file_read('stderr'))

    def test_init(self):
        """Test BuildContext.__init__."""
        self.setup_rc()
        bcontext = self.build_context
        self.assertEqual(bcontext.context, self.context)
        self.assertEqual(bcontext.relcfg, self.relcfg)
        self.assertEqual(bcontext.logdir, self.args.logdir)
        self.assertEqual(bcontext.parallelism, self.args.parallelism)
        self.assertEqual(bcontext.build_objdir,
                         self.relcfg.objdir_path(None, 'build'))
        self.assertTrue(stat.S_ISDIR(os.stat(bcontext.sockdir,
                                             follow_symlinks=False).st_mode))
        self.assertIsInstance(bcontext.server, sourcery.rpc.RPCServer)

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
        self.assertIn('rm -rf',
                      commands['task-end/x86_64-linux-gnu/all-hosts'][1])

    def test_setup_build_dir_remove(self):
        """Test setup_build_dir removal of existing directory."""
        self.setup_rc('cfg.add_component("build_test")\n')
        os.makedirs(os.path.join(self.build_context.build_objdir, 'x'))
        self.build_context.setup_build_dir()
        dir_contents = sorted(os.listdir(self.build_context.build_objdir))
        self.assertEqual(dir_contents, ['GNUmakefile'])

    def test_run_build(self):
        """Test run_build, simple successful build."""
        self.setup_rc('cfg.add_component("build_test")\n')
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
        self.assertEqual(stdout, '')
        lines = stderr.splitlines()
        self.assertEqual(len(lines), 8)
        for line in lines:
            self.assertRegex(line,
                             r'^\[[0-2][0-9]:[0-5][0-9]:[0-6][0-9]\] '
                             r'\[000[1-4]/0004\] /.*(start|end)\Z')
        self.assertIn('[0001/0004]', stderr)
        self.assertIn('[0004/0004]', stderr)
        self.assertIn('/x86_64-linux-gnu/all-hosts start', stderr)
        self.assertIn('/x86_64-w64-mingw32/other-hosts end', stderr)
