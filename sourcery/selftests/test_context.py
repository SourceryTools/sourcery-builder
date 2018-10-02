# Test sourcery.context.

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

"""Test sourcery.context."""

import argparse
import os
import os.path
import unittest

from sourcery.context import add_common_options, ScriptContext

__all__ = ['ContextTestCase']


class ContextTestCase(unittest.TestCase):

    """Test the ScriptContext class and associated functions."""

    def setUp(self):
        """Set up a context test."""
        self.context = ScriptContext()
        self.cwd = os.getcwd()

    def test_add_common_options(self):
        """Test add_common_options."""
        parser = argparse.ArgumentParser()
        add_common_options(parser, os.getcwd())
        args = parser.parse_args([])
        self.assertEqual(args.toplevelprefix,
                         os.path.join(self.cwd, 'install'))
        self.assertEqual(args.logdir,
                         os.path.join(self.cwd, 'logs'))
        self.assertEqual(args.objdir,
                         os.path.join(self.cwd, 'obj'))
        self.assertEqual(args.pkgdir,
                         os.path.join(self.cwd, 'pkg'))
        self.assertEqual(args.srcdir,
                         os.path.join(self.cwd, 'src'))
        self.assertEqual(args.testlogdir,
                         os.path.join(self.cwd, 'testlogs'))
        self.assertFalse(args.verbose)
        self.assertFalse(args.silent)
        args = parser.parse_args(['-i', 'arg1', '-l', 'arg2', '-o', 'arg3',
                                  '-p', 'arg4', '-s', 'arg5', '-T', 'arg6',
                                  '-v'])
        self.assertEqual(args.toplevelprefix,
                         os.path.join(self.cwd, 'arg1'))
        self.assertEqual(args.logdir,
                         os.path.join(self.cwd, 'arg2'))
        self.assertEqual(args.objdir,
                         os.path.join(self.cwd, 'arg3'))
        self.assertEqual(args.pkgdir,
                         os.path.join(self.cwd, 'arg4'))
        self.assertEqual(args.srcdir,
                         os.path.join(self.cwd, 'arg5'))
        self.assertEqual(args.testlogdir,
                         os.path.join(self.cwd, 'arg6'))
        self.assertTrue(args.verbose)
        self.assertFalse(args.silent)
        args = parser.parse_args(['-i', '/arg1', '-l', '/arg2', '-o', '/arg3',
                                  '-p', '/arg4', '-s', '/arg5', '-T', '/arg6',
                                  '--silent'])
        self.assertEqual(args.toplevelprefix, '/arg1')
        self.assertEqual(args.logdir, '/arg2')
        self.assertEqual(args.objdir, '/arg3')
        self.assertEqual(args.pkgdir, '/arg4')
        self.assertEqual(args.srcdir, '/arg5')
        self.assertEqual(args.testlogdir, '/arg6')
        self.assertFalse(args.verbose)
        self.assertTrue(args.silent)
