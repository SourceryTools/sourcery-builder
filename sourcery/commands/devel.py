# sourcery-builder devel command.

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

"""sourcery-builder devel command."""

from sourcery.build import BuildContext
import sourcery.command
from sourcery.context import add_parallelism_option
from sourcery.relcfg import add_release_config_arg

__all__ = ['Command']


class Command(sourcery.command.Command):
    """sourcery-builder devel implementation."""

    short_desc = 'Build a config.'

    @staticmethod
    def add_arguments(parser):
        add_parallelism_option(parser)
        add_release_config_arg(parser)

    @staticmethod
    def main(context, relcfg, args):
        args.build_source_packages = False
        BuildContext(context, relcfg, args).run_build()
