# Test sourcery.tsort.

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

"""Test sourcery.tsort."""

import unittest

from sourcery.context import ScriptError, ScriptContext
from sourcery.tsort import tsort

__all__ = ['TsortTestCase']


class TsortTestCase(unittest.TestCase):

    """Test the tsort function."""

    def setUp(self):
        """Set up a tsort test."""
        self.context = ScriptContext()

    def test_tsort_basic(self):
        """Test basic use of the tsort function."""
        deps = {'a': ['x', 'b', 'd'], 'b': ['x'], 'd': [], 'x': []}
        out = tsort(self.context, deps)
        self.assertEqual(out, ['x', 'b', 'd', 'a'])
        deps = {'a': ['d', 'b', 'x'], 'b': ['x'], 'd': [], 'x': []}
        out = tsort(self.context, deps)
        self.assertEqual(out, ['x', 'b', 'd', 'a'])
        deps = {'a': ['b'], 'b': ['c'], 'c': ['d', 'e', 'f'], 'd': ['e'],
                'e': [], 'f': []}
        out = tsort(self.context, deps)
        self.assertEqual(out, ['e', 'd', 'f', 'c', 'b', 'a'])

    def test_tsort_errors(self):
        """Test errors from the tsort function."""
        deps = {'a': ['b']}
        self.assertRaises(KeyError, tsort, self.context, deps)
        deps = {'a': ['a']}
        self.assertRaisesRegex(ScriptError,
                               'circular dependency',
                               tsort, self.context, deps)
        deps = {'a': ['b'], 'b': ['a']}
        self.assertRaisesRegex(ScriptError,
                               'circular dependency',
                               tsort, self.context, deps)
        deps = {'a': ['b'], 'b': ['c'], 'c': ['d'], 'd': ['a']}
        self.assertRaisesRegex(ScriptError,
                               'circular dependency',
                               tsort, self.context, deps)
