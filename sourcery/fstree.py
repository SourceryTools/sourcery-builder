# Support filesystem trees.

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

"""Support filesystem trees."""

import collections
import fnmatch
import os
import os.path
import shutil
import stat

__all__ = ['MapFSTree', 'MapFSTreeCopy', 'MapFSTreeMap', 'FSTree',
           'FSTreeCopy', 'FSTreeEmpty', 'FSTreeMove', 'FSTreeRemove',
           'FSTreeUnion']


def _invalid_path(path):
    """Return whether a file or subdirectory path is invalid."""
    path_exp = '/%s/' % path
    return '//' in path_exp or '/./' in path_exp or '/../' in path_exp


class _NoBool(object):
    """Internal class disallowing boolean conversions."""

    def __bool__(self):
        raise NotImplementedError


class MapFSTree(object):
    """A MapFSTree describes how to construct a filesystem object.

    A filesystem object (the entity referred to by a filesystem name),
    as described by a MapFSTree, is either a regular file, a symbolic
    link, or a directory.  It may be constructed by copying from a
    filesystem path, or as a directory with a MapFSTree object for
    each name in that directory.

    From the point of view of users of MapFSTree objects, they are
    read-only; the attributes should not be modified after creation,
    and nor should the contents of filesystem paths described as being
    copied be modified while the object is live.  The implementation
    of MapFSTree and subclasses, however, may internally create
    objects that are modified after creation.

    """

    def __init__(self, context):
        self.context = context
        self.is_dir = _NoBool()

    def export(self, path):
        """Write the contents of this object to the filesystem.

        The specified path must not currently exist, but its parent
        directory must exist.

        """
        if os.access(path, os.F_OK, follow_symlinks=False):
            self.context.error('path %s already exists' % path)
        self._export_impl(path)

    def _export_impl(self, path):
        """Implement export method, without checking for path existence."""
        raise NotImplementedError

    def _expand(self, copy):
        """Return an expanded version of this object if possible.

        An expanded version is a MapFSTreeMap whenever the object
        represents a directory.  Thus, it has a 'name_map' member
        pointing to the contained files, symlinks and subdirectories.
        Expansion only takes place at top level, not recursively.  If
        the object is already a MapFSTreeMap, a shallow copy is
        returned if 'copy' is true and the original otherwise.

        """
        raise NotImplementedError

    def union(self, other, name):
        """Return the union of this object with another MapFSTree.

        Directories may appear in both objects.  Regular files and
        symlinks may appear in only one, not both, even with identical
        contents.  The specified 'name' is for use in diagnostics
        related to this issue.

        """
        if not self.is_dir or not other.is_dir:
            self.context.error('non-directory involved in union operation: %s'
                               % name)
        ret = self._expand(True)
        other = other._expand(False)
        for filename in other.name_map:
            if filename in ret.name_map:
                sub_name = os.path.join(name, filename) if name else filename
                ret.name_map[filename] = ret.name_map[filename].union(
                    other.name_map[filename], sub_name)
            else:
                ret.name_map[filename] = other.name_map[filename]
        return ret

    def remove(self, paths):
        """Return a MapFSTree like this one but with the given paths removed.

        Paths to be removed may be files, directories or symlinks;
        contents of directories are removed recursively; symlinks are
        not dereferenced, so e.g. 'foo/*' where foo is a symlink does
        not match anything.  fnmatch patterns may be used to match
        individual components.  If removals result in a subdirectory
        being empty where it was not empty before, that subdirectory
        is removed.

        """
        for path in paths:
            if _invalid_path(path):
                self.context.error('invalid path to remove: %s' % path)
        if not self.is_dir:
            return self
        ret = self._expand(True)
        sub_paths = collections.defaultdict(set)
        for path in paths:
            if '/' in path:
                p_dir, p_rest = path.split('/', maxsplit=1)
                p_dir_exp = fnmatch.filter(ret.name_map.keys(), p_dir)
                for subdir in p_dir_exp:
                    sub_paths[subdir].add(p_rest)
            else:
                p_exp = fnmatch.filter(ret.name_map.keys(), path)
                for p_match in p_exp:
                    del ret.name_map[p_match]
        for subdir in sub_paths:
            if subdir in ret.name_map and ret.name_map[subdir].is_dir:
                sub = ret.name_map[subdir]._expand(False)
                if sub.name_map:
                    sub = sub.remove(sorted(sub_paths[subdir]))
                    if sub.name_map:
                        ret.name_map[subdir] = sub
                    else:
                        del ret.name_map[subdir]
        return ret


class MapFSTreeCopy(MapFSTree):
    """A MapFSTreeCopy constructs a filesystem object from a path."""

    def __init__(self, context, path):
        """Initialize a MapFSTreeCopy object."""
        super().__init__(context)
        path = os.path.abspath(path)
        self.path = path
        mode = os.stat(path, follow_symlinks=False).st_mode
        if stat.S_ISDIR(mode):
            self.is_dir = True
        elif stat.S_ISREG(mode) or stat.S_ISLNK(mode):
            self.is_dir = False
        else:
            context.error('bad file type for %s' % path)

    def _export_impl(self, path):
        if self.is_dir:
            shutil.copytree(self.path, path, symlinks=True)
        else:
            shutil.copy2(self.path, path, follow_symlinks=False)

    def _expand(self, copy):
        if not self.is_dir:
            return self
        name_map = {name: MapFSTreeCopy(self.context,
                                        os.path.join(self.path, name))
                    for name in os.listdir(self.path)}
        return MapFSTreeMap(self.context, name_map)


class MapFSTreeMap(MapFSTree):
    """A MapFSTreeMap maps names in a directory to MapFSTree objects."""

    def __init__(self, context, name_map):
        """Initialize a MapFSTreeMap object."""
        super().__init__(context)
        self.is_dir = True
        for key in name_map:
            if key == '' or key == '.' or key == '..' or '/' in key:
                context.error('bad file name in map: %s' % key)
        self.name_map = dict(name_map)

    def _export_impl(self, path):
        os.mkdir(path)
        for filename in self.name_map:
            self.name_map[filename].export(os.path.join(path, filename))

    def _expand(self, copy):
        if copy:
            return MapFSTreeMap(self.context, self.name_map)
        else:
            return self


class FSTree(object):
    """An FSTree describes how to construct a filesystem object.

    This is similar to MapFSTree, except that FSTree works at a higher
    level and describes construction based on files and directories
    that will exist at some point in the future, rather than those
    that exist now; the files and directories may be, or be derived
    from, named install trees, in which case the FSTree objects are
    used to determine dependencies between the build tasks required to
    construct those directories and those that use the FSTree.

    The same restrictions on valid kinds of filesystem objects apply
    as for MapFSTree, and FSTree objects are also read-only from the
    point of view of users (but depend on directories that may not
    exist at the time of FSTree creation, or may change after that
    creation).

    """

    def export_map(self):
        """Return a MapFSTree corresponding to this FSTree."""
        raise NotImplementedError

    def export(self, path):
        """Write the contents of this object to the filesystem.

        The specified path must not currently exist, but its parent
        directory must exist.

        """
        self.export_map().export(path)


class FSTreeCopy(FSTree):
    """An FSTreeCopy constructs a filesystem object from a path."""

    def __init__(self, context, path, install_trees):
        """Initialize an FSTreeCopy object.

        The install tree names are intended to be tuples (host, name);
        the FSTree code allows any hashable object, but tuples are how
        they are used by BuildTask code.

        """
        self.context = context
        self.path = os.path.abspath(path)
        self.install_trees = set(install_trees)

    def export_map(self):
        return MapFSTreeCopy(self.context, self.path)


class FSTreeEmpty(FSTree):
    """An FSTreeEmpty represents an empty directory."""

    def __init__(self, context):
        """Initialize an FSTreeEmpty object."""
        self.context = context
        self.install_trees = set()

    def export_map(self):
        return MapFSTreeMap(self.context, {})


class FSTreeMove(FSTree):
    """An FSTreeMove represents an FSTree placed at a subdirectory location."""

    def __init__(self, other, subdir):
        """Initialize an FSTreeMove object."""
        self.context = other.context
        if _invalid_path(subdir):
            self.context.error('invalid subdirectory: %s' % subdir)
        self.other = other
        self.install_trees = other.install_trees
        self.subdir = subdir

    def export_map(self):
        ret = self.other.export_map()
        for subdir in reversed(self.subdir.split('/')):
            ret = MapFSTreeMap(self.context, {subdir: ret})
        return ret


class FSTreeRemove(FSTree):
    """An FSTreeRemove represents an FSTree with some paths removed."""

    def __init__(self, other, paths):
        """Initialize an FSTreeRemove object.

        Paths to be removed are interpreted as for
        MapFSTree.remove.

        """
        self.context = other.context
        for path in paths:
            if _invalid_path(path):
                self.context.error('invalid path to remove: %s' % path)
        self.other = other
        self.install_trees = other.install_trees
        self.paths = paths

    def export_map(self):
        return self.other.export_map().remove(self.paths)


class FSTreeUnion(FSTree):
    """An FSTreeUnion represents the union of two other FSTree objects.

    The same rules as for MapFSTree.union apply to paths in both
    objects.

    """

    def __init__(self, first, second):
        """Initialize an FSTreeUnion object."""
        self.context = first.context
        self.first = first
        self.second = second
        self.install_trees = first.install_trees | second.install_trees

    def export_map(self):
        return self.first.export_map().union(self.second.export_map(), '')
