# Support multilibs.

# Copyright 2019 Mentor Graphics Corporation.

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

"""Support multilibs."""

import os.path

from sourcery.buildcfg import BuildCfg

__all__ = ['Multilib']


class Multilib:
    """A Multilib describes how target code is built and packaged.

    Multilib objects are related to BuildCfg objects.  BuildCfg
    objects describe how both host and target code is built; Multilib
    objects only relate to target code (code for which the
    corresponding compiler is included in the toolchain).  A Multilib
    object describes directory arrangements for packaging the code, in
    addition to how to build it.  A Multilib object has a
    corresponding BuildCfg, but using such a BuildCfg depends on a
    directory or install tree containing the compiler to be used being
    available; as there is more than one build of a compiler in
    general when bootstrapping a toolchain for cross-compilation, such
    a BuildCfg cannot be used without that extra information.

    """

    def __init__(self, context, compiler, libc, ccopts, sysroot_suffix=None,
                 headers_suffix=None, sysroot_osdir=None, osdir=None,
                 target=None):
        """Initialize a Multilib object.

        Initialization saves various information in the object; a
        subsequent finalization step, to which the release config is
        passed, is also required to avoid ordering issues in release
        configs (for example, so the default target setting can be
        that of the release config, without requiring the release
        config to set the target before setting multilibs).

        The compiler and libc specified are component names (component
        copy names, if there are multiple instances of the same
        component present, such as for offloading compilers).  The
        libc may be specified as None, if this multilib uses
        externally built libraries (e.g., if it is configured to use
        the system libraries for a native compiler); compiler
        libraries are still built in that case.  ccopts is a list or
        tuple of compiler options used to build code for this
        multilib.  sysroot_suffix is a relative directory name for the
        sysroot subdirectory for this multilib, '.' for the top-level
        sysroot directory or None for non-sysrooted libc
        implementations; the same applies to headers_suffix; for
        sysrooted libc implementations, None is replaced by '.'.
        sysroot_osdir gives the name of the library directory relative
        to 'lib' inside a sysroot, while osdir gives the corresponding
        name outside a sysroot (that is, the output of
        -print-multi-os-directory); these may be '.' (the default,
        when applicable), or names such as '../lib64'; the default for
        osdir is the concatenation of sysroot_osdir and sysroot_suffix
        if those are specified.  The target specified is the GNU
        triplet to be used as a configured host for code built for
        this multilib; the default is the target for the specified
        compiler.

        """
        self.context = context
        self._save_compiler = compiler
        self._save_libc = libc
        if isinstance(ccopts, str):
            context.error('ccopts must be a list of strings, not a single '
                          'string')
        self.ccopts = tuple(ccopts)
        self._save_sysroot_suffix = sysroot_suffix
        self._save_headers_suffix = headers_suffix
        self._save_sysroot_osdir = sysroot_osdir
        self._save_osdir = osdir
        self._save_target = target
        self._finalized = False
        # These are ComponentInConfig objects after finalization.
        self.compiler = None
        self.libc = None
        # These are set at finalization, with defaults depending on
        # properties of the config and the compiler and libc
        # components.
        self.sysroot_suffix = None
        self.headers_suffix = None
        self.sysroot_osdir = None
        self.osdir = None
        self.target = None
        self.build_cfg = None

    def finalize(self, relcfg):
        """Finalize this Multilib for use with the given release config."""
        if self._finalized:
            self.context.error('multilib already finalized')
        self._finalized = True
        self.compiler = relcfg.get_component(self._save_compiler)
        if self._save_libc is not None:
            self.libc = relcfg.get_component(self._save_libc)
            sysrooted = self.libc.cls.sysrooted_libc
        else:
            sysrooted = self._save_sysroot_suffix is not None
        if sysrooted:
            self.sysroot_suffix = ('.'
                                   if self._save_sysroot_suffix is None
                                   else self._save_sysroot_suffix)
            self.headers_suffix = ('.'
                                   if self._save_headers_suffix is None
                                   else self._save_headers_suffix)
            self.sysroot_osdir = ('.'
                                  if self._save_sysroot_osdir is None
                                  else self._save_sysroot_osdir)
        else:
            if self._save_sysroot_suffix is not None:
                self.context.error('sysroot suffix for non-sysrooted libc')
            self.sysroot_suffix = None
            if self._save_headers_suffix is not None:
                self.context.error('headers suffix for non-sysrooted libc')
            self.headers_suffix = None
            if self._save_sysroot_osdir is not None:
                self.context.error('sysroot osdir for non-sysrooted libc')
            self.sysroot_osdir = None
        if self._save_osdir is not None:
            self.osdir = self._save_osdir
        elif sysrooted:
            self.osdir = os.path.normpath(os.path.join(self.sysroot_osdir,
                                                       self.sysroot_suffix))
        else:
            self.osdir = '.'
        self.target = (self._save_target
                       if self._save_target is not None
                       else relcfg.target.get())
        tool_prefix = '%s-' % relcfg.target.get()
        self.build_cfg = BuildCfg(self.context, self.target,
                                  tool_prefix=tool_prefix, ccopts=self.ccopts)
