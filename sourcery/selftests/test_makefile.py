# Test sourcery.makefile.

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

"""Test sourcery.makefile."""

import os.path
import subprocess
import tempfile
import unittest

import sourcery.context
from sourcery.makefile import command_to_make, Makefile

__all__ = ['MakefileTestCase']


class MakefileTestCase(unittest.TestCase):

    """Test makefile generation."""

    def setUp(self):
        """Set up a makefile test."""
        self.context = sourcery.context.ScriptContext()

    def test_command_to_make_basic(self):
        """Test basic use of command_to_make."""
        self.assertEqual(command_to_make(self.context, ['foo', 'bar']),
                         'foo bar')
        self.assertEqual(command_to_make(self.context, ('foo', '/bar')),
                         'foo /bar')
        self.assertEqual(command_to_make(self.context, ['foo', 'b a r']),
                         "foo 'b a r'")
        self.assertEqual(command_to_make(self.context, ['foo', '']),
                         "foo ''")
        self.assertEqual(command_to_make(self.context, ['foo', 'a$b']),
                         "foo 'a$$b'")
        self.assertEqual(command_to_make(self.context, ['#a>b']),
                         "'#a>b'")

    def test_command_to_make_errors(self):
        """Test errors from command_to_make."""
        self.assertRaisesRegex(sourcery.context.ScriptError,
                               'newline in command',
                               command_to_make, self.context, ['a\nb'])

    def test_makefile_basic(self):
        """Test basic use of the Makefile class."""
        makefile = Makefile(self.context, 'all')
        makefile.add_target('aaa')
        makefile.add_target('bbb')
        makefile.add_target('ccc')
        makefile.add_target('ddd')
        makefile.add_target('zzz')
        makefile.add_deps('all', ['zzz'])
        makefile.add_deps('zzz', ['aaa', 'bbb'])
        makefile.add_deps('zzz', ['ddd'])
        makefile.add_deps('zzz', ['aaa'])
        makefile.add_deps('bbb', ['ccc'])
        makefile.add_command('zzz', 'command for zzz')
        makefile.add_command('zzz', 'another command for zzz')
        mftext = makefile.makefile_text()
        self.assertTrue(mftext.startswith('all: zzz\n'))
        self.assertIn('\n.PHONY: all aaa bbb ccc ddd zzz\n', mftext)
        self.assertIn('\nzzz: aaa bbb ddd\n\t@command for zzz\n'
                      '\t@another command for zzz\n', mftext)
        self.assertIn('\nbbb: ccc\n\n', mftext)
        self.assertIn('\nccc:\n\n', mftext)

    def test_makefile_errors(self):
        """Test errors from the Makefile class."""
        makefile = Makefile(self.context, 'all')
        self.assertRaisesRegex(sourcery.context.ScriptError,
                               'target all already added',
                               makefile.add_target, 'all')
        self.assertRaisesRegex(sourcery.context.ScriptError,
                               'target foo not known',
                               makefile.add_deps, 'foo', ['all'])
        self.assertRaisesRegex(sourcery.context.ScriptError,
                               'dependency foo not known',
                               makefile.add_deps, 'all', ['foo'])
        self.assertRaisesRegex(sourcery.context.ScriptError,
                               'target foo not known',
                               makefile.add_command, 'foo', 'some command')
        self.assertRaisesRegex(sourcery.context.ScriptError,
                               'newline in command',
                               makefile.add_command, 'all', 'bad\ncommand')
        makefile.add_target('other')
        makefile.add_deps('all', ['other'])
        makefile.add_deps('other', ['all'])
        self.assertRaisesRegex(sourcery.context.ScriptError,
                               'circular dependency',
                               makefile.makefile_text)

    def test_makefile_build(self):
        """Test use of make with a generated makefile."""
        makefile = Makefile(self.context, 'all')
        makefile.add_target('a')
        makefile.add_target('b')
        makefile.add_target('c')
        makefile.add_deps('all', ['c'])
        makefile.add_deps('c', ['b'])
        makefile.add_deps('b', ['a'])
        makefile.add_command('c', 'echo c >> out')
        makefile.add_command('b', 'echo b >> out')
        makefile.add_command('a', 'echo a >> out')
        mftext = makefile.makefile_text()
        with tempfile.TemporaryDirectory() as tempdir:
            makefile = os.path.join(tempdir, 'GNUmakefile')
            with open(makefile, 'w', encoding='utf-8') as file:
                file.write(mftext)
            subprocess.run(['make', '-j'], cwd=tempdir, check=True)
            outfile = os.path.join(tempdir, 'out')
            with open(outfile, 'r', encoding='utf-8') as file:
                self.assertEqual(file.read(), 'a\nb\nc\n')
