# Support building source and binary packages.

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

"""Support building source and binary packages."""

import collections
import hashlib
import os
import os.path
import stat

__all__ = ['fix_perms', 'hard_link_files', 'tar_command']


_NOEX_PERM = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH
_EX_PERM = _NOEX_PERM | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH


def fix_perms(path):
    """Change permissions on files and directories to a canonical form for
    packaging.

    Directories become mode 0o755.  Files become mode 0o755 or 0o644
    according to whether they were already user-executable or not.  No
    changes are made to permissions on symbolic links (on OSes where
    such permissions are meaningful).

    """
    os.chmod(path, _EX_PERM)
    for direntry in os.scandir(path):
        if direntry.is_dir(follow_symlinks=False):
            fix_perms(direntry.path)
        elif direntry.is_file(follow_symlinks=False):
            mode = direntry.stat(follow_symlinks=False).st_mode
            os.chmod(direntry.path,
                     _EX_PERM if mode & stat.S_IXUSR else _NOEX_PERM)


def hard_link_files(context, path):
    """Convert files with identical contents and permissions to hard links.

    This is useful in various cases.  Files that were originally hard
    linked by individual components' 'make install' cease to be hard
    linked when install tree processing copies the results of 'make
    install'.  Some files installed separately for each multilib are
    in fact identical and so should be hard linked to save space in
    the final packages.

    It is expected, but not required, that permissions have previously
    been put in a canonical form by fix_perms.  Directories in which
    files to be made into hard links are present must be writable.

    """
    file_hashes = collections.defaultdict(list)
    for dirpath, dummy_dirnames, filenames in os.walk(path):
        for name in filenames:
            full = os.path.join(dirpath, name)
            mode = os.stat(full, follow_symlinks=False).st_mode
            if stat.S_ISREG(mode):
                with open(full, 'rb') as file:
                    digest = hashlib.sha256(file.read()).digest()
                file_hashes[(digest, mode)].append(full)
    # Sorted to ensure it is deterministic whether errors occur and
    # what errors occur first.
    for files in sorted(file_hashes.values()):
        if len(files) > 1:
            files.sort()
            first = files[0]
            with open(first, 'rb') as file:
                first_contents = file.read()
            for name in files[1:]:
                with open(name, 'rb') as file:
                    if file.read() != first_contents:
                        context.error('hash collision: %s and %s'
                                      % (first, name))
                os.remove(name)
                os.link(first, name)


def tar_command(output_name, top_dir_name, source_date_epoch):
    """Return a tar command to create a tarball package.

    The command is to be run in the directory to be packaged;
    top_dir_name will be used as the name of the top-level directory
    in the tarball, and source_date_epoch for timestamps.

    """
    return ['tar', '-c', '-J', '-f', output_name, '--sort=name',
            '--mtime=@%d' % source_date_epoch, '--owner=0', '--group=0',
            '--numeric-owner', r'--transform=s|^\.|%s|rSh' % top_dir_name, '.']
