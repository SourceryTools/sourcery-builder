# Test sourcery.multilib.

# Copyright 2019 Mentor Graphics Corporation.

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
import unittest

from sourcery.buildcfg import BuildCfg
from sourcery.context import add_common_options, ScriptError, ScriptContext
from sourcery.multilib import Multilib
from sourcery.relcfg import ReleaseConfig, ReleaseConfigTextLoader

__all__ = ['MultilibTestCase']


class MultilibTestCase(unittest.TestCase):

    """Test the Multilib class."""

    def setUp(self):
        """Set up a Multilib test."""
        self.context = ScriptContext(['sourcery.selftests'])
        parser = argparse.ArgumentParser()
        add_common_options(parser, os.getcwd())
        self.args = parser.parse_args([])

    def test_init(self):
        """Test __init__."""
        # Most public attributes are only set after finalization, so
        # not much can be tested here.
        multilib = Multilib(self.context, 'gcc', 'glibc', ('-mx', '-my'),
                            sysroot_suffix='foo', headers_suffix='foo2',
                            sysroot_osdir='os', osdir='os2', target='other')
        self.assertEqual(multilib.ccopts, ('-mx', '-my'))
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

    def test_init_errors(self):
        """Test errors from __init__."""
        self.assertRaisesRegex(ScriptError,
                               'ccopts must be a list of strings',
                               Multilib, self.context, 'gcc', 'glibc',
                               '-msomething')

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
                            ('-mx', '-my'), sysroot_suffix='foo',
                            headers_suffix='foo2', sysroot_osdir='os',
                            osdir='os2', target='other')
        multilib.finalize(relcfg)
        self.assertEqual(repr(multilib),
                         "Multilib('generic', 'sysrooted_libc', "
                         "('-mx', '-my'), sysroot_suffix='foo', "
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
                            ('-mx', '-my'), sysroot_suffix='foo',
                            headers_suffix='foo2', sysroot_osdir='os',
                            osdir='os2', target='other')
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
                         "ccopts=('-mx', '-my'))")
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
