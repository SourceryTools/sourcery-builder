# Test sourcery.package.

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

"""Test sourcery.package."""

import os
import os.path
import stat
import tempfile
import unittest

from sourcery.package import fix_perms
from sourcery.selftests.support import create_files, read_files

__all__ = ['PackageTestCase']


class PackageTestCase(unittest.TestCase):

    """Test sourcery.package."""

    def setUp(self):
        """Set up a sourcery.package test."""
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
