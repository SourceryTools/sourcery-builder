# sourcery-builder mpfr component.

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

"""sourcery-builder mpfr component."""

from sourcery.autoconf import add_host_lib_cfg_build_tasks
import sourcery.component

__all__ = ['Component']


class Component(sourcery.component.Component):
    """sourcery-builder mpfr component implementation."""

    @staticmethod
    def add_release_config_vars(group):
        group.source_type.set_implicit('open')

    # Various files may be regenerated in the source directory by
    # default unless timestamps are in the right order, and the paths
    # to some of those files have changed between MPFR versions.
    files_to_touch = ['aclocal.m4', 'configure', '**/Makefile.in',
                      'get_patches.c', 'src/get_patches.c', 'mpfr.info*',
                      'doc/mpfr.info*']

    @staticmethod
    def add_build_tasks_for_host(cfg, host, component, host_group):
        host_b = host.build_cfg
        group = add_host_lib_cfg_build_tasks(cfg, host_b, component,
                                             host_group)
        group.depend_install(host_b, 'gmp')

    @staticmethod
    def configure_opts(cfg, host):
        return ['--with-gmp=%s' % cfg.install_tree_path(host, 'gmp')]
