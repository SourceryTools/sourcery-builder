# sourcery-builder sourcery_builder component.

# Copyright 2019-2021 Mentor Graphics Corporation.

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

"""sourcery-builder sourcery_builder component."""

import sourcery.component

__all__ = ['Component']


class Component(sourcery.component.Component):
    """sourcery-builder sourcery_builder component implementation."""

    @staticmethod
    def add_release_config_vars(group):
        group.source_type.set_implicit('open')
        group.srcdirname.set_implicit('sourcery-builder')
