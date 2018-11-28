# Support makefile generation.

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

"""Support makefile generation."""

import shlex

from sourcery.tsort import tsort

__all__ = ['command_to_make', 'Makefile']


def command_to_make(context, command):
    """Convert a command and arguments to a suitable form for a makefile."""
    ret = ' '.join([shlex.quote(s).replace('$', '$$')
                    for s in command])
    if '\n' in ret:
        context.error('newline in command for makefile: %s' % ret)
    return ret


class Makefile:
    """Class for generated makefiles.

    A Makefile represents the dependencies and commands involved in a
    makefile generated to run some build tasks, typically in parallel.
    All targets in the generated makefile are marked as phony.

    """

    def __init__(self, context, first_target):
        """Initialize a Makefile object."""
        self.context = context
        self._first_target = first_target
        self._targets = set()
        self._deps = {}
        self._commands = {}
        self.add_target(first_target)

    def add_target(self, target):
        """Add a target to the makefile.

        Each target must be added exactly once.

        """
        if target in self._targets:
            self.context.error('target %s already added' % target)
        self._targets.add(target)
        self._deps[target] = set()
        self._commands[target] = []

    def add_deps(self, target, deps):
        """Add a dependency to the makefile.

        Duplicate dependencies are OK.  Both the source and the target
        of any dependency must already have been added.

        """
        if target not in self._targets:
            self.context.error('target %s not known' % target)
        for dep in deps:
            if dep not in self._targets:
                self.context.error('dependency %s not known' % dep)
        self._deps[target].update(deps)

    def add_command(self, target, command):
        """Add a command to those for a makefile target.

        The command is a string, which will be inserted in the
        makefile after a leading tab and '@'.

        """
        if target not in self._targets:
            self.context.error('target %s not known' % target)
        if '\n' in command:
            self.context.error('newline in command for makefile: %s' % command)
        self._commands[target].append(command)

    def makefile_text(self):
        """Return the text of this makefile."""
        # Verify there are no circular dependencies.
        tsort(self.context, self._deps)
        targets_sorted = [t for t in sorted(self._targets)
                          if t != self._first_target]
        targets_sorted = [self._first_target] + targets_sorted
        glist = []
        for target in targets_sorted:
            dep_text = ' '.join(sorted(self._deps[target]))
            if dep_text:
                dep_text = ' ' + dep_text
            t_dep = '%s:%s' % (target, dep_text)
            t_cmds = ['\t@%s' % c for c in self._commands[target]]
            t_all = [t_dep] + t_cmds
            t_text = '\n'.join(t_all) + '\n'
            glist.append(t_text)
        glist.append('.PHONY: %s' % ' '.join(targets_sorted))
        return '\n'.join(glist) + '\n'
