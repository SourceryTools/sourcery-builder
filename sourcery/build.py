# Support building toolchains (development and release).

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

"""Support building toolchains (development and release)."""

import collections
import os
import os.path
import shutil
import subprocess
import tempfile

from sourcery.buildtask import BuildTask
from sourcery.rpc import RPCServer

__all__ = ['BuildContext']


class BuildContext:
    """A BuildContext represents the configuration for a build."""

    def __init__(self, context, relcfg, args):
        """Initialize a BuildContext for a configuration."""
        self.context = context
        self.relcfg = relcfg
        self.logdir = args.logdir
        self.parallelism = args.parallelism
        self.build_objdir = relcfg.objdir_path(None, 'build')
        self._tempdir_td = tempfile.TemporaryDirectory()
        self.sockdir = self._tempdir_td.name
        self.server = RPCServer(self.sockdir)

    def setup_build_dir(self):
        """Set up tasks and build directory for a configuration.

        This function creates the specified directory for files
        related to the build process (not files used in the build of
        individual components), removing and recreating it as
        necessary; logs go in the specified directory for logs.  The
        separate directory for sockets is expected to exist and to be
        empty; that directory is separate because paths to Unix-domain
        sockets have a small length limit, so a short path in /tmp is
        appropriate rather than the longer paths used for the rest of
        the build.

        As well as other files, a GNUmakefile is created in the
        specified directory for controlling the build, via 'make all'
        unless a more selective build of particular tasks is required.

        """
        relcfg = self.relcfg
        top_task = BuildTask(relcfg, None, '', True)
        first_host = True
        for host in relcfg.hosts.get():
            host_task = BuildTask(relcfg, top_task, host.name, True)
            for component in relcfg.list_components():
                component.cls.add_build_tasks_for_host(relcfg, host, component,
                                                       host_task)
                if first_host:
                    component.cls.add_build_tasks_for_first_host(relcfg, host,
                                                                 component,
                                                                 host_task)
                else:
                    component.cls.add_build_tasks_for_other_hosts(relcfg, host,
                                                                  component,
                                                                  host_task)
            first_host = False
        build_objdir = self.build_objdir
        if os.access(build_objdir, os.F_OK):
            shutil.rmtree(build_objdir)
        os.makedirs(build_objdir)
        os.makedirs(self.logdir, exist_ok=True)
        makefile_text = top_task.makefile_text(self)
        makefile_name = os.path.join(build_objdir, 'GNUmakefile')
        with open(makefile_name, 'w', encoding='utf-8') as file:
            file.write(makefile_text)

    def wrapper_run_command(self, log, fail_message, cwd):
        """Generate a call to the run-command wrapper.

        A list of the command and its arguments, to come before the
        actual command being run, is returned.

        """
        return [self.context.build_wrapper_path('run-command'),
                self.context.interp, self.context.script_full,
                self.build_objdir, log, self.sockdir, str(fail_message), cwd]

    def wrapper_start_task(self, log, msg_start):
        """Generate a call to the start-task wrapper.

        A list of the command and its arguments is returned.

        """
        return [self.context.build_wrapper_path('start-task'),
                self.context.interp, self.context.script_full,
                self.build_objdir, log, self.sockdir, str(msg_start)]

    def wrapper_end_task(self, log, msg_end):
        """Generate a call to the end-task wrapper.

        A list of the command and its arguments is returned.

        """
        return [self.context.build_wrapper_path('end-task'),
                self.context.interp, self.context.script_full,
                self.build_objdir, log, self.sockdir, str(msg_end)]

    def rpc_client_command(self, msg):
        """Generate a call to the rpc-client command.

        A list of the command and its arguments is returned.

        """
        return self.context.script_command() + ['rpc-client', self.sockdir,
                                                str(msg)]

    def task_start(self, task_desc_text):
        """Record that a build task has started."""
        self.context.inform('%s start' % task_desc_text)

    def task_fail_command(self, task_desc_text, command, log):
        """Record that a command in a build task has failed."""
        context = self.context
        context.warning('%s FAILED' % task_desc_text)
        context.warning('failed command was: %s' % str(command))
        context.warning('current log file is: %s (last 25 lines shown)' % log)
        # Given the LC_CTYPE setting we hope logs are plain ASCII, but
        # avoid any character set conversion errors if they are not.
        lines = collections.deque([], 25)
        with open(log, 'r', encoding='ascii',
                  errors='backslashreplace') as log_file:
            for line in log_file:
                lines.append(line)
        lines_text = ''.join(lines)
        if not lines_text.endswith('\n'):
            lines_text += '\n'
        log_text = ('%s start %s\n%s%s end %s\n'
                    % ('-' * 36, '-' * 36, lines_text, '-' * 37, '-' * 37))
        context.message_file.write(log_text)

    def task_end(self, task_desc_text):
        """Record that a build task has ended."""
        self.context.inform('%s end' % task_desc_text)

    def run_build(self):
        """Run the build of a release configuration."""
        try:
            self.setup_build_dir()
            self.server.start()
            try:
                subprocess.run(['make', '-j%d' % self.parallelism],
                               stdin=subprocess.DEVNULL, cwd=self.build_objdir,
                               env=self.context.environ, check=True)
            finally:
                self.server.stop()
        finally:
            self._tempdir_td.cleanup()
        build_failed_file = os.path.join(self.build_objdir, 'build-failed')
        if os.access(build_failed_file, os.F_OK):
            self.context.error('build failed')
