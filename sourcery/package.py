# Support building source and binary packages.

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

"""Support building source and binary packages."""

import os
import stat

__all__ = ['fix_perms']


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
