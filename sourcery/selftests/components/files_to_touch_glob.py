# sourcery-builder component for testing files_to_touch using globs.

# Copyright 2018-2020 Mentor Graphics Corporation.

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

"""sourcery-builder component for testing files_to_touch using globs."""

import sourcery.selftests.component

__all__ = ['Component']


class Component(sourcery.selftests.component.Component):
    """files_to_touch_glob component implementation."""

    @staticmethod
    def add_release_config_vars(group):
        group.source_type.set_implicit('open')

    files_to_touch = ['**/x', 'g*', 'h']
