# sourcery-builder package component.

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

"""sourcery-builder package component."""

import os.path

from sourcery.buildtask import BuildTask
import sourcery.component
from sourcery.package import fix_perms, hard_link_files, tar_command

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
        task = BuildTask(cfg, host_group, 'package')
        task.depend_install(host, 'package-input')
        inst_in_path = cfg.install_tree_path(host, 'package-input')
        inst_out_path = cfg.install_tree_path(host, 'package-output')
        task.add_empty_dir_parent(inst_out_path)
        task.add_command(['cp', '-a', inst_in_path, inst_out_path])
        # The top-level directory in a package corresponds to the
        # contents of installdir.  In degenerate cases of nothing in a
        # package, installdir may not have been created (although the
        # package-input tree will always have been created, even if
        # empty).
        inst_out_main = os.path.join(inst_out_path, cfg.installdir_rel.get())
        task.add_create_dir(inst_out_main)
        task.add_python(fix_perms, (inst_out_main,))
        task.add_python(hard_link_files, (cfg.context, inst_out_main))
        task.add_create_dir(cfg.args.pkgdir)
        pkg_path = cfg.pkgdir_path(host, '.tar.xz')
        task.add_command(tar_command(pkg_path,
                                     cfg.pkg_name_no_target_build.get(),
                                     cfg.source_date_epoch.get()),
                         cwd=inst_out_main)
