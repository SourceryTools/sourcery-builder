# sourcery-builder build_test component for testing.

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

"""sourcery-builder build_test component for testing."""

import os
import os.path

import sourcery.buildtask
import sourcery.component

__all__ = ['Component']


class Component(sourcery.component.Component):
    """build_test component implementation."""

    @staticmethod
    def add_release_config_vars(group):
        group.source_type.set_implicit('none')

    @staticmethod
    def add_build_tasks_for_host(cfg, host, component, host_group):
        task = sourcery.buildtask.BuildTask(cfg, host_group, 'all-hosts')
        host_b = host.build_cfg
        objdir = cfg.objdir_path(host_b, '%s-all' % component.copy_name)
        objdir2 = cfg.objdir_path(host_b, '%s-all2' % component.copy_name)
        task.add_empty_dir(objdir)
        # Create objdir2 with some contents to test add_empty_dir
        # removal of an existing directory.
        os.makedirs(os.path.join(objdir2, 'x', 'y'))
        task.add_empty_dir(objdir2)
        task.add_command(['sh', '-c', 'echo all-hosts > %s/out1' % objdir])
        task.add_command(['sh', '-c', 'echo all-hosts-2 > out2'], cwd=objdir)

    @staticmethod
    def add_build_tasks_for_first_host(cfg, host, component, host_group):
        task = sourcery.buildtask.BuildTask(cfg, host_group, 'first-host')
        host_b = host.build_cfg
        objdir = cfg.objdir_path(host_b, '%s-first' % component.copy_name)
        objdir2 = cfg.objdir_path(host_b, '%s-first2' % component.copy_name)
        task.add_empty_dir(objdir)
        # Test add_empty_dir_parent with and without the directory
        # existing.
        task.add_empty_dir_parent(os.path.join(objdir, 'x', 'y', 'z'))
        os.makedirs(os.path.join(objdir2, 'x', 'y', 'z'))
        task.add_empty_dir_parent(os.path.join(objdir2, 'x', 'y', 'z'))
        task.add_command(['sh', '-c',
                          'echo "all:; echo first-host \\$(X) > out" > '
                          '%s/GNUmakefile' % objdir])
        task.add_make(['all', 'X=Y'], objdir)

    @staticmethod
    def add_build_tasks_for_other_hosts(cfg, host, component, host_group):
        task = sourcery.buildtask.BuildTask(cfg, host_group, 'other-hosts')
        host_b = host.build_cfg
        objdir = cfg.objdir_path(host_b, '%s-other' % component.copy_name)
        task.add_empty_dir(objdir)

        def py_test_fn(arg1, arg2):
            """Test Python build step."""
            out_name = os.path.join(objdir, 'out')
            with open(out_name, 'w', encoding='utf-8') as outfile:
                outfile.write('%s %s\n' % (arg1, arg2))

        task.add_python(py_test_fn, ('test', 'python'))
