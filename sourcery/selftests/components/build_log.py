# sourcery-builder build_log component for testing.

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

"""sourcery-builder build_log component for testing."""

from sourcery.buildtask import BuildTask
import sourcery.selftests.component

__all__ = ['Component']


class Component(sourcery.selftests.component.Component):
    """build_log component implementation."""

    @staticmethod
    def add_release_config_vars(group):
        group.source_type.set_implicit('none')

    @staticmethod
    def add_build_tasks_for_first_host(cfg, host, component, host_group):
        task = BuildTask(cfg, host_group, 'first-host')
        # Test that output gets properly redirected by build wrappers.
        # The generated output must not appear in the command being
        # run, to avoid the copy of the command in the log being
        # confused by the tests with the command's output.
        task.add_command(['sh', '-c',
                          'n=0; while [ $n -lt 10 ]; do '
                          'if [ $(($n & 1)) -eq 0 ]; then echo $n; '
                          'else echo $n >& 2; fi; n=$(($n + 1)); done'])
        task.add_command(['sh', '-c',
                          'n=10; while [ $n -lt 20 ]; do '
                          'if [ $(($n & 1)) -eq 0 ]; then echo $n; '
                          'else echo $n >& 2; fi; n=$(($n + 1)); done'])
