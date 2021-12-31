# Test sourcery.buildcfg.

# Copyright 2018-2021 Mentor Graphics Corporation.

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

"""Test sourcery.buildcfg."""

import os
import stat
import subprocess
import tempfile
import unittest

from sourcery.buildcfg import BuildCfg
from sourcery.context import ScriptError, ScriptContext
from sourcery.selftests.support import create_files

__all__ = ['BuildCfgTestCase']


class BuildCfgTestCase(unittest.TestCase):

    """Test the BuildCfg class."""

    def setUp(self):
        """Set up a BuildCfg test."""
        self.context = ScriptContext()
        self.tempdir_td = tempfile.TemporaryDirectory()
        self.tempdir = self.tempdir_td.name
        self.bindir = os.path.join(self.tempdir, 'bin')

    def tearDown(self):
        """Tear down a BuildCfg test."""
        self.tempdir_td.cleanup()

    def test_init_attrs(self):
        """Test public attributes set by __init__."""
        cfg = BuildCfg(self.context, 'aarch64-linux-gnu')
        self.assertIs(cfg.context, self.context)
        self.assertEqual(cfg.triplet, 'aarch64-linux-gnu')
        self.assertEqual(cfg.name, 'aarch64-linux-gnu')
        cfg = BuildCfg(self.context, 'aarch64-linux-gnu', ccopts=['-mfoo',
                                                                  '-mbar=a+b'])
        self.assertEqual(cfg.name, 'aarch64-linux-gnu-mfoo-mbar_a_b')
        cfg = BuildCfg(self.context, 'aarch64-linux-gnu', name='random',
                       ccopts=['-mfoo', '-mbar=a+b'])
        self.assertEqual(cfg.name, 'random')

    def test_init_errors(self):
        """Test errors from __init__."""
        self.assertRaisesRegex(ScriptError,
                               'triplet must be a string',
                               BuildCfg, self.context, None)
        self.assertRaisesRegex(ScriptError,
                               'ccopts must be a list of strings',
                               BuildCfg, self.context, 'i686-pc-linux-gnu',
                               ccopts='-m64')
        self.assertRaisesRegex(ScriptError,
                               'tool_opts values must be lists of strings',
                               BuildCfg, self.context, 'i686-pc-linux-gnu',
                               tool_opts={'as': '--64'})

    def test_repr(self):
        """Test BuildCfg.__repr__."""
        # Default case.
        cfg = BuildCfg(self.context, 'aarch64-linux-gnu')
        self.assertEqual(repr(cfg), "BuildCfg('aarch64-linux-gnu')")
        cfg = BuildCfg(self.context, 'aarch64-linux-gnu',
                       name='aarch64-linux-gnu',
                       tool_prefix='aarch64-linux-gnu-', ccopts=[],
                       tool_opts={})
        self.assertEqual(repr(cfg), "BuildCfg('aarch64-linux-gnu')")
        # Non-default settings.
        cfg = BuildCfg(self.context, 'aarch64-linux-gnu',
                       name='aarch64-linux-gnu-name',
                       tool_prefix='aarch64-linux-gnu-prefix-',
                       ccopts=['-mx', '-my'],
                       tool_opts={'ld': ['--ldopt'], 'as': ('--asopt',)})
        self.assertEqual(repr(cfg),
                         "BuildCfg('aarch64-linux-gnu', "
                         "name='aarch64-linux-gnu-name', "
                         "tool_prefix='aarch64-linux-gnu-prefix-', "
                         "ccopts=('-mx', '-my'), "
                         "tool_opts={'as': ('--asopt',), 'ld': ('--ldopt',)})")
        # Partial default settings.
        cfg = BuildCfg(self.context, 'aarch64-linux-gnu',
                       name='aarch64-linux-gnu-ma_b', ccopts=['-ma=b'])
        self.assertEqual(repr(cfg),
                         "BuildCfg('aarch64-linux-gnu', ccopts=('-ma=b',))")

    def test_is_windows(self):
        """Test the is_windows method."""
        cfg = BuildCfg(self.context, 'i686-mingw32')
        self.assertTrue(cfg.is_windows())
        cfg = BuildCfg(self.context, 'x86_64-w64-mingw32')
        self.assertTrue(cfg.is_windows())
        cfg = BuildCfg(self.context, 'x86_64-pc-linux-gnu')
        self.assertFalse(cfg.is_windows())

    def test_use_libiconv(self):
        """Test the use_libiconv method."""
        cfg = BuildCfg(self.context, 'i686-mingw32')
        self.assertTrue(cfg.use_libiconv())
        cfg = BuildCfg(self.context, 'x86_64-w64-mingw32')
        self.assertTrue(cfg.use_libiconv())
        cfg = BuildCfg(self.context, 'x86_64-pc-linux-gnu')
        self.assertFalse(cfg.use_libiconv())

    def test_use_ncurses(self):
        """Test the use_ncurses method."""
        cfg = BuildCfg(self.context, 'i686-mingw32')
        self.assertFalse(cfg.use_ncurses())
        cfg = BuildCfg(self.context, 'x86_64-w64-mingw32')
        self.assertFalse(cfg.use_ncurses())
        cfg = BuildCfg(self.context, 'x86_64-pc-linux-gnu')
        self.assertTrue(cfg.use_ncurses())

    def test_tool_basic(self):
        """Test basic use of the tool method."""
        cfg = BuildCfg(self.context, 'aarch64-linux-gnu')
        self.assertEqual(cfg.tool('gcc'), ['aarch64-linux-gnu-gcc'])
        self.assertEqual(cfg.tool('c-compiler'), ['aarch64-linux-gnu-gcc'])
        self.assertEqual(cfg.tool('c++-compiler'), ['aarch64-linux-gnu-g++'])
        cfg = BuildCfg(self.context, 'i686-pc-linux-gnu',
                       tool_prefix='i386-linux-')
        self.assertEqual(cfg.tool('ld'), ['i386-linux-ld'])
        cfg = BuildCfg(self.context, 'x86_64-linux-gnu',
                       tool_prefix='i686-pc-linux-gnu-', ccopts=['-m64'],
                       tool_opts={'as': ['--64']})
        self.assertEqual(cfg.tool('objdump'), ['i686-pc-linux-gnu-objdump'])
        self.assertEqual(cfg.tool('c-compiler'), ['i686-pc-linux-gnu-gcc',
                                                  '-m64'])
        self.assertEqual(cfg.tool('c++-compiler'), ['i686-pc-linux-gnu-g++',
                                                    '-m64'])
        self.assertEqual(cfg.tool('c++'), ['i686-pc-linux-gnu-c++', '-m64'])
        self.assertEqual(cfg.tool('cpp'), ['i686-pc-linux-gnu-cpp', '-m64'])
        self.assertEqual(cfg.tool('g++'), ['i686-pc-linux-gnu-g++', '-m64'])
        self.assertEqual(cfg.tool('gcc'), ['i686-pc-linux-gnu-gcc', '-m64'])
        self.assertEqual(cfg.tool('as'), ['i686-pc-linux-gnu-as', '--64'])
        cfg = BuildCfg(self.context, 'x86_64-linux-gnu',
                       tool_prefix='i686-pc-linux-gnu-', ccopts=['-m64'],
                       tool_opts={'g++': ['-fsomething']})
        self.assertEqual(cfg.tool('c-compiler'), ['i686-pc-linux-gnu-gcc',
                                                  '-m64'])
        self.assertEqual(cfg.tool('c++-compiler'), ['i686-pc-linux-gnu-g++',
                                                    '-m64', '-fsomething'])
        self.assertEqual(cfg.tool('g++'), ['i686-pc-linux-gnu-g++',
                                           '-m64', '-fsomething'])
        self.assertEqual(cfg.tool('ld'), ['i686-pc-linux-gnu-ld'])

    def test_tool_mod(self):
        """Test modification of BuildCfg arguments and tool results."""
        ccopts = ['-m64']
        as_opts = ['--64']
        tool_opts = {'as': as_opts}
        cfg = BuildCfg(self.context, 'x86_64-linux-gnu',
                       tool_prefix='i686-pc-linux-gnu-', ccopts=ccopts,
                       tool_opts=tool_opts)
        self.assertEqual(cfg.tool('as'), ['i686-pc-linux-gnu-as', '--64'])
        # Modifying the original tool_opts must not change the results
        # of the tool method.
        tool_opts['as'] = ['--32']
        self.assertEqual(cfg.tool('as'), ['i686-pc-linux-gnu-as', '--64'])
        # Likewise for elements of tool_opts.
        as_opts.append('--other')
        self.assertEqual(cfg.tool('as'), ['i686-pc-linux-gnu-as', '--64'])
        # Likewise, for ccopts.
        ccopts.append('-mavx')
        self.assertEqual(cfg.tool('gcc'), ['i686-pc-linux-gnu-gcc', '-m64'])
        # Modifying the result is also OK.
        res1 = cfg.tool('gcc')
        res1.append('-mavx')
        res2 = cfg.tool('gcc')
        self.assertEqual(res1, ['i686-pc-linux-gnu-gcc', '-m64', '-mavx'])
        self.assertEqual(res2, ['i686-pc-linux-gnu-gcc', '-m64'])

    def test_configure_vars_basic(self):
        """Test basic use of the configure_vars method."""
        cfg = BuildCfg(self.context, 'aarch64-linux-gnu')
        cfg_vars = cfg.configure_vars()
        self.assertEqual(cfg_vars, sorted(cfg_vars))
        self.assertIn('CC=aarch64-linux-gnu-gcc', cfg_vars)
        self.assertIn('CXX=aarch64-linux-gnu-g++', cfg_vars)
        self.assertIn('AR=aarch64-linux-gnu-ar', cfg_vars)
        self.assertIn('AS=aarch64-linux-gnu-as', cfg_vars)
        self.assertIn('LD=aarch64-linux-gnu-ld', cfg_vars)
        self.assertIn('NM=aarch64-linux-gnu-nm', cfg_vars)
        self.assertIn('OBJCOPY=aarch64-linux-gnu-objcopy', cfg_vars)
        self.assertIn('OBJDUMP=aarch64-linux-gnu-objdump', cfg_vars)
        self.assertIn('RANLIB=aarch64-linux-gnu-ranlib', cfg_vars)
        self.assertIn('READELF=aarch64-linux-gnu-readelf', cfg_vars)
        self.assertIn('STRIP=aarch64-linux-gnu-strip', cfg_vars)
        self.assertNotIn('WINDRES=aarch64-linux-gnu-windres', cfg_vars)
        self.assertNotIn('RC=aarch64-linux-gnu-windres', cfg_vars)
        cfg = BuildCfg(self.context, 'i686-mingw32')
        cfg_vars = cfg.configure_vars()
        self.assertIn('CC=i686-mingw32-gcc', cfg_vars)
        self.assertIn('CXX=i686-mingw32-g++', cfg_vars)
        self.assertIn('AR=i686-mingw32-ar', cfg_vars)
        self.assertIn('AS=i686-mingw32-as', cfg_vars)
        self.assertIn('LD=i686-mingw32-ld', cfg_vars)
        self.assertIn('NM=i686-mingw32-nm', cfg_vars)
        self.assertIn('OBJCOPY=i686-mingw32-objcopy', cfg_vars)
        self.assertIn('OBJDUMP=i686-mingw32-objdump', cfg_vars)
        self.assertIn('RANLIB=i686-mingw32-ranlib', cfg_vars)
        self.assertIn('READELF=i686-mingw32-readelf', cfg_vars)
        self.assertIn('STRIP=i686-mingw32-strip', cfg_vars)
        self.assertIn('WINDRES=i686-mingw32-windres', cfg_vars)
        self.assertIn('RC=i686-mingw32-windres', cfg_vars)
        cfg = BuildCfg(self.context, 'x86_64-linux-gnu',
                       tool_prefix='i686-pc-linux-gnu-', ccopts=['-m64'],
                       tool_opts={'as': ['--64']})
        cfg_vars = cfg.configure_vars()
        self.assertIn('CC=i686-pc-linux-gnu-gcc -m64', cfg_vars)
        self.assertIn('CXX=i686-pc-linux-gnu-g++ -m64', cfg_vars)
        self.assertIn('AR=i686-pc-linux-gnu-ar', cfg_vars)
        self.assertIn('AS=i686-pc-linux-gnu-as --64', cfg_vars)
        self.assertIn('LD=i686-pc-linux-gnu-ld', cfg_vars)
        self.assertIn('NM=i686-pc-linux-gnu-nm', cfg_vars)
        self.assertIn('OBJCOPY=i686-pc-linux-gnu-objcopy', cfg_vars)
        self.assertIn('OBJDUMP=i686-pc-linux-gnu-objdump', cfg_vars)
        self.assertIn('RANLIB=i686-pc-linux-gnu-ranlib', cfg_vars)
        self.assertIn('READELF=i686-pc-linux-gnu-readelf', cfg_vars)
        self.assertIn('STRIP=i686-pc-linux-gnu-strip', cfg_vars)
        cfg = BuildCfg(self.context, 'x86_64-linux-gnu',
                       tool_prefix='i686-pc-linux-gnu-',
                       ccopts=['-m64', '-mavx'],
                       tool_opts={'as': ['--64', '--something']})
        cfg_vars = cfg.configure_vars()
        self.assertIn('CC=i686-pc-linux-gnu-gcc -m64 -mavx', cfg_vars)
        self.assertIn('AS=i686-pc-linux-gnu-as --64 --something', cfg_vars)
        cfg = BuildCfg(self.context, 'x86_64-linux-gnu',
                       tool_prefix='i686-pc-linux-gnu-', ccopts=['-m64'],
                       tool_opts={'as': ['--64']})
        cfg_vars = cfg.configure_vars(cflags_extra=['-DA', '-DB'])
        self.assertIn('CC=i686-pc-linux-gnu-gcc -m64 -DA -DB', cfg_vars)
        self.assertIn('CXX=i686-pc-linux-gnu-g++ -m64 -DA -DB', cfg_vars)
        self.assertIn('AR=i686-pc-linux-gnu-ar', cfg_vars)
        self.assertIn('AS=i686-pc-linux-gnu-as --64', cfg_vars)
        self.assertIn('LD=i686-pc-linux-gnu-ld', cfg_vars)
        self.assertIn('NM=i686-pc-linux-gnu-nm', cfg_vars)
        self.assertIn('OBJCOPY=i686-pc-linux-gnu-objcopy', cfg_vars)
        self.assertIn('OBJDUMP=i686-pc-linux-gnu-objdump', cfg_vars)
        self.assertIn('RANLIB=i686-pc-linux-gnu-ranlib', cfg_vars)
        self.assertIn('READELF=i686-pc-linux-gnu-readelf', cfg_vars)
        self.assertIn('STRIP=i686-pc-linux-gnu-strip', cfg_vars)

    def test_configure_vars_mod(self):
        """Test modifying the result of the configure_vars method."""
        cfg = BuildCfg(self.context, 'aarch64-linux-gnu')
        cfg_vars = cfg.configure_vars()
        cfg_vars_orig = list(cfg_vars)
        cfg_vars.append('other arg')
        cfg_vars_mod = list(cfg_vars)
        cfg_vars2 = cfg.configure_vars()
        self.assertEqual(cfg_vars2, cfg_vars_orig)
        self.assertEqual(cfg_vars, cfg_vars_mod)

    def test_configure_vars_errors(self):
        """Test errors from configure_vars."""
        cfg = BuildCfg(self.context, 'aarch64-linux-gnu')
        self.assertRaisesRegex(ScriptError,
                               'cflags_extra must be a list of strings',
                               cfg.configure_vars,
                               cflags_extra='-mfoo')
        cfg = BuildCfg(self.context, 'aarch64-linux-gnu')
        self.assertRaisesRegex(ScriptError,
                               'contains non-shell-safe value',
                               cfg.configure_vars,
                               cflags_extra=['-DFOO="a b"'])
        cfg = BuildCfg(self.context, 'aarch64-linux-gnu',
                       ccopts=['-msomething=not shell safe'])
        self.assertRaisesRegex(ScriptError,
                               'contains non-shell-safe value',
                               cfg.configure_vars)

    def test_run_tool(self):
        """Test the run_tool method."""
        cfg = BuildCfg(self.context, 'aarch64-linux-gnu', ccopts=['-mtest'])
        create_files(self.bindir, ['bin2'],
                     {'aarch64-linux-gnu-gcc':
                      '#!/bin/sh\n'
                      'echo gcc\n'
                      'printf "%s\\n" "$@"\n',
                      'aarch64-linux-gnu-as':
                      '#!/bin/sh\n'
                      'echo as\n'
                      'printf "%s\\n" "$@"\n'
                      'exit 1\n',
                      'bin2/aarch64-linux-gnu-gcc':
                      '#!/bin/sh\n'
                      'echo gcc2\n'
                      'printf "%s\\n" "$@"\n'},
                     {})
        os.chmod(os.path.join(self.bindir, 'aarch64-linux-gnu-gcc'),
                 stat.S_IRWXU)
        os.chmod(os.path.join(self.bindir, 'aarch64-linux-gnu-as'),
                 stat.S_IRWXU)
        os.chmod(os.path.join(self.bindir, 'bin2/aarch64-linux-gnu-gcc'),
                 stat.S_IRWXU)
        run_ret = cfg.run_tool('c-compiler', ['example', 'arg'],
                               path_prepend=self.bindir, check=False)
        self.assertEqual(run_ret.returncode, 0)
        self.assertEqual(run_ret.stdout, 'gcc\n-mtest\nexample\narg\n')
        self.assertEqual(run_ret.stderr, '')
        run_ret = cfg.run_tool('c-compiler', ['example', 'arg'],
                               path_prepend=self.bindir, check=True)
        self.assertEqual(run_ret.returncode, 0)
        self.assertEqual(run_ret.stdout, 'gcc\n-mtest\nexample\narg\n')
        self.assertEqual(run_ret.stderr, '')
        run_ret = cfg.run_tool('as', ['example', 'arg'],
                               path_prepend=self.bindir, check=False)
        self.assertEqual(run_ret.returncode, 1)
        self.assertEqual(run_ret.stdout, 'as\nexample\narg\n')
        self.assertEqual(run_ret.stderr, '')
        self.assertRaises(subprocess.CalledProcessError,
                          cfg.run_tool, 'as', ['example', 'arg'],
                          path_prepend=self.bindir, check=True)
        self.context.environ = dict(self.context.environ)
        self.context.environ['PATH'] = '%s:%s' % (self.bindir,
                                                  self.context.environ['PATH'])
        run_ret = cfg.run_tool('c-compiler', ['example', 'arg'],
                               path_prepend=None, check=False)
        self.assertEqual(run_ret.returncode, 0)
        self.assertEqual(run_ret.stdout, 'gcc\n-mtest\nexample\narg\n')
        self.assertEqual(run_ret.stderr, '')
        run_ret = cfg.run_tool('c-compiler', ['example', 'arg'],
                               path_prepend=os.path.join(self.bindir, 'bin2'),
                               check=False)
        self.assertEqual(run_ret.returncode, 0)
        self.assertEqual(run_ret.stdout, 'gcc2\n-mtest\nexample\narg\n')
        self.assertEqual(run_ret.stderr, '')

    def test_run_c_preprocess(self):
        """Test the run_c_preprocess method."""
        cfg = BuildCfg(self.context, 'aarch64-linux-gnu', tool_prefix='')
        self.assertEqual(cfg.run_c_preprocess('#if 1\n2\n#else\n3\n#endif\n'),
                         '2')
        self.assertEqual(cfg.run_c_preprocess('#if 0\n2\n#else\n3\n#endif\n'),
                         '3')
        self.assertRaises(subprocess.CalledProcessError,
                          cfg.run_c_preprocess, '#error "error"\n')
        create_files(self.bindir, [],
                     {'gcc':
                      '#!/bin/sh\n'
                      'exit 1'},
                     {})
        os.chmod(os.path.join(self.bindir, 'gcc'), stat.S_IRWXU)
        self.assertRaises(subprocess.CalledProcessError,
                          cfg.run_c_preprocess, 'test\n',
                          path_prepend=self.bindir)

    def test_get_endianness(self):
        """Test the get_endianness method."""
        create_files(self.bindir, [],
                     {'big-gcc':
                      '#!/bin/sh\n'
                      'sed -i -e s/__BYTE_ORDER__/4321/ '
                      '-e s/__ORDER_BIG_ENDIAN__/4321/ '
                      '-e s/__ORDER_LITTLE_ENDIAN__/1234/ $3\n'
                      'exec gcc "$@"\n',
                      'little-gcc':
                      '#!/bin/sh\n'
                      'sed -i -e s/__BYTE_ORDER__/1234/ '
                      '-e s/__ORDER_BIG_ENDIAN__/4321/ '
                      '-e s/__ORDER_LITTLE_ENDIAN__/1234/ $3\n'
                      'exec gcc "$@"\n',
                      'pdp-gcc':
                      '#!/bin/sh\n'
                      'sed -i -e s/__BYTE_ORDER__/3412/ '
                      '-e s/__ORDER_BIG_ENDIAN__/4321/ '
                      '-e s/__ORDER_LITTLE_ENDIAN__/1234/ $3\n'
                      'exec gcc "$@"\n',
                      'other-gcc':
                      '#!/bin/sh\n'
                      'echo other\n'},
                     {})
        os.chmod(os.path.join(self.bindir, 'big-gcc'), stat.S_IRWXU)
        os.chmod(os.path.join(self.bindir, 'little-gcc'), stat.S_IRWXU)
        os.chmod(os.path.join(self.bindir, 'pdp-gcc'), stat.S_IRWXU)
        os.chmod(os.path.join(self.bindir, 'other-gcc'), stat.S_IRWXU)
        cfg = BuildCfg(self.context, 'aarch64-linux-gnu', tool_prefix='big-')
        self.assertEqual(cfg.get_endianness(path_prepend=self.bindir), 'big')
        cfg = BuildCfg(self.context, 'aarch64-linux-gnu',
                       tool_prefix='little-')
        self.assertEqual(cfg.get_endianness(path_prepend=self.bindir),
                         'little')
        cfg = BuildCfg(self.context, 'aarch64-linux-gnu', tool_prefix='pdp-')
        self.assertRaises(subprocess.CalledProcessError,
                          cfg.get_endianness, path_prepend=self.bindir)
        cfg = BuildCfg(self.context, 'aarch64-linux-gnu', tool_prefix='other-')
        self.assertRaisesRegex(ScriptError,
                               'could not determine endianness: got other',
                               cfg.get_endianness, path_prepend=self.bindir)
