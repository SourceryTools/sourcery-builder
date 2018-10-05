# sourcery-builder reexec-relcfg command for testing.

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

"""sourcery-builder reexec-relcfg command for testing."""

import sourcery.command
import sourcery.relcfg

__all__ = ['Command']


class Command(sourcery.command.Command):
    """reexec-relcfg command implementation."""

    short_desc = 'Test re-execution.'

    check_script = True

    @staticmethod
    def add_arguments(parser):
        sourcery.relcfg.add_release_config_arg(parser)

    @staticmethod
    def main(context, relcfg, args):
        context.called_with_relcfg = relcfg
        context.called_with_args = args
