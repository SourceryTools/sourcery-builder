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
    ConfigVarTypeDict, ConfigVarTypeStrEnum, ConfigVar

__all__ = ['ConfigVarTypeTestCase', 'ConfigVarTestCase']


class ConfigVarTypeTestCase(unittest.TestCase):

    """Test the ConfigVarType class and subclasses."""

    def setUp(self):
        """Set up a ConfigVarType test."""
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


class ConfigVarTestCase(unittest.TestCase):

    """Test the ConfigVar class and subclasses."""

    def setUp(self):
        """Set up a ConfigVar test."""
        self.context = ScriptContext()

    def test_init(self):
        """Test ConfigVar.__init__."""
        # These tests, and those of set and set_implicit, also
        # effectively cover the get and get_explicit methods without
        # there being anything further to test separately for those
        # methods.
        cvtype = ConfigVarTypeList(ConfigVarType(self.context, str))
        var = ConfigVar(self.context, 'test_var', cvtype, None, 'test-doc')
        self.assertEqual(var.context, self.context)
        self.assertEqual(var.__doc__, 'test-doc')
        self.assertIsNone(var.get())
        self.assertFalse(var.get_explicit())
        var = ConfigVar(self.context, 'test_var', cvtype, 123, 'test-doc')
        self.assertEqual(var.get(), 123)
        # Test copying from another ConfigVar.
        new_context = ScriptContext()
        new_var = ConfigVar(new_context, 'new_name',
                            ConfigVarType(self.context, str), var, 'new-doc')
        # Value, type and doc are copied from the old variable in this
        # case; context is not.
        self.assertEqual(new_var.context, new_context)
        self.assertEqual(new_var.get(), 123)
        self.assertEqual(new_var.__doc__, 'test-doc')
        self.assertFalse(new_var.get_explicit())
        var.set(['a', 'b'])
        new_var.set(['c', 'd'])
        self.assertEqual(var.get(), ('a', 'b'))
        self.assertEqual(new_var.get(), ('c', 'd'))
        # Finalized state and name are not copied.
        var.finalize()
        new_var = ConfigVar(new_context, 'new_name',
                            ConfigVarType(self.context, str), var, 'new-doc')
        new_var.set(('e', 'f'))
        new_var.finalize()
        self.assertRaisesRegex(ScriptError,
                               'release config variable new_name modified '
                               'after finalization',
                               new_var.set, ('new-val3', 'val4'))

    def test_set(self):
        """Test ConfigVar.set."""
        cvtype = ConfigVarTypeList(ConfigVarType(self.context, str))
        var = ConfigVar(self.context, 'test_var', cvtype, None, 'test-doc')
        var.set(('new-val',))
        self.assertEqual(var.get(), ('new-val',))
        self.assertTrue(var.get_explicit())
        var.set(('new-val2',))
        self.assertEqual(var.get(), ('new-val2',))
        self.assertTrue(var.get_explicit())
        # Value modified as needed to map to specified type.
        var.set(['new-val3', 'val4'])
        self.assertEqual(var.get(), ('new-val3', 'val4'))
        self.assertTrue(var.get_explicit())
        # Error for bad type.
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config '
                               'variable test_var',
                               var.set, 'not-a-list')
        # Error for setting once finalized.
        var.finalize()
        self.assertRaisesRegex(ScriptError,
                               'release config variable test_var modified '
                               'after finalization',
                               var.set, ('new-val3', 'val4'))

    def test_set_implicit(self):
        """Test ConfigVar.set_implicit."""
        cvtype = ConfigVarTypeList(ConfigVarType(self.context, str))
        var = ConfigVar(self.context, 'test_var', cvtype, None, 'test-doc')
        var.set_implicit(('new-val',))
        self.assertEqual(var.get(), ('new-val',))
        self.assertFalse(var.get_explicit())
        var.set_implicit(('new-val2',))
        self.assertEqual(var.get(), ('new-val2',))
        self.assertFalse(var.get_explicit())
        # Value modified as needed to map to specified type.
        var.set_implicit(['new-val3', 'val4'])
        self.assertEqual(var.get(), ('new-val3', 'val4'))
        self.assertFalse(var.get_explicit())
        # Once set explicitly, always marked as explicit.
        var.set(('new-val3', 'val4'))
        self.assertEqual(var.get(), ('new-val3', 'val4'))
        self.assertTrue(var.get_explicit())
        var.set_implicit(('new-val3', 'val4'))
        self.assertEqual(var.get(), ('new-val3', 'val4'))
        self.assertTrue(var.get_explicit())
        # Error for bad type.
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config '
                               'variable test_var',
                               var.set_implicit, 'not-a-list')
        # Error for setting once finalized.
        var.finalize()
        self.assertRaisesRegex(ScriptError,
                               'release config variable test_var modified '
                               'after finalization',
                               var.set_implicit, ('new-val3', 'val4'))

    def test_finalize(self):
        """Test ConfigVar.finalize."""
        cvtype = ConfigVarTypeList(ConfigVarType(self.context, str))
        var = ConfigVar(self.context, 'test_var', cvtype, None, 'test-doc')
        var.finalize()
        self.assertRaisesRegex(ScriptError,
                               'release config variable test_var modified '
                               'after finalization',
                               var.set, ('new-val3', 'val4'))
        # Can finalize more than once.
        var.finalize()
        self.assertRaisesRegex(ScriptError,
                               'release config variable test_var modified '
                               'after finalization',
                               var.set, ('new-val3', 'val4'))
        # get and get_explicit work after finalization.
        self.assertIsNone(var.get())
        self.assertFalse(var.get_explicit())
        var = ConfigVar(self.context, 'test_var', cvtype, None, 'test-doc')
        var.set(['a', 'b'])
        var.finalize()
        self.assertEqual(var.get(), ('a', 'b'))
        self.assertTrue(var.get_explicit())
