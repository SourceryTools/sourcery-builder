# sourcery-builder build_install_tree component for testing.

# Copyright 2018-2021 Mentor Graphics Corporation.

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

"""sourcery-builder build_install_tree component for testing."""

from sourcery.buildtask import BuildTask
import sourcery.selftests.component
from sourcery.fstree import FSTreeMove

__all__ = ['Component']


class Component(sourcery.selftests.component.Component):
    """build_install_tree component implementation."""

    @staticmethod
    def add_release_config_vars(group):
        group.source_type.set_implicit('none')

    @staticmethod
    def add_build_tasks_for_first_host(cfg, host, component, host_group):
        task = BuildTask(cfg, host_group, 'first-host')
        host_b = host.build_cfg
        objdir = cfg.objdir_path(host_b, '%s-first' % component.copy_name)
        task.add_empty_dir(objdir)
        instdir_1 = cfg.install_tree_path(host_b, 'first-inst-1')
        task.add_empty_dir(instdir_1)
        task.provide_install(host_b, 'first-inst-1')
        instdir_2 = cfg.install_tree_path(host_b, 'first-inst-2')
        task.add_empty_dir(instdir_2)
        task.provide_install(host_b, 'first-inst-2')
        instdir_3 = cfg.install_tree_path(host_b, 'first-inst-3')
        task.add_empty_dir(instdir_3)
        task.provide_install(host_b, 'first-inst-3')
        task.add_command(['sh', '-c', 'echo a > %s/a' % instdir_1])
        task.add_command(['sh', '-c', 'echo b > %s/b' % instdir_2])
        task.add_command(['sh', '-c', 'echo c > %s/c' % instdir_3])
        tree_1 = cfg.install_tree_fstree(host_b, 'first-inst-1')
        tree_1 = FSTreeMove(tree_1, 'q')
        tree_2 = cfg.install_tree_fstree(host_b, 'first-inst-2')
        tree_3 = cfg.install_tree_fstree(host_b, 'first-inst-3')
        task.define_implicit_install(host_b, 'impl-def', tree_1)
        task.declare_implicit_install(host_b, 'impl-empty')
        task.declare_implicit_install(host_b, 'impl-one')
        task.contribute_implicit_install(host_b, 'impl-one', tree_2)
        task.declare_implicit_install(host_b, 'impl-two')
        task.contribute_implicit_install(host_b, 'impl-two', tree_2)
        task.contribute_implicit_install(host_b, 'impl-two', tree_3)
