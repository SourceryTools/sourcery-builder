# sourcery-builder binutils component.

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

"""sourcery-builder binutils component."""

from sourcery.autoconf import add_host_tool_cfg_build_tasks
import sourcery.component
from sourcery.fstree import FSTreeRemove

__all__ = ['Component']


class Component(sourcery.component.Component):
    """sourcery-builder binutils component implementation."""

    @staticmethod
    def add_release_config_vars(group):
        group.source_type.set_implicit('open')

    @staticmethod
    def add_build_tasks_for_host(cfg, host, component, host_group):
        host_b = host.build_cfg
        add_host_tool_cfg_build_tasks(cfg, host_b, component, host_group)
        tree = cfg.install_tree_fstree(host_b, 'binutils')
        tree = FSTreeRemove(tree, [cfg.info_dir_rel.get()])
        if host == cfg.build.get():
            host_group.contribute_implicit_install(host_b,
                                                   'toolchain-1-before', tree)
            host_group.contribute_implicit_install(host_b, 'toolchain-1', tree)
        host_group.contribute_implicit_install(host_b, 'toolchain-2-before',
                                               tree)
        host_group.contribute_implicit_install(host_b, 'toolchain-2', tree)
        host_group.contribute_package(host, tree)

    @staticmethod
    def configure_opts(cfg, host):
        # Avoid building GDB when using a checkout that has both.
        return ['--disable-gdb', '--disable-libdecnumber',
                '--disable-readline', '--disable-sim']
