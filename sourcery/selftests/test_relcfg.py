# Test sourcery.relcfg.

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

"""Test sourcery.relcfg."""

import argparse
import collections
import os
import os.path
import shutil
import subprocess
import tempfile
import time
import unittest
import unittest.mock

from sourcery.buildcfg import BuildCfg
from sourcery.context import add_common_options, ScriptContext, ScriptError
from sourcery.fstree import FSTreeCopy
from sourcery.pkghost import PkgHost
from sourcery.relcfg import ConfigVarType, ConfigVarTypeList, \
    ConfigVarTypeDict, ConfigVarTypeStrEnum, ConfigVar, ConfigVarGroup, \
    ComponentInConfig, add_release_config_arg, ReleaseConfigPathLoader, \
    ReleaseConfigTextLoader, ReleaseConfig
import sourcery.selftests.components.generic
from sourcery.selftests.support import create_files, read_files
from sourcery.vc import GitVC, SvnVC, TarVC

__all__ = ['ConfigVarTypeTestCase', 'ConfigVarTestCase',
           'ConfigVarGroupTestCase', 'ComponentInConfigTestCase',
           'AddReleaseConfigArgTestCase', 'ReleaseConfigPathLoaderSub',
           'ReleaseConfigLoaderTestCase', 'ReleaseConfigTestCase']


class ConfigVarTypeTestCase(unittest.TestCase):

    """Test the ConfigVarType class and subclasses."""

    def setUp(self):
        """Set up a ConfigVarType test."""
        self.context = ScriptContext()

    def test_init(self):
        """Test ConfigVarType.__init__."""
        cvtype = ConfigVarType(self.context)
        self.assertIs(cvtype.context, self.context)
        cvtype = ConfigVarType(self.context, str)
        self.assertIs(cvtype.context, self.context)
        cvtype = ConfigVarType(self.context, list, tuple)
        self.assertIs(cvtype.context, self.context)

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

    """Test the ConfigVar class."""

    def setUp(self):
        """Set up a ConfigVar test."""
        self.context = ScriptContext()

    def test_init(self):
        """Test ConfigVar.__init__."""
        # These tests, and those of set and set_implicit, also
        # effectively cover the get, get_explicit and get_internal
        # methods without there being anything further to test
        # separately for those methods.
        cvtype = ConfigVarTypeList(ConfigVarType(self.context, str))
        var = ConfigVar(self.context, 'test_var', cvtype, None, 'test-doc')
        self.assertIs(var.context, self.context)
        self.assertEqual(var.__doc__, 'test-doc')
        self.assertIsNone(var.get())
        self.assertFalse(var.get_explicit())
        self.assertFalse(var.get_internal())
        var = ConfigVar(self.context, 'test_var', cvtype, 123, 'test-doc')
        self.assertEqual(var.get(), 123)
        var = ConfigVar(self.context, 'test_var', cvtype, 123, 'test-doc',
                        internal=True)
        self.assertTrue(var.get_internal())
        # Test copying from another ConfigVar.
        new_context = ScriptContext()
        new_var = ConfigVar(new_context, 'new_name',
                            ConfigVarType(self.context, str), var, 'new-doc')
        # Value, type and doc are copied from the old variable in this
        # case; context is not.
        self.assertIs(new_var.context, new_context)
        self.assertEqual(new_var.get(), 123)
        self.assertEqual(new_var.__doc__, 'test-doc')
        self.assertFalse(new_var.get_explicit())
        self.assertTrue(new_var.get_internal())
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


class ConfigVarGroupTestCase(unittest.TestCase):

    """Test the ConfigVarGroup class."""

    def setUp(self):
        """Set up a ConfigVarGroup test."""
        self.context = ScriptContext(['sourcery.selftests'])

    def test_init(self):
        """Test ConfigVarGroup.__init__."""
        # These and other tests also effectively cover the __getattr__
        # method without there being anything further to test
        # separately for that method other than errors from it.
        group = ConfigVarGroup(self.context, '')
        self.assertIs(group.context, self.context)
        self.assertEqual(group.list_vars(), [])
        self.assertEqual(group.list_groups(), [])
        # Test copying from another ConfigVarGroup.
        cvtype = ConfigVarType(self.context, str)
        group2 = ConfigVarGroup(self.context, 'abc')
        group2.add_var('test_var', cvtype, 123, 'test-doc')
        group2.add_group('test_group', None)
        group2.test_group.add_var('var2', cvtype, 456, 'doc2')
        group = ConfigVarGroup(self.context, 'def', group2)
        self.assertEqual(group.list_vars(), ['test_var'])
        self.assertEqual(group.list_groups(), ['test_group'])
        self.assertEqual(group.test_group.list_vars(), ['var2'])
        self.assertEqual(group.test_group.list_groups(), [])
        self.assertEqual(group.test_var.get(), 123)
        self.assertEqual(group.test_group.var2.get(), 456)
        # The name is that passed to __init__, not that of the copied
        # group.
        group.finalize()
        self.assertRaisesRegex(ScriptError,
                               r'release config variable def\.test_var '
                               r'modified after finalization',
                               group.test_var.set, 'value')
        # Finalized state is separate from that for the copied group.
        group2.test_var.set('value')
        self.assertEqual(group2.test_var.get(), 'value')
        # Finalized state is not copied.
        group2.finalize()
        group = ConfigVarGroup(self.context, 'def', group2)
        self.assertEqual(group.list_vars(), ['test_var'])
        self.assertEqual(group.list_groups(), ['test_group'])
        self.assertEqual(group.test_group.list_vars(), ['var2'])
        self.assertEqual(group.test_group.list_groups(), [])
        self.assertEqual(group.test_var.get(), 'value')
        self.assertEqual(group.test_group.var2.get(), 456)
        group.test_var.set('value2')
        self.assertEqual(group.test_var.get(), 'value2')
        group.add_var('another', cvtype, 'test', 'doc')
        self.assertEqual(group.another.get(), 'test')

    def test_getattr_errors(self):
        """Test errors from ConfigVarGroup.__getattr__."""
        group = ConfigVarGroup(self.context, '')
        self.assertRaisesRegex(AttributeError,
                               'no_such_var_or_component',
                               getattr, group, 'no_such_var_or_component')

    def test_add_var(self):
        """Test ConfigVarGroup.add_var."""
        group = ConfigVarGroup(self.context, '')
        cvtype = ConfigVarType(self.context, str)
        group.add_var('var_name', cvtype, 123, 'test-doc')
        self.assertEqual(group.list_vars(), ['var_name'])
        self.assertEqual(group.list_groups(), [])
        self.assertEqual(group.var_name.get(), 123)
        self.assertFalse(group.var_name.get_explicit())
        self.assertEqual(group.var_name.__doc__, 'test-doc')
        group.var_name.set('xyz')
        self.assertEqual(group.var_name.get(), 'xyz')
        self.assertTrue(group.var_name.get_explicit())
        # Test copying variables.
        group.add_var('copied', None, group.var_name, None)
        self.assertEqual(group.copied.get(), 'xyz')
        self.assertTrue(group.copied.get_explicit())
        # Test constructed variable names.
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config '
                               'variable var_name',
                               group.var_name.set, 123)
        group = ConfigVarGroup(self.context, 'abc')
        group.add_var('var_name', cvtype, 123, 'test-doc')
        self.assertRaisesRegex(ScriptError,
                               r'bad type for value of release config '
                               r'variable abc\.var_name',
                               group.var_name.set, 123)

    def test_add_var_errors(self):
        """Test errors from ConfigVarGroup.add_var."""
        group = ConfigVarGroup(self.context, '')
        cvtype = ConfigVarType(self.context, str)
        group.finalize()
        self.assertRaisesRegex(ScriptError,
                               'variable var_name defined after finalization',
                               group.add_var, 'var_name', cvtype, 123,
                               'test-doc')
        group = ConfigVarGroup(self.context, '')
        group.add_var('var_name', cvtype, 123, 'test-doc')
        self.assertRaisesRegex(ScriptError,
                               'duplicate variable var_name',
                               group.add_var, 'var_name', cvtype, 123,
                               'test-doc')
        group.add_group('group_name', None)
        self.assertRaisesRegex(ScriptError,
                               'variable group_name duplicates group',
                               group.add_var, 'group_name', cvtype, 123,
                               'test-doc')

    def test_add_group(self):
        """Test ConfigVarGroup.add_group."""
        group = ConfigVarGroup(self.context, '')
        cvtype = ConfigVarType(self.context, str)
        sub = group.add_group('sub', None)
        sub.add_var('var_name', cvtype, 123, 'test-doc')
        self.assertEqual(group.list_vars(), [])
        self.assertEqual(group.list_groups(), ['sub'])
        self.assertEqual(sub, group.sub)
        self.assertEqual(sub.list_vars(), ['var_name'])
        self.assertEqual(sub.list_groups(), [])
        # Test copying groups.
        sub2 = group.add_group('sub2', sub)
        self.assertEqual(group.list_vars(), [])
        self.assertEqual(group.list_groups(), ['sub', 'sub2'])
        self.assertEqual(sub2, group.sub2)
        self.assertEqual(sub2.list_vars(), ['var_name'])
        self.assertEqual(sub2.list_groups(), [])
        sub2.var_name.set('bcd')
        self.assertEqual(group.sub.var_name.get(), 123)
        self.assertEqual(group.sub2.var_name.get(), 'bcd')
        # Test constructed group names.
        self.assertRaisesRegex(ScriptError,
                               r'bad type for value of release config '
                               r'variable sub\.var_name',
                               group.sub.var_name.set, 123)
        self.assertRaisesRegex(ScriptError,
                               r'bad type for value of release config '
                               r'variable sub2\.var_name',
                               group.sub2.var_name.set, 123)
        another = sub.add_group('another', None)
        another.add_var('x', cvtype, 123, '')
        self.assertRaisesRegex(ScriptError,
                               r'bad type for value of release config '
                               r'variable sub\.another\.x',
                               group.sub.another.x.set, 123)

    def test_add_group_errors(self):
        """Test errors from ConfigVarGroup.add_group."""
        group = ConfigVarGroup(self.context, '')
        cvtype = ConfigVarType(self.context, str)
        group.finalize()
        self.assertRaisesRegex(ScriptError,
                               'variable group x defined after finalization',
                               group.add_group, 'x', None)
        group = ConfigVarGroup(self.context, '')
        group.add_group('x', None)
        self.assertRaisesRegex(ScriptError,
                               'duplicate variable group x',
                               group.add_group, 'x', None)
        group.add_var('y', cvtype, 'test', 'doc')
        self.assertRaisesRegex(ScriptError,
                               'variable group y duplicates variable',
                               group.add_group, 'y', None)

    def test_list_vars(self):
        """Test ConfigVarGroup.list_vars."""
        group = ConfigVarGroup(self.context, '')
        cvtype = ConfigVarType(self.context, str)
        group.add_var('z', cvtype, 'test', 'doc')
        group.add_var('a', cvtype, 'test', 'doc')
        group.add_var('y', cvtype, 'test', 'doc')
        group.add_var('b', cvtype, 'test', 'doc')
        group.add_group('c', None)
        self.assertEqual(group.list_vars(), ['a', 'b', 'y', 'z'])

    def test_list_groups(self):
        """Test ConfigVarGroup.list_groups."""
        group = ConfigVarGroup(self.context, '')
        cvtype = ConfigVarType(self.context, str)
        group.add_group('z', None)
        group.add_group('a', None)
        group.add_group('y', None)
        group.add_group('b', None)
        group.add_var('c', cvtype, 'test', 'doc')
        self.assertEqual(group.list_groups(), ['a', 'b', 'y', 'z'])

    def test_finalize(self):
        """Test ConfigVarGroup.finalize."""
        group = ConfigVarGroup(self.context, '')
        cvtype = ConfigVarType(self.context, str)
        sub1 = group.add_group('sub1', None)
        sub2 = sub1.add_group('sub2', None)
        sub3 = sub2.add_group('sub3', None)
        group.add_var('var1', cvtype, 'val1', 'doc1')
        sub1.add_var('var2', cvtype, 'val2', 'doc2')
        sub2.add_var('var3', cvtype, 'val3', 'doc3')
        sub3.add_var('var4', cvtype, 'val4', 'doc4')
        group.finalize()
        self.assertRaisesRegex(ScriptError,
                               'release config variable var1 modified '
                               'after finalization',
                               group.var1.set, 'new')
        self.assertRaisesRegex(ScriptError,
                               r'release config variable '
                               r'sub1\.sub2\.sub3\.var4 modified after '
                               'finalization',
                               group.sub1.sub2.sub3.var4.set, 'new')
        self.assertRaisesRegex(ScriptError,
                               'variable var_new defined after finalization',
                               group.sub1.sub2.add_var, 'var_new', cvtype,
                               'val_new', 'doc-new')
        # Can finalize more than once.
        group.finalize()
        self.assertRaisesRegex(ScriptError,
                               'release config variable var1 modified '
                               'after finalization',
                               group.var1.set, 'new')

    def test_add_release_config_vars(self):
        """Test ConfigVarGroup.add_release_config_vars."""
        group = ConfigVarGroup(self.context, '')
        time_before = int(time.time())
        group.add_release_config_vars()
        time_after = int(time.time())
        # Test the list of release config variables.
        self.assertEqual(group.list_vars(),
                         ['bootstrap_components_vc',
                          'bootstrap_components_version', 'build', 'env_set',
                          'hosts', 'installdir', 'interp', 'pkg_build',
                          'pkg_prefix', 'pkg_version', 'script_full',
                          'source_date_epoch', 'target'])
        # Test each variable's default value and type constraints.
        self.assertEqual(group.bootstrap_components_vc.get(), {})
        self.assertRaisesRegex(ScriptError,
                               r'bad type for value of release config '
                               r'variable bootstrap_components_vc',
                               group.bootstrap_components_vc.set,
                               None)
        self.assertRaisesRegex(ScriptError,
                               r'bad type for value of release config '
                               r'variable bootstrap_components_vc',
                               group.bootstrap_components_vc.set,
                               {'sourcery_builder': None})
        group.bootstrap_components_vc.set(
            {'sourcery_builder': GitVC(self.context, '/some/where'),
             'release_configs': SvnVC(self.context, 'file:///some/where'),
             'generic': TarVC(self.context, '/some/where.tar')})
        self.assertEqual(group.bootstrap_components_version.get(), {})
        self.assertRaisesRegex(ScriptError,
                               r'bad type for value of release config '
                               r'variable bootstrap_components_version',
                               group.bootstrap_components_version.set,
                               None)
        self.assertRaisesRegex(ScriptError,
                               r'bad type for value of release config '
                               r'variable bootstrap_components_version',
                               group.bootstrap_components_version.set,
                               {'sourcery_builder': None})
        group.bootstrap_components_version.set(
            {'sourcery_builder': 'example',
             'release_configs': 'other'})
        self.assertIsNone(group.build.get())
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config variable '
                               'build',
                               group.build.set, None)
        group.build.set('aarch64-linux-gnu')
        group.build.set(PkgHost(self.context, 'i686-pc-linux-gnu'))
        self.assertEqual(group.env_set.get(), {})
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config variable '
                               'env_set',
                               group.env_set.set, {'X': 1})
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config variable '
                               'env_set',
                               group.env_set.set, {2: 'X'})
        group.env_set.set({'A': 'B'})
        self.assertIsNone(group.hosts.get())
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config variable '
                               'hosts',
                               group.hosts.set, None)
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config variable '
                               'hosts',
                               group.hosts.set, [1])
        group.hosts.set(['x86_64-linux-gnu', 'aarch64-linux-gnu'])
        group.hosts.set([PkgHost(self.context, 'powerpc64le-linux-gnu')])
        self.assertEqual(group.installdir.get(), '/opt/toolchain')
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config variable '
                               'installdir',
                               group.installdir.set, None)
        group.installdir.set('/some/where')
        self.assertEqual(group.interp.get(), self.context.interp)
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config variable '
                               'interp',
                               group.interp.set, None)
        group.interp.set('/path/to/python3')
        self.assertEqual(group.pkg_build.get(), 1)
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config variable '
                               'pkg_build',
                               group.pkg_build.set, '1')
        group.pkg_build.set(2)
        self.assertEqual(group.pkg_prefix.get(), 'toolchain')
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config variable '
                               'pkg_prefix',
                               group.pkg_prefix.set, 1)
        group.pkg_prefix.set('gcc')
        self.assertEqual(group.pkg_version.get(), '1.0')
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config variable '
                               'pkg_version',
                               group.pkg_version.set, 1)
        group.pkg_version.set('1234')
        self.assertEqual(group.script_full.get(), self.context.script_full)
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config variable '
                               'script_full',
                               group.script_full.set, 12345)
        group.script_full.set('/some/where/sourcery-builder')
        self.assertGreaterEqual(group.source_date_epoch.get(), time_before)
        self.assertLessEqual(group.source_date_epoch.get(), time_after)
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config variable '
                               'source_date_epoch',
                               group.source_date_epoch.set, '1234567890')
        group.source_date_epoch.set(1234567890)
        self.assertIsNone(group.target.get())
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config variable '
                               'target',
                               group.target.set, None)
        group.target.set('x86_64-w64-mingw32')
        # Test the list of components.
        self.assertEqual(group.list_groups(),
                         sorted(self.context.components.keys()))
        # Test the list of per-component variables.
        self.assertEqual(group.generic.list_vars(),
                         ['configure_opts', 'source_type', 'srcdirname',
                          'vc', 'version'])
        # Test each component variable's default value and type
        # constraints.
        self.assertEqual(group.no_add_rel_cfg_vars.configure_opts.get(), ())
        self.assertRaisesRegex(ScriptError,
                               r'bad type for value of release config '
                               r'variable no_add_rel_cfg_vars\.configure_opts',
                               group.no_add_rel_cfg_vars.configure_opts.set,
                               [1, 2])
        self.assertRaisesRegex(ScriptError,
                               r'bad type for value of release config '
                               r'variable no_add_rel_cfg_vars\.configure_opts',
                               group.no_add_rel_cfg_vars.configure_opts.set,
                               '--option')
        group.no_add_rel_cfg_vars.configure_opts.set(['--a', '--b'])
        group.no_add_rel_cfg_vars.configure_opts.set(('--c',))
        self.assertIsNone(group.no_add_rel_cfg_vars.source_type.get())
        self.assertRaisesRegex(ScriptError,
                               r'bad type for value of release config '
                               r'variable no_add_rel_cfg_vars\.source_type',
                               group.no_add_rel_cfg_vars.source_type.set,
                               None)
        self.assertRaisesRegex(ScriptError,
                               r'bad value for release config '
                               r'variable no_add_rel_cfg_vars\.source_type',
                               group.no_add_rel_cfg_vars.source_type.set,
                               'other')
        group.no_add_rel_cfg_vars.source_type.set('open')
        group.no_add_rel_cfg_vars.source_type.set('closed')
        group.no_add_rel_cfg_vars.source_type.set('none')
        self.assertEqual(group.no_add_rel_cfg_vars.srcdirname.get(),
                         'no_add_rel_cfg_vars')
        self.assertRaisesRegex(ScriptError,
                               r'bad type for value of release config '
                               r'variable no_add_rel_cfg_vars\.srcdirname',
                               group.no_add_rel_cfg_vars.srcdirname.set,
                               None)
        group.no_add_rel_cfg_vars.srcdirname.set('other-name')
        self.assertIsNone(group.no_add_rel_cfg_vars.vc.get())
        self.assertRaisesRegex(ScriptError,
                               r'bad type for value of release config '
                               r'variable no_add_rel_cfg_vars\.vc',
                               group.no_add_rel_cfg_vars.vc.set,
                               None)
        group.no_add_rel_cfg_vars.vc.set(GitVC(self.context, '/some/where'))
        group.no_add_rel_cfg_vars.vc.set(SvnVC(self.context,
                                               'file:///some/where'))
        group.no_add_rel_cfg_vars.vc.set(TarVC(self.context,
                                               '/some/where.tar'))
        self.assertIsNone(group.no_add_rel_cfg_vars.version.get())
        self.assertRaisesRegex(ScriptError,
                               r'bad type for value of release config '
                               r'variable no_add_rel_cfg_vars\.version',
                               group.no_add_rel_cfg_vars.version.set,
                               None)
        group.no_add_rel_cfg_vars.version.set('123.456a')
        # Test use of add_release_config_vars hook, for changing
        # existing variables and adding new ones.
        self.assertEqual(group.generic.source_type.get(), 'open')
        self.assertEqual(group.add_rel_cfg_vars.extra_var.get(), 'value')
        self.assertRaisesRegex(ScriptError,
                               r'bad type for value of release config '
                               r'variable add_rel_cfg_vars\.extra_var',
                               group.add_rel_cfg_vars.extra_var.set,
                               None)
        group.add_rel_cfg_vars.extra_var.set('other value')


class ComponentInConfigTestCase(unittest.TestCase):

    """Test the ComponentInConfig class."""

    def setUp(self):
        """Set up a ComponentInConfig test."""
        self.context = ScriptContext(['sourcery.selftests'])

    def test_init(self):
        """Test ComponentInConfig.__init__."""
        group = ConfigVarGroup(self.context, 'name')
        component = ComponentInConfig(
            'generic', 'second', group,
            sourcery.selftests.components.generic.Component)
        self.assertEqual(component.orig_name, 'generic')
        self.assertEqual(component.copy_name, 'second')
        self.assertIs(component.vars, group)
        self.assertIs(component.cls,
                      sourcery.selftests.components.generic.Component)


class AddReleaseConfigArgTestCase(unittest.TestCase):

    """Test the add_release_config_arg function."""

    def test_add_release_config_arg(self):
        """Test add_release_config_arg."""
        parser = argparse.ArgumentParser()
        add_release_config_arg(parser)
        args = parser.parse_args(['test.cfg'])
        self.assertEqual(args.release_config, 'test.cfg')


class ReleaseConfigPathLoaderSub(ReleaseConfigPathLoader):

    """Subclass of ReleaseConfigPathLoader for test purposes."""

    bootstrap_components = ('release_configs', 'sourcery_builder')

    def branch_to_vc(self, relcfg, component, branch):
        return GitVC(relcfg.context, '/some/where/%s.git' % component, branch)


class ReleaseConfigPathLoaderTar(ReleaseConfigPathLoader):

    """Subclass of ReleaseConfigPathLoader for test purposes."""

    bootstrap_components = ('release_configs', 'sourcery_builder')

    def __init__(self, tar_dir):
        self.tar_dir = tar_dir

    def branch_to_vc(self, relcfg, component, branch):
        return TarVC(relcfg.context,
                     os.path.join(
                         self.tar_dir,
                         '%s-%s.tar' % (component,
                                        self.branch_to_version(branch))))


class ReleaseConfigLoaderTestCase(unittest.TestCase):

    """Test the ReleaseConfigLoader class and subclasses."""

    def setUp(self):
        """Set up a release config test."""
        self.context = ScriptContext(['sourcery.selftests'])
        self.parser = argparse.ArgumentParser()
        self.tempdir_td = tempfile.TemporaryDirectory()
        self.tempdir = self.tempdir_td.name
        add_common_options(self.parser, self.tempdir)
        os.makedirs(os.path.join(self.tempdir, '1/2/3'))
        os.makedirs(os.path.join(self.tempdir, 'src/release-configs-x-y/1'))

    def tearDown(self):
        """Tear down a release config test."""
        self.tempdir_td.cleanup()

    def temp_config_file(self):
        """Return the path to the test config file."""
        return os.path.join(self.tempdir, 'test.cfg')

    def temp_config_write(self, text):
        """Write text to the test config file."""
        with open(self.temp_config_file(), 'w', encoding='utf-8') as file:
            file.write(text)

    def test_load_config_text(self):
        """Test load_config, ReleaseConfigTextLoader case."""
        # get_config_text, add_cfg_vars_extra, get_context_wrap_extra
        # and apply_overrides are interfaces for subclasses to
        # override and are not useful to test directly.  Here we test
        # the main functionality of loading configs (but not the work
        # done in the ReleaseConfig class).
        loader = ReleaseConfigTextLoader()
        args = self.parser.parse_args([])
        relcfg_text = ('cfg.add_component("generic")\n'
                       'cfg.generic.vc.set(GitVC("dummy"))\n'
                       'cfg.generic.version.set("1.23")\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, args)
        self.assertIsInstance(relcfg.generic.vc.get(), GitVC)
        self.assertEqual(relcfg.generic.version.get(), '1.23')
        relcfg_text = ('cfg.add_component("generic")\n'
                       'cfg.generic.vc.set(SvnVC("dummy"))\n'
                       'cfg.generic.version.set("1.23")\n'
                       'cfg.build.set(PkgHost("x86_64-linux-gnu"))\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, args)
        self.assertIsInstance(relcfg.generic.vc.get(), SvnVC)
        self.assertIsInstance(relcfg.build.get(), PkgHost)
        self.assertEqual(relcfg.build.get().name, 'x86_64-linux-gnu')
        self.assertIs(relcfg.build.get().context, self.context)
        relcfg_text = ('cfg.add_component("generic")\n'
                       'cfg.generic.vc.set(TarVC("dummy"))\n'
                       'cfg.generic.version.set("1.23")\n'
                       'cfg.build.set(PkgHost("x86_64-linux-gnu", '
                       'BuildCfg("x86_64-linux-gnu", "x86_64-linux-gnu", '
                       '"i686-pc-linux-gnu-", ("-m64", ))))\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, args)
        self.assertIsInstance(relcfg.generic.vc.get(), TarVC)
        build_cfg = relcfg.build.get().build_cfg
        self.assertIsInstance(build_cfg, BuildCfg)
        self.assertEqual(build_cfg.tool('gcc'),
                         ['i686-pc-linux-gnu-gcc', '-m64'])

    def test_load_config_path(self):
        """Test load_config, ReleaseConfigPathLoader case."""
        # This specifically tests the loading of configs from files,
        # with the detailed testing of how contents of configs are
        # handled (e.g., names defined when reading a config) being
        # done in test_load_config_text and elsewhere.
        loader = ReleaseConfigPathLoader()
        args = self.parser.parse_args([])
        relcfg_text = ('cfg.add_component("generic")\n'
                       'cfg.generic.vc.set(GitVC("dummy"))\n'
                       'cfg.generic.version.set("1.23")\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        self.temp_config_write(relcfg_text)
        relcfg = ReleaseConfig(self.context, self.temp_config_file(), loader,
                               args)
        self.assertIsInstance(relcfg.generic.vc.get(), GitVC)
        self.assertEqual(relcfg.generic.version.get(), '1.23')
        # Test use of 'include' in configs.
        self.temp_config_write('cfg.add_component("generic")\n'
                               'include("1/2/3/test.inc")\n'
                               'cfg.target.set("aarch64-linux-gnu")\n')
        with open(os.path.join(self.tempdir, '1/2/3/test.inc'), 'w',
                  encoding='utf-8') as file:
            file.write('cfg.generic.vc.set(GitVC("dummy"))\n'
                       'include("../../more.inc")\n'
                       'include("../other.inc")\n')
        with open(os.path.join(self.tempdir, '1/more.inc'), 'w',
                  encoding='utf-8') as file:
            file.write('cfg.generic.version.set("1.23")\n')
        with open(os.path.join(self.tempdir, '1/2/other.inc'), 'w',
                  encoding='utf-8') as file:
            file.write('cfg.build.set("x86_64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, self.temp_config_file(), loader,
                               args)
        self.assertIsInstance(relcfg.generic.vc.get(), GitVC)
        self.assertEqual(relcfg.generic.version.get(), '1.23')
        self.assertEqual(relcfg.build.get().name, 'x86_64-linux-gnu')
        self.assertEqual(relcfg.target.get(), 'aarch64-linux-gnu')

    def test_load_config_path_branch(self):
        """Test load_config, ReleaseConfigPathLoader case, branch named."""
        loader = ReleaseConfigPathLoader()
        args = self.parser.parse_args([])
        relcfg_text = ('cfg.add_component("generic")\n'
                       'cfg.generic.vc.set(GitVC("dummy"))\n'
                       'cfg.generic.version.set("1.23")\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg_dir = os.path.join(self.tempdir, 'src/release-configs-x-y')
        relcfg_file = os.path.join(relcfg_dir, 'test.cfg')
        with open(relcfg_file, 'w', encoding='utf-8') as file:
            file.write(relcfg_text)
        relcfg = ReleaseConfig(self.context, 'x/y:test.cfg', loader, args)
        self.assertIsInstance(relcfg.generic.vc.get(), GitVC)
        self.assertEqual(relcfg.generic.version.get(), '1.23')
        with open(os.path.join(relcfg_dir, '1/test.cfg'), 'w',
                  encoding='utf-8') as file:
            file.write('cfg.add_component("generic")\n'
                       'cfg.generic.vc.set(GitVC("dummy"))\n'
                       'cfg.generic.version.set("1.23")\n'
                       'include("../test.inc")\n')
        with open(os.path.join(relcfg_dir, 'test.inc'), 'w',
                  encoding='utf-8') as file:
            file.write('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("arm-linux-gnueabi")\n')
        relcfg = ReleaseConfig(self.context, 'x/y:1/test.cfg', loader, args)
        self.assertIsInstance(relcfg.generic.vc.get(), GitVC)
        self.assertEqual(relcfg.generic.version.get(), '1.23')
        self.assertEqual(relcfg.build.get().name, 'x86_64-linux-gnu')
        self.assertEqual(relcfg.target.get(), 'arm-linux-gnueabi')

    def test_load_config_path_branch_errors(self):
        """Test load_config, ReleaseConfigPathLoader branch case errors."""
        loader = ReleaseConfigPathLoader()
        args = self.parser.parse_args([])
        relcfg_dir = os.path.join(self.tempdir, 'src/release-configs-x-y')
        relcfg_file = os.path.join(relcfg_dir, 'test.cfg')
        with open(relcfg_file, 'w', encoding='utf-8') as file:
            file.write('include("../bad-path.inc")\n')
        with open(os.path.join(self.tempdir, 'src/example'), 'w',
                  encoding='utf-8') as file:
            file.write('\n')
        self.assertRaisesRegex(ScriptError,
                               'release config path .* outside directory',
                               ReleaseConfig, self.context, 'x/y:../example',
                               loader, args)
        self.assertRaisesRegex(ScriptError,
                               'release config path .* outside directory',
                               ReleaseConfig, self.context, 'x/y:/dev/null',
                               loader, args)
        self.assertRaisesRegex(ScriptError,
                               'release config path .* outside directory',
                               ReleaseConfig, self.context, 'x/y:test.cfg',
                               loader, args)

    def test_load_config_path_sub_branch(self):
        """Test load_config, ReleaseConfigPathLoaderSub case, branch named."""
        loader = ReleaseConfigPathLoaderSub()
        args = self.parser.parse_args([])
        relcfg_text = ('cfg.add_component("sourcery_builder")\n'
                       'cfg.sourcery_builder.vc.set(GitVC('
                       '"/some/where/sourcery_builder.git", "x/y"))\n'
                       'cfg.sourcery_builder.version.set("x-y")\n'
                       'cfg.add_component("release_configs")\n'
                       'cfg.release_configs.source_type.set("open")\n'
                       'cfg.release_configs.vc.set(GitVC('
                       '"/some/where/release_configs.git", "x/y"))\n'
                       'cfg.release_configs.version.set("x-y")\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg_dir = os.path.join(self.tempdir, 'src/release-configs-x-y')
        relcfg_file = os.path.join(relcfg_dir, 'test.cfg')
        with open(relcfg_file, 'w', encoding='utf-8') as file:
            file.write(relcfg_text)
        relcfg = ReleaseConfig(self.context, 'x/y:test.cfg', loader, args)
        self.assertEqual(relcfg.script_full.get(),
                         os.path.join(
                             self.tempdir,
                             'src/sourcery-builder-x-y/sourcery-builder'))
        self.assertEqual(relcfg.bootstrap_components_vc.get(),
                         {'release_configs':
                          GitVC(self.context,
                                '/some/where/release_configs.git', 'x/y'),
                          'sourcery_builder':
                          GitVC(self.context,
                                '/some/where/sourcery_builder.git', 'x/y')})
        self.assertEqual(relcfg.bootstrap_components_version.get(),
                         {'release_configs': 'x-y',
                          'sourcery_builder': 'x-y'})

    def test_load_config_path_sub_branch_errors(self):
        """Test load_config, ReleaseConfigPathLoaderSub branch case errors."""
        loader = ReleaseConfigPathLoaderSub()
        args = self.parser.parse_args([])
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg_dir = os.path.join(self.tempdir, 'src/release-configs-x-y')
        relcfg_file = os.path.join(relcfg_dir, 'test.cfg')
        with open(relcfg_file, 'w', encoding='utf-8') as file:
            file.write(relcfg_text)
        self.assertRaisesRegex(ScriptError,
                               'component release_configs not in config',
                               ReleaseConfig, self.context, 'x/y:test.cfg',
                               loader, args)
        relcfg_text = ('cfg.add_component("sourcery_builder")\n'
                       'cfg.sourcery_builder.vc.set(GitVC('
                       '"/some/where/sourcery_builder.git", "x/y"))\n'
                       'cfg.sourcery_builder.version.set("x-y")\n'
                       'cfg.sourcery_builder.srcdirname.set("sb")\n'
                       'cfg.add_component("release_configs")\n'
                       'cfg.release_configs.source_type.set("open")\n'
                       'cfg.release_configs.vc.set(GitVC('
                       '"/some/where/release_configs.git", "x/y"))\n'
                       'cfg.release_configs.version.set("x-y")\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        with open(relcfg_file, 'w', encoding='utf-8') as file:
            file.write(relcfg_text)
        self.assertRaisesRegex(ScriptError,
                               'sourcery_builder source directory name is '
                               'sb, expected sourcery-builder',
                               ReleaseConfig, self.context, 'x/y:test.cfg',
                               loader, args)
        relcfg_text = ('cfg.add_component("sourcery_builder")\n'
                       'cfg.sourcery_builder.vc.set(GitVC('
                       '"/some/where/sourcery_builder.git", "x/y"))\n'
                       'cfg.sourcery_builder.version.set("xy")\n'
                       'cfg.add_component("release_configs")\n'
                       'cfg.release_configs.source_type.set("open")\n'
                       'cfg.release_configs.vc.set(GitVC('
                       '"/some/where/release_configs.git", "x/y"))\n'
                       'cfg.release_configs.version.set("x-y")\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        with open(relcfg_file, 'w', encoding='utf-8') as file:
            file.write(relcfg_text)
        self.assertRaisesRegex(ScriptError,
                               'sourcery_builder version is xy, expected x-y',
                               ReleaseConfig, self.context, 'x/y:test.cfg',
                               loader, args)
        relcfg_text = ('cfg.add_component("sourcery_builder")\n'
                       'cfg.sourcery_builder.vc.set(GitVC('
                       '"/some/other/sourcery_builder.git", "x/y"))\n'
                       'cfg.sourcery_builder.version.set("x-y")\n'
                       'cfg.add_component("release_configs")\n'
                       'cfg.release_configs.source_type.set("open")\n'
                       'cfg.release_configs.vc.set(GitVC('
                       '"/some/where/release_configs.git", "x/y"))\n'
                       'cfg.release_configs.version.set("x-y")\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        with open(relcfg_file, 'w', encoding='utf-8') as file:
            file.write(relcfg_text)
        self.assertRaisesRegex(ScriptError,
                               'sourcery_builder sources from GitVC.*, '
                               'expected GitVC',
                               ReleaseConfig, self.context, 'x/y:test.cfg',
                               loader, args)

    def test_load_config_path_bootstrap(self):
        """Test load_config, ReleaseConfigPathLoader, bootstrap case."""
        loader = ReleaseConfigPathLoaderTar(self.tempdir)
        self.context.argv = ['test', 'argv']
        self.context.bootstrap_command = True
        self.context.execve = unittest.mock.MagicMock()
        self.context.silent = True
        self.context.execute_silent = True
        args = self.parser.parse_args([])
        shutil.rmtree(os.path.join(self.tempdir, 'src'))
        relcfg_text = ('cfg.add_component("sourcery_builder")\n'
                       'cfg.sourcery_builder.vc.set(TarVC('
                       '"%s/sourcery_builder-y-z.tar"))\n'
                       'cfg.sourcery_builder.version.set("y-z")\n'
                       'cfg.add_component("release_configs")\n'
                       'cfg.release_configs.source_type.set("open")\n'
                       'cfg.release_configs.vc.set(TarVC('
                       '"%s/release_configs-y-z.tar"))\n'
                       'cfg.release_configs.version.set("y-z")\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       % (self.tempdir, self.tempdir))
        test_input_dir = os.path.join(self.tempdir, 'input')
        create_files(test_input_dir,
                     ['empty', 'rc'],
                     {'rc/test.cfg': relcfg_text},
                     {})
        subprocess.run(['tar', '-c', '-f', '../sourcery_builder-y-z.tar',
                        'empty'],
                       cwd=test_input_dir, check=True)
        subprocess.run(['tar', '-c', '-f', '../release_configs-y-z.tar',
                        'rc'],
                       cwd=test_input_dir, check=True)
        relcfg = ReleaseConfig(self.context, 'y/z:test.cfg', loader, args)
        self.assertEqual(self.context.script_full, os.path.join(
            self.tempdir, 'src/sourcery-builder-y-z/sourcery-builder'))
        self.context.execve.assert_called_once_with(
            self.context.interp,
            self.context.script_command() + ['test', 'argv'],
            self.context.environ)
        self.assertEqual(read_files(os.path.join(self.tempdir, 'src')),
                         ({'release-configs-y-z', 'sourcery-builder-y-z'},
                          {'release-configs-y-z/test.cfg': relcfg_text},
                          {}))
        self.assertEqual(relcfg.target.get(), 'aarch64-linux-gnu')
        # Even with scripts and release configs checked out, bootstrap
        # still needed if the script run was wrong.
        self.context.execve.reset_mock()
        self.context.script_full = self.context.orig_script_full
        relcfg = ReleaseConfig(self.context, 'y/z:test.cfg', loader, args)
        self.assertEqual(self.context.script_full, os.path.join(
            self.tempdir, 'src/sourcery-builder-y-z/sourcery-builder'))
        self.context.execve.assert_called_once_with(
            self.context.interp,
            self.context.script_command() + ['test', 'argv'],
            self.context.environ)
        self.assertEqual(read_files(os.path.join(self.tempdir, 'src')),
                         ({'release-configs-y-z', 'sourcery-builder-y-z'},
                          {'release-configs-y-z/test.cfg': relcfg_text},
                          {}))

    def test_path_branch_to_version(self):
        """Test ReleaseConfigPathLoader.branch_to_version."""
        # This function is not particularly useful as an external
        # interface, but is tested here anyway.
        loader = ReleaseConfigPathLoader()
        self.assertEqual(loader.branch_to_version('example'), 'example')
        self.assertEqual(loader.branch_to_version('sub/dir'), 'sub-dir')
        self.assertEqual(loader.branch_to_version('sub/dir/2'), 'sub-dir-2')

    def test_path_branch_to_srcdir(self):
        """Test ReleaseConfigPathLoader.branch_to_srcdir."""
        # This function is not particularly useful as an external
        # interface, but is tested here anyway.
        relcfg = unittest.mock.MagicMock()
        relcfg.args = unittest.mock.MagicMock()
        relcfg.args.srcdir = '/src/dir'
        loader = ReleaseConfigPathLoader()
        self.assertEqual(loader.branch_to_srcdir(relcfg, 'release_configs',
                                                 'x/y'),
                         '/src/dir/release-configs-x-y')

    def test_path_branch_to_script(self):
        """Test ReleaseConfigPathLoader.branch_to_script."""
        # This function is not particularly useful as an external
        # interface, but is tested here anyway.
        relcfg = unittest.mock.MagicMock()
        relcfg.args = unittest.mock.MagicMock()
        relcfg.args.srcdir = '/src/dir'
        loader = ReleaseConfigPathLoader()
        self.assertEqual(loader.branch_to_script(relcfg, 'x/y'),
                         '/src/dir/sourcery-builder-x-y/sourcery-builder')

    def test_path_get_config_path(self):
        """Test ReleaseConfigPathLoader.get_config_path."""
        # This function is not particularly useful as an external
        # interface, but is tested here anyway.
        relcfg = unittest.mock.MagicMock()
        relcfg.args = unittest.mock.MagicMock()
        relcfg.args.srcdir = '/src/dir'
        loader = ReleaseConfigPathLoader()
        self.assertEqual(loader.get_config_path(relcfg, 'a/b.cfg'),
                         ('a/b.cfg', '/'))
        self.assertEqual(loader.get_config_path(relcfg, 'p/q/r:a/b.cfg'),
                         ('/src/dir/release-configs-p-q-r/a/b.cfg',
                          '/src/dir/release-configs-p-q-r'))


class ReleaseConfigTestCase(unittest.TestCase):

    """Test the ReleaseConfig class."""

    def setUp(self):
        """Set up a ReleaseConfig test."""
        self.context = ScriptContext(['sourcery.selftests'])
        self.parser = argparse.ArgumentParser()
        add_common_options(self.parser, os.getcwd())
        self.args = self.parser.parse_args([])

    def test_init(self):
        """Test ReleaseConfig.__init__."""
        # __getattr__ is effectively covered by this and other tests,
        # so not tested separately.
        loader = ReleaseConfigTextLoader()
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        self.assertIs(relcfg.args, self.args)
        self.assertIs(relcfg.context, self.context)
        # Verify SOURCE_DATE_EPOCH in env_set.
        self.assertEqual(relcfg.env_set.get()['SOURCE_DATE_EPOCH'],
                         str(relcfg.source_date_epoch.get()))
        # Verify build and hosts settings.
        self.assertIsInstance(relcfg.build.get(), PkgHost)
        self.assertEqual(relcfg.build.get().name, 'x86_64-linux-gnu')
        self.assertEqual(len(relcfg.hosts.get()), 1)
        self.assertIsInstance(relcfg.hosts.get()[0], PkgHost)
        self.assertIs(relcfg.hosts.get()[0], relcfg.build.get())
        # Test case of hosts set explicitly using strings: verify same
        # PkgHost object used as first host.
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.hosts.set(("x86_64-linux-gnu", '
                       '"x86_64-w64-mingw32"))\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        self.assertIsInstance(relcfg.build.get(), PkgHost)
        self.assertEqual(relcfg.build.get().name, 'x86_64-linux-gnu')
        self.assertEqual(len(relcfg.hosts.get()), 2)
        self.assertIsInstance(relcfg.hosts.get()[0], PkgHost)
        self.assertIs(relcfg.hosts.get()[0], relcfg.build.get())
        self.assertIsInstance(relcfg.hosts.get()[1], PkgHost)
        self.assertEqual(relcfg.hosts.get()[1].name, 'x86_64-w64-mingw32')
        # Test case of PkgHost objects used directly for build and
        # hosts.
        relcfg_text = ('build = PkgHost("x86_64-linux-gnu")\n'
                       'cfg.build.set(build)\n'
                       'cfg.hosts.set((build, PkgHost("i686-pc-linux-gnu")))\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        self.assertIsInstance(relcfg.build.get(), PkgHost)
        self.assertEqual(relcfg.build.get().name, 'x86_64-linux-gnu')
        self.assertEqual(len(relcfg.hosts.get()), 2)
        self.assertIsInstance(relcfg.hosts.get()[0], PkgHost)
        self.assertIs(relcfg.hosts.get()[0], relcfg.build.get())
        self.assertIsInstance(relcfg.hosts.get()[1], PkgHost)
        self.assertEqual(relcfg.hosts.get()[1].name, 'i686-pc-linux-gnu')
        # Test internal variables set by __init__.
        self.assertEqual(relcfg.installdir_rel.get(), 'opt/toolchain')
        self.assertEqual(relcfg.bindir.get(), '/opt/toolchain/bin')
        self.assertEqual(relcfg.bindir_rel.get(), 'opt/toolchain/bin')
        self.assertEqual(relcfg.sysroot.get(),
                         '/opt/toolchain/aarch64-linux-gnu/libc')
        self.assertEqual(relcfg.sysroot_rel.get(),
                         'opt/toolchain/aarch64-linux-gnu/libc')
        self.assertEqual(relcfg.info_dir_rel.get(),
                         'opt/toolchain/share/info/dir')
        self.assertEqual(relcfg.version.get(), '1.0-1')
        self.assertEqual(relcfg.pkg_name_no_target_build.get(),
                         'toolchain-1.0')
        self.assertEqual(relcfg.pkg_name_full.get(),
                         'toolchain-1.0-1-aarch64-linux-gnu')
        self.assertEqual(relcfg.pkg_name_no_version.get(),
                         'toolchain-aarch64-linux-gnu')
        # Test per-component internal variables set by __init__.
        relcfg_text = ('cfg.add_component("generic")\n'
                       'cfg.generic.version.set("1.23")\n'
                       'cfg.generic.vc.set(TarVC("dummy"))\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        self.assertEqual(relcfg.generic.srcdir.get(),
                         os.path.join(self.args.srcdir, 'generic-1.23'))
        relcfg_text = ('cfg.add_component("generic")\n'
                       'cfg.generic.version.set("4.56")\n'
                       'cfg.generic.vc.set(TarVC("dummy"))\n'
                       'cfg.generic.srcdirname.set("other-name")\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        self.assertEqual(relcfg.generic.srcdir.get(),
                         os.path.join(self.args.srcdir, 'other-name-4.56'))
        # Test that the ConfigVarGroup has been finalized.
        self.assertRaisesRegex(ScriptError,
                               'release config variable installdir modified '
                               'after finalization',
                               relcfg.installdir.set, '/opt/test')

    def test_init_errors(self):
        """Test errors from ReleaseConfig.__init__."""
        loader = ReleaseConfigTextLoader()
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       'cfg.bootstrap_components_vc.set({'
                       '"sourcery_builder": GitVC("/some/where")})\n'
                       'cfg.bootstrap_components_version.set({'
                       '"release_configs": "master"})\n')
        self.assertRaisesRegex(ScriptError,
                               'inconsistent set of bootstrap components',
                               ReleaseConfig, self.context, relcfg_text,
                               loader, self.args)
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       'cfg.bootstrap_components_vc.set({'
                       '"sourcery_builder": GitVC("/some/where")})\n'
                       'cfg.bootstrap_components_version.set({'
                       '"sourcery_builder": "master"})\n')
        self.assertRaisesRegex(ScriptError,
                               'component sourcery_builder not in config',
                               ReleaseConfig, self.context, relcfg_text,
                               loader, self.args)
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       'cfg.bootstrap_components_vc.set({'
                       '"sourcery_builder": GitVC("/some/where")})\n'
                       'cfg.bootstrap_components_version.set({'
                       '"sourcery_builder": "master"})\n'
                       'cfg.add_component("sourcery_builder")\n'
                       'cfg.sourcery_builder.source_type.set("none")\n')
        self.assertRaisesRegex(ScriptError,
                               'sourcery_builder has no sources',
                               ReleaseConfig, self.context, relcfg_text,
                               loader, self.args)
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       'cfg.bootstrap_components_vc.set({'
                       '"sourcery_builder": GitVC("/some/where")})\n'
                       'cfg.bootstrap_components_version.set({'
                       '"sourcery_builder": "master"})\n'
                       'cfg.add_component("sourcery_builder")\n'
                       'cfg.sourcery_builder.srcdirname.set("sourcery")\n')
        self.assertRaisesRegex(ScriptError,
                               'sourcery_builder source directory name is '
                               'sourcery, expected sourcery-builder',
                               ReleaseConfig, self.context, relcfg_text,
                               loader, self.args)
        # This one is OK.
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       'cfg.bootstrap_components_vc.set({'
                       '"sourcery_builder": GitVC("/some/where")})\n'
                       'cfg.bootstrap_components_version.set({'
                       '"sourcery_builder": "master"})\n'
                       'cfg.add_component("sourcery_builder")\n'
                       'cfg.sourcery_builder.vc.set(GitVC("/some/where"))\n'
                       'cfg.sourcery_builder.version.set("master")\n')
        ReleaseConfig(self.context, relcfg_text, loader, self.args)
        # Variants on it with different vc or version settings aren't OK.
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       'cfg.bootstrap_components_vc.set({'
                       '"sourcery_builder": GitVC("/some/where")})\n'
                       'cfg.bootstrap_components_version.set({'
                       '"sourcery_builder": "master"})\n'
                       'cfg.add_component("sourcery_builder")\n'
                       'cfg.sourcery_builder.vc.set(GitVC("/some/other"))\n'
                       'cfg.sourcery_builder.version.set("master")\n')
        self.assertRaisesRegex(ScriptError,
                               r"sourcery_builder sources from "
                               r"GitVC\('/some/other', 'master'\), expected "
                               r"GitVC\('/some/where', 'master'\)",
                               ReleaseConfig, self.context, relcfg_text,
                               loader, self.args)
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       'cfg.bootstrap_components_vc.set({'
                       '"sourcery_builder": GitVC("/some/where")})\n'
                       'cfg.bootstrap_components_version.set({'
                       '"sourcery_builder": "master"})\n'
                       'cfg.add_component("sourcery_builder")\n'
                       'cfg.sourcery_builder.vc.set(GitVC("/some/where"))\n'
                       'cfg.sourcery_builder.version.set("other")\n')
        self.assertRaisesRegex(ScriptError,
                               'sourcery_builder version is other, expected '
                               'master',
                               ReleaseConfig, self.context, relcfg_text,
                               loader, self.args)
        # Also test a case with more than one bootstrap component.
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       'cfg.bootstrap_components_vc.set({'
                       '"release_configs": GitVC("/some/relcfg"), '
                       '"sourcery_builder": GitVC("/some/where")})\n'
                       'cfg.bootstrap_components_version.set({'
                       '"release_configs": "master", '
                       '"sourcery_builder": "master"})\n'
                       'cfg.add_component("release_configs")\n'
                       'cfg.release_configs.source_type.set("open")\n'
                       'cfg.release_configs.vc.set(GitVC("/some/relcfg"))\n'
                       'cfg.release_configs.version.set("master")\n'
                       'cfg.add_component("sourcery_builder")\n'
                       'cfg.sourcery_builder.vc.set(GitVC("/some/where"))\n'
                       'cfg.sourcery_builder.version.set("master")\n')
        ReleaseConfig(self.context, relcfg_text, loader, self.args)
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       'cfg.bootstrap_components_vc.set({'
                       '"release_configs": GitVC("/some/relcfg"), '
                       '"sourcery_builder": GitVC("/some/where")})\n'
                       'cfg.bootstrap_components_version.set({'
                       '"release_configs": "master", '
                       '"sourcery_builder": "master"})\n'
                       'cfg.add_component("release_configs")\n'
                       'cfg.release_configs.source_type.set("open")\n'
                       'cfg.release_configs.vc.set(GitVC("/some/relcfg"))\n'
                       'cfg.release_configs.version.set("master")\n'
                       'cfg.add_component("sourcery_builder")\n'
                       'cfg.sourcery_builder.vc.set(GitVC("/some/other"))\n'
                       'cfg.sourcery_builder.version.set("master")\n')
        self.assertRaisesRegex(ScriptError,
                               r"sourcery_builder sources from "
                               r"GitVC\('/some/other', 'master'\), expected "
                               r"GitVC\('/some/where', 'master'\)",
                               ReleaseConfig, self.context, relcfg_text,
                               loader, self.args)
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       'cfg.bootstrap_components_vc.set({'
                       '"release_configs": GitVC("/some/relcfg"), '
                       '"sourcery_builder": GitVC("/some/where")})\n'
                       'cfg.bootstrap_components_version.set({'
                       '"release_configs": "master", '
                       '"sourcery_builder": "master"})\n'
                       'cfg.add_component("release_configs")\n'
                       'cfg.release_configs.source_type.set("open")\n'
                       'cfg.release_configs.vc.set(GitVC("/some/relcfg"))\n'
                       'cfg.release_configs.version.set("master")\n'
                       'cfg.add_component("sourcery_builder")\n'
                       'cfg.sourcery_builder.vc.set(GitVC("/some/where"))\n'
                       'cfg.sourcery_builder.version.set("other")\n')
        self.assertRaisesRegex(ScriptError,
                               'sourcery_builder version is other, expected '
                               'master',
                               ReleaseConfig, self.context, relcfg_text,
                               loader, self.args)
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.hosts.set(("i686-pc-linux-gnu", '
                       '"x86_64-linux-gnu"))\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        self.assertRaisesRegex(ScriptError,
                               'first host not the same as build system',
                               ReleaseConfig, self.context, relcfg_text,
                               loader, self.args)
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       'cfg.add_component("no_source_type")\n')
        self.assertRaisesRegex(ScriptError,
                               'no source type specified for no_source_type',
                               ReleaseConfig, self.context, relcfg_text,
                               loader, self.args)
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       'cfg.add_component("generic")\n'
                       'cfg.generic.vc.set(TarVC("dummy"))\n')
        self.assertRaisesRegex(ScriptError,
                               'no version specified for generic',
                               ReleaseConfig, self.context, relcfg_text,
                               loader, self.args)
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       'cfg.add_component("generic")\n'
                       'cfg.generic.version.set("1.0")\n')
        self.assertRaisesRegex(ScriptError,
                               'no version control location specified for '
                               'generic',
                               ReleaseConfig, self.context, relcfg_text,
                               loader, self.args)
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       'cfg.add_component("generic")\n'
                       'cfg.generic.source_type.set("closed")\n'
                       'cfg.generic.vc.set(TarVC("dummy"))\n')
        self.assertRaisesRegex(ScriptError,
                               'no version specified for generic',
                               ReleaseConfig, self.context, relcfg_text,
                               loader, self.args)
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       'cfg.add_component("generic")\n'
                       'cfg.generic.source_type.set("closed")\n'
                       'cfg.generic.version.set("1.0")\n')
        self.assertRaisesRegex(ScriptError,
                               'no version control location specified for '
                               'generic',
                               ReleaseConfig, self.context, relcfg_text,
                               loader, self.args)

    def test_list_vars(self):
        """Test ReleaseConfig.list_vars."""
        loader = ReleaseConfigTextLoader()
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        self.assertEqual(relcfg.list_vars(),
                         ['bindir', 'bindir_rel', 'bootstrap_components_vc',
                          'bootstrap_components_version', 'build', 'env_set',
                          'hosts', 'info_dir_rel', 'installdir',
                          'installdir_rel', 'interp', 'pkg_build',
                          'pkg_name_full', 'pkg_name_no_target_build',
                          'pkg_name_no_version', 'pkg_prefix', 'pkg_version',
                          'script_full', 'source_date_epoch', 'sysroot',
                          'sysroot_rel', 'target', 'version'])

    def test_add_component(self):
        """Test ReleaseConfig.add_component."""
        loader = ReleaseConfigTextLoader()
        # Components may be added more than once.
        relcfg_text = ('cfg.add_component("generic")\n'
                       'cfg.add_component("generic")\n'
                       'cfg.generic.version.set("1")\n'
                       'cfg.generic.vc.set(TarVC("dummy"))\n'
                       'cfg.add_component("postcheckout")\n'
                       'cfg.postcheckout.version.set("2")\n'
                       'cfg.postcheckout.vc.set(TarVC("dummy"))\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        self.assertEqual(relcfg.list_components(),
                         (relcfg.get_component('generic'),
                          relcfg.get_component('package'),
                          relcfg.get_component('postcheckout')))

    def test_add_component_errors(self):
        """Test errors from ReleaseConfig.add_component."""
        loader = ReleaseConfigTextLoader()
        relcfg_text = ('cfg.add_component("no_such_component")\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        self.assertRaisesRegex(ScriptError,
                               'unknown component no_such_component',
                               ReleaseConfig, self.context, relcfg_text,
                               loader, self.args)

    def test_list_components(self):
        """Test ReleaseConfig.list_components."""
        loader = ReleaseConfigTextLoader()
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        self.assertEqual(relcfg.list_components(),
                         (relcfg.get_component('package'),))
        relcfg_text = ('cfg.add_component("postcheckout")\n'
                       'cfg.postcheckout.version.set("2")\n'
                       'cfg.postcheckout.vc.set(TarVC("dummy"))\n'
                       'cfg.add_component("generic")\n'
                       'cfg.generic.version.set("1")\n'
                       'cfg.generic.vc.set(TarVC("dummy"))\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        self.assertEqual(relcfg.list_components(),
                         (relcfg.get_component('generic'),
                          relcfg.get_component('package'),
                          relcfg.get_component('postcheckout')))

    def test_list_source_components(self):
        """Test ReleaseConfig.list_source_components."""
        loader = ReleaseConfigTextLoader()
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        self.assertEqual(relcfg.list_source_components(), ())
        relcfg_text = ('cfg.add_component("postcheckout")\n'
                       'cfg.postcheckout.version.set("2")\n'
                       'cfg.postcheckout.vc.set(TarVC("dummy"))\n'
                       'cfg.add_component("generic")\n'
                       'cfg.generic.version.set("1")\n'
                       'cfg.generic.vc.set(TarVC("dummy"))\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        self.assertEqual(relcfg.list_source_components(),
                         (relcfg.get_component('generic'),
                          relcfg.get_component('postcheckout')))
        relcfg_text = ('cfg.add_component("postcheckout")\n'
                       'cfg.postcheckout.version.set("2")\n'
                       'cfg.postcheckout.vc.set(TarVC("dummy"))\n'
                       'cfg.postcheckout.source_type.set("closed")\n'
                       'cfg.add_component("generic")\n'
                       'cfg.generic.version.set("1")\n'
                       'cfg.generic.vc.set(TarVC("dummy"))\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        self.assertEqual(relcfg.list_source_components(),
                         (relcfg.get_component('generic'),
                          relcfg.get_component('postcheckout')))
        relcfg_text = ('cfg.add_component("postcheckout")\n'
                       'cfg.postcheckout.version.set("2")\n'
                       'cfg.postcheckout.vc.set(TarVC("dummy"))\n'
                       'cfg.add_component("generic")\n'
                       'cfg.generic.source_type.set("none")\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        self.assertEqual(relcfg.list_source_components(),
                         (relcfg.get_component('postcheckout'),))

    def test_get_component(self):
        """Test ReleaseConfig.get_component."""
        loader = ReleaseConfigTextLoader()
        relcfg_text = ('cfg.add_component("generic")\n'
                       'cfg.generic.version.set("1.23")\n'
                       'cfg.generic.vc.set(TarVC("dummy"))\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        component = relcfg.get_component('generic')
        self.assertIsInstance(component, ComponentInConfig)
        self.assertEqual(component.orig_name, 'generic')
        self.assertEqual(component.copy_name, 'generic')
        self.assertIs(component.cls,
                      sourcery.selftests.components.generic.Component)
        self.assertEqual(component.vars.version.get(), '1.23')

    def test_get_component_errors(self):
        """Test errors from ReleaseConfig.get_component."""
        loader = ReleaseConfigTextLoader()
        relcfg_text = ('cfg.add_component("generic")\n'
                       'cfg.generic.version.set("1.23")\n'
                       'cfg.generic.vc.set(TarVC("dummy"))\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        self.assertRaisesRegex(KeyError,
                               'postcheckout',
                               relcfg.get_component, 'postcheckout')

    def test_get_component_vars(self):
        """Test ReleaseConfig.get_component_vars."""
        loader = ReleaseConfigTextLoader()
        relcfg_text = ('cfg.add_component("generic")\n'
                       'cfg.generic.version.set("1.23")\n'
                       'cfg.generic.vc.set(TarVC("dummy"))\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        vars_group = relcfg.get_component_vars('generic')
        self.assertIsInstance(vars_group, ConfigVarGroup)
        self.assertEqual(vars_group.version.get(), '1.23')

    def test_get_component_vars_errors(self):
        """Test errors from ReleaseConfig.get_component_vars."""
        loader = ReleaseConfigTextLoader()
        relcfg_text = ('cfg.add_component("generic")\n'
                       'cfg.generic.version.set("1.23")\n'
                       'cfg.generic.vc.set(TarVC("dummy"))\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        self.assertRaisesRegex(ScriptError,
                               'component postcheckout not in config',
                               relcfg.get_component_vars, 'postcheckout')

    def test_get_component_var(self):
        """Test ReleaseConfig.get_component_var."""
        loader = ReleaseConfigTextLoader()
        relcfg_text = ('cfg.add_component("generic")\n'
                       'cfg.generic.version.set("1.23")\n'
                       'cfg.generic.vc.set(TarVC("dummy"))\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        self.assertEqual(relcfg.get_component_var('generic', 'version'),
                         '1.23')

    def test_get_component_var_errors(self):
        """Test errors from ReleaseConfig.get_component_var."""
        loader = ReleaseConfigTextLoader()
        relcfg_text = ('cfg.add_component("generic")\n'
                       'cfg.generic.version.set("1.23")\n'
                       'cfg.generic.vc.set(TarVC("dummy"))\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        self.assertRaisesRegex(ScriptError,
                               'component postcheckout not in config',
                               relcfg.get_component_var, 'postcheckout',
                               'version')
        self.assertRaisesRegex(AttributeError,
                               'no_such_variable',
                               relcfg.get_component_var, 'generic',
                               'no_such_variable')

    def test_objdir_path(self):
        """Test ReleaseConfig.objdir_path."""
        loader = ReleaseConfigTextLoader()
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        self.assertEqual(relcfg.objdir_path(None, 'example'),
                         os.path.join(self.args.objdir,
                                      'toolchain-1.0-1-aarch64-linux-gnu',
                                      'example'))
        self.assertEqual(relcfg.objdir_path(relcfg.build.get(), 'other'),
                         os.path.join(self.args.objdir,
                                      'toolchain-1.0-1-aarch64-linux-gnu',
                                      'pkg-other-x86_64-linux-gnu'))
        self.assertEqual(relcfg.objdir_path(relcfg.build.get().build_cfg,
                                            'third'),
                         os.path.join(self.args.objdir,
                                      'toolchain-1.0-1-aarch64-linux-gnu',
                                      'third-x86_64-linux-gnu'))
        build_cfg = BuildCfg('i686-pc-linux-gnu', 'some-other-name')
        self.assertEqual(relcfg.objdir_path(build_cfg, 'next'),
                         os.path.join(self.args.objdir,
                                      'toolchain-1.0-1-aarch64-linux-gnu',
                                      'next-some-other-name'))

    def test_pkgdir_path(self):
        """Test ReleaseConfig.pkgdir_path."""
        loader = ReleaseConfigTextLoader()
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        self.assertEqual(relcfg.pkgdir_path(None, '.src.tar.xz'),
                         os.path.join(self.args.pkgdir,
                                      'toolchain-1.0-1-aarch64-linux-gnu'
                                      '.src.tar.xz'))
        self.assertEqual(relcfg.pkgdir_path(relcfg.build.get(), '.tar.xz'),
                         os.path.join(self.args.pkgdir,
                                      'toolchain-1.0-1-aarch64-linux-gnu'
                                      '-x86_64-linux-gnu.tar.xz'))

    def test_install_tree_path(self):
        """Test ReleaseConfig.install_tree_path."""
        loader = ReleaseConfigTextLoader()
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        self.assertEqual(relcfg.install_tree_path(relcfg.build.get(), 'other'),
                         os.path.join(self.args.objdir,
                                      'toolchain-1.0-1-aarch64-linux-gnu',
                                      'pkg-install-trees-x86_64-linux-gnu',
                                      'other'))
        self.assertEqual(relcfg.install_tree_path(relcfg.build.get().build_cfg,
                                                  'second'),
                         os.path.join(self.args.objdir,
                                      'toolchain-1.0-1-aarch64-linux-gnu',
                                      'install-trees-x86_64-linux-gnu',
                                      'second'))
        build_cfg = BuildCfg('i686-pc-linux-gnu', 'some-other-name')
        self.assertEqual(relcfg.install_tree_path(build_cfg, 'next'),
                         os.path.join(self.args.objdir,
                                      'toolchain-1.0-1-aarch64-linux-gnu',
                                      'install-trees-some-other-name', 'next'))

    def test_install_tree_fstree(self):
        """Test ReleaseConfig.install_tree_fstree."""
        loader = ReleaseConfigTextLoader()
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        tree = relcfg.install_tree_fstree(relcfg.build.get(), 'example')
        self.assertIsInstance(tree, FSTreeCopy)
        self.assertIs(tree.context, self.context)
        self.assertEqual(tree.path,
                         relcfg.install_tree_path(relcfg.build.get(),
                                                  'example'))
        self.assertEqual(tree.install_trees, {(relcfg.build.get(), 'example')})
        tree = relcfg.install_tree_fstree(relcfg.build.get().build_cfg, 'test')
        self.assertIs(tree.context, self.context)
        self.assertEqual(tree.path,
                         relcfg.install_tree_path(relcfg.build.get().build_cfg,
                                                  'test'))
        self.assertEqual(tree.install_trees, {(relcfg.build.get().build_cfg,
                                               'test')})
