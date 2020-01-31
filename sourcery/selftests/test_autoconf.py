# Test sourcery.autoconf.

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

"""Test sourcery.autoconf."""

import argparse
import tempfile
import unittest

from sourcery.autoconf import add_host_cfg_build_tasks, \
    add_host_lib_cfg_build_tasks, add_host_tool_cfg_build_tasks
from sourcery.build import BuildContext
from sourcery.buildtask import BuildTask
from sourcery.context import add_common_options, add_parallelism_option, \
    ScriptContext
from sourcery.relcfg import ReleaseConfig, ReleaseConfigTextLoader
from sourcery.selftests.support import parse_makefile

__all__ = ['AutoconfTestCase']


class AutoconfTestCase(unittest.TestCase):

    """Test sourcery.autoconf."""

    def setUp(self):
        """Set up a sourcery.autoconf test."""
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
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       + rc_text_extra)
        self.relcfg = ReleaseConfig(self.context, relcfg_text,
                                    ReleaseConfigTextLoader(), self.args)
        self.build_context = BuildContext(self.context, self.relcfg, self.args)

    def tearDown(self):
        """Tear down a sourcery.autoconf test."""
        self.tempdir_td.cleanup()

    def test_add_host_cfg_build_tasks(self):
        """Test add_host_cfg_build_tasks."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_cfg_build_tasks(self.relcfg, host, component, top_task, None,
                                 None, None, ['--test-option'], 'test-target',
                                 None, 'install', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        objdir = self.relcfg.objdir_path(host, 'generic')
        instdir = self.relcfg.install_tree_path(host, 'generic')
        srcdir = component.vars.srcdir.get()
        cmds_init = commands['task-end/generic/init']
        self.assertIn('rm -rf %s' % objdir, cmds_init[1])
        self.assertIn('mkdir -p %s' % objdir, cmds_init[2])
        self.assertIn('rm -rf %s' % instdir, cmds_init[3])
        self.assertIn('mkdir -p %s' % instdir, cmds_init[4])
        cmds_cfg = commands['task-end/generic/configure']
        self.assertIn(' %s ' % objdir, cmds_cfg[1])
        self.assertIn('%s/configure --build=x86_64-linux-gnu '
                      '--host=x86_64-linux-gnu --prefix=%s '
                      '--target=test-target --test-option %s '
                      'CC_FOR_BUILD=x86_64-linux-gnu-gcc '
                      'CXX_FOR_BUILD=x86_64-linux-gnu-g++'
                      % (srcdir, instdir, ' '.join(host.configure_vars())),
                      cmds_cfg[1])
        cmds_build = commands['task-end/generic/build']
        self.assertIn(' %s ' % objdir, cmds_build[1])
        self.assertTrue(cmds_build[1].strip().endswith('$(MAKE)'))
        cmds_inst = commands['task-end/generic/install']
        self.assertIn(' %s ' % objdir, cmds_inst[1])
        self.assertIn('$(MAKE) -j1 install', cmds_inst[1])

    def test_add_host_cfg_build_tasks_return(self):
        """Test add_host_cfg_build_tasks, returned task group."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        task_group = add_host_cfg_build_tasks(self.relcfg, host, component,
                                              top_task, None,
                                              None, None, ['--test-option'],
                                              'test-target', None, 'install',
                                              True)
        extra_task = BuildTask(self.relcfg, task_group, 'extra')
        extra_task.add_command(['test', 'command'])
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        self.assertIn('task-end/generic/install',
                      deps['task-start/generic/extra'])
        cmds_extra = commands['task-end/generic/extra']
        self.assertIn('test command', cmds_extra[1])

    def test_add_host_cfg_build_tasks_name(self):
        """Test add_host_cfg_build_tasks, alternate name provided."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_cfg_build_tasks(self.relcfg, host, component, top_task,
                                 'name', None, None, ['--test-option'],
                                 'test-target', None, 'install', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/name/init',
                      deps['task-start/name/configure'])
        self.assertIn('task-end/name/configure',
                      deps['task-start/name/build'])
        self.assertIn('task-end/name/build',
                      deps['task-start/name/install'])
        objdir = self.relcfg.objdir_path(host, 'name')
        instdir = self.relcfg.install_tree_path(host, 'name')
        srcdir = component.vars.srcdir.get()
        cmds_init = commands['task-end/name/init']
        self.assertIn('rm -rf %s' % objdir, cmds_init[1])
        self.assertIn('mkdir -p %s' % objdir, cmds_init[2])
        self.assertIn('rm -rf %s' % instdir, cmds_init[3])
        self.assertIn('mkdir -p %s' % instdir, cmds_init[4])
        cmds_cfg = commands['task-end/name/configure']
        self.assertIn(' %s ' % objdir, cmds_cfg[1])
        self.assertIn('%s/configure --build=x86_64-linux-gnu '
                      '--host=x86_64-linux-gnu --prefix=%s '
                      '--target=test-target --test-option %s '
                      'CC_FOR_BUILD=x86_64-linux-gnu-gcc '
                      'CXX_FOR_BUILD=x86_64-linux-gnu-g++'
                      % (srcdir, instdir, ' '.join(host.configure_vars())),
                      cmds_cfg[1])
        cmds_build = commands['task-end/name/build']
        self.assertIn(' %s ' % objdir, cmds_build[1])
        self.assertTrue(cmds_build[1].strip().endswith('$(MAKE)'))
        cmds_inst = commands['task-end/name/install']
        self.assertIn(' %s ' % objdir, cmds_inst[1])
        self.assertIn('$(MAKE) -j1 install', cmds_inst[1])

    def test_add_host_cfg_build_tasks_srcdir(self):
        """Test add_host_cfg_build_tasks, alternate srcdir provided."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_cfg_build_tasks(self.relcfg, host, component, top_task, None,
                                 '/other/srcdir', None, ['--test-option'],
                                 'test-target', None, 'install', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        cmds_cfg = commands['task-end/generic/configure']
        self.assertIn('/other/srcdir/configure', cmds_cfg[1])

    def test_add_host_cfg_build_tasks_prefix(self):
        """Test add_host_cfg_build_tasks, prefix provided."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_cfg_build_tasks(self.relcfg, host, component, top_task, None,
                                 None, '/cfg/prefix', ['--test-option'],
                                 'test-target', None, 'install', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        instdir = self.relcfg.install_tree_path(host, 'generic')
        cmds_cfg = commands['task-end/generic/configure']
        self.assertIn('--prefix=/cfg/prefix', cmds_cfg[1])
        cmds_inst = commands['task-end/generic/install']
        self.assertIn('$(MAKE) -j1 install DESTDIR=%s' % instdir, cmds_inst[1])

    def test_add_host_cfg_build_tasks_notarget(self):
        """Test add_host_cfg_build_tasks, no configured target."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_cfg_build_tasks(self.relcfg, host, component, top_task, None,
                                 None, None, ['--test-option'], None, None,
                                 'install', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        objdir = self.relcfg.objdir_path(host, 'generic')
        instdir = self.relcfg.install_tree_path(host, 'generic')
        srcdir = component.vars.srcdir.get()
        cmds_cfg = commands['task-end/generic/configure']
        self.assertIn(' %s ' % objdir, cmds_cfg[1])
        self.assertIn('%s/configure --build=x86_64-linux-gnu '
                      '--host=x86_64-linux-gnu --prefix=%s '
                      '--test-option %s '
                      'CC_FOR_BUILD=x86_64-linux-gnu-gcc '
                      'CXX_FOR_BUILD=x86_64-linux-gnu-g++'
                      % (srcdir, instdir, ' '.join(host.configure_vars())),
                      cmds_cfg[1])

    def test_add_host_cfg_build_tasks_cfg_opts_var(self):
        """Test add_host_cfg_build_tasks, configure_opts variable."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n'
                      'cfg.generic.configure_opts.set(["--abc", "--def"])\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_cfg_build_tasks(self.relcfg, host, component, top_task, None,
                                 None, None, ['--test-option'], 'test-target',
                                 None, 'install', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        objdir = self.relcfg.objdir_path(host, 'generic')
        instdir = self.relcfg.install_tree_path(host, 'generic')
        srcdir = component.vars.srcdir.get()
        cmds_cfg = commands['task-end/generic/configure']
        self.assertIn(' %s ' % objdir, cmds_cfg[1])
        self.assertIn('%s/configure --build=x86_64-linux-gnu '
                      '--host=x86_64-linux-gnu --prefix=%s '
                      '--target=test-target --test-option --abc --def %s '
                      'CC_FOR_BUILD=x86_64-linux-gnu-gcc '
                      'CXX_FOR_BUILD=x86_64-linux-gnu-g++'
                      % (srcdir, instdir, ' '.join(host.configure_vars())),
                      cmds_cfg[1])

    def test_add_host_cfg_build_tasks_cfg_opts_component(self):
        """Test add_host_cfg_build_tasks, configure_opts from component."""
        self.setup_rc('cfg.add_component("configure_opts")\n'
                      'cfg.configure_opts.version.set("test")\n'
                      'cfg.configure_opts.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('configure_opts')
        add_host_cfg_build_tasks(self.relcfg, host, component, top_task, None,
                                 None, None, ['--test-option'], 'test-target',
                                 None, 'install', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/configure_opts/init',
                      deps['task-start/configure_opts/configure'])
        self.assertIn('task-end/configure_opts/configure',
                      deps['task-start/configure_opts/build'])
        self.assertIn('task-end/configure_opts/build',
                      deps['task-start/configure_opts/install'])
        objdir = self.relcfg.objdir_path(host, 'configure_opts')
        instdir = self.relcfg.install_tree_path(host, 'configure_opts')
        srcdir = component.vars.srcdir.get()
        cmds_cfg = commands['task-end/configure_opts/configure']
        self.assertIn(' %s ' % objdir, cmds_cfg[1])
        self.assertIn('%s/configure --build=x86_64-linux-gnu '
                      '--host=x86_64-linux-gnu --prefix=%s '
                      '--target=test-target --test-option --test --option '
                      '--for-target=aarch64-linux-gnu '
                      '--for-host=x86_64-linux-gnu %s '
                      'CC_FOR_BUILD=x86_64-linux-gnu-gcc '
                      'CXX_FOR_BUILD=x86_64-linux-gnu-g++'
                      % (srcdir, instdir, ' '.join(host.configure_vars())),
                      cmds_cfg[1])

    def test_add_host_cfg_build_tasks_make_target(self):
        """Test add_host_cfg_build_tasks, target for make provided."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_cfg_build_tasks(self.relcfg, host, component, top_task, None,
                                 None, None, ['--test-option'], 'test-target',
                                 'make-target', 'install', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        cmds_build = commands['task-end/generic/build']
        self.assertTrue(cmds_build[1].strip().endswith('$(MAKE) make-target'))

    def test_add_host_cfg_build_tasks_install_target(self):
        """Test add_host_cfg_build_tasks, target for install provided."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_cfg_build_tasks(self.relcfg, host, component, top_task, None,
                                 None, None, ['--test-option'], 'test-target',
                                 None, 'install-test', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        cmds_inst = commands['task-end/generic/install']
        self.assertIn('$(MAKE) -j1 install-test', cmds_inst[1])

    def test_add_host_cfg_build_tasks_serial(self):
        """Test add_host_cfg_build_tasks, serial build."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_cfg_build_tasks(self.relcfg, host, component, top_task, None,
                                 None, None, ['--test-option'], 'test-target',
                                 None, 'install', False)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        cmds_build = commands['task-end/generic/build']
        self.assertTrue(cmds_build[1].strip().endswith('$(MAKE) -j1'))

    def test_add_host_lib_cfg_build_tasks(self):
        """Test add_host_lib_cfg_build_tasks."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_lib_cfg_build_tasks(self.relcfg, host, component, top_task,
                                     None, None, None, ['--test-option'], None,
                                     'install', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        objdir = self.relcfg.objdir_path(host, 'generic')
        instdir = self.relcfg.install_tree_path(host, 'generic')
        srcdir = component.vars.srcdir.get()
        cmds_init = commands['task-end/generic/init']
        self.assertIn('rm -rf %s' % objdir, cmds_init[1])
        self.assertIn('mkdir -p %s' % objdir, cmds_init[2])
        self.assertIn('rm -rf %s' % instdir, cmds_init[3])
        self.assertIn('mkdir -p %s' % instdir, cmds_init[4])
        cmds_cfg = commands['task-end/generic/configure']
        self.assertIn(' %s ' % objdir, cmds_cfg[1])
        self.assertIn('%s/configure --build=x86_64-linux-gnu '
                      '--host=x86_64-linux-gnu --prefix=%s '
                      '--disable-shared --test-option %s '
                      'CC_FOR_BUILD=x86_64-linux-gnu-gcc '
                      'CXX_FOR_BUILD=x86_64-linux-gnu-g++'
                      % (srcdir, instdir, ' '.join(host.configure_vars())),
                      cmds_cfg[1])
        cmds_build = commands['task-end/generic/build']
        self.assertIn(' %s ' % objdir, cmds_build[1])
        self.assertTrue(cmds_build[1].strip().endswith('$(MAKE)'))
        cmds_inst = commands['task-end/generic/install']
        self.assertIn(' %s ' % objdir, cmds_inst[1])
        self.assertIn('$(MAKE) -j1 install', cmds_inst[1])

    def test_add_host_lib_cfg_build_tasks_return(self):
        """Test add_host_lib_cfg_build_tasks, returned task group."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        task_group = add_host_lib_cfg_build_tasks(self.relcfg, host, component,
                                                  top_task, None, None, None,
                                                  ['--test-option'], None,
                                                  'install', True)
        extra_task = BuildTask(self.relcfg, task_group, 'extra')
        extra_task.add_command(['test', 'command'])
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        self.assertIn('task-end/generic/install',
                      deps['task-start/generic/extra'])
        cmds_extra = commands['task-end/generic/extra']
        self.assertIn('test command', cmds_extra[1])

    def test_add_host_lib_cfg_build_tasks_name(self):
        """Test add_host_lib_cfg_build_tasks, alternate name provided."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_lib_cfg_build_tasks(self.relcfg, host, component, top_task,
                                     'name', None, None, ['--test-option'],
                                     None, 'install', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/name/init',
                      deps['task-start/name/configure'])
        self.assertIn('task-end/name/configure',
                      deps['task-start/name/build'])
        self.assertIn('task-end/name/build',
                      deps['task-start/name/install'])
        objdir = self.relcfg.objdir_path(host, 'name')
        instdir = self.relcfg.install_tree_path(host, 'name')
        srcdir = component.vars.srcdir.get()
        cmds_init = commands['task-end/name/init']
        self.assertIn('rm -rf %s' % objdir, cmds_init[1])
        self.assertIn('mkdir -p %s' % objdir, cmds_init[2])
        self.assertIn('rm -rf %s' % instdir, cmds_init[3])
        self.assertIn('mkdir -p %s' % instdir, cmds_init[4])
        cmds_cfg = commands['task-end/name/configure']
        self.assertIn(' %s ' % objdir, cmds_cfg[1])
        self.assertIn('%s/configure --build=x86_64-linux-gnu '
                      '--host=x86_64-linux-gnu --prefix=%s '
                      '--disable-shared --test-option %s '
                      'CC_FOR_BUILD=x86_64-linux-gnu-gcc '
                      'CXX_FOR_BUILD=x86_64-linux-gnu-g++'
                      % (srcdir, instdir, ' '.join(host.configure_vars())),
                      cmds_cfg[1])
        cmds_build = commands['task-end/name/build']
        self.assertIn(' %s ' % objdir, cmds_build[1])
        self.assertTrue(cmds_build[1].strip().endswith('$(MAKE)'))
        cmds_inst = commands['task-end/name/install']
        self.assertIn(' %s ' % objdir, cmds_inst[1])
        self.assertIn('$(MAKE) -j1 install', cmds_inst[1])

    def test_add_host_lib_cfg_build_tasks_srcdir(self):
        """Test add_host_lib_cfg_build_tasks, alternate srcdir provided."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_lib_cfg_build_tasks(self.relcfg, host, component, top_task,
                                     None, '/other/srcdir', None,
                                     ['--test-option'], None, 'install', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        cmds_cfg = commands['task-end/generic/configure']
        self.assertIn('/other/srcdir/configure', cmds_cfg[1])

    def test_add_host_lib_cfg_build_tasks_prefix(self):
        """Test add_host_lib_cfg_build_tasks, prefix provided."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_lib_cfg_build_tasks(self.relcfg, host, component, top_task,
                                     None, None, '/cfg/prefix',
                                     ['--test-option'], None, 'install', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        instdir = self.relcfg.install_tree_path(host, 'generic')
        cmds_cfg = commands['task-end/generic/configure']
        self.assertIn('--prefix=/cfg/prefix', cmds_cfg[1])
        cmds_inst = commands['task-end/generic/install']
        self.assertIn('$(MAKE) -j1 install DESTDIR=%s' % instdir, cmds_inst[1])

    def test_add_host_lib_cfg_build_tasks_cfg_opts_var(self):
        """Test add_host_lib_cfg_build_tasks, configure_opts variable."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n'
                      'cfg.generic.configure_opts.set(["--abc", "--def"])\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_lib_cfg_build_tasks(self.relcfg, host, component, top_task,
                                     None, None, None, ['--test-option'], None,
                                     'install', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        objdir = self.relcfg.objdir_path(host, 'generic')
        instdir = self.relcfg.install_tree_path(host, 'generic')
        srcdir = component.vars.srcdir.get()
        cmds_cfg = commands['task-end/generic/configure']
        self.assertIn(' %s ' % objdir, cmds_cfg[1])
        self.assertIn('%s/configure --build=x86_64-linux-gnu '
                      '--host=x86_64-linux-gnu --prefix=%s '
                      '--disable-shared --test-option --abc --def %s '
                      'CC_FOR_BUILD=x86_64-linux-gnu-gcc '
                      'CXX_FOR_BUILD=x86_64-linux-gnu-g++'
                      % (srcdir, instdir, ' '.join(host.configure_vars())),
                      cmds_cfg[1])

    def test_add_host_lib_cfg_build_tasks_cfg_opts_component(self):
        """Test add_host_lib_cfg_build_tasks, configure_opts from component."""
        self.setup_rc('cfg.add_component("configure_opts")\n'
                      'cfg.configure_opts.version.set("test")\n'
                      'cfg.configure_opts.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('configure_opts')
        add_host_lib_cfg_build_tasks(self.relcfg, host, component, top_task,
                                     None, None, None, ['--test-option'], None,
                                     'install', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/configure_opts/init',
                      deps['task-start/configure_opts/configure'])
        self.assertIn('task-end/configure_opts/configure',
                      deps['task-start/configure_opts/build'])
        self.assertIn('task-end/configure_opts/build',
                      deps['task-start/configure_opts/install'])
        objdir = self.relcfg.objdir_path(host, 'configure_opts')
        instdir = self.relcfg.install_tree_path(host, 'configure_opts')
        srcdir = component.vars.srcdir.get()
        cmds_cfg = commands['task-end/configure_opts/configure']
        self.assertIn(' %s ' % objdir, cmds_cfg[1])
        self.assertIn('%s/configure --build=x86_64-linux-gnu '
                      '--host=x86_64-linux-gnu --prefix=%s '
                      '--disable-shared --test-option --test --option '
                      '--for-target=aarch64-linux-gnu '
                      '--for-host=x86_64-linux-gnu %s '
                      'CC_FOR_BUILD=x86_64-linux-gnu-gcc '
                      'CXX_FOR_BUILD=x86_64-linux-gnu-g++'
                      % (srcdir, instdir, ' '.join(host.configure_vars())),
                      cmds_cfg[1])

    def test_add_host_lib_cfg_build_tasks_make_target(self):
        """Test add_host_lib_cfg_build_tasks, target for make provided."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_lib_cfg_build_tasks(self.relcfg, host, component, top_task,
                                     None, None, None, ['--test-option'],
                                     'make-target', 'install', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        cmds_build = commands['task-end/generic/build']
        self.assertTrue(cmds_build[1].strip().endswith('$(MAKE) make-target'))

    def test_add_host_lib_cfg_build_tasks_install_target(self):
        """Test add_host_lib_cfg_build_tasks, target for install provided."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_lib_cfg_build_tasks(self.relcfg, host, component, top_task,
                                     None, None, None, ['--test-option'], None,
                                     'install-test', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        cmds_inst = commands['task-end/generic/install']
        self.assertIn('$(MAKE) -j1 install-test', cmds_inst[1])

    def test_add_host_lib_cfg_build_tasks_serial(self):
        """Test add_host_lib_cfg_build_tasks, serial build."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_lib_cfg_build_tasks(self.relcfg, host, component, top_task,
                                     None, None, None, ['--test-option'], None,
                                     'install', False)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        cmds_build = commands['task-end/generic/build']
        self.assertTrue(cmds_build[1].strip().endswith('$(MAKE) -j1'))

    def test_add_host_tool_cfg_build_tasks(self):
        """Test add_host_tool_cfg_build_tasks."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_tool_cfg_build_tasks(self.relcfg, host, component, top_task,
                                      None, None, ['--test-option'], '', None,
                                      'install', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        objdir = self.relcfg.objdir_path(host, 'generic')
        instdir = self.relcfg.install_tree_path(host, 'generic')
        srcdir = component.vars.srcdir.get()
        cmds_init = commands['task-end/generic/init']
        self.assertIn('rm -rf %s' % objdir, cmds_init[1])
        self.assertIn('mkdir -p %s' % objdir, cmds_init[2])
        self.assertIn('rm -rf %s' % instdir, cmds_init[3])
        self.assertIn('mkdir -p %s' % instdir, cmds_init[4])
        cmds_cfg = commands['task-end/generic/configure']
        self.assertIn(' %s ' % objdir, cmds_cfg[1])
        self.assertIn('%s/configure --build=x86_64-linux-gnu '
                      '--host=x86_64-linux-gnu --prefix=/opt/toolchain '
                      '--target=aarch64-linux-gnu --test-option %s '
                      'CC_FOR_BUILD=x86_64-linux-gnu-gcc '
                      'CXX_FOR_BUILD=x86_64-linux-gnu-g++'
                      % (srcdir, ' '.join(host.configure_vars())),
                      cmds_cfg[1])
        cmds_build = commands['task-end/generic/build']
        self.assertIn(' %s ' % objdir, cmds_build[1])
        self.assertTrue(cmds_build[1].strip().endswith('$(MAKE)'))
        cmds_inst = commands['task-end/generic/install']
        self.assertIn(' %s ' % objdir, cmds_inst[1])
        self.assertIn('$(MAKE) -j1 install DESTDIR=%s' % instdir, cmds_inst[1])

    def test_add_host_tool_cfg_build_tasks_target(self):
        """Test add_host_tool_cfg_build_tasks, explicit target specified."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_tool_cfg_build_tasks(self.relcfg, host, component, top_task,
                                      None, None, ['--test-option'],
                                      'test-target', None, 'install', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        cmds_cfg = commands['task-end/generic/configure']
        self.assertIn('--target=test-target', cmds_cfg[1])

    def test_add_host_tool_cfg_build_tasks_return(self):
        """Test add_host_tool_cfg_build_tasks, returned task group."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        task_group = add_host_tool_cfg_build_tasks(self.relcfg, host,
                                                   component, top_task, None,
                                                   None, ['--test-option'], '',
                                                   None, 'install', True)
        extra_task = BuildTask(self.relcfg, task_group, 'extra')
        extra_task.add_command(['test', 'command'])
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        self.assertIn('task-end/generic/install',
                      deps['task-start/generic/extra'])
        cmds_extra = commands['task-end/generic/extra']
        self.assertIn('test command', cmds_extra[1])

    def test_add_host_tool_cfg_build_tasks_name(self):
        """Test add_host_tool_cfg_build_tasks, alternate name provided."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_tool_cfg_build_tasks(self.relcfg, host, component, top_task,
                                      'name', None, ['--test-option'], '',
                                      None, 'install', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/name/init',
                      deps['task-start/name/configure'])
        self.assertIn('task-end/name/configure',
                      deps['task-start/name/build'])
        self.assertIn('task-end/name/build',
                      deps['task-start/name/install'])
        objdir = self.relcfg.objdir_path(host, 'name')
        instdir = self.relcfg.install_tree_path(host, 'name')
        srcdir = component.vars.srcdir.get()
        cmds_init = commands['task-end/name/init']
        self.assertIn('rm -rf %s' % objdir, cmds_init[1])
        self.assertIn('mkdir -p %s' % objdir, cmds_init[2])
        self.assertIn('rm -rf %s' % instdir, cmds_init[3])
        self.assertIn('mkdir -p %s' % instdir, cmds_init[4])
        cmds_cfg = commands['task-end/name/configure']
        self.assertIn(' %s ' % objdir, cmds_cfg[1])
        self.assertIn('%s/configure --build=x86_64-linux-gnu '
                      '--host=x86_64-linux-gnu --prefix=/opt/toolchain '
                      '--target=aarch64-linux-gnu --test-option %s '
                      'CC_FOR_BUILD=x86_64-linux-gnu-gcc '
                      'CXX_FOR_BUILD=x86_64-linux-gnu-g++'
                      % (srcdir, ' '.join(host.configure_vars())),
                      cmds_cfg[1])
        cmds_build = commands['task-end/name/build']
        self.assertIn(' %s ' % objdir, cmds_build[1])
        self.assertTrue(cmds_build[1].strip().endswith('$(MAKE)'))
        cmds_inst = commands['task-end/name/install']
        self.assertIn(' %s ' % objdir, cmds_inst[1])
        self.assertIn('$(MAKE) -j1 install', cmds_inst[1])

    def test_add_host_tool_cfg_build_tasks_srcdir(self):
        """Test add_host_tool_cfg_build_tasks, alternate srcdir provided."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_tool_cfg_build_tasks(self.relcfg, host, component, top_task,
                                      None, '/other/srcdir', ['--test-option'],
                                      '', None, 'install', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        cmds_cfg = commands['task-end/generic/configure']
        self.assertIn('/other/srcdir/configure', cmds_cfg[1])

    def test_add_host_tool_cfg_build_tasks_prefix(self):
        """Test add_host_tool_cfg_build_tasks, prefix provided in config."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n'
                      'cfg.installdir.set("/some/where")')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_tool_cfg_build_tasks(self.relcfg, host, component, top_task,
                                      None, None, ['--test-option'], '', None,
                                      'install', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        instdir = self.relcfg.install_tree_path(host, 'generic')
        cmds_cfg = commands['task-end/generic/configure']
        self.assertIn('--prefix=/some/where', cmds_cfg[1])
        cmds_inst = commands['task-end/generic/install']
        self.assertIn('$(MAKE) -j1 install DESTDIR=%s' % instdir, cmds_inst[1])

    def test_add_host_tool_cfg_build_tasks_notarget(self):
        """Test add_host_tool_cfg_build_tasks, no configured target."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_tool_cfg_build_tasks(self.relcfg, host, component, top_task,
                                      None, None, ['--test-option'], None,
                                      None, 'install', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        objdir = self.relcfg.objdir_path(host, 'generic')
        srcdir = component.vars.srcdir.get()
        cmds_cfg = commands['task-end/generic/configure']
        self.assertIn(' %s ' % objdir, cmds_cfg[1])
        self.assertIn('%s/configure --build=x86_64-linux-gnu '
                      '--host=x86_64-linux-gnu --prefix=/opt/toolchain '
                      '--test-option %s '
                      'CC_FOR_BUILD=x86_64-linux-gnu-gcc '
                      'CXX_FOR_BUILD=x86_64-linux-gnu-g++'
                      % (srcdir, ' '.join(host.configure_vars())),
                      cmds_cfg[1])

    def test_add_host_tool_cfg_build_tasks_cfg_opts_var(self):
        """Test add_host_tool_cfg_build_tasks, configure_opts variable."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n'
                      'cfg.generic.configure_opts.set(["--abc", "--def"])\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_tool_cfg_build_tasks(self.relcfg, host, component, top_task,
                                      None, None, ['--test-option'], '', None,
                                      'install', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        objdir = self.relcfg.objdir_path(host, 'generic')
        srcdir = component.vars.srcdir.get()
        cmds_cfg = commands['task-end/generic/configure']
        self.assertIn(' %s ' % objdir, cmds_cfg[1])
        self.assertIn('%s/configure --build=x86_64-linux-gnu '
                      '--host=x86_64-linux-gnu --prefix=/opt/toolchain '
                      '--target=aarch64-linux-gnu --test-option '
                      '--abc --def %s '
                      'CC_FOR_BUILD=x86_64-linux-gnu-gcc '
                      'CXX_FOR_BUILD=x86_64-linux-gnu-g++'
                      % (srcdir, ' '.join(host.configure_vars())),
                      cmds_cfg[1])

    def test_add_host_tool_cfg_build_tasks_cfg_opts_component(self):
        """Test add_host_tool_cfg_build_tasks, configure_opts from component.
        """
        self.setup_rc('cfg.add_component("configure_opts")\n'
                      'cfg.configure_opts.version.set("test")\n'
                      'cfg.configure_opts.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('configure_opts')
        add_host_tool_cfg_build_tasks(self.relcfg, host, component, top_task,
                                      None, None, ['--test-option'], '', None,
                                      'install', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/configure_opts/init',
                      deps['task-start/configure_opts/configure'])
        self.assertIn('task-end/configure_opts/configure',
                      deps['task-start/configure_opts/build'])
        self.assertIn('task-end/configure_opts/build',
                      deps['task-start/configure_opts/install'])
        objdir = self.relcfg.objdir_path(host, 'configure_opts')
        srcdir = component.vars.srcdir.get()
        cmds_cfg = commands['task-end/configure_opts/configure']
        self.assertIn(' %s ' % objdir, cmds_cfg[1])
        self.assertIn('%s/configure --build=x86_64-linux-gnu '
                      '--host=x86_64-linux-gnu --prefix=/opt/toolchain '
                      '--target=aarch64-linux-gnu --test-option '
                      '--test --option '
                      '--for-target=aarch64-linux-gnu '
                      '--for-host=x86_64-linux-gnu %s '
                      'CC_FOR_BUILD=x86_64-linux-gnu-gcc '
                      'CXX_FOR_BUILD=x86_64-linux-gnu-g++'
                      % (srcdir, ' '.join(host.configure_vars())),
                      cmds_cfg[1])

    def test_add_host_tool_cfg_build_tasks_make_target(self):
        """Test add_host_tool_cfg_build_tasks, target for make provided."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_tool_cfg_build_tasks(self.relcfg, host, component, top_task,
                                      None, None, ['--test-option'], '',
                                      'make-target', 'install', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        cmds_build = commands['task-end/generic/build']
        self.assertTrue(cmds_build[1].strip().endswith('$(MAKE) make-target'))

    def test_add_host_tool_cfg_build_tasks_install_target(self):
        """Test add_host_tool_cfg_build_tasks, target for install provided."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_tool_cfg_build_tasks(self.relcfg, host, component, top_task,
                                      None, None, ['--test-option'], '', None,
                                      'install-test', True)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        cmds_inst = commands['task-end/generic/install']
        self.assertIn('$(MAKE) -j1 install-test', cmds_inst[1])

    def test_add_host_tool_cfg_build_tasks_serial(self):
        """Test add_host_tool_cfg_build_tasks, serial build."""
        self.setup_rc('cfg.add_component("generic")\n'
                      'cfg.generic.version.set("test")\n'
                      'cfg.generic.vc.set(TarVC("dummy"))\n')
        top_task = BuildTask(self.relcfg, None, '', True)
        host = self.relcfg.hosts.get()[0].build_cfg
        component = self.relcfg.get_component('generic')
        add_host_tool_cfg_build_tasks(self.relcfg, host, component, top_task,
                                      None, None, ['--test-option'], '', None,
                                      'install', False)
        text = top_task.makefile_text(self.build_context)
        deps, commands = parse_makefile(text)
        self.assertIn('task-end/generic/init',
                      deps['task-start/generic/configure'])
        self.assertIn('task-end/generic/configure',
                      deps['task-start/generic/build'])
        self.assertIn('task-end/generic/build',
                      deps['task-start/generic/install'])
        cmds_build = commands['task-end/generic/build']
        self.assertTrue(cmds_build[1].strip().endswith('$(MAKE) -j1'))
