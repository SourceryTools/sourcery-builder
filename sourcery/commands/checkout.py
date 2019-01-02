# sourcery-builder checkout command.

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

"""sourcery-builder checkout command."""

import sourcery.command
from sourcery.relcfg import add_release_config_arg

__all__ = ['Command']


class Command(sourcery.command.Command):
    """sourcery-builder checkout implementation."""

    short_desc = 'Check out toolchain sources.'

    @staticmethod
    def add_arguments(parser):
        add_release_config_arg(parser)

    @staticmethod
    def main(context, relcfg, args):
        for component in relcfg.list_source_components():
            vc_obj = component.vars.vc.get()
            vc_obj.checkout_component(component)
