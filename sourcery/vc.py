# Support version control.

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

"""Support version control."""

import glob
import os
import os.path
import tempfile

__all__ = ['VC', 'GitVC', 'SvnVC', 'TarVC']


class VC:
    """Support version control operations.

    This is a base class for classes for version control systems (the
    vc_* methods).  In addition, it provides version control
    operations that are implemented on top of those methods but do not
    themselves depend on the particular version control system in
    use.

    """

    def __init__(self, context):
        self.context = context

    def vc_checkout(self, srcdir, update):
        """Check out sources, or update a checkout.

        If update is true, the directory must already exist and be
        checked out from the specified location; if false, it must not
        exist; it is the caller's responsibility to check these
        things, and to ensure, in any case, that the parent directory
        of the specified directory already exists.  No postcheckout
        hooks are run to update timestamps; that is also the caller's
        responsibility; this function is only expected to do things
        that are specific to the version control system in question.

        """

        raise NotImplementedError

    def checkout_component(self, component):
        """Check out sources for a component, or update a checkout.

        If the directory already exists, it must be checked out from
        the specified location and will be updated; if not, it will be
        checked out.  Postcheckout hooks to update timestamps are run.

        """
        srcdir = component.vars.srcdir.get()
        if os.access(srcdir, os.F_OK):
            self.vc_checkout(srcdir, True)
        else:
            os.makedirs(os.path.dirname(srcdir), exist_ok=True)
            self.vc_checkout(srcdir, False)
        files_to_touch = []
        for filename in component.cls.files_to_touch:
            files_to_touch.extend(sorted(glob.glob(os.path.join(srcdir,
                                                                filename),
                                                   recursive=True)))
        # This can be done with Python code, but that requires dealing
        # with the mismatch between file timestamps in nanoseconds and
        # the current time as a float; calling the touch program is
        # simpler.
        if files_to_touch:
            self.context.execute(['touch'] + files_to_touch)
        component.cls.postcheckout(self.context, component)


class GitVC(VC):
    """Class for sources coming from git."""

    def __init__(self, context, uri, branch='master'):
        super().__init__(context)
        self._uri = uri
        self._branch = branch

    def vc_checkout(self, srcdir, update):
        if update:
            self.context.execute(['git', 'pull', '-q'], cwd=srcdir)
        else:
            self.context.execute(['git', 'clone', '-b', self._branch,
                                  '-q', self._uri, srcdir])


class SvnVC(VC):
    """Class for sources coming from Subversion."""

    def __init__(self, context, uri):
        super().__init__(context)
        self._uri = uri

    def vc_checkout(self, srcdir, update):
        # To ensure that tagging and branching automatically cover all
        # the sources without any dependency on some other repository,
        # --ignore-externals is used when checking out sources from
        # SVN.
        if update:
            self.context.execute(['svn', '-q', 'update', '--ignore-externals',
                                  '--non-interactive'],
                                 cwd=srcdir)
        else:
            self.context.execute(['svn', '-q', 'co', '--ignore-externals',
                                  self._uri, srcdir])


class TarVC(VC):
    """Class for sources coming from tarballs."""

    def __init__(self, context, path):
        super().__init__(context)
        self._path = path

    def vc_checkout(self, srcdir, update):
        if update:
            self.context.warning('not updating %s from tarball' % srcdir)
        else:
            parent = os.path.dirname(srcdir)
            with tempfile.TemporaryDirectory(dir=parent) as tempdir:
                thisdir = os.path.join(tempdir, 'tar-contents')
                os.mkdir(thisdir)
                self.context.execute(['tar', '-x', '-f', self._path],
                                     cwd=thisdir)
                # If the tarball unpacked to a single directory, that
                # becomes the source directory checked out.  In any
                # other case, the contents of the tarball are the
                # contents of the source directory checked out.
                contents = list(os.scandir(thisdir))
                if (len(contents) == 1
                    and contents[0].is_dir(follow_symlinks=False)):
                    os.rename(contents[0].path, srcdir)
                else:
                    os.rename(thisdir, srcdir)
