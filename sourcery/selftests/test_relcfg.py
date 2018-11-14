# Test sourcery.relcfg.

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

"""Test sourcery.relcfg."""

import collections
import unittest

from sourcery.context import ScriptContext, ScriptError
from sourcery.relcfg import ConfigVarType, ConfigVarTypeList, \
    ConfigVarTypeDict, ConfigVarTypeStrEnum

__all__ = ['ConfigVarTypeTestCase']


class ConfigVarTypeTestCase(unittest.TestCase):

    """Test the ConfigVarType class and subclasses."""

    def setUp(self):
        """Set up a version control test."""
        self.context = ScriptContext()

    def test_init(self):
        """Test ConfigVarType.__init__."""
        cvtype = ConfigVarType(self.context)
        self.assertEqual(cvtype.context, self.context)
        cvtype = ConfigVarType(self.context, str)
        self.assertEqual(cvtype.context, self.context)
        cvtype = ConfigVarType(self.context, list, tuple)
        self.assertEqual(cvtype.context, self.context)

    def test_check(self):
        """Test ConfigVarType.check."""
        cvtype = ConfigVarType(self.context)
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config '
                               'variable some_name',
                               cvtype.check, 'some_name', None)
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config '
                               'variable some_name',
                               cvtype.check, 'some_name', 0)
        cvtype = ConfigVarType(self.context, int)
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config '
                               'variable other_name',
                               cvtype.check, 'other_name', None)
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config '
                               'variable other_name',
                               cvtype.check, 'other_name', 'test')
        self.assertEqual(cvtype.check('var', 0), 0)
        self.assertEqual(cvtype.check('var', 1), 1)
        # Subclass types are OK.
        self.assertEqual(cvtype.check('var', True), True)
        cvtype = ConfigVarType(self.context, str, int)
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config '
                               'variable other_name',
                               cvtype.check, 'other_name', None)
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config '
                               'variable other_name',
                               cvtype.check, 'other_name', {})
        self.assertEqual(cvtype.check('var', 'test'), 'test')
        self.assertEqual(cvtype.check('var', 0), 0)
        self.assertEqual(cvtype.check('var', 1), 1)

    def test_list_check(self):
        """Test ConfigVarTypeList.check."""
        cvtype = ConfigVarTypeList(ConfigVarType(self.context, str))
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config '
                               'variable test_name',
                               cvtype.check, 'test_name', None)
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config '
                               'variable test_name',
                               cvtype.check, 'test_name', 'some-string')
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config '
                               'variable test_name',
                               cvtype.check, 'test_name', ['a', 123])
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config '
                               'variable test_name',
                               cvtype.check, 'test_name', [456, 'b'])
        self.assertEqual(cvtype.check('name', ['a', 'b']), ('a', 'b'))
        self.assertEqual(cvtype.check('x', ('c', 'd')), ('c', 'd'))
        self.assertEqual(cvtype.check('y.z', []), ())
        self.assertEqual(cvtype.check('w', ['x']), ('x',))
        cvtype = ConfigVarTypeList(ConfigVarTypeList(ConfigVarType(
            self.context, int)))
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config '
                               'variable test_name',
                               cvtype.check, 'test_name', [[1, 2], [3, 'x']])
        self.assertEqual(cvtype.check('t', [[1, 2], [3, 4]]), ((1, 2), (3, 4)))

    def test_dict_check(self):
        """Test ConfigVarTypeDict.check."""
        cvtype = ConfigVarTypeDict(
            ConfigVarType(self.context, int),
            ConfigVarTypeList(ConfigVarType(self.context, str)))
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config '
                               'variable test_name',
                               cvtype.check, 'test_name', None)
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config '
                               'variable test_name',
                               cvtype.check, 'test_name', {'a': 'b'})
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config '
                               'variable test_name',
                               cvtype.check, 'test_name', {1: ['c', 2]})
        self.assertEqual(cvtype.check('var', {1: ['x', 'y'], 2: [],
                                              3: ('z',)}),
                         {1: ('x', 'y'), 2: (), 3: ('z',)})
        # Test use of another mapping class.
        test_val = collections.OrderedDict(
            ((1, ['x']), (3, ['z', 'y'])))
        self.assertEqual(cvtype.check('var', test_val),
                         {1: ('x',), 3: ('z', 'y')})

    def test_str_enum_check(self):
        """Test ConfigVarTypeStrEnum.check."""
        cvtype = ConfigVarTypeStrEnum(self.context, {'a', 'y', 'z'})
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config '
                               'variable test_name',
                               cvtype.check, 'test_name', None)
        self.assertRaisesRegex(ScriptError,
                               'bad value for release config variable '
                               'test_name',
                               cvtype.check, 'test_name', 'b')
        self.assertRaisesRegex(ScriptError,
                               'bad value for release config variable '
                               'test_name',
                               cvtype.check, 'test_name', 'az')
        self.assertEqual(cvtype.check('var', 'a'), 'a')
        self.assertEqual(cvtype.check('var', 'y'), 'y')
        self.assertEqual(cvtype.check('var', 'z'), 'z')
