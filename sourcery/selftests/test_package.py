# Test sourcery.package.

# Copyright 2018-2020 Mentor Graphics Corporation.

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

"""Test sourcery.package."""

import os
import os.path
import shutil
import stat
import subprocess
import tarfile
import tempfile
import unittest

from sourcery.context import ScriptError, ScriptContext
from sourcery.package import fix_perms, hard_link_files, resolve_symlinks, \
    replace_symlinks, tar_command
from sourcery.selftests.support import create_files, read_files

__all__ = ['PackageTestCase']


class PackageTestCase(unittest.TestCase):

    """Test sourcery.package."""

    def setUp(self):
        """Set up a sourcery.package test."""
        self.context = ScriptContext()
        self.tempdir_td = tempfile.TemporaryDirectory()
        self.tempdir = self.tempdir_td.name
        self.indir = os.path.join(self.tempdir, 'in')

    def tearDown(self):
        """Tear down a sourcery.package test."""
        self.tempdir_td.cleanup()

    def test_fix_perms(self):
        """Test the fix_perms function."""
        create_files(self.indir, ['a', 'b', 'b/c'],
                     {'x': 'file x', 'b/c/y': 'file b/c/y'},
                     {'dead-symlink': 'bad', 'ext-symlink': '/'})
        os.chmod(self.indir, stat.S_IRWXU)
        os.chmod(os.path.join(self.indir, 'x'), stat.S_IRWXU | stat.S_IROTH)
        os.chmod(os.path.join(self.indir, 'b/c/y'), 0)
        fix_perms(self.indir)
        self.assertEqual(read_files(self.indir),
                         ({'a', 'b', 'b/c'},
                          {'x': 'file x', 'b/c/y': 'file b/c/y'},
                          {'dead-symlink': 'bad', 'ext-symlink': '/'}))
        mode_ex = (stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP
                   | stat.S_IROTH | stat.S_IXOTH)
        mode_noex = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH
        mode = stat.S_IMODE(os.stat(self.indir).st_mode)
        self.assertEqual(mode, mode_ex)
        mode = stat.S_IMODE(os.stat(os.path.join(self.indir, 'a')).st_mode)
        self.assertEqual(mode, mode_ex)
        mode = stat.S_IMODE(os.stat(os.path.join(self.indir, 'b')).st_mode)
        self.assertEqual(mode, mode_ex)
        mode = stat.S_IMODE(os.stat(os.path.join(self.indir, 'b/c')).st_mode)
        self.assertEqual(mode, mode_ex)
        mode = stat.S_IMODE(os.stat(os.path.join(self.indir, 'x')).st_mode)
        self.assertEqual(mode, mode_ex)
        mode = stat.S_IMODE(os.stat(os.path.join(self.indir, 'b/c/y')).st_mode)
        self.assertEqual(mode, mode_noex)

    def test_hard_link_files(self):
        """Test the hard_link_files function."""
        create_files(self.indir, ['a', 'b', 'b/c'],
                     {'a1': 'a', 'a2': 'a', 'b/c/a3': 'a', 'b/a4': 'a',
                      'b1': 'b', 'b/b2': 'b', 'c': 'c'},
                     {'a-link': 'a1', 'dead-link': 'bad'})
        os.chmod(os.path.join(self.indir, 'a1'), stat.S_IRWXU)
        os.chmod(os.path.join(self.indir, 'b/c/a3'), stat.S_IRWXU)
        os.chmod(os.path.join(self.indir, 'a2'), stat.S_IRUSR)
        os.chmod(os.path.join(self.indir, 'b/a4'), stat.S_IRUSR)
        hard_link_files(self.context, self.indir)
        self.assertEqual(read_files(self.indir),
                         ({'a', 'b', 'b/c'},
                          {'a1': 'a', 'a2': 'a', 'b/c/a3': 'a', 'b/a4': 'a',
                           'b1': 'b', 'b/b2': 'b', 'c': 'c'},
                          {'a-link': 'a1', 'dead-link': 'bad'}))
        stat_a1 = os.stat(os.path.join(self.indir, 'a1'))
        self.assertEqual(stat.S_IMODE(stat_a1.st_mode), stat.S_IRWXU)
        stat_a3 = os.stat(os.path.join(self.indir, 'b/c/a3'))
        self.assertEqual(stat.S_IMODE(stat_a3.st_mode), stat.S_IRWXU)
        stat_a2 = os.stat(os.path.join(self.indir, 'a2'))
        self.assertEqual(stat.S_IMODE(stat_a2.st_mode), stat.S_IRUSR)
        stat_a4 = os.stat(os.path.join(self.indir, 'b/a4'))
        self.assertEqual(stat.S_IMODE(stat_a4.st_mode), stat.S_IRUSR)
        self.assertEqual(stat_a1.st_nlink, 2)
        self.assertEqual(stat_a2.st_nlink, 2)
        self.assertEqual(stat_a3.st_nlink, 2)
        self.assertEqual(stat_a4.st_nlink, 2)
        self.assertEqual(stat_a1.st_dev, stat_a3.st_dev)
        self.assertEqual(stat_a1.st_ino, stat_a3.st_ino)
        self.assertEqual(stat_a2.st_dev, stat_a4.st_dev)
        self.assertEqual(stat_a2.st_ino, stat_a4.st_ino)
        stat_b1 = os.stat(os.path.join(self.indir, 'b1'))
        stat_b2 = os.stat(os.path.join(self.indir, 'b/b2'))
        self.assertEqual(stat_b1.st_nlink, 2)
        self.assertEqual(stat_b2.st_nlink, 2)
        self.assertEqual(stat_b1.st_dev, stat_b2.st_dev)
        self.assertEqual(stat_b1.st_ino, stat_b2.st_ino)

    def test_resolve_symlinks(self):
        """Test the resolve_symlinks function."""
        create_files(self.indir, ['b', 'x', 'x/e'],
                     {'f': 'contents'},
                     {'a': 'b/c/d', 'b/c': '././//../././b/../x//', 'x/d': 'e',
                      'z': 'y', 'y': 'f', 'x/e/m': '../../', 'p': 'q/../',
                      'q': 'x/e'})
        being_resolved = set()
        self.assertEqual(resolve_symlinks(self.context, self.indir, (), 'a',
                                          False, being_resolved),
                         ('x', 'e'))
        self.assertEqual(being_resolved, set())
        self.assertEqual(resolve_symlinks(self.context, self.indir, (), 'a',
                                          True, being_resolved),
                         ('x', 'e'))
        self.assertEqual(being_resolved, set())
        self.assertEqual(resolve_symlinks(self.context, self.indir, ('x', 'e'),
                                          'm', False, being_resolved),
                         ())
        self.assertEqual(being_resolved, set())
        self.assertEqual(resolve_symlinks(self.context, self.indir, ('x', 'e'),
                                          'm', True, being_resolved),
                         ())
        self.assertEqual(being_resolved, set())
        self.assertEqual(resolve_symlinks(self.context, self.indir, (), 'z',
                                          False, being_resolved),
                         ('f',))
        self.assertEqual(being_resolved, set())
        self.assertEqual(resolve_symlinks(self.context, self.indir, (), 'p',
                                          False, being_resolved),
                         ('x',))
        self.assertEqual(being_resolved, set())
        self.assertEqual(resolve_symlinks(self.context, self.indir, (), 'p',
                                          True, being_resolved),
                         ('x',))
        self.assertEqual(being_resolved, set())

    def test_resolve_symlinks_errors(self):
        """Test errors from resolve_symlinks."""
        create_files(self.indir, ['d1'],
                     {'file': 'contents'},
                     {'a': 'a',
                      'b': 'c', 'c': 'd', 'd': 'b',
                      'e': 'd1/f/g', 'd1/f': 'g', 'd1/g': '../e',
                      'abs': self.indir, 'up': 'd1/../..', 'x': 'file/',
                      'y': 'file/something', 'tofile': 'file'})
        self.assertRaisesRegex(ScriptError,
                               'symbolic link cycle',
                               resolve_symlinks, self.context, self.indir,
                               (), 'a', False, set())
        self.assertRaisesRegex(ScriptError,
                               'symbolic link cycle',
                               resolve_symlinks, self.context, self.indir,
                               (), 'a', True, set())
        self.assertRaisesRegex(ScriptError,
                               'symbolic link cycle',
                               resolve_symlinks, self.context, self.indir,
                               (), 'b', False, set())
        self.assertRaisesRegex(ScriptError,
                               'symbolic link cycle',
                               resolve_symlinks, self.context, self.indir,
                               (), 'b', True, set())
        self.assertRaisesRegex(ScriptError,
                               'symbolic link cycle',
                               resolve_symlinks, self.context, self.indir,
                               (), 'e', False, set())
        self.assertRaisesRegex(ScriptError,
                               'symbolic link cycle',
                               resolve_symlinks, self.context, self.indir,
                               (), 'e', True, set())
        self.assertRaisesRegex(ScriptError,
                               'absolute symbolic link',
                               resolve_symlinks, self.context, self.indir,
                               (), 'abs', False, set())
        self.assertRaisesRegex(ScriptError,
                               'absolute symbolic link',
                               resolve_symlinks, self.context, self.indir,
                               (), 'abs', True, set())
        self.assertRaisesRegex(ScriptError,
                               'symbolic link goes outside',
                               resolve_symlinks, self.context, self.indir,
                               (), 'up', False, set())
        self.assertRaisesRegex(ScriptError,
                               'symbolic link goes outside',
                               resolve_symlinks, self.context, self.indir,
                               (), 'up', True, set())
        self.assertRaisesRegex(ScriptError,
                               'not a directory',
                               resolve_symlinks, self.context, self.indir,
                               (), 'x', False, set())
        self.assertRaisesRegex(ScriptError,
                               'not a directory',
                               resolve_symlinks, self.context, self.indir,
                               (), 'x', True, set())
        self.assertRaisesRegex(ScriptError,
                               'not a directory',
                               resolve_symlinks, self.context, self.indir,
                               (), 'y', False, set())
        self.assertRaisesRegex(ScriptError,
                               'not a directory',
                               resolve_symlinks, self.context, self.indir,
                               (), 'y', True, set())
        self.assertRaisesRegex(ScriptError,
                               'not a directory',
                               resolve_symlinks, self.context, self.indir,
                               (), 'tofile', True, set())

    def test_replace_symlinks(self):
        """Test the replace_symlinks function."""
        create_files(self.indir, ['d1', 'd2'],
                     {'f': 'f', 'd1/f': 'd1/f', 'd2/f': 'd2/f'},
                     {'d1/link': '../f', 'd1/d2': '../d2', 'd2/link': '../f'})
        replace_symlinks(self.context, self.indir)
        self.assertEqual(read_files(self.indir),
                         ({'d1', 'd2', 'd1/d2'},
                          {'f': 'f', 'd1/f': 'd1/f', 'd2/f': 'd2/f',
                           'd1/link': 'f', 'd2/link': 'f', 'd1/d2/f': 'd2/f',
                           'd1/d2/link': 'f'},
                          {}))

    def test_replace_symlinks_errors(self):
        """Test errors from replace_symlinks."""
        create_files(self.indir, ['a', 'b'],
                     {},
                     {'a/x': '../b', 'b/y': '../a'})
        self.assertRaisesRegex(ScriptError,
                               'circular dependency',
                               replace_symlinks, self.context, self.indir)
        shutil.rmtree(self.indir)
        create_files(self.indir, [],
                     {},
                     {'a': '.'})
        self.assertRaisesRegex(ScriptError,
                               'circular dependency',
                               replace_symlinks, self.context, self.indir)

    def test_tar_command(self):
        """Test the tar_command function."""
        self.assertEqual(tar_command('/some/where/example.tar.xz',
                                     'top+dir-1.0', 1234567890),
                         ['tar', '-c', '-J', '-f',
                          '/some/where/example.tar.xz', '--sort=name',
                          '--mtime=@1234567890', '--owner=0', '--group=0',
                          '--numeric-owner',
                          r'--transform=s|^\.|top+dir-1.0|rSh', '.'])

    def test_tar_command_run(self):
        """Test running the command from the tar_command function."""
        create_files(self.indir, ['a', 'b', 'b/c'],
                     {'a1': 'a', 'a2': 'a', 'b/c/a3': 'a', 'b/a4': 'a',
                      'b1': 'b', 'b/b2': 'b', 'c': 'c'},
                     {'a-link': 'a1', 'dead-link': 'bad'})
        hard_link_files(self.context, self.indir)
        test_tar_xz = os.path.join(self.tempdir, 'test.tar.xz')
        subprocess.run(tar_command(test_tar_xz, 'top+dir-1.0', 1234567890),
                       cwd=self.indir, check=True)
        subprocess.run(['tar', '-x', '-f', test_tar_xz], cwd=self.tempdir,
                       check=True)
        outdir = os.path.join(self.tempdir, 'top+dir-1.0')
        self.assertEqual(read_files(outdir),
                         ({'a', 'b', 'b/c'},
                          {'a1': 'a', 'a2': 'a', 'b/c/a3': 'a', 'b/a4': 'a',
                           'b1': 'b', 'b/b2': 'b', 'c': 'c'},
                          {'a-link': 'a1', 'dead-link': 'bad'}))
        stat_a1 = os.stat(os.path.join(outdir, 'a1'))
        self.assertEqual(stat_a1.st_nlink, 4)
        self.assertEqual(stat_a1.st_mtime, 1234567890)
        stat_dead_link = os.stat(os.path.join(outdir, 'dead-link'),
                                 follow_symlinks=False)
        self.assertEqual(stat_dead_link.st_mtime, 1234567890)
        # Test that the files are correctly sorted in the tarball.
        subprocess.run(['xz', '-d', test_tar_xz], check=True)
        tarfile_obj = tarfile.open(os.path.join(self.tempdir, 'test.tar'),
                                   'r:')
        self.assertEqual(tarfile_obj.getnames(),
                         ['top+dir-1.0', 'top+dir-1.0/a', 'top+dir-1.0/a-link',
                          'top+dir-1.0/a1', 'top+dir-1.0/a2', 'top+dir-1.0/b',
                          'top+dir-1.0/b/a4', 'top+dir-1.0/b/b2',
                          'top+dir-1.0/b/c', 'top+dir-1.0/b/c/a3',
                          'top+dir-1.0/b1', 'top+dir-1.0/c',
                          'top+dir-1.0/dead-link'])
