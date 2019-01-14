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
from sourcery.fstree import MapFSTreeCopy, MapFSTreeMap, FSTreeCopy, \
    FSTreeEmpty, FSTreeMove, FSTreeRemove, FSTreeUnion
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

    def test_union_errors(self):
        """Test errors from unions of MapFSTree objects."""
        create_files(self.indir,
                     ['a', 'a/x', 'b', 'c'],
                     {'b/x': 'file b/x'},
                     {'c/x': 'target'})
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

    def test_remove_errors(self):
        """Test errors removing paths from MapFSTree objects."""
        tree = MapFSTreeMap(self.context, {})
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

    def test_remove_errors(self):
        """Test errors from FSTreeRemove."""
        ctree = FSTreeCopy(self.context, self.indir, {'foo/bar'})
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
