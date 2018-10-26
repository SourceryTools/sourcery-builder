# Base class for sourcery-builder commands.

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

"""Base class for sourcery-builder commands."""

__all__ = ['Command']


class Command:
    """Base class from which each command's class inherits."""

    short_desc = None
    """A description of this command for --help output."""

    long_desc = None
    """Additional information about this command for --help output."""

    check_script = False
    """Whether to check the executing script and Python interpreter.

    For certain commands involved in the release process, it is
    important for the command to check that it has been run from the
    copy checked out by the release config, not another copy
    somewhere, and that it is running under the Python interpreter
    specified by the release config, to make sure that the build is
    reproducible from the specified sources.  Those commands set
    check_script to True, meaning that the script automatically
    re-execs itself using the correct script and Python interpreter,
    and with user site packages disabled, after reading the release
    config.  Other commands do not need this (although using the
    correct copy is still advisable), and for the initial checkout it
    is necessary to use a separate copy of the script to bootstrap the
    checked-out copy of the scripts.

    """

    @staticmethod
    def add_arguments(parser):
        """Add command-specific arguments to the parser.

        If there is a release_config argument (added via
        sourcery.relcfg.add_release_config_arg), that config will be
        loaded automatically; otherwise, None will be passed as the
        first argument of main.

        """

        raise NotImplementedError

    @staticmethod
    def main(context, relcfg, args):
        """Implement the command.

        The first argument is the context for this script; the second
        is the release config passed, if the script takes one; the
        third is the parsed arguments to the script.

        """

        raise NotImplementedError
