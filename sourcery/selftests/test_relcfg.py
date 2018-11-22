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

import argparse
import collections
import os
import os.path
import tempfile
import unittest

from sourcery.buildcfg import BuildCfg
from sourcery.context import add_common_options, ScriptContext, ScriptError
from sourcery.pkghost import PkgHost
from sourcery.relcfg import ConfigVarType, ConfigVarTypeList, \
    ConfigVarTypeDict, ConfigVarTypeStrEnum, ConfigVar, ConfigVarGroup, \
    ComponentInConfig, add_release_config_arg, ReleaseConfigPathLoader, \
    ReleaseConfigTextLoader, ReleaseConfig
import sourcery.selftests.components.generic
from sourcery.vc import GitVC, SvnVC, TarVC

__all__ = ['ConfigVarTypeTestCase', 'ConfigVarTestCase',
           'ConfigVarGroupTestCase', 'ComponentInConfigTestCase',
           'AddReleaseConfigArgTestCase', 'ReleaseConfigLoaderTestCase']


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

    """Test the ConfigVar class."""

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
        self.assertEqual(group.context, self.context)
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
        group.add_release_config_vars()
        # Test the list of release config variables.
        self.assertEqual(group.list_vars(),
                         ['build', 'env_set', 'hosts', 'installdir', 'interp',
                          'script_full', 'target'])
        # Test each variable's default value and type constraints.
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
        self.assertEqual(group.script_full.get(), self.context.script_full)
        self.assertRaisesRegex(ScriptError,
                               'bad type for value of release config variable '
                               'script_full',
                               group.script_full.set, 12345)
        group.script_full.set('/some/where/sourcery-builder')
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
        self.assertEqual(group.no_add_rel_cfg_vars.configure_opts.get(), [])
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
        self.assertEqual(component.vars, group)
        self.assertEqual(component.cls,
                         sourcery.selftests.components.generic.Component)


class AddReleaseConfigArgTestCase(unittest.TestCase):

    """Test the add_release_config_arg function."""

    def test_add_release_config_arg(self):
        """Test add_release_config_arg."""
        parser = argparse.ArgumentParser()
        add_release_config_arg(parser)
        args = parser.parse_args(['test.cfg'])
        self.assertEqual(args.release_config, 'test.cfg')


class ReleaseConfigLoaderTestCase(unittest.TestCase):

    """Test the ReleaseConfigLoader class and subclasses."""

    def setUp(self):
        """Set up a release config test."""
        self.context = ScriptContext(['sourcery.selftests'])
        self.parser = argparse.ArgumentParser()
        add_common_options(self.parser, os.getcwd())
        self.tempdir_td = tempfile.TemporaryDirectory()
        self.tempdir = self.tempdir_td.name

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
        # get_config_text, add_cfg_vars_extra and
        # get_context_wrap_extra are interfaces for subclasses to
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
        self.assertEqual(relcfg.build.get().context, self.context)
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
        self.assertEqual(relcfg.args, self.args)
        self.assertEqual(relcfg.context, self.context)
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
        # Test per-component internal variables set by __init__.
        relcfg_text = ('cfg.add_component("generic")\n'
                       'cfg.generic.version.set("1.23")\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        self.assertEqual(relcfg.generic.srcdir.get(),
                         os.path.join(self.args.srcdir, 'generic-1.23'))
        relcfg_text = ('cfg.add_component("generic")\n'
                       'cfg.generic.version.set("4.56")\n'
                       'cfg.generic.srcdirname.set("other-name")\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        self.assertEqual(relcfg.generic.srcdir.get(),
                         os.path.join(self.args.srcdir, 'other-name-4.56'))

    def test_init_errors(self):
        """Test errors from ReleaseConfig.__init__."""
        loader = ReleaseConfigTextLoader()
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.hosts.set(("i686-pc-linux-gnu", '
                       '"x86_64-linux-gnu"))\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        self.assertRaisesRegex(ScriptError,
                               'first host not the same as build system',
                               ReleaseConfig, self.context, relcfg_text,
                               loader, self.args)