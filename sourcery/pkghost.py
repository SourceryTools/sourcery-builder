# Support package hosts.

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

"""Support package hosts."""

from sourcery.buildcfg import BuildCfg

__all__ = ['PkgHost']


class PkgHost:
    """A PkgHost represents a host for which packages are built.

    Host code in such packages will typically be built with the tools
    for the corresponding BuildCfg (although in principle a PkgHost
    could have multiple BuildCfgs, used for different parts of the
    package, this is not currently supported).  Target code in such
    packages will typically be built with the tools for the BuildCfgs
    for the various target multilibs.  The set of packages built may
    depend on the host.  Each host in a configuration must have a
    different name.  In simple cases that name would typically be the
    GNU triplet for the host, but sometimes that is not possible (if
    e.g. there are tools built for both hard-float and soft-float
    configurations using the same triplet).

    """

    def __init__(self, context, name, build_cfg=None):
        """Initialize a PkgHost object.

        If only a name is specified, that is used as a GNU triplet to
        construct a corresponding BuildCfg.

        """
        self.context = context
        self.name = name
        if build_cfg is None:
            build_cfg = BuildCfg(context, name)
        self.build_cfg = build_cfg

    def __repr__(self):
        """Return a textual representation of a PkgHost object.

        The representation is in the form a PkgHost call might appear
        in a release config, omitting the context argument.

        """
        build_cfg_repr = repr(self.build_cfg)
        default_build_cfg_repr = 'BuildCfg(%s)' % repr(self.name)
        if build_cfg_repr == default_build_cfg_repr:
            return 'PkgHost(%s)' % repr(self.name)
        else:
            return 'PkgHost(%s, %s)' % (repr(self.name), build_cfg_repr)

    def have_symlinks(self):
        """Return whether packages for this host can use symlinks."""
        return not self.build_cfg.is_windows()
