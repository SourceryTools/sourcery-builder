# sourcery-builder gcc component.

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

"""sourcery-builder gcc component."""

import os.path

from sourcery.autoconf import add_host_tool_cfg_build_tasks
import sourcery.component
from sourcery.fstree import FSTreeRemove

__all__ = ['Component']


class Component(sourcery.component.Component):
    """sourcery-builder gcc component implementation."""

    @staticmethod
    def add_release_config_vars(group):
        group.source_type.set_implicit('open')

    @staticmethod
    def postcheckout(context, component):
        context.execute(['contrib/gcc_update', '--touch'],
                        cwd=component.vars.srcdir.get())

    @staticmethod
    def add_build_tasks_for_host(cfg, host, component, host_group):
        host_b = host.build_cfg
        build = cfg.build.get()
        target = cfg.target.get()
        sysroot = cfg.sysroot.get()
        sysroot_rel = cfg.sysroot_rel.get()
        bindir_rel = cfg.bindir_rel.get()
        inst_1_before = cfg.install_tree_path(host_b, 'toolchain-1-before')
        build_sysroot_1 = os.path.join(inst_1_before, sysroot_rel)
        bindir_1 = os.path.join(inst_1_before, bindir_rel)
        inst_2_before = cfg.install_tree_path(host_b, 'toolchain-2-before')
        build_sysroot_2 = os.path.join(inst_2_before, sysroot_rel)
        bindir_2 = os.path.join(inst_2_before, bindir_rel)
        build_time_tools_1 = os.path.join(
            cfg.install_tree_path(build.build_cfg, 'toolchain-1-before'),
            target, 'bin')
        build_time_tools_2 = os.path.join(
            cfg.install_tree_path(build.build_cfg, 'toolchain-2-before'),
            target, 'bin')
        # glibc version hardcoding only for initial prototype.
        opts_first = ['--enable-languages=c',
                      '--disable-shared',
                      '--disable-threads',
                      '--without-headers', '--with-newlib',
                      '--with-glibc-version=2.28',
                      '--with-sysroot=%s' % sysroot,
                      '--with-build-sysroot=%s' % build_sysroot_1,
                      '--with-build-time-tools=%s' % build_time_tools_1,
                      '--disable-decimal-float',
                      '--disable-libatomic',
                      '--disable-libcilkrts',
                      '--disable-libffi',
                      '--disable-libgomp',
                      '--disable-libitm',
                      '--disable-libmpx',
                      '--disable-libquadmath',
                      '--disable-libsanitizer']
        opts_second = ['--enable-languages=c,c++',
                       '--enable-shared',
                       '--enable-threads',
                       '--with-sysroot=%s' % sysroot,
                       '--with-build-sysroot=%s' % build_sysroot_2,
                       '--with-build-time-tools=%s' % build_time_tools_2]
        if host == build:
            group = add_host_tool_cfg_build_tasks(
                cfg, host_b, component, host_group, name='gcc-first',
                pkg_cfg_opts=opts_first)
            group.depend_install(host_b, 'gmp')
            group.depend_install(host_b, 'mpfr')
            group.depend_install(host_b, 'mpc')
            group.depend_install(host_b, 'toolchain-1-before')
            group.env_prepend('PATH', bindir_1)
            tree = cfg.install_tree_fstree(host_b, 'gcc-first')
            tree = FSTreeRemove(tree, [cfg.info_dir_rel.get()])
            host_group.contribute_implicit_install(host_b, 'toolchain-1', tree)
        group = add_host_tool_cfg_build_tasks(
            cfg, host_b, component, host_group, name='gcc',
            pkg_cfg_opts=opts_second)
        group.depend_install(host_b, 'gmp')
        group.depend_install(host_b, 'mpfr')
        group.depend_install(host_b, 'mpc')
        group.depend_install(host_b, 'toolchain-2-before')
        group.env_prepend('PATH', bindir_2)
        tree = cfg.install_tree_fstree(host_b, 'gcc')
        tree = FSTreeRemove(tree, [cfg.info_dir_rel.get()])
        host_group.contribute_implicit_install(host_b, 'toolchain-2', tree)
        host_group.contribute_package(host, tree)

    @staticmethod
    def configure_opts(cfg, host):
        return ['--disable-libssp',
                '--with-gmp=%s' % cfg.install_tree_path(host, 'gmp'),
                '--with-mpfr=%s' % cfg.install_tree_path(host, 'mpfr'),
                '--with-mpc=%s' % cfg.install_tree_path(host, 'mpc')]
