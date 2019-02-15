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

import collections
import os.path

from sourcery.buildtask import BuildTask
import sourcery.component
from sourcery.fstree import FSTreeEmpty, FSTreeMove, FSTreeRemove, \
    FSTreeExtract, FSTreeUnion

__all__ = ['Component']


def _contribute_sysroot_tree(cfg, host, host_group, is_build, multilib):
    """Contribute the glibc installation to all required install trees."""
    host_b = host.build_cfg
    target_build = multilib.build_cfg
    tree = cfg.install_tree_fstree(target_build, 'glibc')
    # Headers must be unified for each sysroot headers suffix, so are
    # handled separately.
    tree = FSTreeRemove(tree, ['usr/include'])
    sysroot_rel = multilib.sysroot_rel
    tree = FSTreeMove(tree, sysroot_rel)
    # Ensure lib directories exist so that GCC's use of paths such
    # as lib/../lib64 works.
    tree_lib = FSTreeMove(FSTreeEmpty(cfg.context),
                          os.path.join(sysroot_rel, 'lib'))
    tree_usr_lib = FSTreeMove(FSTreeEmpty(cfg.context),
                              os.path.join(sysroot_rel, 'usr', 'lib'))
    tree = FSTreeUnion(tree, tree_lib)
    tree = FSTreeUnion(tree, tree_usr_lib)
    if is_build:
        host_group.contribute_implicit_install(host_b, 'toolchain-2-before',
                                               tree)
        host_group.contribute_implicit_install(host_b, 'toolchain-2', tree)
    host_group.contribute_package(host, tree)


def _contribute_headers_tree(cfg, host, component, host_group, is_build):
    """Contribute the glibc headers to all required install trees."""
    host_b = host.build_cfg
    # Most glibc headers should be the same between multilibs, but
    # some headers (gnu/stubs.h, gnu/lib-names.h) are set up to have
    # per-ABI conditionals and include per-ABI header variants that
    # are only installed for glibc built for that ABI.  Thus, form a
    # union of all the headers for multilibs using a given headers
    # suffix, allowing duplicate files.  (Normally there should be
    # just one headers suffix for all glibc multilibs, since it isn't
    # useful to have more than one such suffix, given headers that
    # properly support all ABIs.)
    headers_trees = collections.defaultdict(lambda: FSTreeEmpty(cfg.context))
    for multilib in cfg.multilibs.get():
        if multilib.libc is component:
            tree = cfg.install_tree_fstree(multilib.build_cfg, 'glibc')
            tree = FSTreeExtract(tree, ['usr/include'])
            headers_trees[multilib.headers_rel] = FSTreeUnion(
                headers_trees[multilib.headers_rel], tree, True)
    for headers_rel, tree in sorted(headers_trees.items()):
        tree = FSTreeMove(tree, headers_rel)
        if is_build:
            host_group.contribute_implicit_install(host_b,
                                                   'toolchain-2-before', tree)
            host_group.contribute_implicit_install(host_b, 'toolchain-2', tree)
        host_group.contribute_package(host, tree)


class Component(sourcery.component.Component):
    """sourcery-builder glibc component implementation."""

    @staticmethod
    def add_release_config_vars(group):
        group.source_type.set_implicit('open')

    @staticmethod
    def add_dependencies(relcfg):
        relcfg.add_component('toolchain')

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

    sysrooted_libc = True

    @staticmethod
    def add_build_tasks_for_first_host(cfg, host, component, host_group):
        _contribute_headers_tree(cfg, host, component, host_group, True)

    @staticmethod
    def add_build_tasks_for_other_hosts(cfg, host, component, host_group):
        _contribute_headers_tree(cfg, host, component, host_group, False)

    @staticmethod
    def add_build_tasks_for_first_host_multilib(cfg, host, component,
                                                host_group, multilib):
        if multilib.libc is not component:
            return
        host_b = host.build_cfg
        inst_1 = cfg.install_tree_path(host_b, 'toolchain-1')
        bindir_1 = os.path.join(inst_1, cfg.bindir_rel.get())
        target_build = multilib.build_cfg
        srcdir = component.vars.srcdir.get()
        objdir = cfg.objdir_path(target_build, 'glibc')
        instdir = cfg.install_tree_path(target_build, 'glibc')
        group = BuildTask(cfg, host_group, 'glibc-%s' % target_build.name)
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
        _contribute_sysroot_tree(cfg, host, host_group, True, multilib)

    @staticmethod
    def add_build_tasks_for_other_hosts_multilib(cfg, host, component,
                                                 host_group, multilib):
        if multilib.libc is not component:
            return
        _contribute_sysroot_tree(cfg, host, host_group, False, multilib)
