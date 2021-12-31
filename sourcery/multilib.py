# Support multilibs.

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

"""Support multilibs."""

import os.path

from sourcery.buildcfg import BuildCfg
from sourcery.fstree import FSTreeEmpty, FSTreeMove, FSTreeRemove, \
    FSTreeExtractOne, FSTreeUnion

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

    def __init__(self, context, compiler, libc, ccopts, tool_opts=None,
                 sysroot_suffix=None, headers_suffix=None, sysroot_osdir=None,
                 osdir=None, target=None):
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
        multilib.  tool_opts maps the names of tools to options to
        pass to those tools, as in the corresponding BuildCfg
        argument.  sysroot_suffix is a relative directory name for the
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
        if tool_opts is not None:
            for val in tool_opts.values():
                if isinstance(val, str):
                    context.error('tool_opts values must be lists of '
                                  'strings, not single strings')
            tool_opts = {key: tuple(value)
                         for key, value in tool_opts.items()}
        self.tool_opts = tool_opts
        self._save_sysroot_suffix = sysroot_suffix
        self._save_headers_suffix = headers_suffix
        self._save_sysroot_osdir = sysroot_osdir
        self._save_osdir = osdir
        self._save_target = target
        self._finalized = False
        self._relcfg = None
        # These are ComponentInConfig objects after finalization.
        self.compiler = None
        self.libc = None
        # These are set at finalization, with defaults depending on
        # properties of the config and the compiler and libc
        # components.
        self.sysroot_suffix = None
        self.headers_suffix = None
        self.sysroot_rel = None
        self.headers_rel = None
        self.sysroot_osdir = None
        self.osdir = None
        self.target = None
        self.build_cfg = None

    def __repr__(self):
        """Return a textual representation of a Multilib object.

        The representation is in the form a Multilib call might appear
        in a release config, omitting the context argument.

        """
        ml_args = []
        ml_args.append(repr(self.compiler.copy_name))
        if self.libc is None:
            ml_args.append('None')
        else:
            ml_args.append(repr(self.libc.copy_name))
        ml_args.append(repr(self.ccopts))
        if self.tool_opts:
            ml_args.append('tool_opts={%s}'
                           % ', '.join('%s: %s' % (repr(key), repr(value))
                                       for key, value in sorted(
                                               self.tool_opts.items())))
        if self.sysroot_suffix is not None and (self.sysroot_suffix != '.'
                                                or self.libc is None):
            ml_args.append('sysroot_suffix=%s' % repr(self.sysroot_suffix))
        if self.headers_suffix is not None and self.headers_suffix != '.':
            ml_args.append('headers_suffix=%s' % repr(self.headers_suffix))
        if self.sysroot_osdir is not None and self.sysroot_osdir != '.':
            ml_args.append('sysroot_osdir=%s' % repr(self.sysroot_osdir))
        if self.osdir != self._default_osdir():
            ml_args.append('osdir=%s' % repr(self.osdir))
        if self.target != self._relcfg.target.get():
            ml_args.append('target=%s' % repr(self.target))
        return 'Multilib(%s)' % ', '.join(ml_args)

    def _default_osdir(self):
        """Return the default osdir setting for this Multilib."""
        if self.sysroot_suffix is not None:
            return os.path.normpath(os.path.join(self.sysroot_osdir,
                                                 self.sysroot_suffix))
        else:
            return '.'

    def finalize(self, relcfg):
        """Finalize this Multilib for use with the given release config."""
        if self._finalized:
            self.context.error('multilib already finalized')
        self._finalized = True
        self._relcfg = relcfg
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
            self.sysroot_rel = os.path.normpath(os.path.join(
                relcfg.sysroot_rel.get(), self.sysroot_suffix))
            self.headers_rel = os.path.normpath(os.path.join(
                relcfg.sysroot_rel.get(), self.headers_suffix))
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
            self.sysroot_rel = None
            self.headers_rel = None
        if self._save_osdir is not None:
            self.osdir = self._save_osdir
        else:
            self.osdir = self._default_osdir()
        self.target = (self._save_target
                       if self._save_target is not None
                       else relcfg.target.get())
        tool_prefix = '%s-' % relcfg.target.get()
        self.build_cfg = BuildCfg(self.context, self.target,
                                  tool_prefix=tool_prefix, ccopts=self.ccopts,
                                  tool_opts=self.tool_opts)

    def move_sysroot_executables(self, tree, dirs):
        """Move executables to a per-multilib directory such as usr/lib/bin.

        This is for the case where a sysroot is shared between
        multilibs, and so different multilibs have different library
        directories such as usr/lib and usr/lib64, but executables go
        in the same directory such as usr/bin for all multilibs.  To
        avoid conflicts between files for different multilibs, those
        executables are moved to per-multilib directories such as
        usr/lib/bin (this is an arrangement for packaging, with users
        of the sysroot expected to copy the preferred version of a
        binary back into directories such as usr/bin).  For user
        convenience, copies of the files are left in their original
        directories if there is only one multilib in the sysroot.

        dirs is a list of directories in the sysroot from which files
        are to be moved or copied.  tree is an FSTree for the sysroot;
        dir_src must exist therein.  An FSTree is returned; the
        directories in dirs still exist there, but may be empty.

        """
        if self.sysroot_suffix is None:
            self.context.error('move_sysroot_executables called for '
                               'non-sysroot multilib')
        if isinstance(dirs, str):
            self.context.error('dirs must be a list of strings, not a single '
                               'string')
        dir_dst = os.path.normpath(os.path.join('usr/lib', self.sysroot_osdir,
                                                'bin'))
        num_multilibs = len([m for m in self._relcfg.multilibs.get()
                             if m.sysroot_suffix == self.sysroot_suffix])
        for dir_src in dirs:
            tree_src = FSTreeExtractOne(tree, dir_src)
            tree_moved = FSTreeMove(tree_src, dir_dst)
            if num_multilibs > 1:
                tree = FSTreeRemove(tree, [dir_src])
            tree = FSTreeUnion(tree, tree_moved)
            if num_multilibs > 1:
                # Keep the original binary directory present in the
                # packages, although empty (again for user convenience).
                empty = FSTreeMove(FSTreeEmpty(self.context), dir_src)
                tree = FSTreeUnion(tree, empty)
        return tree
