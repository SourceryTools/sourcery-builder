# Implement topological sort.

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

"""Implement topological sort."""

__all__ = ['tsort']


def _tsort_rec(context, deps, cur_list, deps_list, seen, tseen):
    """Topologically sort, recursively."""
    for name in cur_list:
        if name not in seen:
            if name in tseen:
                context.error('circular dependency for %s' % name)
            tseen.add(name)
            _tsort_rec(context, deps, sorted(deps[name]), deps_list, seen,
                       tseen)
            deps_list.append(name)
            seen.add(name)
            tseen.remove(name)


def tsort(context, deps):
    """Topologically sort by dependencies.

    Given a mapping from entities to their dependencies, return a
    topologically sorted list in which each entity's dependencies come
    before that entity.

    """
    deps_list = []
    seen = set()
    tseen = set()
    cur_list = sorted(deps.keys())
    _tsort_rec(context, deps, cur_list, deps_list, seen, tseen)
    return deps_list
