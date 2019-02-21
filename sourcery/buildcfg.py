# Support build configurations.

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

"""Support build configurations."""

import os.path
import re
import shlex
import subprocess
import tempfile

__all__ = ['BuildCfg']


class BuildCfg:
    """A BuildCfg represents a choice of tools for building code.

    BuildCfg objects describe both hosts in a toolchain, and target
    multilibs.  Where different pieces of code are built with
    different tools or different GNU triplets, they use different
    BuildCfg objects, even if the code ends up being packaged
    together.  BuildCfg objects do not describe anything about where
    the code ends up in a package.

    """

    def __init__(self, context, triplet, name=None, tool_prefix=None,
                 ccopts=None, tool_opts=None):
        """Initialize a BuildCfg object.

        Tool names to use are prefixed by the specified triplet
        followed by '-' unless tool_prefix is specified (if an empty
        string, that means native tools are used); tool_prefix may
        include a directory name, and if it does not, the tools are
        found from the PATH.  ccopts specifies a list of options
        passed to all compilers; tool_opts maps the names of tools to
        options to pass to those tools (passed after those from
        ccopts, in the case of compilers.

        A BuildCfg has a name (used in naming build directories, so
        needs to be unique), which defaults to the concatentation of
        the triplet and compiler options, with characters other than
        alphanumerics, '-' and '_' mapped to '_'.

        """
        self.context = context
        if not isinstance(triplet, str):
            context.error('triplet must be a string')
        self.triplet = triplet
        if tool_prefix is None:
            self._tool_prefix = self._default_tool_prefix()
        else:
            self._tool_prefix = tool_prefix
        # An easy mistake to make is specifying a string for ccopts or
        # a value in tool_opts instead of the expected list of
        # strings, so check for that.
        if ccopts is None:
            self._ccopts = tuple()
        else:
            if isinstance(ccopts, str):
                context.error('ccopts must be a list of strings, not '
                              'a single string')
            self._ccopts = tuple(ccopts)
        if name is None:
            name = self._default_name()
        self.name = name
        if tool_opts is None:
            self._tool_opts = {}
        else:
            for val in tool_opts.values():
                if isinstance(val, str):
                    context.error('tool_opts values must be lists of '
                                  'strings, not single strings')
            self._tool_opts = {key: tuple(value)
                               for key, value in tool_opts.items()}

    def __repr__(self):
        """Return a textual representation of a BuildCfg object.

        The representation is in the form a BuildCfg call might appear
        in a release config, omitting the context argument.

        """
        args = [repr(self.triplet)]
        if self.name != self._default_name():
            args.append('name=%s' % repr(self.name))
        if self._tool_prefix != self._default_tool_prefix():
            args.append('tool_prefix=%s' % repr(self._tool_prefix))
        if self._ccopts:
            args.append('ccopts=%s' % repr(self._ccopts))
        if self._tool_opts:
            args.append('tool_opts={%s}'
                        % ', '.join('%s: %s' % (repr(key), repr(value))
                                    for key, value in sorted(
                                            self._tool_opts.items())))
        return 'BuildCfg(%s)' % ', '.join(args)

    def _default_tool_prefix(self):
        """Return the default tool prefix for this triplet."""
        return self.triplet + '-'

    def _default_name(self):
        """Return the default name for this triplet and compiler options."""
        name = self.triplet + ''.join(self._ccopts)
        name = re.sub('[^0-9A-Za-z_-]', '_', name)
        return name

    def is_windows(self):
        """Return whether this triplet is for Windows OS."""
        # This is not implemented in terms of a general mapping from
        # triplet to OS identifier because, while various such
        # mappings are useful, the amount of detail required in
        # describing the OS depends on the context, so such specific
        # predicates as this make sense.
        return '-mingw' in self.triplet

    def use_libiconv(self):
        """Return whether to use libiconv on this system."""
        return self.is_windows()

    def use_ncurses(self):
        """Return whether to use ncurses on this system."""
        return not self.is_windows()

    def tool(self, name):
        """Return the full name and arguments for the specified tool.

        In addition to actual tool names, 'c-compiler' and
        'c++-compiler' may be passed to map to the appropriate
        compilers for this BuildCfg.

        The return value is a list that may be modified by the caller
        (e.g., to add extra arguments required).

        """
        tool_map = {'c-compiler': 'gcc', 'c++-compiler': 'g++'}
        name = tool_map.get(name, name)
        tool_name = self._tool_prefix + name
        if name in ('c++', 'cpp', 'g++', 'gcc'):
            tool_args_ccopts = self._ccopts
        else:
            tool_args_ccopts = tuple()
        if name in self._tool_opts:
            tool_args = self._tool_opts[name]
        else:
            tool_args = tuple()
        tool_list = [tool_name]
        tool_list.extend(tool_args_ccopts)
        tool_list.extend(tool_args)
        return tool_list

    def configure_vars(self, cflags_extra=None):
        """Return the list of standard configure-time variable settings.

        cflags_extra specifies extra options to include in compiler
        settings, such as for debug info relocation.

        """
        var_map = {'CC': 'c-compiler',
                   'CXX': 'c++-compiler',
                   'AR': 'ar',
                   'AS': 'as',
                   'LD': 'ld',
                   'NM': 'nm',
                   'OBJCOPY': 'objcopy',
                   'OBJDUMP': 'objdump',
                   'RANLIB': 'ranlib',
                   'READELF': 'readelf',
                   'STRIP': 'strip'}
        if self.is_windows():
            var_map['WINDRES'] = 'windres'
            # Used by libtool:
            var_map['RC'] = 'windres'
        var_list = []
        # As above, cflags_extra might mistakenly be a string instead
        # of a list of strings.
        if isinstance(cflags_extra, str):
            self.context.error('cflags_extra must be a list of strings, not '
                               'a single string')
        for var in sorted(var_map.keys()):
            val = self.tool(var_map[var])
            if cflags_extra is not None and var in ('CC', 'CXX'):
                val.extend(cflags_extra)
            # The individual list elements will be used in shell
            # commands without extra quoting added, so must be safe
            # for that.
            for val_word in val:
                if shlex.quote(val_word) != val_word:
                    self.context.error('%s contains non-shell-safe value: %s'
                                       % (var, val_word))
            var_list.append('%s=%s' % (var, ' '.join(val)))
        return var_list

    def run_tool(self, name, args, path_prepend=None, check=False):
        """Run the specified tool, returning a CompletedProcess object.

        The tool is run with the given arguments (a list or tuple).
        If path_prepend is specified, it is a string to prepend to
        PATH (with ':' added) for running the tool.  If check is true,
        the tool is expected to return successfully.

        """
        if path_prepend is None:
            new_env = self.context.environ
        else:
            new_env = dict(self.context.environ)
            new_env['PATH'] = '%s:%s' % (path_prepend, new_env['PATH'])
        tool_list = self.tool(name)
        tool_list.extend(args)
        return subprocess.run(tool_list, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, env=new_env,
                              check=check)

    def get_endianness(self, path_prepend=None):
        """Determine the endianness of this BuildCfg ('big' or 'little').

        This depends on running a C compiler, which must support the
        __BYTE_ORDER__, __ORDER_BIG_ENDIAN__ and
        __ORDER_LITTLE_ENDIAN__ built-in macros.

        """
        with tempfile.TemporaryDirectory() as tempdir:
            file_name = os.path.join(tempdir, 'endian.c')
            with open(file_name, 'w', encoding='utf-8') as file:
                file.write('#if __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__\n'
                           'big\n'
                           '#elif __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__\n'
                           'little\n'
                           '#else\n'
                           '# error unknown endianness\n'
                           '#endif\n')
            tool_out = self.run_tool('c-compiler', ['-E', '-P', file_name],
                                     path_prepend=path_prepend, check=True)
        endian = tool_out.stdout.strip()
        if endian not in ('big', 'little'):
            self.context.error('could not determine endianness: got %s'
                               % endian)
        return endian
