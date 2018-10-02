# sourcery-builder self-test command.

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

"""sourcery-builder self-test command."""

import unittest

import sourcery.command

__all__ = ['Command']


class Command(sourcery.command.Command):
    """sourcery-builder self-test implementation."""

    short_desc = 'Run self-tests of Sourcery Builder.'

    @staticmethod
    def add_arguments(parser):
        pass

    @staticmethod
    def main(context, relcfg, args):
        suite = unittest.defaultTestLoader.discover(
            'sourcery.selftests', top_level_dir=context.sourcery_builder_dir)
        unittest.TextTestRunner(verbosity=2).run(suite)
