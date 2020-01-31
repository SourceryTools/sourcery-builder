# sourcery-builder generic command for testing.

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

"""sourcery-builder generic command for testing."""

import sourcery.selftests.command

__all__ = ['Command']


class Command(sourcery.selftests.command.Command):
    """generic command implementation."""

    short_desc = 'Save argument information.'

    long_desc = 'Additional description.'

    @staticmethod
    def add_arguments(parser):
        parser.add_argument('extra')

    @staticmethod
    def main(context, relcfg, args):
        context.called_with_relcfg = relcfg
        context.called_with_args = args
