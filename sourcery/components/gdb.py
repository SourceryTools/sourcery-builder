# sourcery-builder gdb component.

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

"""sourcery-builder gdb component."""

from sourcery.autoconf import add_host_tool_cfg_build_tasks
import sourcery.component
from sourcery.fstree import FSTreeRemove

__all__ = ['Component']


class Component(sourcery.component.Component):
    """sourcery-builder gdb component implementation."""

    @staticmethod
    def add_release_config_vars(group):
        group.source_type.set_implicit('open')

    @staticmethod
    def add_dependencies(relcfg):
        relcfg.add_component('expat')
        if any(host.build_cfg.use_libiconv() for host in relcfg.hosts.get()):
            relcfg.add_component('libiconv')
        if any(host.build_cfg.use_ncurses() for host in relcfg.hosts.get()):
            relcfg.add_component('ncurses')

    @staticmethod
    def add_build_tasks_for_host(cfg, host, component, host_group):
        host_b = host.build_cfg
        group = add_host_tool_cfg_build_tasks(cfg, host_b, component,
                                              host_group)
        group.depend_install(host_b, 'expat')
        if host_b.use_libiconv():
            group.depend_install(host_b, 'libiconv')
        if host_b.use_ncurses():
            group.depend_install(host_b, 'ncurses')
        # Not all versions of GDB use MPFR, but depend on the install
        # tree anyway (and on that for GMP) if present in the
        # toolchain, even if it might only be used by GCC.
        if cfg.have_component('mpfr'):
            group.depend_install(host_b, 'gmp')
            group.depend_install(host_b, 'mpfr')
        extra_paths = Component.get_extra_host_lib_paths(cfg, host_b)
        if extra_paths:
            # CPPFLAGS has to be passed in the environment because it
            # is not passed down to subdirectory configure scripts
            # when passed on the configure command line.
            group.env_set('CPPFLAGS',
                          (' '.join('-I%s/include' % path
                                    for path in extra_paths)))
        tree = cfg.install_tree_fstree(host_b, 'gdb')
        # Remove the info directory installed by various packages, and
        # files installed by shared directories for both binutils and
        # GDB.
        installdir_rel = cfg.installdir_rel.get()
        tree = FSTreeRemove(
            tree,
            [cfg.info_dir_rel.get(),
             '%s/share/info/bfd.info*' % installdir_rel,
             '%s/share/locale/*/*/bfd.mo' % installdir_rel,
             '%s/share/locale/*/*/opcodes.mo' % installdir_rel])
        host_group.contribute_package(host, tree)

    @staticmethod
    def get_extra_host_lib_paths(cfg, host):
        """Return the install tree paths for extra host libraries to use.

        These are paths for libraries without corresponding configure
        options (ncurses, and GMP as a dependency of MPFR), which thus
        need to be included in CPPFLAGS and LDFLAGS.

        """
        extra_paths = []
        if cfg.have_component('mpfr'):
            extra_paths.append(cfg.install_tree_path(host, 'gmp'))
        if host.use_ncurses():
            extra_paths.append(cfg.install_tree_path(host, 'ncurses'))
        return extra_paths

    @staticmethod
    def configure_opts(cfg, host):
        # Avoid building binutils when using a checkout that has both.
        opts = ['--disable-binutils', '--disable-elfcpp', '--disable-gas',
                '--disable-gold', '--disable-gprof', '--disable-ld',
                '--with-libexpat-prefix=%s'
                % cfg.install_tree_path(host, 'expat')]
        if host.use_libiconv():
            opts.append('--with-libiconv-prefix=%s'
                        % cfg.install_tree_path(host, 'libiconv'))
        if cfg.have_component('mpfr'):
            opts.append('--with-libmpfr-prefix=%s'
                        % cfg.install_tree_path(host, 'mpfr'))
        extra_paths = Component.get_extra_host_lib_paths(cfg, host)
        if extra_paths:
            opts.append('LDFLAGS=%s' % (' '.join('-L%s/lib' % path
                                                 for path in extra_paths)))
        return opts
