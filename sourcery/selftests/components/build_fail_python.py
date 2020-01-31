# sourcery-builder build_fail_python component for testing.

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

"""sourcery-builder build_fail_python component for testing."""

from sourcery.buildtask import BuildTask
import sourcery.selftests.component

__all__ = ['Component']


class Component(sourcery.selftests.component.Component):
    """build_fail_python component implementation."""

    @staticmethod
    def add_release_config_vars(group):
        group.source_type.set_implicit('none')

    @staticmethod
    def add_build_tasks_for_first_host(cfg, host, component, host_group):
        task = BuildTask(cfg, host_group, 'first-host')

        def py_test_fn():
            """Test Python build step failure."""
            raise ValueError('test failure')

        task.add_python(py_test_fn, ())
