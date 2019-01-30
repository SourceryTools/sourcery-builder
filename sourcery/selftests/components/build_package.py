# sourcery-builder build_package component for testing.

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

"""sourcery-builder build_package component for testing."""

import os.path

from sourcery.buildtask import BuildTask
import sourcery.selftests.component

__all__ = ['Component']


class Component(sourcery.selftests.component.Component):
    """build_package component implementation."""

    @staticmethod
    def add_release_config_vars(group):
        group.source_type.set_implicit('none')

    @staticmethod
    def add_build_tasks_for_host(cfg, host, component, host_group):
        task = BuildTask(cfg, host_group, 'example')
        host_b = host.build_cfg
        instdir = cfg.install_tree_path(host_b, 'example')
        instdir = os.path.join(instdir, cfg.installdir_rel.get())
        task.add_empty_dir(instdir)
        task.provide_install(host_b, 'example')
        tree = cfg.install_tree_fstree(host_b, 'example')
        host_group.contribute_package(host, tree)
        task.add_command(['sh', '-c', 'echo a > %s/a1' % instdir])
        task.add_command(['ln', '%s/a1' % instdir, '%s/a2' % instdir])
        task.add_command(['sh', '-c', 'echo a > %s/a3' % instdir])
        task.add_command(['chmod', 'a-w', '%s/a3' % instdir])
        instdir2 = cfg.install_tree_path(host_b, 'example2')
        instdir2 = os.path.join(instdir2, cfg.installdir_rel.get())
        task.add_empty_dir(instdir2)
        task.provide_install(host_b, 'example2')
        tree2 = cfg.install_tree_fstree(host_b, 'example2')
        host_group.contribute_package(host, tree2)
        task.add_command(['sh', '-c', 'echo b > %s/b' % instdir2])
        task.add_command(['ln', '-s', 'b', '%s/c' % instdir2])
