# sourcery-builder rpc-client command.

# Copyright 2018-2021 Mentor Graphics Corporation.

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

"""sourcery-builder rpc-client command."""

import sourcery.command
from sourcery.rpc import send_message

__all__ = ['Command']


class Command(sourcery.command.Command):
    """sourcery-builder rpc-client implementation."""

    short_desc = ('Send an RPC message (for use from other commands, not '
                  'direct use by users).')

    @staticmethod
    def add_arguments(parser):
        parser.add_argument('dir',
                            help='The directory containing the RPC sockets')
        parser.add_argument('message', type=int,
                            help='The number of the message to send')

    @staticmethod
    def main(context, relcfg, args):
        result = send_message(args.dir, args.message)
        if result != 0:
            context.error('RPC message failed, status %d' % result)
