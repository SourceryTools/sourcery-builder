# sourcery-builder gmp component.

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

"""sourcery-builder gmp component."""

from sourcery.autoconf import add_host_lib_cfg_build_tasks
import sourcery.component

__all__ = ['Component']


class Component(sourcery.component.Component):
    """sourcery-builder gmp component implementation."""

    @staticmethod
    def add_release_config_vars(group):
        group.source_type.set_implicit('open')

    files_to_touch = ['doc/gmp.info*']

    @staticmethod
    def add_build_tasks_for_host(cfg, host, component, host_group):
        host_b = host.build_cfg
        add_host_lib_cfg_build_tasks(cfg, host_b, component, host_group)

    @staticmethod
    def configure_opts(cfg, host):
        # GMP's configure script may select CFLAGS that choose a
        # non-default ABI (so causing problems for subsequent
        # components built using GMP that require the default ABI for
        # the compiler) or that assume building natively for the same
        # hardware on which GMP is built (so causing problems for the
        # portable use of the compiler binaries).  To avoid this,
        # specify CFLAGS explicitly here.
        return ['CFLAGS=-g -O2']
