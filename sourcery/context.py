# Global script context and errors.

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

"""Global script context and errors."""

import argparse
import datetime
import importlib
import locale
import os
import os.path
import shlex
import subprocess
import sys

from sourcery.relcfg import ReleaseConfig

__all__ = ['add_common_options', 'add_parallelism_option', 'ScriptError',
           'ScriptContext']


def add_common_options(parser, cwd):
    """Add the script-independent options to an argument parser."""
    parser.add_argument('-i', type=os.path.abspath, metavar='DIR',
                        dest='toplevelprefix',
                        default=os.path.join(cwd, 'install'),
                        help='Use DIR for toolchain installation during '
                        'build (default $(pwd)/install)')
    parser.add_argument('-l', type=os.path.abspath, metavar='DIR',
                        dest='logdir',
                        default=os.path.join(cwd, 'logs'),
                        help='Use DIR for build log files '
                        '(default $(pwd)/logs)')
    parser.add_argument('-o', type=os.path.abspath, metavar='DIR',
                        dest='objdir',
                        default=os.path.join(cwd, 'obj'),
                        help='Use DIR for build and other temporary '
                        'directories (default $(pwd)/obj)')
    parser.add_argument('-p', type=os.path.abspath, metavar='DIR',
                        dest='pkgdir',
                        default=os.path.join(cwd, 'pkg'),
                        help='Use DIR for the final toolchain packages built '
                        '(default $(pwd)/pkg)')
    parser.add_argument('-s', type=os.path.abspath, metavar='DIR',
                        dest='srcdir',
                        default=os.path.join(cwd, 'src'),
                        help='Use DIR for toolchain source trees '
                        '(default $(pwd)/src)')
    parser.add_argument('-T', type=os.path.abspath, metavar='DIR',
                        dest='testlogdir',
                        default=os.path.join(cwd, 'testlogs'),
                        help='Use DIR for testsuite log files '
                        '(default $(pwd)/testlogs)')
    parser.add_argument('-v', action='store_true', dest='verbose',
                        help='Emit verbose messages')
    parser.add_argument('--silent', action='store_true', dest='silent',
                        help='Do not emit informational messages')


def add_parallelism_option(parser):
    """Add the -j option for parallelism to an argument parser."""
    parser.add_argument('-j', type=int, dest='parallelism',
                        default=os.cpu_count(),
                        help='Use PARALLELISM tasks in parallel '
                        '(default = number of CPU cores)')


class ScriptError(Exception):
    """Errors detected by a script."""


class ScriptContext:
    """Global context for a script as a whole."""

    def __init__(self, extra=None):
        """Initialize a context.

        A list of names of extra packages in which to find commands
        and components may be provided.  These are listed in order
        from least to most derived.

        """
        # The full name of the script being run.  This is not
        # necessarily the correct script to use for executing other
        # commands; the script to use for executing other commands may
        # be determined by the release config, if a Sourcery Builder
        # checkout is specified by that config, and a different copy
        # of the script may have been called by the user (necessarily,
        # in the case of the initial checkout process).  The script
        # may re-execute the correct copy of itself after reading the
        # release config.
        self.orig_script_full = os.path.abspath(sys.argv[0])
        # The full name of the script for executing other commands.
        self.script_full = self.orig_script_full
        # The script arguments for re-execing this script (set in main).
        self.argv = None
        # Whether this command is used to bootstrap a checkout.
        self.bootstrap_command = False
        # The Python interpreter for executing other commands.  This
        # may be changed from its original value based on the release
        # config.
        self.interp = sys.executable
        # The name of the script without sub-command to use in
        # diagnostic messages.
        self.script_only = os.path.basename(sys.argv[0])
        # The top-level Sourcery Builder directory.
        self.sourcery_builder_dir = os.path.dirname(os.path.dirname(__file__))
        # The name of the script to use in diagnostic messages.
        self.script = self.script_only
        # Whether to suppress informational messages.
        self.silent = False
        # Whether to print verbose messages.
        self.verbose_messages = False
        # Where to print messages.
        self.message_file = sys.stderr
        # Whether to suppress output from executed processes.
        self.execute_silent = False
        # The environment cleaned up by the script (os.environ unless
        # changed for testing purposes).
        self.environ = os.environ
        # The initial environment before cleanup.  This is for when
        # original values of variables such as EDITOR and VISUAL are
        # wanted for interactive use.
        self.environ_orig = dict(self.environ)
        # Python interpreter flags (sys.flags unless changed for
        # testing purposes).
        self.flags = sys.flags
        # How to re-exec this script (os.execve unless changed for
        # testing purposes).
        self.execve = os.execve
        # How to set locale for (locale.setlocale unless changed for
        # testing purposes).
        self.setlocale = locale.setlocale
        # How to set umask (os.umask unless changed for testing
        # purposes).
        self.umask = os.umask
        load_list = ['sourcery']
        if extra is not None:
            load_list.extend(extra)
        # The list of packages from which Sourcery Builder modules,
        # and those extending it, are loaded.
        self.package_list = tuple(load_list)
        self._load_commands()
        self._load_components()
        # Set by tests only, otherwise unused.
        self.called_with_args = None
        self.called_with_relcfg = None

    def _load_subunits(self, mod_name, subpkg_name, class_name, do_replace):
        """Load the modules for commands or components.

        Each package (in self.package_list) is expected to have a
        module named mod_name, with a class named class_name, as well
        as to contain a package named subpkg_name, which contains the
        individual subunits (commands or components); if do_replace,
        the logical name of such a subunit contains '-' where the
        module name contains '_'.  Say there are packages A, B, C (in
        the order from least to most derived, as in
        self.package_list).  Then a subunit X would be expected to
        have a class C.subpkg_name.X.class_name, that inherits, in
        order from most to least derived, from C.mod_name.class_name,
        B.subpkg_name.X.class_name, B.mod_name.class_name,
        A.subpkg_name.X.class_name, A.mod_name.class_name.  However, X
        may not exist in all of A, B and C.  Thus, a class is
        constructed dynamically that inherits from all the required
        base classes in the required order.

        """
        pkgs_base = {}
        pkgs_sub = {}
        subunits = set()
        for pkg in self.package_list:
            base_str = '%s.%s' % (pkg, mod_name)
            base_mod = importlib.import_module(base_str)
            pkgs_base[pkg] = getattr(base_mod, class_name)
            pkg_str = '%s.%s' % (pkg, subpkg_name)
            pkg_mod = importlib.import_module(pkg_str)
            pkgs_sub[pkg] = {}
            for subunit in pkg_mod.__all__:
                mod = importlib.import_module('%s.%s' % (pkg_str, subunit))
                if do_replace:
                    subunit = subunit.replace('_', '-')
                subunits.add(subunit)
                pkgs_sub[pkg][subunit] = getattr(mod, class_name)
        subunits_ret = {}
        for subunit in sorted(subunits):
            bases = []
            last_class = None
            for pkg in self.package_list:
                bases.append(pkgs_base[pkg])
                if subunit in pkgs_sub[pkg]:
                    last_class = pkgs_sub[pkg][subunit]
                    bases.append(last_class)
                else:
                    last_class = None
            for base in bases:
                if last_class is not None:
                    if not issubclass(last_class, base):
                        last_class = None
            bases = tuple(reversed(bases))
            if last_class is None:
                last_class = type(class_name, bases, {})
            else:
                # Construct a class and throw it away to ensure an
                # error if the method resolution order is not as
                # expected.
                type(class_name, bases, {})
            subunits_ret[subunit] = last_class
        return subunits_ret

    def _load_commands(self):
        """Load the modules for all sourcery-builder commands."""
        self.commands = self._load_subunits('command', 'commands', 'Command',
                                            True)

    def _load_components(self):
        """Load the modules for all sourcery-builder components."""
        self.components = self._load_subunits('component', 'components',
                                              'Component', False)

    def _set_script(self, script):
        """Set the name of the script for use in diagnostic messages."""
        self.script = '%s %s' % (self.script_only, script)

    def build_wrapper_path(self, wrapper):
        """Return the path to one of the build wrapper scripts."""
        return os.path.join(self.sourcery_builder_dir, 'build-wrappers',
                            wrapper)

    def inform(self, message):
        """Print an informational message."""
        if not self.silent:
            timestamp = datetime.datetime.today()
            timestr = timestamp.strftime('[%H:%M:%S] ')
            print(timestr + message, file=self.message_file)

    def inform_start(self, argv):
        """Print a message about a script starting."""
        self.inform('%s %s starting...' % (self.script_only, ' '.join(argv)))

    def inform_end(self):
        """Print a message about a script ending."""
        self.inform('... %s complete.' % self.script)

    def verbose(self, message):
        """Print a verbose message."""
        if self.verbose_messages:
            print('%s: %s' % (self.script, message), file=self.message_file)

    def warning(self, message):
        """Print a warning message."""
        print('%s: warning: %s' % (self.script, message),
              file=self.message_file)

    def error(self, message):
        """Print an error message and exit.

        This function exists, rather than callers raising an exception
        directly, for interface consistency with the other functions
        printing messages.

        """
        raise ScriptError('%s: error: %s' % (self.script, message))

    def execute(self, cmd, cwd=None):
        """Print and execute the given command, checking for errors.

        Standard output and standard error go to the standard output and
        standard error of the calling script.  The current working
        directory of the calling script is used if cwd is not specified.

        """
        if not self.silent:
            cmd_quoted = [shlex.quote(s) for s in cmd]
            cmd_str = ' '.join(cmd_quoted)
            if cwd is not None:
                cmd_str = 'pushd %s; %s; popd' % (shlex.quote(cwd), cmd_str)
            print(cmd_str, file=self.message_file)
        if self.execute_silent:
            silent_args = {'stdout': subprocess.DEVNULL,
                           'stderr': subprocess.DEVNULL}
        else:
            silent_args = {}
        subprocess.run(cmd, stdin=subprocess.DEVNULL, cwd=cwd,
                       env=self.environ, check=True, **silent_args)

    def script_command(self):
        """Return a list for the start of a command to run this script.

        The individual Sourcery Builder command, and its arguments,
        are not included; the list stops with the name of the Sourcery
        Builder script itself.

        """
        return [self.interp, '-s', '-E', self.script_full]

    def exec_self(self):
        """Re-execute this script in a controlled environment.

        Re-execution may be required if environment variables were
        found that might have affected how the script behaves, or if
        user site packages were not disabled.

        """
        argv = self.script_command() + self.argv
        self.execve(self.interp, argv, self.environ)

    def clean_environment(self, extra_vars=None, reexec=False):
        """Clean the environment in which this script is run.

        If extra_vars is specified, it contains extra environment
        variables to set, determined from a release configuration.  If
        reexec is true, the script should be re-executed with the
        correct interpreter and clean environment if necessary.

        """
        self.setlocale(locale.LC_ALL, 'C')
        self.umask(0o022)
        need_reexec = False
        if not self.flags.no_user_site:
            need_reexec = True
        if self.interp != sys.executable:
            need_reexec = True
        if self.script_full != self.orig_script_full:
            need_reexec = True
        if extra_vars is None:
            extra_vars = {}
        # Environment variables that are safe to keep and may be
        # required by subprocesses.
        env_vars_keep = {'HOME', 'LOGNAME', 'SSH_AUTH_SOCK', 'TERM', 'USER'}
        # Environment variables kept initially, but possibly replaced
        # after a release config is loaded.
        env_vars_replace_relcfg = {'PATH', 'LD_LIBRARY_PATH'}
        # Environment variables set to fixed values.
        env_vars_replace = {'LANG': 'C', 'LC_ALL': 'C'}
        remove_vars = set()
        for key in self.environ:
            if key in env_vars_keep:
                pass
            elif key in env_vars_replace_relcfg:
                if key in extra_vars:
                    remove_vars.add(key)
            elif key not in env_vars_replace:
                remove_vars.add(key)
        for key in remove_vars:
            if key.startswith('PYTHON') and not self.flags.ignore_environment:
                need_reexec = True
            del self.environ[key]
        for key in env_vars_replace:
            self.environ[key] = env_vars_replace[key]
        for key in extra_vars:
            self.environ[key] = extra_vars[key]
        if reexec and need_reexec:
            self.exec_self()

    def main(self, loader, argv):

        """Main sourcery-builder command."""
        self.argv = argv
        self.clean_environment()
        parser = argparse.ArgumentParser()
        add_common_options(parser, os.getcwd())
        subparsers = parser.add_subparsers(dest='cmd_name')
        for cmd in sorted(self.commands.keys()):
            cls = self.commands[cmd]
            subparser = subparsers.add_parser(cmd, description=cls.short_desc,
                                              help=cls.short_desc,
                                              epilog=cls.long_desc)
            cls.add_arguments(subparser)
        args = parser.parse_args(argv)
        self.silent = args.silent
        self.verbose_messages = args.verbose
        self._set_script(args.cmd_name)
        self.inform_start(argv)
        cmd_cls = self.commands[args.cmd_name]
        self.bootstrap_command = cmd_cls.bootstrap_command
        if 'release_config' in vars(args):
            relcfg = ReleaseConfig(self, args.release_config, loader, args)
            extra_vars = relcfg.env_set.get()
            self.script_full = relcfg.script_full.get()
            self.interp = relcfg.interp.get()
        else:
            relcfg = None
            extra_vars = None
        self.clean_environment(extra_vars=extra_vars,
                               reexec=cmd_cls.check_script)
        cmd_cls.main(self, relcfg, args)
        self.inform_end()
