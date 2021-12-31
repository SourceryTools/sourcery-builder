# sourcery-builder self-test command.

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

"""sourcery-builder self-test command."""

import importlib
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
        top_suite = unittest.TestSuite()
        for pkg in context.package_list:
            pkg_str = pkg + '.selftests'
            pkg_str_init = pkg_str + '.__init__'
            pkg_mod = importlib.import_module(pkg_str_init)
            pkg_len = len(pkg_str_init.split('.'))
            pkg_path = pkg_mod.__file__.rsplit('/', pkg_len)[0]
            suite = unittest.defaultTestLoader.discover(
                pkg_str, top_level_dir=pkg_path)
            top_suite.addTest(suite)
        unittest.TextTestRunner(verbosity=2).run(top_suite)
