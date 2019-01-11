# sourcery-builder glibc component.

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

"""sourcery-builder glibc component."""

import os.path

from sourcery.buildcfg import BuildCfg
from sourcery.buildtask import BuildTask
import sourcery.component
from sourcery.fstree import FSTreeEmpty, FSTreeMove, FSTreeUnion

__all__ = ['Component']


class Component(sourcery.component.Component):
    """sourcery-builder glibc component implementation."""

    @staticmethod
    def add_release_config_vars(group):
        group.source_type.set_implicit('open')

    # These files may be regenerated in the source directory as part
    # of building and testing glibc (some have been removed from the
    # source tree in later glibc versions).  Even with timestamps in
    # the right order, the glibc build process still writes into the
    # source tree before commit
    # f2da2fd81f1d3f43678de9cf39b12692c6fa449b ("Do not build .mo
    # files in source directory (bug 14121)."), and, for Hurd, before
    # commit b473b7d88e6829fd0c8a02512b86950dc7089039 ("Fix Hurd build
    # with read-only source directory.").
    files_to_touch = ['**/configure', '**/preconfigure', '**/*-kw.h',
                      'intl/plural.c', 'locale/C-translit.h',
                      'posix/ptestcases.h', 'posix/testcases.h',
                      'sysdeps/gnu/errlist.c',
                      'sysdeps/mach/hurd/bits/errno.h',
                      'sysdeps/sparc/sparc32/rem.S',
                      'sysdeps/sparc/sparc32/sdiv.S',
                      'sysdeps/sparc/sparc32/udiv.S',
                      'sysdeps/sparc/sparc32/urem.S']

    @staticmethod
    def add_build_tasks_for_first_host(cfg, host, component, host_group):
        host_b = host.build_cfg
        target = cfg.target.get()
        inst_1 = cfg.install_tree_path(host_b, 'toolchain-1')
        bindir_1 = os.path.join(inst_1, cfg.bindir_rel.get())
        # This should actually run in a loop over multilibs, with
        # appropriate handling for files appearing for more than
        # multilib sharing the same sysroot and for headers shared by
        # all multilibs.
        target_build = BuildCfg(cfg.context, target)
        srcdir = component.vars.srcdir.get()
        objdir = cfg.objdir_path(target_build, 'glibc')
        instdir = cfg.install_tree_path(target_build, 'glibc')
        group = BuildTask(cfg, host_group, 'glibc')
        group.depend_install(host_b, 'toolchain-1')
        group.env_prepend('PATH', bindir_1)
        group.provide_install(target_build, 'glibc')
        init_task = BuildTask(cfg, group, 'init')
        init_task.add_empty_dir(objdir)
        init_task.add_empty_dir(instdir)
        cfg_task = BuildTask(cfg, group, 'configure')
        cfg_cmd = [os.path.join(srcdir, 'configure'),
                   '--build=%s' % host_b.triplet,
                   '--host=%s' % target_build.triplet,
                   '--prefix=/usr']
        cfg_cmd.extend(component.vars.configure_opts.get())
        cfg_cmd.extend(target_build.configure_vars())
        cfg_cmd.append('BUILD_CC=%s'
                       % ' '.join(host_b.tool('c-compiler')))
        cfg_task.add_command(cfg_cmd, cwd=objdir)
        build_task = BuildTask(cfg, group, 'build')
        build_task.add_make([], objdir)
        install_task = BuildTask(cfg, group, 'install')
        install_task.add_make(['-j1', 'install', 'install_root=%s' % instdir],
                              objdir)
        tree = cfg.install_tree_fstree(target_build, 'glibc')
        sysroot_rel = cfg.sysroot_rel.get()
        tree = FSTreeMove(tree, sysroot_rel)
        # Ensure lib directories exist so that GCC's use of paths such
        # as lib/../lib64 works.
        tree_lib = FSTreeMove(FSTreeEmpty(cfg.context),
                              os.path.join(sysroot_rel, 'lib'))
        tree_usr_lib = FSTreeMove(FSTreeEmpty(cfg.context),
                                  os.path.join(sysroot_rel, 'usr', 'lib'))
        tree = FSTreeUnion(tree, tree_lib)
        tree = FSTreeUnion(tree, tree_usr_lib)
        host_group.contribute_implicit_install(host_b, 'toolchain-2-before',
                                               tree)
        host_group.contribute_implicit_install(host_b, 'toolchain-2', tree)
        host_group.contribute_package(host, tree)

    @staticmethod
    def add_build_tasks_for_other_hosts(cfg, host, component, host_group):
        host_b = host.build_cfg
        target = cfg.target.get()
        # As for the first host, this should run in a loop over
        # multilibs.
        target_build = BuildCfg(cfg.context, target)
        tree = cfg.install_tree_fstree(target_build, 'glibc')
        sysroot_rel = cfg.sysroot_rel.get()
        tree = FSTreeMove(tree, sysroot_rel)
        # Ensure lib directories exist so that GCC's use of paths such
        # as lib/../lib64 works.
        tree_lib = FSTreeMove(FSTreeEmpty(cfg.context),
                              os.path.join(sysroot_rel, 'lib'))
        tree_usr_lib = FSTreeMove(FSTreeEmpty(cfg.context),
                                  os.path.join(sysroot_rel, 'usr', 'lib'))
        tree = FSTreeUnion(tree, tree_lib)
        tree = FSTreeUnion(tree, tree_usr_lib)
        host_group.contribute_implicit_install(host_b, 'toolchain-2-before',
                                               tree)
        host_group.contribute_implicit_install(host_b, 'toolchain-2', tree)
        host_group.contribute_package(host, tree)
