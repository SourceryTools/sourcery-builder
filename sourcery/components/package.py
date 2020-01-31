# sourcery-builder package component.

# Copyright 2018-2020 Mentor Graphics Corporation.

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

"""sourcery-builder package component."""

import os.path

from sourcery.buildtask import BuildTask
import sourcery.component
from sourcery.package import fix_perms, hard_link_files, replace_symlinks, \
    tar_command

__all__ = ['Component']


class Component(sourcery.component.Component):
    """sourcery-builder package component implementation."""

    @staticmethod
    def add_release_config_vars(group):
        group.source_type.set_implicit('none')

    @staticmethod
    def add_build_tasks_for_host(cfg, host, component, host_group):
        # The package-input install tree is contributed to by each
        # component that installs files intended to go in the final
        # release package.  This is an install tree for a PkgHost, not
        # for a BuildCfg.  This install tree is then subject to global
        # manipulations (such as hard-linking identical files,
        # replacing symlinks by hard links on hosts not supporting
        # symlinks, and stripping binaries) to produce the
        # package-output tree that corresponds to the exact data for
        # the release package.  Most manipulations, such as moving
        # files to different locations or removing files that are
        # installed by default but should not go in the final release
        # packages, should be done at the level of the individual
        # components; only a few manipulations are most appropriately
        # done globally just before packaging.
        host_group.declare_implicit_install(host, 'package-input')
        pkg_out_task = BuildTask(cfg, host_group, 'package-output')
        pkg_out_task.depend_install(host, 'package-input')
        pkg_out_task.provide_install(host, 'package-output')
        inst_in_path = cfg.install_tree_path(host, 'package-input')
        inst_out_path = cfg.install_tree_path(host, 'package-output')
        pkg_out_task.add_empty_dir_parent(inst_out_path)
        pkg_out_task.add_command(['cp', '-a', inst_in_path, inst_out_path])
        # The top-level directory in a package corresponds to the
        # contents of installdir.  In degenerate cases of nothing in a
        # package, installdir may not have been created (although the
        # package-input tree will always have been created, even if
        # empty).
        inst_out_main = os.path.join(inst_out_path, cfg.installdir_rel.get())
        pkg_out_task.add_create_dir(inst_out_main)
        if not host.have_symlinks():
            pkg_out_task.add_python(replace_symlinks,
                                    (cfg.context, inst_out_main))
        pkg_out_task.add_python(fix_perms, (inst_out_main,))
        pkg_out_task.add_python(hard_link_files, (cfg.context, inst_out_main))
        # Creating the package-output install tree is separated from
        # creating a .tar.xz package from it so that .tar.xz creation
        # can run in parallel with other package format creation using
        # the same tree.
        pkg_task = BuildTask(cfg, host_group, 'package-tar-xz')
        pkg_task.depend_install(host, 'package-output')
        pkg_path = cfg.pkgdir_path(host, '.tar.xz')
        pkg_task.add_command(tar_command(
            pkg_path, cfg.pkg_name_no_target_build.get(),
            cfg.source_date_epoch.get()),
                                 cwd=inst_out_main)

    @staticmethod
    def add_build_tasks_init(cfg, component, init_group):
        pkgdir_task = BuildTask(cfg, init_group, 'pkgdir')
        pkgdir_task.add_create_dir(cfg.args.pkgdir)
        if not cfg.args.build_source_packages:
            return
        # Component sources are copied in an init task to ensure that
        # source packages contain the sources at the start of the
        # build, even if a bug in a component's build process
        # (e.g. missing or insufficient configuration of files to
        # touch on checkout) results in the source directory being
        # modified during the build.  If a component's build process
        # is known to modify the source directory intentionally, that
        # component's build tasks must create a separate copy for use
        # in the build.
        source_copy_group = BuildTask(cfg, init_group, 'source-copy', True)
        objdir = cfg.objdir_path(None, 'source-copy')
        for src_component in cfg.list_source_components():
            name = src_component.copy_name
            srcdir = src_component.vars.srcdir.get()
            srcdir_copy = os.path.join(objdir, name)
            copy_task = BuildTask(cfg, source_copy_group, name)
            copy_task.add_empty_dir_parent(srcdir_copy)
            copy_task.add_python(
                src_component.vars.vc.get().copy_without_metadata,
                (srcdir, srcdir_copy))

    @staticmethod
    def add_build_tasks_host_indep(cfg, component, host_indep_group):
        if not cfg.args.build_source_packages:
            return
        # The source package has the sources of open source
        # components; the backup package has the sources of closed
        # source components.
        source_group = BuildTask(cfg, host_indep_group, 'source-package')
        source_objdir = cfg.objdir_path(None, 'source-package')
        source_init_task = BuildTask(cfg, source_group, 'init')
        source_init_task.add_empty_dir(source_objdir)
        source_components_group = BuildTask(cfg, source_group, 'components',
                                            True)
        source_package_task = BuildTask(cfg, source_group, 'package')
        source_pkg_path = cfg.pkgdir_path(None, '.src.tar.xz')
        source_package_task.add_command(tar_command(
            source_pkg_path, cfg.pkg_name_full.get(),
            cfg.source_date_epoch.get()),
                                        cwd=source_objdir)
        backup_group = BuildTask(cfg, host_indep_group, 'backup-package')
        backup_objdir = cfg.objdir_path(None, 'backup-package')
        backup_init_task = BuildTask(cfg, backup_group, 'init')
        backup_init_task.add_empty_dir(backup_objdir)
        backup_components_group = BuildTask(cfg, backup_group, 'components',
                                            True)
        backup_package_task = BuildTask(cfg, backup_group, 'package')
        backup_pkg_path = cfg.pkgdir_path(None, '.backup.tar.xz')
        backup_package_task.add_command(tar_command(
            backup_pkg_path, '%s.backup' % cfg.pkg_name_full.get(),
            cfg.source_date_epoch.get()),
                                        cwd=backup_objdir)
        copy_objdir = cfg.objdir_path(None, 'source-copy')
        for src_component in cfg.list_source_components():
            name = src_component.copy_name
            srcdir_copy = os.path.join(copy_objdir, name)
            if src_component.vars.source_type.get() == 'open':
                group = source_components_group
                objdir = source_objdir
            else:
                group = backup_components_group
                objdir = backup_objdir
            task = BuildTask(cfg, group, name)
            pkg_dir = '%s-%s' % (name, cfg.version.get())
            pkg_path = os.path.join(objdir, '%s.tar.xz' % pkg_dir)
            task.add_command(tar_command(pkg_path, pkg_dir,
                                         cfg.source_date_epoch.get()),
                             cwd=srcdir_copy)
