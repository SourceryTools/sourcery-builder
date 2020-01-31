# sourcery-builder info command.

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

"""sourcery-builder info command."""

import sourcery.command
from sourcery.info import info_text
from sourcery.relcfg import add_release_config_arg

__all__ = ['Command']


class Command(sourcery.command.Command):
    """sourcery-builder info implementation."""

    short_desc = 'Provide information about a config.'

    long_desc = """By default, only summary information about the config and
    its components is shown.  If -v is used, details of public config variables
    and their values are shown; if --internal-vars is used, internal variables
    are shown."""

    @staticmethod
    def add_arguments(parser):
        parser.add_argument('--internal-vars', action='store_true',
                            help='Show values of internal variables')
        add_release_config_arg(parser)

    @staticmethod
    def main(context, relcfg, args):
        print(info_text(relcfg, args.verbose, args.internal_vars))
