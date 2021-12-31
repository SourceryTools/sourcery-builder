# sourcery-builder glibc component.

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

"""sourcery-builder glibc component."""

import collections
import os.path
import shlex

from sourcery.buildtask import BuildTask
import sourcery.component
from sourcery.fstree import FSTree, FSTreeEmpty, FSTreeMove, FSTreeRemove, \
    FSTreeExtract, FSTreeUnion
from sourcery.makefile import Makefile

__all__ = ['Component']


_SYSROOT_SHARED_PATHS = ('etc', 'usr/share', 'var')


class _FSTreeLocale(FSTree):
    """An _FSTreeLocale is like an FSTreeExtractOne, but the path
    extracted depends on the endianness of a multilib so cannot be
    determined at the time the _FSTreeLocale is created.

    """

    def __init__(self, other, multilib, bindir):
        """Initialize an _FSTreeLocale object."""
        self.context = other.context
        self.other = other
        self.install_trees = other.install_trees
        self.multilib = multilib
        self.bindir = bindir

    def export_map(self):
        endian = self.multilib.build_cfg.get_endianness(
            path_prepend=self.bindir)
        return self.other.export_map().extract_one(endian)


def _contribute_sysroot_tree(cfg, host, host_group, is_build, multilib):
    """Contribute the glibc installation to all required install trees."""
    host_b = host.build_cfg
    target_build = multilib.build_cfg
    tree = cfg.install_tree_fstree(target_build, 'glibc')
    # Copy or move executables to locations that do not conflict
    # between sysroots.
    tree = multilib.move_sysroot_executables(tree, ('sbin', 'usr/bin',
                                                    'usr/sbin',
                                                    'usr/libexec/getconf'))
    # Ensure lib directories exist so that GCC's use of paths such
    # as lib/../lib64 works.
    tree_lib = FSTreeMove(FSTreeEmpty(cfg.context), 'lib')
    tree_usr_lib = FSTreeMove(FSTreeEmpty(cfg.context), 'usr/lib')
    tree = FSTreeUnion(tree, tree_lib)
    tree = FSTreeUnion(tree, tree_usr_lib)
    # Some files are shared between multilibs sharing a sysroot, so
    # are handled separately.
    tree = FSTreeRemove(tree, _SYSROOT_SHARED_PATHS)
    # Headers must be unified for each sysroot headers suffix, so are
    # handled separately.
    tree = FSTreeRemove(tree, ['usr/include'])
    # Move the tree to its final location.
    tree = FSTreeMove(tree, multilib.sysroot_rel)
    if is_build:
        host_group.contribute_implicit_install(host_b, 'toolchain-2-before',
                                               tree)
        host_group.contribute_implicit_install(host_b, 'toolchain-2', tree)
    host_group.contribute_package(host, tree)


def _contribute_shared_tree(cfg, host, component, host_group, is_build):
    """Contribute sysroot-shared files to all required install trees.

    This is for files that are identical between multilibs sharing a
    sysroot, so should be unified between such multilibs (duplicates
    allowed).

    """
    build_b = cfg.build.get().build_cfg
    host_b = host.build_cfg
    inst_1 = cfg.install_tree_path(build_b, 'toolchain-1')
    bindir_1 = os.path.join(inst_1, cfg.bindir_rel.get())
    tree = FSTreeEmpty(cfg.context)
    for multilib in cfg.multilibs.get():
        if multilib.libc is component:
            this_tree = cfg.install_tree_fstree(multilib.build_cfg, 'glibc')
            this_tree = FSTreeExtract(this_tree, _SYSROOT_SHARED_PATHS)
            locales_tree = cfg.install_tree_fstree(build_b, 'glibc-locales')
            locale_tree = _FSTreeLocale(locales_tree, multilib, bindir_1)
            this_tree = FSTreeUnion(this_tree, locale_tree)
            this_tree = FSTreeMove(this_tree, multilib.sysroot_rel)
            tree = FSTreeUnion(tree, this_tree, True)
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


def _generate_locales_makefile(cfg, component, srcdir, objdir, objdir2,
                               instdir):
    """Generate a makefile to use to generate locales."""
    # Generating locales requires knowing the endiannesses used by
    # locales, so we generate a makefile after the first compiler and
    # glibc have been built, and use that makefile to build locales
    # for the required endiannesses.
    build_b = cfg.build.get().build_cfg
    inst_1 = cfg.install_tree_path(build_b, 'toolchain-1')
    bindir_1 = os.path.join(inst_1, cfg.bindir_rel.get())
    endians = {m.build_cfg.get_endianness(path_prepend=bindir_1)
               for m in cfg.multilibs.get() if m.libc is component}
    makefile = Makefile(cfg.context, 'all')
    for endian in endians:
        makefile.add_target(endian)
    makefile.add_deps('all', endians)
    for endian in endians:
        localedef_list = ['%s/testrun.sh' % objdir,
                          '%s/locale/localedef' % objdir,
                          '--%s-endian' % endian,
                          '--no-archive']
        localedef_cmd = ' '.join(localedef_list)
        make_args = ['install_root=%s/%s' % (instdir, endian),
                     'LOCALEDEF=%s' % localedef_cmd,
                     'localedata/install-locales']
        make_cmd = '$(MAKE) %s' % ' '.join([shlex.quote(s) for s in make_args])
        make_cmd = ('cd %s && I18NPATH=%s/localedata %s'
                    % (objdir, srcdir, make_cmd))
        makefile.add_command(endian, make_cmd)
    makefile_text = makefile.makefile_text()
    makefile_name = os.path.join(objdir2, 'GNUmakefile')
    with open(makefile_name, 'w', encoding='utf-8') as file:
        file.write(makefile_text)


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
        _contribute_shared_tree(cfg, host, component, host_group, True)
        # Build glibc for the build system, and use its localedef to
        # build locales.  The normal glibc configure options are not
        # used for this (they may only be appropriate for the target),
        # so the common support for autoconf-based components isn't
        # used either.
        host_b = host.build_cfg
        srcdir = component.vars.srcdir.get()
        objdir = cfg.objdir_path(host_b, 'glibc-host')
        group = BuildTask(cfg, host_group, 'glibc-host')
        init_task = BuildTask(cfg, group, 'init')
        init_task.add_empty_dir(objdir)
        cfg_task = BuildTask(cfg, group, 'configure')
        cfg_cmd = [os.path.join(srcdir, 'configure'),
                   '--build=%s' % host_b.triplet,
                   '--host=%s' % host_b.triplet,
                   '--prefix=/usr']
        cfg_cmd.extend(host_b.configure_vars())
        cfg_cmd.append('BUILD_CC=%s'
                       % ' '.join(host_b.tool('c-compiler')))
        cfg_task.add_command(cfg_cmd, cwd=objdir)
        build_task = BuildTask(cfg, group, 'build')
        build_task.add_make([], objdir)
        group = BuildTask(cfg, host_group, 'glibc-locales')
        group.depend('/%s/glibc-host' % host.name)
        # Building the host glibc itself does not depend on the target
        # compiler.  Building the locales does depend on the target
        # compiler (but not on the target libc), as it is used to
        # determine the endianness of each locale.
        group.depend_install(host_b, 'toolchain-1')
        group.provide_install(host_b, 'glibc-locales')
        objdir2 = cfg.objdir_path(host_b, 'glibc-locales')
        instdir = cfg.install_tree_path(host_b, 'glibc-locales')
        init_task = BuildTask(cfg, group, 'init')
        init_task.add_empty_dir(objdir2)
        init_task.add_empty_dir(instdir)
        build_task = BuildTask(cfg, group, 'build')
        build_task.add_python(_generate_locales_makefile,
                              (cfg, component, srcdir, objdir, objdir2,
                               instdir))
        build_task.add_make([], objdir2)

    @staticmethod
    def add_build_tasks_for_other_hosts(cfg, host, component, host_group):
        _contribute_headers_tree(cfg, host, component, host_group, False)
        _contribute_shared_tree(cfg, host, component, host_group, False)

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
