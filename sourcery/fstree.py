# Support filesystem trees.

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

"""Support filesystem trees."""

import collections
import fnmatch
import os
import os.path
import shutil
import stat

__all__ = ['MapFSTree', 'MapFSTreeCopy', 'MapFSTreeMap', 'MapFSTreeSymlink',
           'FSTree', 'FSTreeCopy', 'FSTreeEmpty', 'FSTreeSymlink',
           'FSTreeMove', 'FSTreeRemove', 'FSTreeExtract', 'FSTreeExtractOne',
           'FSTreeUnion']


def _invalid_path(path):
    """Return whether a file or subdirectory path is invalid."""
    path_exp = '/%s/' % path
    return '//' in path_exp or '/./' in path_exp or '/../' in path_exp


class _NoBool:
    """Internal class disallowing boolean conversions."""

    def __bool__(self):
        raise NotImplementedError


class MapFSTree:
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

    def _contents(self):
        """Return a tuple that represents the contents of this object.

        The tuples are suitable for comparison purposes but not
        otherwise specified.  This may only be called for regular
        files and symlinks, not for directories.

        """
        raise NotImplementedError

    def union(self, other, name, allow_duplicate_files=False):
        """Return the union of this object with another MapFSTree.

        Directories may appear in both objects.  If
        allow_duplicate_files is False (the default), regular files
        and symlinks may appear in only one, not both, even with
        identical contents; if it is True, regular files and symlinks
        may appear in both provided the contents, and the permissions
        for regular files, are identical.  The specified 'name' is for
        use in diagnostics related to this issue.

        """
        if not self.is_dir or not other.is_dir:
            if allow_duplicate_files and not self.is_dir and not other.is_dir:
                if self._contents() == other._contents():
                    return self
                else:
                    self.context.error('inconsistent contents in union '
                                       'operation: %s' % name)
            else:
                self.context.error('non-directory involved in union '
                                   'operation: %s' % name)
        ret = self._expand(True)
        other = other._expand(False)
        for filename in other.name_map:
            if filename in ret.name_map:
                sub_name = os.path.join(name, filename) if name else filename
                ret.name_map[filename] = ret.name_map[filename].union(
                    other.name_map[filename], sub_name, allow_duplicate_files)
            else:
                ret.name_map[filename] = other.name_map[filename]
        return ret

    def remove(self, paths):
        """Return a MapFSTree like this one but with the given paths removed.

        Paths to be removed may be files, directories or symlinks;
        contents of directories are removed recursively; symlinks are
        not dereferenced, so e.g. 'foo/*' where foo is a symlink does
        not match anything.  fnmatch patterns may be used to match
        individual components; a component of '**' refers to both the
        directory it appears in and all files and subdirectories under
        it, recursively, so 'foo/**/bar' matches all files called
        'bar' located anywhere under 'foo'.  If removals result in a
        subdirectory being empty where it was not empty before, that
        subdirectory is removed.

        """
        if isinstance(paths, str):
            self.context.error('paths must be a list of strings, not a single '
                               'string')
        for path in paths:
            if _invalid_path(path):
                self.context.error('invalid path to remove: %s' % path)
        if not self.is_dir:
            return self
        ret = self._expand(True)
        paths_exp = []
        for path in paths:
            if path.startswith('**/'):
                while path.startswith('**/'):
                    path = path[3:]
                paths_exp.append(path)
                paths_exp.append('*/**/%s' % path)
            else:
                paths_exp.append(path)
        sub_paths = collections.defaultdict(set)
        for path in paths_exp:
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

    def extract(self, paths):
        """Return a MapFSTree like this one but with only the given paths.

        Paths may be files, directories or symlinks; contents of
        directories are included recursively; symlinks are not
        dereferenced, so e.g. 'foo/*' where foo is a symlink does not
        match anything.  fnmatch patterns may be used to match
        individual components; '**' is not handled specially.  Empty
        directories are only included in the result where they match
        one of the given paths.

        """
        if not self.is_dir:
            self.context.error('extracting paths from non-directory')
        if isinstance(paths, str):
            self.context.error('paths must be a list of strings, not a single '
                               'string')
        for path in paths:
            if _invalid_path(path):
                self.context.error('invalid path to extract: %s' % path)
        ret = self._expand(True)
        keep_sub = set()
        sub_paths = collections.defaultdict(set)
        for path in paths:
            if '/' in path:
                p_dir, p_rest = path.split('/', maxsplit=1)
                p_dir_exp = fnmatch.filter(ret.name_map.keys(), p_dir)
                for subdir in p_dir_exp:
                    sub_paths[subdir].add(p_rest)
            else:
                p_exp = fnmatch.filter(ret.name_map.keys(), path)
                keep_sub.update(p_exp)
        del_sub = set()
        for subdir in ret.name_map:
            if subdir in keep_sub:
                pass
            elif subdir in sub_paths and ret.name_map[subdir].is_dir:
                sub = ret.name_map[subdir].extract(sorted(sub_paths[subdir]))
                if sub.name_map:
                    ret.name_map[subdir] = sub
                else:
                    del_sub.add(subdir)
            else:
                del_sub.add(subdir)
        for subdir in del_sub:
            del ret.name_map[subdir]
        return ret

    def extract_one(self, path):
        """Return a MapFSTree for the given path within this one.

        The path must exist (as a file, directory or symlink).  The
        difference from the extract method with a single path passed
        is that the new MapFSTree refers directly to the given object,
        rather than to a tree with the same top-level directory where
        that object exists at the same path as in the MapFSTree
        passed.

        """
        if not self.is_dir:
            self.context.error('extracting a path from a non-directory')
        if _invalid_path(path):
            self.context.error('invalid path to extract: %s' % path)
        expanded = self._expand(False)
        if '/' in path:
            p_dir, p_rest = path.split('/', maxsplit=1)
            return expanded.name_map[p_dir].extract_one(p_rest)
        else:
            return expanded.name_map[path]


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

    def _contents(self):
        if self.is_dir:
            self.context.error('_contents called for directory %s'
                               % self.path)
        mode = os.stat(self.path, follow_symlinks=False).st_mode
        if stat.S_ISLNK(mode):
            return ('symlink', os.readlink(self.path))
        with open(self.path, 'rb') as file:
            return ('file', file.read(), mode)


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

    def _contents(self):
        self.context.error('_contents called for directory')


class MapFSTreeSymlink(MapFSTree):
    """A MapFSTreeSymlink represents a symbolic link."""

    def __init__(self, context, target):
        """Initialize a MapFSTreeSymlink object."""
        super().__init__(context)
        self.is_dir = False
        if target == '':
            context.error('empty symlink target')
        self.target = target

    def _export_impl(self, path):
        os.symlink(self.target, path)

    def _expand(self, copy):
        return self

    def _contents(self):
        return ('symlink', self.target)


class FSTree:
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


class FSTreeSymlink(FSTree):
    """An FSTreeSymlink represents a symbolic link."""

    def __init__(self, context, target):
        """Initialize an FSTreeSymlink object."""
        self.context = context
        if target == '':
            context.error('empty symlink target')
        self.install_trees = set()
        self.target = target

    def export_map(self):
        return MapFSTreeSymlink(self.context, self.target)


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
        if isinstance(paths, str):
            self.context.error('paths must be a list of strings, not a single '
                               'string')
        for path in paths:
            if _invalid_path(path):
                self.context.error('invalid path to remove: %s' % path)
        self.other = other
        self.install_trees = other.install_trees
        self.paths = paths

    def export_map(self):
        return self.other.export_map().remove(self.paths)


class FSTreeExtract(FSTree):
    """An FSTreeExtract represents an FSTree with only the given paths kept."""

    def __init__(self, other, paths):
        """Initialize an FSTreeExtract object.

        Paths to be kept are interpreted as for MapFSTree.extract.

        """
        self.context = other.context
        if isinstance(paths, str):
            self.context.error('paths must be a list of strings, not a single '
                               'string')
        for path in paths:
            if _invalid_path(path):
                self.context.error('invalid path to extract: %s' % path)
        self.other = other
        self.install_trees = other.install_trees
        self.paths = paths

    def export_map(self):
        return self.other.export_map().extract(self.paths)


class FSTreeExtractOne(FSTree):
    """An FSTreeExtractOne represents a single path from an FSTree, moved
    to top level."""

    def __init__(self, other, path):
        """Initialize an FSTreeExtractOne object."""
        self.context = other.context
        if _invalid_path(path):
            self.context.error('invalid path to extract: %s' % path)
        self.other = other
        self.install_trees = other.install_trees
        self.path = path

    def export_map(self):
        return self.other.export_map().extract_one(self.path)


class FSTreeUnion(FSTree):
    """An FSTreeUnion represents the union of two other FSTree objects.

    The same rules as for MapFSTree.union apply to paths in both
    objects.

    """

    def __init__(self, first, second, allow_duplicate_files=False):
        """Initialize an FSTreeUnion object."""
        self.context = first.context
        self.first = first
        self.second = second
        self.allow_duplicate_files = allow_duplicate_files
        self.install_trees = first.install_trees | second.install_trees

    def export_map(self):
        return self.first.export_map().union(self.second.export_map(), '',
                                             self.allow_duplicate_files)
