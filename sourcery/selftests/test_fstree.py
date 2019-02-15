# Test sourcery.fstree.

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

"""Test sourcery.fstree."""

import os
import os.path
import shutil
import stat
import tempfile
import unittest

from sourcery.context import ScriptError, ScriptContext
from sourcery.fstree import MapFSTreeCopy, MapFSTreeMap, MapFSTreeSymlink, \
    FSTreeCopy, FSTreeEmpty, FSTreeSymlink, FSTreeMove, FSTreeRemove, \
    FSTreeExtract, FSTreeExtractOne, FSTreeUnion
from sourcery.selftests.support import create_files, read_files

__all__ = ['MapFSTreeTestCase', 'FSTreeTestCase']


class MapFSTreeTestCase(unittest.TestCase):

    """Test the MapFSTree class and subclasses."""

    def setUp(self):
        """Set up a MapFSTree test."""
        self.context = ScriptContext()
        self.tempdir_td = tempfile.TemporaryDirectory()
        self.tempdir = self.tempdir_td.name
        self.indir = os.path.join(self.tempdir, 'in')
        self.outdir = os.path.join(self.tempdir, 'out')

    def tearDown(self):
        """Tear down a MapFSTree test."""
        self.tempdir_td.cleanup()

    def test_init_copy(self):
        """Test valid initialization of MapFSTreeCopy."""
        create_files(self.indir, ['foo', 'foo/bar'],
                     {'a': 'file a', 'foo/b': 'file foo/b'},
                     {'dead-symlink': 'bad', 'file-symlink': 'a',
                      'dir-symlink': 'foo/bar'})
        tree = MapFSTreeCopy(self.context, os.path.join(self.indir, 'a'))
        self.assertFalse(tree.is_dir)
        tree = MapFSTreeCopy(self.context, os.path.join(self.indir, 'foo'))
        self.assertTrue(tree.is_dir)
        tree = MapFSTreeCopy(self.context, os.path.join(self.indir,
                                                        'dead-symlink'))
        self.assertFalse(tree.is_dir)
        tree = MapFSTreeCopy(self.context, os.path.join(self.indir,
                                                        'file-symlink'))
        self.assertFalse(tree.is_dir)
        tree = MapFSTreeCopy(self.context, os.path.join(self.indir,
                                                        'dir-symlink'))
        self.assertFalse(tree.is_dir)

    def test_init_copy_errors(self):
        """Test errors from initialization of MapFSTreeCopy."""
        self.assertRaises(OSError, MapFSTreeCopy, self.context, self.indir)
        os.mkdir(self.indir)
        os.mkfifo(os.path.join(self.indir, 'fifo'))
        self.assertRaisesRegex(ScriptError,
                               'bad file type for',
                               MapFSTreeCopy, self.context,
                               os.path.join(self.indir, 'fifo'))

    def test_init_map(self):
        """Test valid initialization of MapFSTreeMap."""
        create_files(self.indir, [],
                     {'a': 'file a', 'b': 'file b'}, {})
        tree_a = MapFSTreeCopy(self.context, os.path.join(self.indir, 'a'))
        tree_b = MapFSTreeCopy(self.context, os.path.join(self.indir, 'b'))
        tree = MapFSTreeMap(self.context, {'a': tree_b, 'b': tree_a})
        self.assertTrue(tree.is_dir)
        tree = MapFSTreeMap(self.context, {})
        self.assertTrue(tree.is_dir)

    def test_init_map_errors(self):
        """Test errors from initialization of MapFSTreeMap."""
        empty = MapFSTreeMap(self.context, {})
        self.assertRaisesRegex(ScriptError,
                               'bad file name in map',
                               MapFSTreeMap, self.context, {'': empty})
        self.assertRaisesRegex(ScriptError,
                               'bad file name in map',
                               MapFSTreeMap, self.context, {'.': empty})
        self.assertRaisesRegex(ScriptError,
                               'bad file name in map',
                               MapFSTreeMap, self.context, {'..': empty})
        self.assertRaisesRegex(ScriptError,
                               'bad file name in map',
                               MapFSTreeMap, self.context, {'a/b': empty})

    def test_init_symlink(self):
        """Test valid initialization of MapFSTreeSymlink."""
        tree = MapFSTreeSymlink(self.context, 'test')
        self.assertFalse(tree.is_dir)
        tree = MapFSTreeSymlink(self.context, '.')
        self.assertFalse(tree.is_dir)
        tree = MapFSTreeSymlink(self.context, '/')
        self.assertFalse(tree.is_dir)

    def test_init_symlink_errors(self):
        """Test errors from initialization of MapFSTreeSymlink."""
        self.assertRaisesRegex(ScriptError,
                               'empty symlink target',
                               MapFSTreeSymlink, self.context, '')

    def test_export(self):
        """Test exporting MapFSTree objects."""
        create_files(self.indir, ['foo', 'foo/bar'],
                     {'a': 'file a', 'foo/b': 'file foo/b'},
                     {'dead-symlink': 'bad', 'file-symlink': 'a',
                      'dir-symlink': 'foo/bar'})
        tree = MapFSTreeCopy(self.context, os.path.join(self.indir, 'a'))
        os.mkdir(self.outdir)
        tree.export(os.path.join(self.outdir, 'x'))
        self.assertEqual(read_files(self.outdir),
                         (set(), {'x': 'file a'}, {}))
        shutil.rmtree(self.outdir)
        tree = MapFSTreeCopy(self.context, os.path.join(self.indir, 'foo'))
        tree.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'bar'}, {'b': 'file foo/b'}, {}))
        shutil.rmtree(self.outdir)
        os.mkdir(self.outdir)
        tree = MapFSTreeCopy(self.context, os.path.join(self.indir,
                                                        'dir-symlink'))
        tree.export(os.path.join(self.outdir, 'x'))
        self.assertEqual(read_files(self.outdir),
                         (set(), {}, {'x': 'foo/bar'}))
        shutil.rmtree(self.outdir)
        tree = MapFSTreeCopy(self.context, self.indir)
        tree.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'foo', 'foo/bar'},
                          {'a': 'file a', 'foo/b': 'file foo/b'},
                          {'dead-symlink': 'bad', 'file-symlink': 'a',
                           'dir-symlink': 'foo/bar'}))
        srcmode = os.stat(os.path.join(self.indir, 'a')).st_mode
        destmode = os.stat(os.path.join(self.outdir, 'a')).st_mode
        self.assertEqual(srcmode, destmode)
        os.chmod(os.path.join(self.indir, 'a'), stat.S_IRWXU)
        shutil.rmtree(self.outdir)
        tree = MapFSTreeCopy(self.context, self.indir)
        tree.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'foo', 'foo/bar'},
                          {'a': 'file a', 'foo/b': 'file foo/b'},
                          {'dead-symlink': 'bad', 'file-symlink': 'a',
                           'dir-symlink': 'foo/bar'}))
        srcmode = os.stat(os.path.join(self.indir, 'a')).st_mode
        destmode = os.stat(os.path.join(self.outdir, 'a')).st_mode
        self.assertEqual(srcmode, destmode)
        shutil.rmtree(self.outdir)
        tree = MapFSTreeMap(self.context,
                            {'x': MapFSTreeCopy(self.context,
                                                os.path.join(self.indir, 'a')),
                             'y': MapFSTreeCopy(self.context,
                                                os.path.join(self.indir,
                                                             'foo')),
                             's': MapFSTreeCopy(self.context,
                                                os.path.join(self.indir,
                                                             'dir-symlink')),
                             'z': MapFSTreeCopy(self.context,
                                                os.path.join(self.indir,
                                                             'foo/bar')),
                             'empty': MapFSTreeMap(self.context, {})})
        tree.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'y', 'y/bar', 'z', 'empty'},
                          {'x': 'file a', 'y/b': 'file foo/b'},
                          {'s': 'foo/bar'}))
        shutil.rmtree(self.outdir)
        tree = MapFSTreeSymlink(self.context, 'target')
        tree.export(self.outdir)
        self.assertEqual(os.readlink(self.outdir), 'target')

    def test_export_errors(self):
        """Test errors exporting MapFSTree objects."""
        tree = MapFSTreeMap(self.context, {})
        os.mkdir(self.outdir)
        self.assertRaisesRegex(ScriptError,
                               'already exists',
                               tree.export, self.outdir)
        os.rmdir(self.outdir)
        os.symlink(self.indir, self.outdir)
        self.assertRaisesRegex(ScriptError,
                               'already exists',
                               tree.export, self.outdir)
        os.mkdir(self.indir)
        self.assertRaisesRegex(ScriptError,
                               'already exists',
                               tree.export, self.outdir)
        os.remove(self.outdir)
        with open(self.outdir, 'w', encoding='utf-8') as file:
            file.write('test')
        self.assertRaisesRegex(ScriptError,
                               'already exists',
                               tree.export, self.outdir)

    def test_union(self):
        """Test unions of MapFSTree objects."""
        create_files(self.indir,
                     ['a', 'a/foo', 'a/foo/bar', 'b', 'b/foo', 'b/x'],
                     {'a/a': 'file a/a', 'a/foo/b': 'file a/foo/b',
                      'b/foo/x': 'file b/foo/x'},
                     {'a/dead-symlink': 'bad', 'a/file-symlink': 'a',
                      'a/dir-symlink': 'foo/bar'})
        tree_a = MapFSTreeCopy(self.context, os.path.join(self.indir, 'a'))
        tree_b = MapFSTreeCopy(self.context, os.path.join(self.indir, 'b'))
        tree_u = tree_a.union(tree_b, '')
        tree_u.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'foo', 'foo/bar', 'x'},
                          {'a': 'file a/a', 'foo/b': 'file a/foo/b',
                           'foo/x': 'file b/foo/x'},
                          {'dead-symlink': 'bad', 'file-symlink': 'a',
                           'dir-symlink': 'foo/bar'}))
        shutil.rmtree(self.outdir)
        # Verify contents of tree_a and tree_b are unchanged by
        # creating the union.
        tree_a.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'foo', 'foo/bar'},
                          {'a': 'file a/a', 'foo/b': 'file a/foo/b'},
                          {'dead-symlink': 'bad', 'file-symlink': 'a',
                           'dir-symlink': 'foo/bar'}))
        shutil.rmtree(self.outdir)
        tree_b.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'foo', 'x'},
                          {'foo/x': 'file b/foo/x'},
                          {}))
        # Test unions of MapFSTreeMap objects.
        tree_a = MapFSTreeMap(self.context, {'x': tree_a})
        tree_b = MapFSTreeMap(self.context, {'x': tree_b})
        tree_u = tree_a.union(tree_b, '')
        shutil.rmtree(self.outdir)
        tree_u.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'x', 'x/foo', 'x/foo/bar', 'x/x'},
                          {'x/a': 'file a/a', 'x/foo/b': 'file a/foo/b',
                           'x/foo/x': 'file b/foo/x'},
                          {'x/dead-symlink': 'bad', 'x/file-symlink': 'a',
                           'x/dir-symlink': 'foo/bar'}))
        # Test duplicate files or symlinks when allowed.
        tree_a = MapFSTreeCopy(self.context, os.path.join(self.indir, 'a'))
        tree_u = tree_a.union(tree_a, '', True)
        shutil.rmtree(self.outdir)
        tree_u.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'foo', 'foo/bar'},
                          {'a': 'file a/a', 'foo/b': 'file a/foo/b'},
                          {'dead-symlink': 'bad', 'file-symlink': 'a',
                           'dir-symlink': 'foo/bar'}))
        tree_s = MapFSTreeSymlink(self.context, 'bad')
        tree_s = MapFSTreeMap(self.context, {'dead-symlink': tree_s})
        tree_u = tree_a.union(tree_a, '', True)
        shutil.rmtree(self.outdir)
        tree_u.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'foo', 'foo/bar'},
                          {'a': 'file a/a', 'foo/b': 'file a/foo/b'},
                          {'dead-symlink': 'bad', 'file-symlink': 'a',
                           'dir-symlink': 'foo/bar'}))

    def test_union_errors(self):
        """Test errors from unions of MapFSTree objects."""
        create_files(self.indir,
                     ['a', 'a/x', 'b', 'c', 'd', 'e', 'f'],
                     {'b/x': 'file b/x', 'd/x': 'file d/x', 'f/x': 'file b/x'},
                     {'c/x': 'target', 'e/x': 'target2'})
        tree_a = MapFSTreeCopy(self.context, os.path.join(self.indir, 'a'))
        tree_b = MapFSTreeCopy(self.context, os.path.join(self.indir, 'b'))
        tree_c = MapFSTreeCopy(self.context, os.path.join(self.indir, 'c'))
        self.assertRaisesRegex(ScriptError,
                               'non-directory involved in union operation: x',
                               tree_a.union, tree_b, '')
        self.assertRaisesRegex(ScriptError,
                               'non-directory involved in union operation: x',
                               tree_a.union, tree_c, '')
        self.assertRaisesRegex(ScriptError,
                               'non-directory involved in union operation: x',
                               tree_b.union, tree_a, '')
        self.assertRaisesRegex(ScriptError,
                               'non-directory involved in union operation: x',
                               tree_b.union, tree_b, '')
        self.assertRaisesRegex(ScriptError,
                               'non-directory involved in union operation: x',
                               tree_b.union, tree_c, '')
        self.assertRaisesRegex(ScriptError,
                               'non-directory involved in union operation: x',
                               tree_c.union, tree_a, '')
        self.assertRaisesRegex(ScriptError,
                               'non-directory involved in union operation: x',
                               tree_c.union, tree_b, '')
        self.assertRaisesRegex(ScriptError,
                               'non-directory involved in union operation: x',
                               tree_c.union, tree_c, '')
        # Invalid cases with duplicates allowed.
        self.assertRaisesRegex(ScriptError,
                               'non-directory involved in union operation: x',
                               tree_a.union, tree_b, '', True)
        self.assertRaisesRegex(ScriptError,
                               'non-directory involved in union operation: x',
                               tree_a.union, tree_c, '', True)
        self.assertRaisesRegex(ScriptError,
                               'non-directory involved in union operation: x',
                               tree_b.union, tree_a, '', True)
        self.assertRaisesRegex(ScriptError,
                               'inconsistent contents in union operation: x',
                               tree_b.union, tree_c, '', True)
        self.assertRaisesRegex(ScriptError,
                               'non-directory involved in union operation: x',
                               tree_c.union, tree_a, '', True)
        self.assertRaisesRegex(ScriptError,
                               'inconsistent contents in union operation: x',
                               tree_c.union, tree_b, '', True)
        # Invalid with duplicates allowed because of different contents.
        tree_d = MapFSTreeCopy(self.context, os.path.join(self.indir, 'd'))
        tree_e = MapFSTreeCopy(self.context, os.path.join(self.indir, 'e'))
        self.assertRaisesRegex(ScriptError,
                               'inconsistent contents in union operation: x',
                               tree_b.union, tree_d, '', True)
        self.assertRaisesRegex(ScriptError,
                               'inconsistent contents in union operation: x',
                               tree_c.union, tree_e, '', True)
        tree_e2 = MapFSTreeSymlink(self.context, 'target2')
        tree_e2 = MapFSTreeMap(self.context, {'x': tree_e2})
        self.assertRaisesRegex(ScriptError,
                               'inconsistent contents in union operation: x',
                               tree_c.union, tree_e2, '', True)
        # Invalid with duplicates allowed because of different file
        # permissions.
        tree_f = MapFSTreeCopy(self.context, os.path.join(self.indir, 'f'))
        # OK before permission change.
        tree_b.union(tree_f, '', True)
        os.chmod(os.path.join(self.indir, 'b', 'x'), stat.S_IRUSR)
        os.chmod(os.path.join(self.indir, 'f', 'x'), stat.S_IRWXU)
        self.assertRaisesRegex(ScriptError,
                               'inconsistent contents in union operation: x',
                               tree_b.union, tree_f, '', True)

    def test_remove(self):
        """Test removal of paths from MapFSTree objects."""
        create_files(self.indir, ['foo', 'foo/bar'],
                     {'a': 'file a', 'foo/b': 'file foo/b',
                      'foo/bar/c': 'file foo/bar/c'},
                     {'dead-symlink': 'bad', 'file-symlink': 'a',
                      'dir-symlink': 'foo/bar'})
        tree = MapFSTreeCopy(self.context, self.indir)
        tree_rm = tree.remove(['a', 'd*/*'])
        tree_rm.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'foo', 'foo/bar'},
                          {'foo/b': 'file foo/b',
                           'foo/bar/c': 'file foo/bar/c'},
                          {'dead-symlink': 'bad', 'file-symlink': 'a',
                           'dir-symlink': 'foo/bar'}))
        shutil.rmtree(self.outdir)
        tree_rm = tree.remove(['d*'])
        tree_rm.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'foo', 'foo/bar'},
                          {'a': 'file a', 'foo/b': 'file foo/b',
                           'foo/bar/c': 'file foo/bar/c'},
                          {'file-symlink': 'a'}))
        shutil.rmtree(self.outdir)
        tree_rm = tree.remove(['f*/*/*'])
        tree_rm.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'foo'},
                          {'a': 'file a', 'foo/b': 'file foo/b'},
                          {'dead-symlink': 'bad', 'file-symlink': 'a',
                           'dir-symlink': 'foo/bar'}))
        shutil.rmtree(self.outdir)
        tree_rm = tree.remove(['f*/*'])
        tree_rm.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         (set(),
                          {'a': 'file a'},
                          {'dead-symlink': 'bad', 'file-symlink': 'a',
                           'dir-symlink': 'foo/bar'}))
        shutil.rmtree(self.outdir)
        tree_rm = tree.remove(['f*'])
        tree_rm.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         (set(),
                          {'a': 'file a'},
                          {'dead-symlink': 'bad', 'dir-symlink': 'foo/bar'}))
        shutil.rmtree(self.outdir)
        tree_rm = tree.remove(['foo/bar/c'])
        tree_rm.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'foo'},
                          {'a': 'file a', 'foo/b': 'file foo/b'},
                          {'dead-symlink': 'bad', 'file-symlink': 'a',
                           'dir-symlink': 'foo/bar'}))
        shutil.rmtree(self.outdir)
        tree.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'foo', 'foo/bar'},
                          {'a': 'file a', 'foo/b': 'file foo/b',
                           'foo/bar/c': 'file foo/bar/c'},
                          {'dead-symlink': 'bad', 'file-symlink': 'a',
                           'dir-symlink': 'foo/bar'}))
        # Test removal from a MapFSTree for a non-directory (does nothing).
        tree = MapFSTreeCopy(self.context, os.path.join(self.indir,
                                                        'dir-symlink'))
        self.assertFalse(tree.is_dir)
        tree_rm = tree.remove(['c'])
        self.assertFalse(tree_rm.is_dir)

    def test_remove_recursive(self):
        """Test removal of paths with '**' from MapFSTree objects."""
        create_files(self.indir, ['foo', 'foo/bar'],
                     {'a': 'file a', 'a.c': 'file a.c',
                      'foo/a.c': 'file foo/a.c',
                      'foo/bar/b.c': 'file foo/bar/b.c'},
                     {})
        tree = MapFSTreeCopy(self.context, self.indir)
        tree_rm = tree.remove(['**/*.c'])
        tree_rm.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         (set(),
                          {'a': 'file a'},
                          {}))
        shutil.rmtree(self.outdir)
        tree_rm = tree.remove(['**/**/**/**/*.c'])
        tree_rm.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         (set(),
                          {'a': 'file a'},
                          {}))
        shutil.rmtree(self.outdir)
        tree_rm = tree.remove(['**/a.c'])
        tree_rm.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'foo', 'foo/bar'},
                          {'a': 'file a', 'foo/bar/b.c': 'file foo/bar/b.c'},
                          {}))
        shutil.rmtree(self.outdir)
        tree_rm = tree.remove(['*/**/a.c'])
        tree_rm.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'foo', 'foo/bar'},
                          {'a': 'file a', 'a.c': 'file a.c',
                           'foo/bar/b.c': 'file foo/bar/b.c'},
                          {}))
        shutil.rmtree(self.outdir)
        # Only exactly '**' as a complete path component is special;
        # other uses just act like '*'.
        tree_rm = tree.remove(['***/*.c'])
        tree_rm.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'foo', 'foo/bar'},
                          {'a': 'file a', 'a.c': 'file a.c',
                           'foo/bar/b.c': 'file foo/bar/b.c'},
                          {}))

    def test_remove_errors(self):
        """Test errors removing paths from MapFSTree objects."""
        tree = MapFSTreeMap(self.context, {})
        self.assertRaisesRegex(ScriptError,
                               'paths must be a list of strings, not a single '
                               'string',
                               tree.remove, 'test')
        self.assertRaisesRegex(ScriptError,
                               r'invalid path to remove: \.',
                               tree.remove, ['.'])
        self.assertRaisesRegex(ScriptError,
                               r'invalid path to remove: \.\.',
                               tree.remove, ['..'])
        self.assertRaisesRegex(ScriptError,
                               'invalid path to remove: foo//bar',
                               tree.remove, ['foo//bar'])
        self.assertRaisesRegex(ScriptError,
                               'invalid path to remove: /foo',
                               tree.remove, ['/foo'])
        self.assertRaisesRegex(ScriptError,
                               'invalid path to remove: bar/',
                               tree.remove, ['bar/'])
        self.assertRaisesRegex(ScriptError,
                               'invalid path to remove: ',
                               tree.remove, [''])

    def test_extract(self):
        """Test extraction of paths from MapFSTree objects."""
        create_files(self.indir, ['a1', 'a1/b1', 'a1/b2', 'a2', 'a2/c', 'd'],
                     {'ax': 'file ax', 'a1/bf': 'file a1/bf',
                      'a1/b1/c': 'file a1/b1/c', 'a2/c/b': 'file a2/c/b',
                      'df': 'file df', 'e': 'file e'},
                     {'dead-symlink': 'bad', 'a-dir-symlink': 'a1'})
        tree = MapFSTreeCopy(self.context, self.indir)
        tree_ex = tree.extract(['a*/b*', 'd*', '*z'])
        tree_ex.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'a1', 'a1/b1', 'a1/b2', 'd'},
                          {'a1/bf': 'file a1/bf', 'a1/b1/c': 'file a1/b1/c',
                           'df': 'file df'},
                          {'dead-symlink': 'bad'}))
        shutil.rmtree(self.outdir)
        tree_ex = tree.extract(['a*/b*', 'a*/c*'])
        tree_ex.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'a1', 'a1/b1', 'a1/b2', 'a2', 'a2/c'},
                          {'a1/bf': 'file a1/bf', 'a1/b1/c': 'file a1/b1/c',
                           'a2/c/b': 'file a2/c/b'},
                          {}))
        shutil.rmtree(self.outdir)
        tree_ex = tree.extract(['*/*/c'])
        tree_ex.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'a1', 'a1/b1'},
                          {'a1/b1/c': 'file a1/b1/c'},
                          {}))
        shutil.rmtree(self.outdir)
        tree.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'a1', 'a1/b1', 'a1/b2', 'a2', 'a2/c', 'd'},
                          {'ax': 'file ax', 'a1/bf': 'file a1/bf',
                           'a1/b1/c': 'file a1/b1/c', 'a2/c/b': 'file a2/c/b',
                           'df': 'file df', 'e': 'file e'},
                          {'dead-symlink': 'bad', 'a-dir-symlink': 'a1'}))

    def test_extract_errors(self):
        """Test errors extracting paths from MapFSTree objects."""
        create_files(self.indir,
                     [],
                     {'f': 'file f'},
                     {'link': 'target'})
        tree_f = MapFSTreeCopy(self.context, os.path.join(self.indir, 'f'))
        self.assertRaisesRegex(ScriptError,
                               r'extracting paths from non-directory',
                               tree_f.extract, [])
        tree_link = MapFSTreeCopy(self.context,
                                  os.path.join(self.indir, 'link'))
        self.assertRaisesRegex(ScriptError,
                               r'extracting paths from non-directory',
                               tree_link.extract, [])
        tree = MapFSTreeMap(self.context, {})
        self.assertRaisesRegex(ScriptError,
                               'paths must be a list of strings, not a single '
                               'string',
                               tree.extract, 'test')
        self.assertRaisesRegex(ScriptError,
                               r'invalid path to extract: \.',
                               tree.extract, ['.'])
        self.assertRaisesRegex(ScriptError,
                               r'invalid path to extract: \.\.',
                               tree.extract, ['..'])
        self.assertRaisesRegex(ScriptError,
                               'invalid path to extract: foo//bar',
                               tree.extract, ['foo//bar'])
        self.assertRaisesRegex(ScriptError,
                               'invalid path to extract: /foo',
                               tree.extract, ['/foo'])
        self.assertRaisesRegex(ScriptError,
                               'invalid path to extract: bar/',
                               tree.extract, ['bar/'])
        self.assertRaisesRegex(ScriptError,
                               'invalid path to extract: ',
                               tree.extract, [''])

    def test_extract_one(self):
        """Test extraction of a single path from a MapFSTree object."""
        create_files(self.indir, ['d', 'd/e', 'd/e/f'],
                     {'d/e/f/g': 'file d/e/f/g'},
                     {'dead-symlink': 'bad'})
        tree = MapFSTreeCopy(self.context, self.indir)
        tree_ex = tree.extract_one('d')
        tree_ex.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'e', 'e/f'},
                          {'e/f/g': 'file d/e/f/g'},
                          {}))
        shutil.rmtree(self.outdir)
        tree_ex = tree.extract_one('d/e/f')
        tree_ex.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         (set(),
                          {'g': 'file d/e/f/g'},
                          {}))
        shutil.rmtree(self.outdir)
        tree_ex = tree.extract_one('d/e/f/g')
        tree_ex.export(self.outdir)
        with open(self.outdir, 'r', encoding='utf-8') as file:
            self.assertEqual(file.read(), 'file d/e/f/g')
        os.remove(self.outdir)
        tree_ex = tree.extract_one('dead-symlink')
        tree_ex.export(self.outdir)
        self.assertEqual(os.readlink(self.outdir), 'bad')
        os.remove(self.outdir)
        tree.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'d', 'd/e', 'd/e/f'},
                          {'d/e/f/g': 'file d/e/f/g'},
                          {'dead-symlink': 'bad'}))

    def test_extract_one_errors(self):
        """Test errors extracting a single paths from a MapFSTree object."""
        create_files(self.indir,
                     [],
                     {'f': 'file f'},
                     {'link': 'target'})
        tree_f = MapFSTreeCopy(self.context, os.path.join(self.indir, 'f'))
        self.assertRaisesRegex(ScriptError,
                               r'extracting a path from a non-directory',
                               tree_f.extract_one, 'test')
        tree_link = MapFSTreeCopy(self.context,
                                  os.path.join(self.indir, 'link'))
        self.assertRaisesRegex(ScriptError,
                               r'extracting a path from a non-directory',
                               tree_link.extract_one, 'test')
        tree = MapFSTreeMap(self.context, {})
        self.assertRaisesRegex(ScriptError,
                               r'invalid path to extract: \.',
                               tree.extract_one, '.')
        self.assertRaisesRegex(ScriptError,
                               r'invalid path to extract: \.\.',
                               tree.extract_one, '..')
        self.assertRaisesRegex(ScriptError,
                               'invalid path to extract: foo//bar',
                               tree.extract_one, 'foo//bar')
        self.assertRaisesRegex(ScriptError,
                               'invalid path to extract: /foo',
                               tree.extract_one, '/foo')
        self.assertRaisesRegex(ScriptError,
                               'invalid path to extract: bar/',
                               tree.extract_one, 'bar/')
        self.assertRaisesRegex(ScriptError,
                               'invalid path to extract: ',
                               tree.extract_one, '')
        self.assertRaises(KeyError, tree.extract_one, 'test')
        self.assertRaises(KeyError, tree.extract_one, 'test1/test2')


class FSTreeTestCase(unittest.TestCase):

    """Test the FSTree class and subclasses."""

    def setUp(self):
        """Set up an FSTree test."""
        self.context = ScriptContext()
        self.tempdir_td = tempfile.TemporaryDirectory()
        self.tempdir = self.tempdir_td.name
        self.indir = os.path.join(self.tempdir, 'in')
        self.outdir = os.path.join(self.tempdir, 'out')

    def tearDown(self):
        """Tear down an FSTree test."""
        self.tempdir_td.cleanup()

    def test_copy(self):
        """Test FSTreeCopy."""
        tree = FSTreeCopy(self.context, self.indir, {'foo/bar'})
        self.assertEqual(tree.install_trees, {'foo/bar'})
        create_files(self.indir, ['foo', 'foo/bar'],
                     {'a': 'file a', 'foo/b': 'file foo/b'},
                     {'dead-symlink': 'bad', 'file-symlink': 'a',
                      'dir-symlink': 'foo/bar'})
        tree.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'foo', 'foo/bar'},
                          {'a': 'file a', 'foo/b': 'file foo/b'},
                          {'dead-symlink': 'bad', 'file-symlink': 'a',
                           'dir-symlink': 'foo/bar'}))
        shutil.rmtree(self.outdir)
        map_tree = tree.export_map()
        map_tree.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'foo', 'foo/bar'},
                          {'a': 'file a', 'foo/b': 'file foo/b'},
                          {'dead-symlink': 'bad', 'file-symlink': 'a',
                           'dir-symlink': 'foo/bar'}))
        shutil.rmtree(self.outdir)
        tree = FSTreeCopy(self.context, os.path.join(self.indir, 'a'),
                          {'p/q', 'r/s'})
        self.assertEqual(tree.install_trees, {'p/q', 'r/s'})
        tree.export(self.outdir)
        with open(self.outdir, 'r', encoding='utf-8') as file:
            self.assertEqual(file.read(), 'file a')

    def test_empty(self):
        """Test FSTreeEmpty."""
        tree = FSTreeEmpty(self.context)
        self.assertEqual(tree.install_trees, set())
        tree.export(self.outdir)
        self.assertEqual(read_files(self.outdir), (set(), {}, {}))

    def test_symlink(self):
        """Test FSTreeSymlink."""
        tree = FSTreeSymlink(self.context, 'example/target')
        self.assertEqual(tree.install_trees, set())
        tree.export(self.outdir)
        self.assertEqual(os.readlink(self.outdir), 'example/target')

    def test_symlink_errors(self):
        """Test errors from FSTreeSymlink."""
        self.assertRaisesRegex(ScriptError,
                               'empty symlink target',
                               FSTreeSymlink, self.context, '')

    def test_move(self):
        """Test FSTreeMove."""
        ctree = FSTreeCopy(self.context, self.indir, {'foo/bar'})
        tree = FSTreeMove(ctree, 'x/y/z')
        self.assertEqual(tree.install_trees, {'foo/bar'})
        create_files(self.indir, ['foo', 'foo/bar'],
                     {'a': 'file a', 'foo/b': 'file foo/b'},
                     {'dead-symlink': 'bad', 'file-symlink': 'a',
                      'dir-symlink': 'foo/bar'})
        tree.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'x', 'x/y', 'x/y/z', 'x/y/z/foo', 'x/y/z/foo/bar'},
                          {'x/y/z/a': 'file a', 'x/y/z/foo/b': 'file foo/b'},
                          {'x/y/z/dead-symlink': 'bad',
                           'x/y/z/file-symlink': 'a',
                           'x/y/z/dir-symlink': 'foo/bar'}))

    def test_move_errors(self):
        """Test errors from FSTreeMove."""
        ctree = FSTreeCopy(self.context, self.indir, {'foo/bar'})
        self.assertRaisesRegex(ScriptError,
                               r'invalid subdirectory: \.',
                               FSTreeMove, ctree, '.')
        self.assertRaisesRegex(ScriptError,
                               r'invalid subdirectory: \.\.',
                               FSTreeMove, ctree, '..')
        self.assertRaisesRegex(ScriptError,
                               'invalid subdirectory: foo//bar',
                               FSTreeMove, ctree, 'foo//bar')
        self.assertRaisesRegex(ScriptError,
                               'invalid subdirectory: /foo',
                               FSTreeMove, ctree, '/foo')
        self.assertRaisesRegex(ScriptError,
                               'invalid subdirectory: bar/',
                               FSTreeMove, ctree, 'bar/')
        self.assertRaisesRegex(ScriptError,
                               'invalid subdirectory: ',
                               FSTreeMove, ctree, '')

    def test_remove(self):
        """Test FSTreeRemove."""
        ctree = FSTreeCopy(self.context, self.indir, {'foo/bar'})
        tree = FSTreeRemove(ctree, ['f*/*', 'a'])
        self.assertEqual(tree.install_trees, {'foo/bar'})
        create_files(self.indir, ['foo', 'foo/bar'],
                     {'a': 'file a', 'foo/b': 'file foo/b'},
                     {'dead-symlink': 'bad', 'file-symlink': 'a',
                      'dir-symlink': 'foo/bar'})
        tree.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         (set(),
                          {},
                          {'dead-symlink': 'bad', 'file-symlink': 'a',
                           'dir-symlink': 'foo/bar'}))
        shutil.rmtree(self.outdir)
        tree = FSTreeRemove(ctree, ['nonesuch', 'd*'])
        self.assertEqual(tree.install_trees, {'foo/bar'})
        tree.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'foo', 'foo/bar'},
                          {'a': 'file a', 'foo/b': 'file foo/b'},
                          {'file-symlink': 'a'}))

    def test_remove_recursive(self):
        """Test FSTreeRemove with '**'."""
        ctree = FSTreeCopy(self.context, self.indir, {'foo/bar'})
        tree = FSTreeRemove(ctree, ['**/*.c'])
        self.assertEqual(tree.install_trees, {'foo/bar'})
        create_files(self.indir, ['foo', 'foo/bar'],
                     {'a': 'file a', 'a.c': 'file a.c',
                      'foo/a.c': 'file foo/a.c',
                      'foo/bar/b.c': 'file foo/bar/b.c'},
                     {})
        tree.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         (set(),
                          {'a': 'file a'},
                          {}))

    def test_remove_errors(self):
        """Test errors from FSTreeRemove."""
        ctree = FSTreeCopy(self.context, self.indir, {'foo/bar'})
        self.assertRaisesRegex(ScriptError,
                               'paths must be a list of strings, not a single '
                               'string',
                               FSTreeRemove, ctree, 'test')
        self.assertRaisesRegex(ScriptError,
                               r'invalid path to remove: \.',
                               FSTreeRemove, ctree, ['.'])
        self.assertRaisesRegex(ScriptError,
                               r'invalid path to remove: \.\.',
                               FSTreeRemove, ctree, ['..'])
        self.assertRaisesRegex(ScriptError,
                               'invalid path to remove: foo//bar',
                               FSTreeRemove, ctree, ['foo//bar'])
        self.assertRaisesRegex(ScriptError,
                               'invalid path to remove: /foo',
                               FSTreeRemove, ctree, ['/foo'])
        self.assertRaisesRegex(ScriptError,
                               'invalid path to remove: bar/',
                               FSTreeRemove, ctree, ['bar/'])
        self.assertRaisesRegex(ScriptError,
                               'invalid path to remove: ',
                               FSTreeRemove, ctree, [''])

    def test_extract(self):
        """Test FSTreeExtract."""
        ctree = FSTreeCopy(self.context, self.indir, {'foo/bar'})
        tree = FSTreeExtract(ctree, ['f*/*', 'a'])
        self.assertEqual(tree.install_trees, {'foo/bar'})
        create_files(self.indir, ['foo', 'foo/bar'],
                     {'a': 'file a', 'foo/b': 'file foo/b'},
                     {'dead-symlink': 'bad', 'file-symlink': 'a',
                      'dir-symlink': 'foo/bar'})
        tree.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'foo', 'foo/bar'},
                          {'a': 'file a', 'foo/b': 'file foo/b'},
                          {}))
        shutil.rmtree(self.outdir)
        tree = FSTreeExtract(ctree, ['nonesuch', 'd*'])
        self.assertEqual(tree.install_trees, {'foo/bar'})
        tree.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         (set(),
                          {},
                          {'dead-symlink': 'bad', 'dir-symlink': 'foo/bar'}))

    def test_extract_errors(self):
        """Test errors from FSTreeExtract."""
        ctree = FSTreeCopy(self.context, self.indir, {'foo/bar'})
        self.assertRaisesRegex(ScriptError,
                               'paths must be a list of strings, not a single '
                               'string',
                               FSTreeExtract, ctree, 'test')
        self.assertRaisesRegex(ScriptError,
                               r'invalid path to extract: \.',
                               FSTreeExtract, ctree, ['.'])
        self.assertRaisesRegex(ScriptError,
                               r'invalid path to extract: \.\.',
                               FSTreeExtract, ctree, ['..'])
        self.assertRaisesRegex(ScriptError,
                               'invalid path to extract: foo//bar',
                               FSTreeExtract, ctree, ['foo//bar'])
        self.assertRaisesRegex(ScriptError,
                               'invalid path to extract: /foo',
                               FSTreeExtract, ctree, ['/foo'])
        self.assertRaisesRegex(ScriptError,
                               'invalid path to extract: bar/',
                               FSTreeExtract, ctree, ['bar/'])
        self.assertRaisesRegex(ScriptError,
                               'invalid path to extract: ',
                               FSTreeExtract, ctree, [''])

    def test_extract_one(self):
        """Test FSTreeExtractOne."""
        ctree = FSTreeCopy(self.context, self.indir, {'foo/bar'})
        tree = FSTreeExtractOne(ctree, 'd/e/f')
        self.assertEqual(tree.install_trees, {'foo/bar'})
        create_files(self.indir, ['d', 'd/e', 'd/e/f'],
                     {'d/e/f/g': 'file d/e/f/g'},
                     {'dead-symlink': 'bad'})
        tree.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         (set(),
                          {'g': 'file d/e/f/g'},
                          {}))
        shutil.rmtree(self.outdir)
        tree = FSTreeExtractOne(ctree, 'dead-symlink')
        self.assertEqual(tree.install_trees, {'foo/bar'})
        tree.export(self.outdir)
        self.assertEqual(os.readlink(self.outdir), 'bad')

    def test_extract_one_errors(self):
        """Test errors from FSTreeExtractOne."""
        ctree = FSTreeCopy(self.context, self.indir, {'foo/bar'})
        self.assertRaisesRegex(ScriptError,
                               r'invalid path to extract: \.',
                               FSTreeExtractOne, ctree, '.')
        self.assertRaisesRegex(ScriptError,
                               r'invalid path to extract: \.\.',
                               FSTreeExtractOne, ctree, '..')
        self.assertRaisesRegex(ScriptError,
                               'invalid path to extract: foo//bar',
                               FSTreeExtractOne, ctree, 'foo//bar')
        self.assertRaisesRegex(ScriptError,
                               'invalid path to extract: /foo',
                               FSTreeExtractOne, ctree, '/foo')
        self.assertRaisesRegex(ScriptError,
                               'invalid path to extract: bar/',
                               FSTreeExtractOne, ctree, 'bar/')
        self.assertRaisesRegex(ScriptError,
                               'invalid path to extract: ',
                               FSTreeExtractOne, ctree, '')

    def test_union(self):
        """Test FSTreeUnion."""
        ctree1 = FSTreeCopy(self.context, os.path.join(self.indir, 'x'),
                            {'foo/bar'})
        ctree2 = FSTreeCopy(self.context, os.path.join(self.indir, 'y'),
                            {'p/q'})
        tree = FSTreeUnion(ctree1, ctree2)
        self.assertEqual(tree.install_trees, {'foo/bar', 'p/q'})
        create_files(self.indir, ['x', 'x/foo', 'x/foo/bar', 'y', 'y/foo'],
                     {'x/a': 'file a', 'x/foo/b': 'file foo/b',
                      'y/foo/c': 'file foo/c'},
                     {'x/dead-symlink': 'bad', 'x/file-symlink': 'a',
                      'x/dir-symlink': 'foo/bar'})
        tree.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'foo', 'foo/bar'},
                          {'a': 'file a', 'foo/b': 'file foo/b',
                           'foo/c': 'file foo/c'},
                          {'dead-symlink': 'bad', 'file-symlink': 'a',
                           'dir-symlink': 'foo/bar'}))
        tree = FSTreeUnion(ctree1, ctree1, True)
        shutil.rmtree(self.outdir)
        tree.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'foo', 'foo/bar'},
                          {'a': 'file a', 'foo/b': 'file foo/b'},
                          {'dead-symlink': 'bad', 'file-symlink': 'a',
                           'dir-symlink': 'foo/bar'}))
