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
from sourcery.fstree import FSTreeRemove, FSTreeExtract, FSTreeUnion

__all__ = ['Component']


class Component(sourcery.component.Component):
    """sourcery-builder gcc component implementation."""

    @staticmethod
    def add_release_config_vars(group):
        group.source_type.set_implicit('open')

    @staticmethod
    def add_dependencies(relcfg):
        relcfg.add_component('toolchain')
        if any(host.build_cfg.use_libiconv() for host in relcfg.hosts.get()):
            relcfg.add_component('libiconv')
        # Some older versions of GCC do not require GMP, MPFR and MPC,
        # but the build code here makes no allowance for such
        # versions, so add them as dependencies for now.
        relcfg.add_component('gmp')
        relcfg.add_component('mpfr')
        relcfg.add_component('mpc')

    @staticmethod
    def postcheckout(context, component):
        context.execute(['contrib/gcc_update', '--touch'],
                        cwd=component.vars.srcdir.get())

    @staticmethod
    def add_build_tasks_for_host(cfg, host, component, host_group):
        host_b = host.build_cfg
        build = cfg.build.get()
        build_b = build.build_cfg
        target = cfg.target.get()
        sysroot = cfg.sysroot.get()
        sysroot_rel = cfg.sysroot_rel.get()
        bindir_rel = cfg.bindir_rel.get()
        inst_1_before = cfg.install_tree_path(build_b, 'toolchain-1-before')
        build_sysroot_1 = os.path.join(inst_1_before, sysroot_rel)
        bindir_1 = os.path.join(inst_1_before, bindir_rel)
        # Building GCC for a host other than the build system, even
        # without building target libraries, requires GCC (configured
        # the same way) built for the build system, because the GCC
        # build runs the compiler for some purposes (e.g. with
        # -dumpspecs).
        toolchain_2_before = ('toolchain-2-before'
                              if host == build
                              else 'toolchain-2')
        inst_2_before = cfg.install_tree_path(build_b, toolchain_2_before)
        build_sysroot_2 = os.path.join(inst_2_before, sysroot_rel)
        bindir_2 = os.path.join(inst_2_before, bindir_rel)
        build_time_tools_1 = os.path.join(inst_1_before, target, 'bin')
        build_time_tools_2 = os.path.join(inst_2_before, target, 'bin')
        opts_first = ['--enable-languages=c',
                      '--disable-shared',
                      '--disable-threads',
                      '--without-headers', '--with-newlib',
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
        if cfg.have_component('glibc'):
            glibc_version_h = os.path.join(cfg.glibc.srcdir.get(), 'version.h')
            glibc_version = None
            with open(glibc_version_h, 'r', encoding='utf-8') as file:
                start = '#define VERSION "'
                for line in file:
                    if line.startswith(start):
                        line = line[len(start):].rstrip('"\n')
                        vers = line.split('.')
                        glibc_version = '.'.join(vers[0:2])
                        break
            if glibc_version is not None:
                opts_first.append('--with-glibc-version=%s' % glibc_version)
            else:
                cfg.context.error('could not determine glibc version')
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
            if host_b.use_libiconv():
                group.depend_install(host_b, 'libiconv')
            if cfg.have_component('isl'):
                group.depend_install(host_b, 'isl')
            group.depend_install(host_b, 'toolchain-1-before')
            group.env_prepend('PATH', bindir_1)
            tree = cfg.install_tree_fstree(host_b, 'gcc-first')
            tree = FSTreeRemove(tree, [cfg.info_dir_rel.get()])
            host_group.contribute_implicit_install(host_b, 'toolchain-1', tree)
            # The compiler is not needed in toolchain-2-before (which
            # is only used to build GCC for the build system).
        make_target = None if host == build else 'all-host'
        install_target = 'install' if host == build else 'install-host'
        group = add_host_tool_cfg_build_tasks(
            cfg, host_b, component, host_group, name='gcc',
            pkg_cfg_opts=opts_second, make_target=make_target,
            install_target=install_target)
        group.depend_install(host_b, 'gmp')
        group.depend_install(host_b, 'mpfr')
        group.depend_install(host_b, 'mpc')
        if host_b.use_libiconv():
            group.depend_install(host_b, 'libiconv')
        if cfg.have_component('isl'):
            group.depend_install(host_b, 'isl')
        group.depend_install(build_b, toolchain_2_before)
        group.env_prepend('PATH', bindir_2)
        tree = cfg.install_tree_fstree(host_b, 'gcc')
        tree = FSTreeRemove(tree, [cfg.info_dir_rel.get()])
        if host == build:
            host_group.contribute_implicit_install(host_b, 'toolchain-2', tree)
        if host != build:
            # Libraries built for the build system, and other files
            # installed with those libraries, are reused for other
            # hosts.  Headers in libsubdir/include are a special case:
            # some are installed from the gcc/ directory, so for all
            # hosts, while others are installed from library
            # directories, so only from the build system.  Thus,
            # extract the two sets of headers and form a union for
            # them allowing duplicates with identical contents.
            installdir_rel = cfg.installdir_rel.get()
            tree_build = cfg.install_tree_fstree(build_b, 'gcc')
            tree_libs = FSTreeExtract(
                tree_build,
                ['%s/%s/include/c++' % (installdir_rel, target),
                 '%s/%s/lib*' % (installdir_rel, target),
                 '%s/lib/gcc/%s/*' % (installdir_rel, target),
                 '%s/share/gcc-*' % installdir_rel,
                 '%s/share/info/lib*' % installdir_rel,
                 '%s/share/locale/*/*/lib*' % installdir_rel])
            tree_libs = FSTreeRemove(
                tree_libs,
                ['%s/lib/gcc/%s/*/include' % (installdir_rel, target),
                 '%s/lib/gcc/%s/*/include-fixed' % (installdir_rel, target),
                 '%s/lib/gcc/%s/*/install-tools' % (installdir_rel, target),
                 '%s/lib/gcc/%s/*/plugin' % (installdir_rel, target)])
            tree_libsubdir_include_build = FSTreeExtract(
                tree_build,
                ['%s/lib/gcc/%s/*/include' % (installdir_rel, target)])
            tree_libsubdir_include_host = FSTreeExtract(
                tree,
                ['%s/lib/gcc/%s/*/include' % (installdir_rel, target)])
            tree_libsubdir_include = FSTreeUnion(tree_libsubdir_include_build,
                                                 tree_libsubdir_include_host,
                                                 True)
            tree = FSTreeRemove(
                tree,
                ['%s/lib/gcc/%s/*/include' % (installdir_rel, target)])
            host_group.contribute_package(host, tree_libs)
            host_group.contribute_package(host, tree_libsubdir_include)
        host_group.contribute_package(host, tree)

    @staticmethod
    def configure_opts(cfg, host):
        opts = ['--disable-libssp',
                '--with-gmp=%s' % cfg.install_tree_path(host, 'gmp'),
                '--with-mpfr=%s' % cfg.install_tree_path(host, 'mpfr'),
                '--with-mpc=%s' % cfg.install_tree_path(host, 'mpc')]
        if host.use_libiconv():
            opts.append('--with-libiconv-prefix=%s'
                        % cfg.install_tree_path(host, 'libiconv'))
        if cfg.have_component('isl'):
            opts.append('--with-isl=%s' % cfg.install_tree_path(host, 'isl'))
        return opts
