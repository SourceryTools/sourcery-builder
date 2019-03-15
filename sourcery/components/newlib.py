# sourcery-builder newlib component.

# Copyright 2019 Mentor Graphics Corporation.

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

"""sourcery-builder newlib component."""

import os.path

from sourcery.autoconf import add_host_tool_cfg_build_tasks
import sourcery.component

__all__ = ['Component']


class Component(sourcery.component.Component):
    """sourcery-builder newlib component implementation."""

    @staticmethod
    def add_release_config_vars(group):
        group.source_type.set_implicit('open')

    @staticmethod
    def add_dependencies(relcfg):
        relcfg.add_component('toolchain')

    @staticmethod
    def add_build_tasks_for_first_host(cfg, host, component, host_group):
        host_b = host.build_cfg
        inst_1 = cfg.install_tree_path(host_b, 'toolchain-1')
        bindir_1 = os.path.join(inst_1, cfg.bindir_rel.get())
        # This is logically a target component, but the top-level
        # configure is used as if it is a host component and deals
        # with passing appropriate options when configuring the
        # relevant subdirectories.  Additional support would be needed
        # to build with compilers other than GCC.
        group = add_host_tool_cfg_build_tasks(cfg, host_b, component,
                                              host_group)
        group.depend_install(host_b, 'toolchain-1')
        group.env_prepend('PATH', bindir_1)
        tree = cfg.install_tree_fstree(host_b, 'newlib')
        host_group.contribute_implicit_install(host_b, 'toolchain-2-before',
                                               tree)
        host_group.contribute_implicit_install(host_b, 'toolchain-2', tree)
        host_group.contribute_package(host, tree)

    @staticmethod
    def add_build_tasks_for_other_hosts(cfg, host, component, host_group):
        build_b = cfg.build.get().build_cfg
        tree = cfg.install_tree_fstree(build_b, 'newlib')
        host_group.contribute_package(host, tree)
