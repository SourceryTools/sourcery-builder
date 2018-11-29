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

import sourcery.component

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
