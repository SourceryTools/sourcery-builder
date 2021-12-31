# sourcery-builder toolchain component.

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

"""sourcery-builder toolchain component."""

import sourcery.component

__all__ = ['Component']


class Component(sourcery.component.Component):
    """sourcery-builder toolchain component implementation."""

    @staticmethod
    def add_release_config_vars(group):
        group.source_type.set_implicit('none')

    @staticmethod
    def add_build_tasks_for_first_host(cfg, host, component, host_group):
        # The toolchain component does not have any tasks.  Rather, it
        # exists to declare install trees that are contributed to by
        # toolchain components.  toolchain-1-before contains pieces
        # built before the first compiler; toolchain-1 also contains
        # the first compiler; toolchain-2-before also contains any
        # libraries built with the first compiler; toolchain-2 also
        # contains the second compiler.  The particular compilers
        # involved may vary depending on the configuration.  For hosts
        # other than the first, these install trees are not needed:
        # target libraries are only built once and building some host
        # binaries for such a host (e.g. GCC) can depend on other host
        # binaries built for the build system (e.g. binutils) but not
        # on other host binaries built for that host.
        host_b = host.build_cfg
        host_group.declare_implicit_install(host_b, 'toolchain-1-before')
        host_group.declare_implicit_install(host_b, 'toolchain-1')
        host_group.declare_implicit_install(host_b, 'toolchain-2-before')
        host_group.declare_implicit_install(host_b, 'toolchain-2')
