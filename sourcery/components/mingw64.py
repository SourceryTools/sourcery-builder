# sourcery-builder mingw64 component.

# Copyright 2019-2021 Mentor Graphics Corporation.

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

"""sourcery-builder mingw64 component."""

import os.path

from sourcery.autoconf import add_host_cfg_build_tasks
import sourcery.component
from sourcery.fstree import FSTreeEmpty, FSTreeSymlink, FSTreeMove, \
    FSTreeRemove, FSTreeExtract, FSTreeUnion

__all__ = ['Component']


def _first_mingw64_multilib(cfg, component):
    """Return the first mingw64 multilib in this config, if any."""
    for multilib in cfg.multilibs.get():
        if multilib.libc is component:
            return multilib
    return None


def _contribute_crt_tree(cfg, host, component, host_group, is_build):
    """Contribute the mingw-w64-crt installation to all required install
    trees."""
    # Most files are separate for each multilib, but there is a
    # <target>/<include> directory with some .c files that are present
    # for each multilib.
    host_b = host.build_cfg
    installdir_rel = cfg.installdir_rel.get()
    target = cfg.target.get()
    include_rel = '%s/%s/include' % (installdir_rel, target)
    tree = FSTreeEmpty(cfg.context)
    tree_headers = FSTreeEmpty(cfg.context)
    for multilib in cfg.multilibs.get():
        if multilib.libc is component:
            target_build = multilib.build_cfg
            this_tree = cfg.install_tree_fstree(target_build,
                                                'mingw64-crt-%s'
                                                % target_build.name)
            this_headers = FSTreeExtract(this_tree, [include_rel])
            this_tree = FSTreeRemove(this_tree, [include_rel])
            tree = FSTreeUnion(tree, this_tree)
            tree_headers = FSTreeUnion(tree_headers, this_headers, True)
    tree = FSTreeUnion(tree, tree_headers)
    if is_build:
        host_group.contribute_implicit_install(host_b, 'toolchain-2-before',
                                               tree)
        host_group.contribute_implicit_install(host_b, 'toolchain-2', tree)
    host_group.contribute_package(host, tree)


class Component(sourcery.component.Component):
    """sourcery-builder mingw64 component implementation."""

    @staticmethod
    def add_release_config_vars(group):
        group.source_type.set_implicit('open')

    @staticmethod
    def add_dependencies(relcfg):
        relcfg.add_component('toolchain')

    @staticmethod
    def add_build_tasks_for_first_host(cfg, host, component, host_group):
        # Install headers.  This is run only for the first mingw64
        # multilib.
        host_b = host.build_cfg
        multilib = _first_mingw64_multilib(cfg, component)
        if multilib is None:
            return
        multilib_b = multilib.build_cfg
        installdir = cfg.installdir.get()
        installdir_rel = cfg.installdir_rel.get()
        target = cfg.target.get()
        prefix = os.path.join(installdir, target)
        srcdir = component.vars.srcdir.get()
        add_host_cfg_build_tasks(cfg, multilib_b, component, host_group,
                                 'mingw64-headers',
                                 os.path.join(srcdir, 'mingw-w64-headers'),
                                 prefix, (), None, None, 'install', True)
        tree = cfg.install_tree_fstree(multilib_b, 'mingw64-headers')
        # Unlike for some target OSes, libgcc files for Windows target
        # do not have inhibit_libc conditionals and thus the library
        # headers are needed before the first compiler is built.
        host_group.contribute_implicit_install(host_b, 'toolchain-1-before',
                                               tree)
        host_group.contribute_implicit_install(host_b, 'toolchain-1', tree)
        host_group.contribute_implicit_install(host_b, 'toolchain-2-before',
                                               tree)
        host_group.contribute_implicit_install(host_b, 'toolchain-2', tree)
        host_group.contribute_package(host, tree)
        # A symlink mingw -> . is needed for configuring GCC using
        # --with-build-sysroot to enable headers and libraries to be
        # found when not installed at the configured prefix.
        tree_link = FSTreeSymlink(cfg.context, '.')
        tree_link = FSTreeMove(tree_link, os.path.join(installdir_rel, target,
                                                       'mingw'))
        host_group.contribute_implicit_install(host_b, 'toolchain-1-before',
                                               tree_link)
        host_group.contribute_implicit_install(host_b, 'toolchain-2-before',
                                               tree_link)
        # This is needed for toolchain-2 because that install tree is
        # used with --with-build-sysroot for hosts other than the
        # first, and although target libraries are not built in that
        # case, the specified directory is still used by fixincludes
        # fixing headers for that host.
        host_group.contribute_implicit_install(host_b, 'toolchain-2',
                                               tree_link)
        _contribute_crt_tree(cfg, host, component, host_group, True)

    @staticmethod
    def add_build_tasks_for_other_hosts(cfg, host, component, host_group):
        multilib = _first_mingw64_multilib(cfg, component)
        if multilib is None:
            return
        multilib_b = multilib.build_cfg
        tree = cfg.install_tree_fstree(multilib_b, 'mingw64-headers')
        host_group.contribute_package(host, tree)
        _contribute_crt_tree(cfg, host, component, host_group, False)

    @staticmethod
    def add_build_tasks_for_first_host_multilib(cfg, host, component,
                                                host_group, multilib):
        if multilib.libc is not component:
            return
        host_b = host.build_cfg
        inst_1 = cfg.install_tree_path(host_b, 'toolchain-1')
        bindir_1 = os.path.join(inst_1, cfg.bindir_rel.get())
        target_build = multilib.build_cfg
        target = cfg.target.get()
        if target.startswith('x86_64'):
            disable_arg = ('--disable-lib64'
                           if '-m32' in target_build.tool('c-compiler')
                           else '--disable-lib32')
        else:
            disable_arg = ('--disable-lib32'
                           if '-m64' in target_build.tool('c-compiler')
                           else '--disable-lib64')
        installdir = cfg.installdir.get()
        prefix = os.path.join(installdir, target)
        srcdir = component.vars.srcdir.get()
        crt_name = 'mingw64-crt-%s' % target_build.name
        group = add_host_cfg_build_tasks(cfg, target_build, component,
                                         host_group, crt_name,
                                         os.path.join(srcdir,
                                                      'mingw-w64-crt'),
                                         prefix, (disable_arg,), None, None,
                                         'install', True)
        group.depend_install(host_b, 'toolchain-1')
        group.env_prepend('PATH', bindir_1)
