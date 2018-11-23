# Test sourcery.vc.

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

"""Test sourcery.vc."""

import argparse
import io
import os
import os.path
import shutil
import subprocess
import tempfile
import time
import unittest

import sourcery.context
from sourcery.relcfg import ReleaseConfig, ReleaseConfigTextLoader
from sourcery.vc import GitVC, SvnVC, TarVC

__all__ = ['VCTestCase', 'VCRelCfgTestCase']


class VCTestCase(unittest.TestCase):

    """Test the version control support."""

    def setUp(self):
        """Set up a version control test."""
        self.context = sourcery.context.ScriptContext()
        self.context.silent = True
        self.tempdir_td = tempfile.TemporaryDirectory()
        self.tempdir = self.tempdir_td.name
        self.svndir = os.path.join(self.tempdir, 'svn')
        self.codir = os.path.join(self.tempdir, 'co')
        self.srcdir = os.path.join(self.tempdir, 'src')

    def tearDown(self):
        """Tear down a version control test."""
        self.tempdir_td.cleanup()

    def co_file(self, name):
        """Return the name of a file in codir for this test."""
        return os.path.join(self.codir, name)

    def co_file_write(self, name, contents):
        """Write to a file in codir for this test."""
        with open(self.co_file(name), 'w', encoding='utf-8') as file:
            file.write(contents)

    def src_file(self, name):
        """Return the name of a file in srcdir for this test."""
        return os.path.join(self.srcdir, name)

    def src_file_read(self, name):
        """Read a file in srcdir for this test."""
        with open(self.src_file(name), 'r', encoding='utf-8') as file:
            return file.read()

    def test_git(self):
        """Test checkouts from git."""
        os.mkdir(self.codir)
        subprocess.run(['git', 'init', '-q'], cwd=self.codir, check=True)
        self.co_file_write('gitfile', 'gitfile contents')
        subprocess.run(['git', 'add', '.'], cwd=self.codir, check=True)
        subprocess.run(['git', 'commit', '-q', '-m', 'commit message'],
                       cwd=self.codir, check=True)
        vc_obj = GitVC(self.context, self.codir)
        vc_obj.vc_checkout(self.srcdir, False)
        self.assertEqual(self.src_file_read('gitfile'), 'gitfile contents')
        self.co_file_write('gitfile', 'modified contents')
        subprocess.run(['git', 'commit', '-q', '-a', '-m', 'commit 2'],
                       cwd=self.codir, check=True)
        vc_obj.vc_checkout(self.srcdir, True)
        self.assertEqual(self.src_file_read('gitfile'), 'modified contents')

    def test_git_branch(self):
        """Test checkouts from git, non-master branch."""
        os.mkdir(self.codir)
        subprocess.run(['git', 'init', '-q'], cwd=self.codir, check=True)
        self.co_file_write('gitfile', 'gitfile contents')
        subprocess.run(['git', 'add', '.'], cwd=self.codir, check=True)
        subprocess.run(['git', 'commit', '-q', '-m', 'commit message'],
                       cwd=self.codir, check=True)
        subprocess.run(['git', 'branch', '-q', 'newbranch'], cwd=self.codir,
                       check=True)
        vc_obj = GitVC(self.context, self.codir, 'newbranch')
        vc_obj.vc_checkout(self.srcdir, False)
        self.assertEqual(self.src_file_read('gitfile'), 'gitfile contents')
        self.co_file_write('gitfile', 'modified contents')
        subprocess.run(['git', 'commit', '-q', '-a', '-m', 'commit 2'],
                       cwd=self.codir, check=True)
        # master has been modified, but not yet newbranch.
        vc_obj.vc_checkout(self.srcdir, True)
        self.assertEqual(self.src_file_read('gitfile'), 'gitfile contents')
        subprocess.run(['git', 'checkout', '-q', 'newbranch'], cwd=self.codir,
                       check=True)
        subprocess.run(['git', 'merge', '-q', 'master'], cwd=self.codir,
                       check=True)
        # newbranch has now been modified as well.
        vc_obj.vc_checkout(self.srcdir, True)
        self.assertEqual(self.src_file_read('gitfile'), 'modified contents')

    def test_git_errors(self):
        """Test checkouts from git, errors."""
        self.context.execute_silent = True
        os.mkdir(self.codir)
        subprocess.run(['git', 'init', '-q'], cwd=self.codir, check=True)
        self.co_file_write('gitfile', 'gitfile contents')
        subprocess.run(['git', 'add', '.'], cwd=self.codir, check=True)
        subprocess.run(['git', 'commit', '-q', '-m', 'commit message'],
                       cwd=self.codir, check=True)
        vc_obj = GitVC(self.context, self.codir)
        vc_obj.vc_checkout(self.srcdir, False)
        self.assertEqual(self.src_file_read('gitfile'), 'gitfile contents')
        shutil.rmtree(self.codir)
        self.assertRaises(subprocess.CalledProcessError, vc_obj.vc_checkout,
                          self.srcdir, True)
        shutil.rmtree(self.srcdir)
        self.assertRaises(subprocess.CalledProcessError, vc_obj.vc_checkout,
                          self.srcdir, False)

    def test_git_repr(self):
        """Test GitVC.__repr__."""
        vc_obj = GitVC(self.context, '/example')
        self.assertEqual(repr(vc_obj), "GitVC('/example', 'master')")
        vc_obj = GitVC(self.context, '/example', 'branch')
        self.assertEqual(repr(vc_obj), "GitVC('/example', 'branch')")

    def test_svn(self):
        """Test checkouts from SVN."""
        subprocess.run(['svnadmin', 'create', self.svndir], check=True)
        svn_uri = 'file://%s' % self.svndir
        subprocess.run(['svn', '-q', 'co', svn_uri, self.codir], check=True)
        self.co_file_write('svnfile', 'svnfile contents')
        subprocess.run(['svn', '-q', 'add', 'svnfile'], cwd=self.codir,
                       check=True)
        subprocess.run(['svn', '-q', 'commit', '-m', 'commit message'],
                       cwd=self.codir, check=True)
        vc_obj = SvnVC(self.context, svn_uri)
        vc_obj.vc_checkout(self.srcdir, False)
        self.assertEqual(self.src_file_read('svnfile'), 'svnfile contents')
        self.co_file_write('svnfile', 'modified contents')
        subprocess.run(['svn', '-q', 'commit', '-m', 'commit 2'],
                       cwd=self.codir, check=True)
        vc_obj.vc_checkout(self.srcdir, True)
        self.assertEqual(self.src_file_read('svnfile'), 'modified contents')

    def test_svn_errors(self):
        """Test checkouts from SVN, errors."""
        self.context.execute_silent = True
        subprocess.run(['svnadmin', 'create', self.svndir], check=True)
        svn_uri = 'file://%s' % self.svndir
        subprocess.run(['svn', '-q', 'co', svn_uri, self.codir], check=True)
        self.co_file_write('svnfile', 'svnfile contents')
        subprocess.run(['svn', '-q', 'add', 'svnfile'], cwd=self.codir,
                       check=True)
        subprocess.run(['svn', '-q', 'commit', '-m', 'commit message'],
                       cwd=self.codir, check=True)
        vc_obj = SvnVC(self.context, svn_uri)
        vc_obj.vc_checkout(self.srcdir, False)
        self.assertEqual(self.src_file_read('svnfile'), 'svnfile contents')
        shutil.rmtree(self.svndir)
        self.assertRaises(subprocess.CalledProcessError, vc_obj.vc_checkout,
                          self.srcdir, True)
        shutil.rmtree(self.srcdir)
        self.assertRaises(subprocess.CalledProcessError, vc_obj.vc_checkout,
                          self.srcdir, False)

    def test_svn_repr(self):
        """Test SvnVC.__repr__."""
        vc_obj = SvnVC(self.context, 'file:///example')
        self.assertEqual(repr(vc_obj), "SvnVC('file:///example')")

    def test_tar(self):
        """Test checkouts from tarballs."""
        # This deliberately creates tarballs with the tar command, not
        # Python's tarfile module, to avoid any dependence on whether
        # the relevant xz / bz2 libraries were available when Python
        # was built.
        # Single, empty directory.
        os.mkdir(self.codir)
        subprocess.run(['tar', '-c', '-f', 'test.tar', 'co'], cwd=self.tempdir,
                       check=True)
        vc_obj = TarVC(self.context, os.path.join(self.tempdir, 'test.tar'))
        vc_obj.vc_checkout(self.srcdir, False)
        contents = sorted(os.listdir(self.srcdir))
        self.assertEqual(contents, [])
        shutil.rmtree(self.srcdir)
        # Single, nonempty directory.
        self.co_file_write('tarfile', 'tarfile contents')
        subprocess.run(['tar', '-c', '-z', '-f', 'test.tar.gz', 'co'],
                       cwd=self.tempdir, check=True)
        vc_obj = TarVC(self.context, os.path.join(self.tempdir, 'test.tar.gz'))
        vc_obj.vc_checkout(self.srcdir, False)
        contents = sorted(os.listdir(self.srcdir))
        self.assertEqual(contents, ['tarfile'])
        self.assertEqual(self.src_file_read('tarfile'), 'tarfile contents')
        shutil.rmtree(self.srcdir)
        # Single file.
        self.co_file_write('tarfile', 'tarfile contents 2')
        subprocess.run(['tar', '-c', '-j', '-f', '../test.tar.bz2', 'tarfile'],
                       cwd=self.codir, check=True)
        vc_obj = TarVC(self.context, os.path.join(self.tempdir,
                                                  'test.tar.bz2'))
        vc_obj.vc_checkout(self.srcdir, False)
        contents = sorted(os.listdir(self.srcdir))
        self.assertEqual(contents, ['tarfile'])
        self.assertEqual(self.src_file_read('tarfile'), 'tarfile contents 2')
        shutil.rmtree(self.srcdir)
        # Single symlink.
        os.symlink('/', os.path.join(self.codir, 'symlink'))
        subprocess.run(['tar', '-c', '-J', '-f', '../test.tar.xz', 'symlink'],
                       cwd=self.codir, check=True)
        vc_obj = TarVC(self.context, os.path.join(self.tempdir, 'test.tar.xz'))
        vc_obj.vc_checkout(self.srcdir, False)
        contents = sorted(os.listdir(self.srcdir))
        self.assertEqual(contents, ['symlink'])
        self.assertEqual(os.readlink(os.path.join(self.srcdir, 'symlink')),
                         '/')
        shutil.rmtree(self.srcdir)
        shutil.rmtree(self.codir)
        os.mkdir(self.codir)
        # Multiple files.
        self.co_file_write('file1', 'file1 contents')
        self.co_file_write('file2', 'file2 contents')
        subprocess.run(['tar', '-c', '-f', '../test.tar', 'file1', 'file2'],
                       cwd=self.codir, check=True)
        vc_obj = TarVC(self.context, os.path.join(self.tempdir, 'test.tar'))
        vc_obj.vc_checkout(self.srcdir, False)
        contents = sorted(os.listdir(self.srcdir))
        self.assertEqual(contents, ['file1', 'file2'])
        self.assertEqual(self.src_file_read('file1'), 'file1 contents')
        self.assertEqual(self.src_file_read('file2'), 'file2 contents')
        shutil.rmtree(self.srcdir)
        # Empty tarball.
        subprocess.run(['tar', '-c', '-T', '/dev/null', '-f', 'test.tar'],
                       cwd=self.tempdir, check=True)
        vc_obj = TarVC(self.context, os.path.join(self.tempdir, 'test.tar'))
        vc_obj.vc_checkout(self.srcdir, False)
        contents = sorted(os.listdir(self.srcdir))
        self.assertEqual(contents, [])
        # Warning for not updating sources.
        self.context.message_file = io.StringIO()
        vc_obj.vc_checkout(self.srcdir, True)
        self.assertIn('warning: not updating',
                      self.context.message_file.getvalue())
        shutil.rmtree(self.srcdir)

    def test_tar_errors(self):
        """Test checkouts from tarballs, errors."""
        self.context.execute_silent = True
        vc_obj = TarVC(self.context, os.path.join(self.tempdir, 'test.tar'))
        self.assertRaises(subprocess.CalledProcessError, vc_obj.vc_checkout,
                          self.srcdir, False)

    def test_tar_repr(self):
        """Test TarVC.__repr__."""
        vc_obj = TarVC(self.context, '/test.tar')
        self.assertEqual(repr(vc_obj), "TarVC('/test.tar')")


class VCRelCfgTestCase(unittest.TestCase):

    """Test the version control support using release configs."""

    def setUp(self):
        """Set up a version control test."""
        self.context = sourcery.context.ScriptContext(['sourcery.selftests'])
        self.context.silent = True
        self.tempdir_td = tempfile.TemporaryDirectory()
        self.tempdir = self.tempdir_td.name
        self.svndir = os.path.join(self.tempdir, 'svn')
        self.codir = os.path.join(self.tempdir, 'co')
        self.srcdir = os.path.join(self.tempdir, 'src')
        parser = argparse.ArgumentParser()
        sourcery.context.add_common_options(parser, self.tempdir)
        self.args = parser.parse_args([])

    def tearDown(self):
        """Tear down a version control test."""
        self.tempdir_td.cleanup()

    def co_file(self, name):
        """Return the name of a file in codir for this test."""
        return os.path.join(self.codir, name)

    def co_file_write(self, name, contents):
        """Write to a file in codir for this test."""
        with open(self.co_file(name), 'w', encoding='utf-8') as file:
            file.write(contents)

    def src_file(self, name):
        """Return the name of a file in srcdir for this test."""
        return os.path.join(self.srcdir, name)

    def src_file_read(self, name):
        """Read a file in srcdir for this test."""
        with open(self.src_file(name), 'r', encoding='utf-8') as file:
            return file.read()

    def test_git(self):
        """Test component checkouts from git."""
        os.mkdir(self.codir)
        subprocess.run(['git', 'init', '-q'], cwd=self.codir, check=True)
        self.co_file_write('gitfile', 'gitfile contents')
        subprocess.run(['git', 'add', '.'], cwd=self.codir, check=True)
        subprocess.run(['git', 'commit', '-q', '-m', 'commit message'],
                       cwd=self.codir, check=True)
        relcfg_text = ('cfg.add_component("generic")\n'
                       'cfg.generic.vc.set(GitVC("%s"))\n'
                       'cfg.generic.version.set("1.23")\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n' % self.codir)
        relcfg = ReleaseConfig(self.context, relcfg_text,
                               ReleaseConfigTextLoader(), self.args)
        component = relcfg.get_component('generic')
        component.vars.vc.get().checkout_component(component)
        self.assertEqual(self.src_file_read('generic-1.23/gitfile'),
                         'gitfile contents')
        self.co_file_write('gitfile', 'modified contents')
        subprocess.run(['git', 'commit', '-q', '-a', '-m', 'commit 2'],
                       cwd=self.codir, check=True)
        component.vars.vc.get().checkout_component(component)
        self.assertEqual(self.src_file_read('generic-1.23/gitfile'),
                         'modified contents')

    def test_svn(self):
        """Test component checkouts from SVN."""
        subprocess.run(['svnadmin', 'create', self.svndir], check=True)
        svn_uri = 'file://%s' % self.svndir
        subprocess.run(['svn', '-q', 'co', svn_uri, self.codir], check=True)
        self.co_file_write('svnfile', 'svnfile contents')
        subprocess.run(['svn', '-q', 'add', 'svnfile'], cwd=self.codir,
                       check=True)
        subprocess.run(['svn', '-q', 'commit', '-m', 'commit message'],
                       cwd=self.codir, check=True)
        relcfg_text = ('cfg.add_component("generic")\n'
                       'cfg.generic.vc.set(SvnVC("%s"))\n'
                       'cfg.generic.version.set("1.23")\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n' % svn_uri)
        relcfg = ReleaseConfig(self.context, relcfg_text,
                               ReleaseConfigTextLoader(), self.args)
        component = relcfg.get_component('generic')
        component.vars.vc.get().checkout_component(component)
        self.assertEqual(self.src_file_read('generic-1.23/svnfile'),
                         'svnfile contents')
        self.co_file_write('svnfile', 'modified contents')
        subprocess.run(['svn', '-q', 'commit', '-m', 'commit 2'],
                       cwd=self.codir, check=True)
        component.vars.vc.get().checkout_component(component)
        self.assertEqual(self.src_file_read('generic-1.23/svnfile'),
                         'modified contents')

    def test_tar(self):
        """Test component checkouts from tarballs."""
        os.mkdir(self.codir)
        self.co_file_write('tarfile', 'tarfile contents')
        subprocess.run(['tar', '-c', '-z', '-f', 'test.tar.gz', 'co'],
                       cwd=self.tempdir, check=True)
        relcfg_text = ('cfg.add_component("generic")\n'
                       'cfg.generic.vc.set(TarVC("%s"))\n'
                       'cfg.generic.version.set("1.23")\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       % os.path.join(self.tempdir, 'test.tar.gz'))
        relcfg = ReleaseConfig(self.context, relcfg_text,
                               ReleaseConfigTextLoader(), self.args)
        component = relcfg.get_component('generic')
        component.vars.vc.get().checkout_component(component)
        contents = sorted(os.listdir(os.path.join(self.srcdir,
                                                  'generic-1.23')))
        self.assertEqual(contents, ['tarfile'])
        self.assertEqual(self.src_file_read('generic-1.23/tarfile'),
                         'tarfile contents')

    def create_test_tar(self, files):
        """Create a test tarball with files with timestamps in given order."""
        os.mkdir(self.codir)
        this_time = int(time.time()) - len(files)
        for filename in files:
            dirname = os.path.dirname(filename)
            if dirname:
                os.makedirs(os.path.join(self.codir, dirname), exist_ok=True)
            self.co_file_write(filename, filename)
            os.utime(self.co_file(filename), times=(this_time, this_time))
            this_time += 1
        subprocess.run(['tar', '-c', '-f', 'test.tar', 'co'], cwd=self.tempdir,
                       check=True)

    def check_file_order(self, testdir, files):
        """Check file timestamps are in the given order."""
        last_time = 0
        for filename in files:
            mod_time = os.stat(os.path.join(testdir, filename)).st_mtime
            self.assertLessEqual(last_time, mod_time)
            last_time = mod_time

    def test_touch(self):
        """Test component checkouts touching files."""
        self.create_test_tar(['f2', 'f4', 'f1', 'f3'])
        relcfg_text = ('cfg.add_component("files_to_touch")\n'
                       'cfg.files_to_touch.vc.set(TarVC("%s"))\n'
                       'cfg.files_to_touch.version.set("1.23")\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       % os.path.join(self.tempdir, 'test.tar'))
        relcfg = ReleaseConfig(self.context, relcfg_text,
                               ReleaseConfigTextLoader(), self.args)
        component = relcfg.get_component('files_to_touch')
        component.vars.vc.get().checkout_component(component)
        self.check_file_order(os.path.join(self.srcdir, 'files_to_touch-1.23'),
                              ['f1', 'f3', 'f2', 'f4'])
        # Test variant with glob patterns used.
        shutil.rmtree(self.codir)
        shutil.rmtree(self.srcdir)
        self.create_test_tar(['g3', 'g2', 'g1', 'f', 'x', 'd/x', 'dd/ee/x',
                              'd/y'])
        relcfg_text = ('cfg.add_component("files_to_touch_glob")\n'
                       'cfg.files_to_touch_glob.vc.set(TarVC("%s"))\n'
                       'cfg.files_to_touch_glob.version.set("1.23")\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       % os.path.join(self.tempdir, 'test.tar'))
        relcfg = ReleaseConfig(self.context, relcfg_text,
                               ReleaseConfigTextLoader(), self.args)
        component = relcfg.get_component('files_to_touch_glob')
        component.vars.vc.get().checkout_component(component)
        self.check_file_order(os.path.join(self.srcdir,
                                           'files_to_touch_glob-1.23'),
                              ['f', 'd/y', 'd/x', 'dd/ee/x', 'x', 'g1', 'g2',
                               'g3'])
        contents = sorted(os.listdir(os.path.join(self.srcdir,
                                                  'files_to_touch_glob-1.23')))
        self.assertEqual(contents, ['d', 'dd', 'f', 'g1', 'g2', 'g3', 'x'])

    def test_postcheckout(self):
        """Test component checkout calls postcheckout hook."""
        os.mkdir(self.codir)
        self.co_file_write('tarfile', 'tarfile contents')
        subprocess.run(['tar', '-c', '-z', '-f', 'test.tar.gz', 'co'],
                       cwd=self.tempdir, check=True)
        relcfg_text = ('cfg.add_component("postcheckout")\n'
                       'cfg.postcheckout.vc.set(TarVC("%s"))\n'
                       'cfg.postcheckout.version.set("1.23")\n'
                       'cfg.build.set("x86_64-linux-gnu")\n'
                       'cfg.target.set("aarch64-linux-gnu")\n'
                       % os.path.join(self.tempdir, 'test.tar.gz'))
        relcfg = ReleaseConfig(self.context, relcfg_text,
                               ReleaseConfigTextLoader(), self.args)
        component = relcfg.get_component('postcheckout')
        component.postcheckout_hook_called = False
        component.vars.vc.get().checkout_component(component)
        self.assertTrue(component.postcheckout_hook_called)
