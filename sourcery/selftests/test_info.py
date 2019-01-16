# Test sourcery.info.

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

"""Test sourcery.info."""

import argparse
import os
import unittest

from sourcery.context import add_common_options, ScriptContext
from sourcery.info import info_text
from sourcery.relcfg import ReleaseConfigTextLoader, ReleaseConfig

__all__ = ['InfoTextTestCase']


class InfoTextTestCase(unittest.TestCase):

    """Test the info_text function."""

    def setUp(self):
        """Set up an info_text test."""
        self.context = ScriptContext(['sourcery.selftests'])
        self.parser = argparse.ArgumentParser()
        add_common_options(self.parser, os.getcwd())
        self.args = self.parser.parse_args([])

    def test_info_text(self):
        """Test the info_text function."""
        loader = ReleaseConfigTextLoader()
        # Test a trivial config, with no explicitly added components
        # (but implicit components still present).
        relcfg_text = ('cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        text = info_text(relcfg, False, False)
        self.assertEqual(text,
                         '%-30s package\n\n%-30s (no source)'
                         % ('Components:', 'package'))
        text = info_text(relcfg, True, False)
        self.assertTrue(text.startswith('Components:'))
        self.assertIn('\n\nVariables:\n\n', text)
        self.assertIn('\n%-30s %s\n' % ('build',
                                        "PkgHost('x86_64-linux-gnu')"),
                      text)
        self.assertNotIn('Internal variables:', text)
        self.assertNotIn('\ninstalldir_rel', text)
        self.assertFalse(text.endswith('\n'))
        text = info_text(relcfg, False, True)
        self.assertTrue(text.startswith('Components:'))
        self.assertNotIn('Variables:', text)
        self.assertIn('\n\nInternal variables:\n\n', text)
        self.assertIn('\n%-30s %s\n' % ('installdir_rel', "'opt/toolchain'"),
                      text)
        self.assertFalse(text.endswith('\n'))
        # Test a config with components.
        relcfg_text = ('cfg.add_component("generic")\n'
                       'cfg.generic.version.set("1.23")\n'
                       'cfg.generic.vc.set(TarVC("dummy"))\n'
                       'cfg.add_component("zz_no_source")\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n')
        relcfg = ReleaseConfig(self.context, relcfg_text, loader, self.args)
        text = info_text(relcfg, False, False)
        self.assertTrue(text.startswith('%-30s %s\n\n'
                                        % ('Components:',
                                           'generic package zz_no_source')))
        self.assertIn('\n\n%-30s 1.23\n' % 'generic', text)
        self.assertTrue(text.endswith('\n%-30s (no source)' % 'zz_no_source'))
        text = info_text(relcfg, True, False)
        self.assertIn("\n%-30s '1.23'\n\n" % 'generic.version', text)
        self.assertIn('\n%-30s None' % 'zz_no_source.version', text)
        self.assertNotIn('\ngeneric.srcdir ', text)
        text = info_text(relcfg, False, True)
        # Verify no stray newline added for last component
        # (alphabetically) not having internal variables.
        self.assertFalse(text.endswith('\n'))
        self.assertIn("\n%-30s '" % 'generic.srcdir', text)
        self.assertNotIn('\nzz_no_source.srcdir', text)
