# Test sourcery.multilib.

# Copyright 2019-2021 Mentor Graphics Corporation.

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

"""Test sourcery.multilib."""

import argparse
import os
import shutil
import tempfile
import unittest

from sourcery.buildcfg import BuildCfg
from sourcery.context import add_common_options, ScriptError, ScriptContext
from sourcery.fstree import FSTreeCopy, FSTreeEmpty
from sourcery.multilib import Multilib
from sourcery.relcfg import ReleaseConfig, ReleaseConfigTextLoader
from sourcery.selftests.support import create_files, read_files

__all__ = ['MultilibTestCase']


class MultilibTestCase(unittest.TestCase):

    """Test the Multilib class."""

    def setUp(self):
        """Set up a Multilib test."""
        self.context = ScriptContext(['sourcery.selftests'])
        parser = argparse.ArgumentParser()
        add_common_options(parser, os.getcwd())
        self.args = parser.parse_args([])
        self.tempdir_td = tempfile.TemporaryDirectory()
        self.tempdir = self.tempdir_td.name
        self.indir = os.path.join(self.tempdir, 'in')
        self.outdir = os.path.join(self.tempdir, 'out')

    def test_init(self):
        """Test __init__."""
        # Most public attributes are only set after finalization, so
        # not much can be tested here.
        multilib = Multilib(self.context, 'gcc', 'glibc', ('-mx', '-my'),
                            tool_opts={'as': ('--64',)},
                            sysroot_suffix='foo', headers_suffix='foo2',
                            sysroot_osdir='os', osdir='os2', target='other')
        self.assertEqual(multilib.ccopts, ('-mx', '-my'))
        self.assertEqual(multilib.tool_opts, {'as': ('--64',)})
        self.assertIsNone(multilib.compiler)
        self.assertIsNone(multilib.libc)
        self.assertIsNone(multilib.sysroot_suffix)
        self.assertIsNone(multilib.headers_suffix)
        self.assertIsNone(multilib.sysroot_osdir)
        self.assertIsNone(multilib.sysroot_rel)
        self.assertIsNone(multilib.headers_rel)
        self.assertIsNone(multilib.osdir)
        self.assertIsNone(multilib.target)
        self.assertIsNone(multilib.build_cfg)
        multilib = Multilib(self.context, 'gcc', 'glibc', ('-mx', '-my'),
                            tool_opts={'as': ['--64']},
                            sysroot_suffix='foo', headers_suffix='foo2',
                            sysroot_osdir='os', osdir='os2', target='other')
        self.assertEqual(multilib.tool_opts, {'as': ('--64',)})

    def test_init_errors(self):
        """Test errors from __init__."""
        self.assertRaisesRegex(ScriptError,
                               'ccopts must be a list of strings',
                               Multilib, self.context, 'gcc', 'glibc',
                               '-msomething')
        self.assertRaisesRegex(ScriptError,
                               'tool_opts values must be lists of strings',
                               Multilib, self.context, 'gcc', 'glibc',
                               ('-msomething',), tool_opts={'as': '--64'})

    def test_repr(self):
        """Test __repr__."""
        loader = ReleaseConfigTextLoader()
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       'cfg.add_component("generic")\n'
                       'cfg.generic.vc.set(GitVC("dummy"))\n'
                       'cfg.generic.version.set("1.23")\n'
                       'cfg.add_component("sysrooted_libc")\n'
                       'cfg.sysrooted_libc.vc.set(GitVC("dummy"))\n'
                       'cfg.sysrooted_libc.version.set("1.23")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        # Test sysrooted libc case, non-default settings for everything.
        multilib = Multilib(self.context, 'generic', 'sysrooted_libc',
                            ('-mx', '-my'), tool_opts={'ld': ['-a'],
                                                       'as': ('-b',)},
                            sysroot_suffix='foo', headers_suffix='foo2',
                            sysroot_osdir='os', osdir='os2', target='other')
        multilib.finalize(relcfg)
        self.assertEqual(repr(multilib),
                         "Multilib('generic', 'sysrooted_libc', "
                         "('-mx', '-my'), tool_opts={'as': ('-b',), "
                         "'ld': ('-a',)}, sysroot_suffix='foo', "
                         "headers_suffix='foo2', sysroot_osdir='os', "
                         "osdir='os2', target='other')")
        # Test variants with some settings as defaults.
        multilib = Multilib(self.context, 'generic', 'sysrooted_libc',
                            ('-mx', '-my'), sysroot_suffix='.',
                            headers_suffix='foo2', sysroot_osdir='os',
                            osdir='os2', target='other')
        multilib.finalize(relcfg)
        self.assertEqual(repr(multilib),
                         "Multilib('generic', 'sysrooted_libc', "
                         "('-mx', '-my'), "
                         "headers_suffix='foo2', sysroot_osdir='os', "
                         "osdir='os2', target='other')")
        multilib = Multilib(self.context, 'generic', 'sysrooted_libc',
                            ('-mx', '-my'), sysroot_suffix='foo',
                            headers_suffix='.', sysroot_osdir='os',
                            osdir='os2', target='other')
        multilib.finalize(relcfg)
        self.assertEqual(repr(multilib),
                         "Multilib('generic', 'sysrooted_libc', "
                         "('-mx', '-my'), sysroot_suffix='foo', "
                         "sysroot_osdir='os', "
                         "osdir='os2', target='other')")
        multilib = Multilib(self.context, 'generic', 'sysrooted_libc',
                            ('-mx', '-my'), sysroot_suffix='foo',
                            headers_suffix='foo2', sysroot_osdir='.',
                            osdir='os2', target='other')
        multilib.finalize(relcfg)
        self.assertEqual(repr(multilib),
                         "Multilib('generic', 'sysrooted_libc', "
                         "('-mx', '-my'), sysroot_suffix='foo', "
                         "headers_suffix='foo2', "
                         "osdir='os2', target='other')")
        multilib = Multilib(self.context, 'generic', 'sysrooted_libc',
                            ('-mx', '-my'), sysroot_suffix='foo',
                            headers_suffix='foo2', sysroot_osdir='os',
                            osdir='os/foo', target='other')
        multilib.finalize(relcfg)
        self.assertEqual(repr(multilib),
                         "Multilib('generic', 'sysrooted_libc', "
                         "('-mx', '-my'), sysroot_suffix='foo', "
                         "headers_suffix='foo2', sysroot_osdir='os', "
                         "target='other')")
        multilib = Multilib(self.context, 'generic', 'sysrooted_libc',
                            ('-mx', '-my'), sysroot_suffix='foo',
                            headers_suffix='foo2', sysroot_osdir='os',
                            osdir='os2', target='aarch64-linux-gnu')
        multilib.finalize(relcfg)
        self.assertEqual(repr(multilib),
                         "Multilib('generic', 'sysrooted_libc', "
                         "('-mx', '-my'), sysroot_suffix='foo', "
                         "headers_suffix='foo2', sysroot_osdir='os', "
                         "osdir='os2')")
        # Test non-sysrooted libc case, non-default settings.
        multilib = Multilib(self.context, 'generic', 'generic',
                            ('-mx', '-my'), osdir='os2', target='other')
        multilib.finalize(relcfg)
        self.assertEqual(repr(multilib),
                         "Multilib('generic', 'generic', "
                         "('-mx', '-my'), osdir='os2', target='other')")
        # Test variants with some settings as defaults.
        multilib = Multilib(self.context, 'generic', 'generic',
                            ('-mx', '-my'), osdir='.', target='other')
        multilib.finalize(relcfg)
        self.assertEqual(repr(multilib),
                         "Multilib('generic', 'generic', "
                         "('-mx', '-my'), target='other')")
        multilib = Multilib(self.context, 'generic', 'generic',
                            ('-mx', '-my'), osdir='os2',
                            target='aarch64-linux-gnu')
        multilib.finalize(relcfg)
        self.assertEqual(repr(multilib),
                         "Multilib('generic', 'generic', "
                         "('-mx', '-my'), osdir='os2')")
        # Test no libc component, sysrooted, non-default settings.
        multilib = Multilib(self.context, 'generic', None,
                            ('-mx', '-my'), sysroot_suffix='foo',
                            headers_suffix='foo2', sysroot_osdir='os',
                            osdir='os2', target='other')
        multilib.finalize(relcfg)
        self.assertEqual(repr(multilib),
                         "Multilib('generic', None, "
                         "('-mx', '-my'), sysroot_suffix='foo', "
                         "headers_suffix='foo2', sysroot_osdir='os', "
                         "osdir='os2', target='other')")
        # Test variants with some settings as defaults.
        multilib = Multilib(self.context, 'generic', None,
                            ('-mx', '-my'), sysroot_suffix='.',
                            headers_suffix='foo2', sysroot_osdir='os',
                            osdir='os2', target='other')
        multilib.finalize(relcfg)
        self.assertEqual(repr(multilib),
                         "Multilib('generic', None, "
                         "('-mx', '-my'), sysroot_suffix='.', "
                         "headers_suffix='foo2', sysroot_osdir='os', "
                         "osdir='os2', target='other')")
        multilib = Multilib(self.context, 'generic', None,
                            ('-mx', '-my'), sysroot_suffix='foo',
                            headers_suffix='.', sysroot_osdir='os',
                            osdir='os2', target='other')
        multilib.finalize(relcfg)
        self.assertEqual(repr(multilib),
                         "Multilib('generic', None, "
                         "('-mx', '-my'), sysroot_suffix='foo', "
                         "sysroot_osdir='os', "
                         "osdir='os2', target='other')")
        multilib = Multilib(self.context, 'generic', None,
                            ('-mx', '-my'), sysroot_suffix='foo',
                            headers_suffix='foo2', sysroot_osdir='.',
                            osdir='os2', target='other')
        multilib.finalize(relcfg)
        self.assertEqual(repr(multilib),
                         "Multilib('generic', None, "
                         "('-mx', '-my'), sysroot_suffix='foo', "
                         "headers_suffix='foo2', "
                         "osdir='os2', target='other')")
        multilib = Multilib(self.context, 'generic', None,
                            ('-mx', '-my'), sysroot_suffix='foo',
                            headers_suffix='foo2', sysroot_osdir='os',
                            osdir='os/foo', target='other')
        multilib.finalize(relcfg)
        self.assertEqual(repr(multilib),
                         "Multilib('generic', None, "
                         "('-mx', '-my'), sysroot_suffix='foo', "
                         "headers_suffix='foo2', sysroot_osdir='os', "
                         "target='other')")
        multilib = Multilib(self.context, 'generic', None,
                            ('-mx', '-my'), sysroot_suffix='foo',
                            headers_suffix='foo2', sysroot_osdir='os',
                            osdir='os2', target='aarch64-linux-gnu')
        multilib.finalize(relcfg)
        self.assertEqual(repr(multilib),
                         "Multilib('generic', None, "
                         "('-mx', '-my'), sysroot_suffix='foo', "
                         "headers_suffix='foo2', sysroot_osdir='os', "
                         "osdir='os2')")
        # Test no libc component, non-sysrooted, non-default settings.
        multilib = Multilib(self.context, 'generic', None,
                            ('-mx', '-my'), osdir='os2', target='other')
        multilib.finalize(relcfg)
        self.assertEqual(repr(multilib),
                         "Multilib('generic', None, "
                         "('-mx', '-my'), osdir='os2', target='other')")
        # Test variants with some settings as defaults.
        multilib = Multilib(self.context, 'generic', None,
                            ('-mx', '-my'), osdir='.', target='other')
        multilib.finalize(relcfg)
        self.assertEqual(repr(multilib),
                         "Multilib('generic', None, "
                         "('-mx', '-my'), target='other')")
        multilib = Multilib(self.context, 'generic', None,
                            ('-mx', '-my'), osdir='os2',
                            target='aarch64-linux-gnu')
        multilib.finalize(relcfg)
        self.assertEqual(repr(multilib),
                         "Multilib('generic', None, "
                         "('-mx', '-my'), osdir='os2')")

    def test_finalize(self):
        """Test finalize."""
        loader = ReleaseConfigTextLoader()
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       'cfg.add_component("generic")\n'
                       'cfg.generic.vc.set(GitVC("dummy"))\n'
                       'cfg.generic.version.set("1.23")\n'
                       'cfg.add_component("sysrooted_libc")\n'
                       'cfg.sysrooted_libc.vc.set(GitVC("dummy"))\n'
                       'cfg.sysrooted_libc.version.set("1.23")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        # Test sysrooted libc case, non-default settings for everything.
        multilib = Multilib(self.context, 'generic', 'sysrooted_libc',
                            ('-mx', '-my'), tool_opts={'as': ['--opt']},
                            sysroot_suffix='foo', headers_suffix='foo2',
                            sysroot_osdir='os', osdir='os2', target='other')
        multilib.finalize(relcfg)
        self.assertIs(multilib.compiler, relcfg.get_component('generic'))
        self.assertIs(multilib.libc, relcfg.get_component('sysrooted_libc'))
        self.assertEqual(multilib.sysroot_suffix, 'foo')
        self.assertEqual(multilib.headers_suffix, 'foo2')
        self.assertEqual(multilib.sysroot_osdir, 'os')
        self.assertEqual(multilib.sysroot_rel,
                         'opt/toolchain/aarch64-linux-gnu/libc/foo')
        self.assertEqual(multilib.headers_rel,
                         'opt/toolchain/aarch64-linux-gnu/libc/foo2')
        self.assertEqual(multilib.osdir, 'os2')
        self.assertEqual(multilib.target, 'other')
        self.assertIsInstance(multilib.build_cfg, BuildCfg)
        self.assertEqual(repr(multilib.build_cfg),
                         "BuildCfg('other', tool_prefix='aarch64-linux-gnu-', "
                         "ccopts=('-mx', '-my'), "
                         "tool_opts={'as': ('--opt',)})")
        # Test sysrooted libc case, default settings.
        multilib = Multilib(self.context, 'generic', 'sysrooted_libc', ())
        multilib.finalize(relcfg)
        self.assertIs(multilib.compiler, relcfg.get_component('generic'))
        self.assertIs(multilib.libc, relcfg.get_component('sysrooted_libc'))
        self.assertEqual(multilib.sysroot_suffix, '.')
        self.assertEqual(multilib.headers_suffix, '.')
        self.assertEqual(multilib.sysroot_osdir, '.')
        self.assertEqual(multilib.sysroot_rel,
                         'opt/toolchain/aarch64-linux-gnu/libc')
        self.assertEqual(multilib.headers_rel,
                         'opt/toolchain/aarch64-linux-gnu/libc')
        self.assertEqual(multilib.osdir, '.')
        self.assertEqual(multilib.target, 'aarch64-linux-gnu')
        self.assertIsInstance(multilib.build_cfg, BuildCfg)
        self.assertEqual(repr(multilib.build_cfg),
                         "BuildCfg('aarch64-linux-gnu')")
        # Test non-sysrooted libc case, non-default settings.
        multilib = Multilib(self.context, 'generic', 'generic',
                            ('-mx', '-my'), osdir='os2', target='other')
        multilib.finalize(relcfg)
        self.assertIs(multilib.compiler, relcfg.get_component('generic'))
        self.assertIs(multilib.libc, relcfg.get_component('generic'))
        self.assertIsNone(multilib.sysroot_suffix)
        self.assertIsNone(multilib.headers_suffix)
        self.assertIsNone(multilib.sysroot_osdir)
        self.assertIsNone(multilib.sysroot_rel)
        self.assertIsNone(multilib.headers_rel)
        self.assertEqual(multilib.osdir, 'os2')
        self.assertEqual(multilib.target, 'other')
        self.assertIsInstance(multilib.build_cfg, BuildCfg)
        self.assertEqual(repr(multilib.build_cfg),
                         "BuildCfg('other', tool_prefix='aarch64-linux-gnu-', "
                         "ccopts=('-mx', '-my'))")
        # Test non-sysrooted libc case, default settings.
        multilib = Multilib(self.context, 'generic', 'generic', ())
        multilib.finalize(relcfg)
        self.assertIs(multilib.compiler, relcfg.get_component('generic'))
        self.assertIs(multilib.libc, relcfg.get_component('generic'))
        self.assertIsNone(multilib.sysroot_suffix)
        self.assertIsNone(multilib.headers_suffix)
        self.assertIsNone(multilib.sysroot_osdir)
        self.assertIsNone(multilib.sysroot_rel)
        self.assertIsNone(multilib.headers_rel)
        self.assertEqual(multilib.osdir, '.')
        self.assertEqual(multilib.target, 'aarch64-linux-gnu')
        self.assertIsInstance(multilib.build_cfg, BuildCfg)
        self.assertEqual(repr(multilib.build_cfg),
                         "BuildCfg('aarch64-linux-gnu')")
        # Test no libc component, sysrooted, non-default settings.
        multilib = Multilib(self.context, 'generic', None,
                            ('-mx', '-my'), sysroot_suffix='foo',
                            headers_suffix='foo2', sysroot_osdir='os',
                            osdir='os2', target='other')
        multilib.finalize(relcfg)
        self.assertIs(multilib.compiler, relcfg.get_component('generic'))
        self.assertIsNone(multilib.libc)
        self.assertEqual(multilib.sysroot_suffix, 'foo')
        self.assertEqual(multilib.headers_suffix, 'foo2')
        self.assertEqual(multilib.sysroot_osdir, 'os')
        self.assertEqual(multilib.sysroot_rel,
                         'opt/toolchain/aarch64-linux-gnu/libc/foo')
        self.assertEqual(multilib.headers_rel,
                         'opt/toolchain/aarch64-linux-gnu/libc/foo2')
        self.assertEqual(multilib.osdir, 'os2')
        self.assertEqual(multilib.target, 'other')
        self.assertIsInstance(multilib.build_cfg, BuildCfg)
        self.assertEqual(repr(multilib.build_cfg),
                         "BuildCfg('other', tool_prefix='aarch64-linux-gnu-', "
                         "ccopts=('-mx', '-my'))")
        # Test no libc component, sysrooted, default settings.
        multilib = Multilib(self.context, 'generic', None, (),
                            sysroot_suffix='.')
        multilib.finalize(relcfg)
        self.assertIs(multilib.compiler, relcfg.get_component('generic'))
        self.assertIsNone(multilib.libc)
        self.assertEqual(multilib.sysroot_suffix, '.')
        self.assertEqual(multilib.headers_suffix, '.')
        self.assertEqual(multilib.sysroot_osdir, '.')
        self.assertEqual(multilib.sysroot_rel,
                         'opt/toolchain/aarch64-linux-gnu/libc')
        self.assertEqual(multilib.headers_rel,
                         'opt/toolchain/aarch64-linux-gnu/libc')
        self.assertEqual(multilib.osdir, '.')
        self.assertEqual(multilib.target, 'aarch64-linux-gnu')
        self.assertIsInstance(multilib.build_cfg, BuildCfg)
        self.assertEqual(repr(multilib.build_cfg),
                         "BuildCfg('aarch64-linux-gnu')")
        # Test no libc component, non-sysrooted, non-default settings.
        multilib = Multilib(self.context, 'generic', None,
                            ('-mx', '-my'), osdir='os2', target='other')
        multilib.finalize(relcfg)
        self.assertIs(multilib.compiler, relcfg.get_component('generic'))
        self.assertIsNone(multilib.libc)
        self.assertIsNone(multilib.sysroot_suffix)
        self.assertIsNone(multilib.headers_suffix)
        self.assertIsNone(multilib.sysroot_osdir)
        self.assertIsNone(multilib.sysroot_rel)
        self.assertIsNone(multilib.headers_rel)
        self.assertEqual(multilib.osdir, 'os2')
        self.assertEqual(multilib.target, 'other')
        self.assertIsInstance(multilib.build_cfg, BuildCfg)
        self.assertEqual(repr(multilib.build_cfg),
                         "BuildCfg('other', tool_prefix='aarch64-linux-gnu-', "
                         "ccopts=('-mx', '-my'))")
        # Test no libc component, non-sysrooted, default settings.
        multilib = Multilib(self.context, 'generic', None, ())
        multilib.finalize(relcfg)
        self.assertIs(multilib.compiler, relcfg.get_component('generic'))
        self.assertIsNone(multilib.libc)
        self.assertIsNone(multilib.sysroot_suffix)
        self.assertIsNone(multilib.headers_suffix)
        self.assertIsNone(multilib.sysroot_osdir)
        self.assertIsNone(multilib.sysroot_rel)
        self.assertIsNone(multilib.headers_rel)
        self.assertEqual(multilib.osdir, '.')
        self.assertEqual(multilib.target, 'aarch64-linux-gnu')
        self.assertIsInstance(multilib.build_cfg, BuildCfg)
        self.assertEqual(repr(multilib.build_cfg),
                         "BuildCfg('aarch64-linux-gnu')")
        # Test default for osdir derived from non-default
        # sysroot_suffix and sysroot_osdir settings.
        multilib = Multilib(self.context, 'generic', 'sysrooted_libc',
                            (), sysroot_suffix='foo', sysroot_osdir='os')
        multilib.finalize(relcfg)
        self.assertEqual(multilib.osdir, 'os/foo')
        multilib = Multilib(self.context, 'generic', 'sysrooted_libc',
                            (), sysroot_suffix='foo', sysroot_osdir='../lib64')
        multilib.finalize(relcfg)
        self.assertEqual(multilib.osdir, '../lib64/foo')
        multilib = Multilib(self.context, 'generic', 'sysrooted_libc',
                            (), sysroot_suffix='.', sysroot_osdir='../lib64')
        multilib.finalize(relcfg)
        self.assertEqual(multilib.osdir, '../lib64')
        multilib = Multilib(self.context, 'generic', 'sysrooted_libc',
                            (), sysroot_suffix='foo', sysroot_osdir='.')
        multilib.finalize(relcfg)
        self.assertEqual(multilib.osdir, 'foo')

    def test_finalize_errors(self):
        """Test errors from finalize."""
        loader = ReleaseConfigTextLoader()
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       'cfg.add_component("generic")\n'
                       'cfg.generic.vc.set(GitVC("dummy"))\n'
                       'cfg.generic.version.set("1.23")\n'
                       'cfg.add_component("sysrooted_libc")\n'
                       'cfg.sysrooted_libc.vc.set(GitVC("dummy"))\n'
                       'cfg.sysrooted_libc.version.set("1.23")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        multilib = Multilib(self.context, 'generic', None, ())
        multilib.finalize(relcfg)
        self.assertRaisesRegex(ScriptError,
                               'multilib already finalized',
                               multilib.finalize, relcfg)
        # Test errors for inappropriate settings for non-sysrooted libc.
        multilib = Multilib(self.context, 'generic', 'generic', (),
                            sysroot_suffix='.')
        self.assertRaisesRegex(ScriptError,
                               'sysroot suffix for non-sysrooted libc',
                               multilib.finalize, relcfg)
        multilib = Multilib(self.context, 'generic', 'generic', (),
                            headers_suffix='.')
        self.assertRaisesRegex(ScriptError,
                               'headers suffix for non-sysrooted libc',
                               multilib.finalize, relcfg)
        multilib = Multilib(self.context, 'generic', 'generic', (),
                            sysroot_osdir='.')
        self.assertRaisesRegex(ScriptError,
                               'sysroot osdir for non-sysrooted libc',
                               multilib.finalize, relcfg)
        # Test errors for inappropriate settings for non-sysrooted
        # libc, no libc component.
        multilib = Multilib(self.context, 'generic', None, (),
                            headers_suffix='.')
        self.assertRaisesRegex(ScriptError,
                               'headers suffix for non-sysrooted libc',
                               multilib.finalize, relcfg)
        multilib = Multilib(self.context, 'generic', None, (),
                            sysroot_osdir='.')
        self.assertRaisesRegex(ScriptError,
                               'sysroot osdir for non-sysrooted libc',
                               multilib.finalize, relcfg)

    def test_move_sysroot_executables(self):
        """Test move_sysroot_executables."""
        loader = ReleaseConfigTextLoader()
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       'cfg.add_component("generic")\n'
                       'cfg.generic.vc.set(GitVC("dummy"))\n'
                       'cfg.generic.version.set("1.23")\n'
                       'cfg.add_component("sysrooted_libc")\n'
                       'cfg.sysrooted_libc.vc.set(GitVC("dummy"))\n'
                       'cfg.sysrooted_libc.version.set("1.23")\n'
                       'cfg.multilibs.set((Multilib("generic", '
                       '"sysrooted_libc", ()), Multilib("generic", '
                       '"sysrooted_libc", ("-m64",), '
                       'sysroot_osdir="../lib64"), Multilib("generic", '
                       '"sysrooted_libc", ("-mfoo",), '
                       'sysroot_suffix="foo")))\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        multilibs = relcfg.multilibs.get()
        create_files(self.indir, ['bin1', 'bin2'],
                     {'bin1/a': 'file bin1/a', 'bin2/b': 'file bin2/b'},
                     {})
        tree = FSTreeCopy(self.context, self.indir, {'name'})
        tree_moved = multilibs[0].move_sysroot_executables(tree,
                                                           ('bin1', 'bin2'))
        tree_moved.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'bin1', 'bin2', 'usr', 'usr/lib', 'usr/lib/bin'},
                          {'usr/lib/bin/a': 'file bin1/a',
                           'usr/lib/bin/b': 'file bin2/b'},
                          {}))
        shutil.rmtree(self.outdir)
        tree_moved = multilibs[1].move_sysroot_executables(tree,
                                                           ['bin1', 'bin2'])
        tree_moved.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'bin1', 'bin2', 'usr', 'usr/lib64',
                           'usr/lib64/bin'},
                          {'usr/lib64/bin/a': 'file bin1/a',
                           'usr/lib64/bin/b': 'file bin2/b'},
                          {}))
        shutil.rmtree(self.outdir)
        # When only one multilib uses the sysroot, the files are kept
        # in their original locations as well as being copied.
        tree_moved = multilibs[2].move_sysroot_executables(tree,
                                                           ('bin1', 'bin2'))
        tree_moved.export(self.outdir)
        self.assertEqual(read_files(self.outdir),
                         ({'bin1', 'bin2', 'usr', 'usr/lib', 'usr/lib/bin'},
                          {'bin1/a': 'file bin1/a', 'bin2/b': 'file bin2/b',
                           'usr/lib/bin/a': 'file bin1/a',
                           'usr/lib/bin/b': 'file bin2/b'},
                          {}))

    def test_move_sysroot_executables_errors(self):
        """Test errors from move_sysroot_executables."""
        loader = ReleaseConfigTextLoader()
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       'cfg.add_component("generic")\n'
                       'cfg.generic.vc.set(GitVC("dummy"))\n'
                       'cfg.generic.version.set("1.23")\n'
                       'cfg.multilibs.set((Multilib("generic", '
                       '"generic", ()),))\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        multilib = relcfg.multilibs.get()[0]
        tree = FSTreeEmpty(self.context)
        self.assertRaisesRegex(ScriptError,
                               'move_sysroot_executables called for '
                               'non-sysroot multilib',
                               multilib.move_sysroot_executables,
                               tree, ('bin',))
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       'cfg.add_component("generic")\n'
                       'cfg.generic.vc.set(GitVC("dummy"))\n'
                       'cfg.generic.version.set("1.23")\n'
                       'cfg.add_component("sysrooted_libc")\n'
                       'cfg.sysrooted_libc.vc.set(GitVC("dummy"))\n'
                       'cfg.sysrooted_libc.version.set("1.23")\n'
                       'cfg.multilibs.set((Multilib("generic", '
                       '"sysrooted_libc", ()),))\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        multilib = relcfg.multilibs.get()[0]
        tree = FSTreeEmpty(self.context)
        self.assertRaisesRegex(ScriptError,
                               'dirs must be a list of strings, not a single '
                               'string',
                               multilib.move_sysroot_executables,
                               tree, 'bin')
