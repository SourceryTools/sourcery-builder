# Support build tasks.

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

"""Support build tasks."""

import os.path
import shlex

from sourcery.fstree import FSTreeEmpty, FSTreeUnion
from sourcery.makefile import command_to_make, Makefile
from sourcery.tsort import tsort

__all__ = ['BuildStep', 'BuildCommand', 'BuildMake', 'BuildPython',
           'BuildTask']


class BuildStep:
    """A BuildStep represents a step run while building a toolchain.

    That step may be an ordinary command, or arguments to 'make', or a
    Python function and its arguments.

    """

    def __init__(self, context):
        """Initialize a BuildStep object."""
        self.context = context
        self._cwd = None

    def make_string(self, build_context, log, fail_message, env):
        """Return the makefile string to run a command."""
        cmd = self._command_main(log, build_context)
        prefix = self._command_prefix
        cmd_str = prefix + command_to_make(self.context, cmd)
        if env:
            env_cmd = ['env'] + ['%s=%s' % k_v for k_v in sorted(env.items())]
            env_str = command_to_make(self.context, env_cmd)
            cmd_str = '%s %s' % (env_str, cmd_str)
        cwd = self._cwd if self._cwd is not None else ''
        wrapper = build_context.wrapper_run_command(log, fail_message, cwd)
        wrapper_str = command_to_make(self.context, wrapper)
        return '%s %s' % (wrapper_str, cmd_str)

    def _command_main(self, log, build_context):
        """Return the main command, before any wrappers are added."""
        raise NotImplementedError

    _command_prefix = ''
    """Any prefix (literal makefile text) to add to the command."""

    def __str__(self):
        """Return the version of a command to use when reporting failure."""
        raise NotImplementedError


class BuildCommand(BuildStep):
    """A BuildCommand represents a command run while building a toolchain.

    A command may be specified with a directory in which it is run.

    """

    def __init__(self, context, command, cwd=None):
        """Initialize a BuildCommand object.

        The command specified is a list or tuple with the sequence of
        strings that should end up being passed to execve.  If cwd is
        specified, it is a directory to use for running the command.

        """
        super().__init__(context)
        command = tuple(command)
        for arg in command:
            if '\n' in arg:
                context.error('newline in command: %s' % ' '.join(command))
        self._command = command
        self._cwd = cwd

    def _command_main(self, log, build_context):
        return self._command

    def __str__(self):
        return ' '.join([shlex.quote(s) for s in self._command])


class BuildMake(BuildCommand):
    """A BuildMake represents a 'make' command run while building a toolchain.

    A command may be specified with a directory in which it is run.
    $(MAKE) is used to support parallelism (prepended in the shell to
    the arguments passed to __init__).

    """

    _command_prefix = '$(MAKE) '

    def __str__(self):
        return '$(MAKE) ' + super().__str__()


class BuildPython(BuildStep):
    """A BuildPython represents a Python step while building a toolchain.

    A Python step consists of a function and its arguments, to be run
    in a forked child of this process.

    """

    def __init__(self, context, function, args):
        """Initialize a BuildPython object."""
        super().__init__(context)
        self._function = function
        self._args = tuple(args)

    def _command_main(self, log, build_context):
        msg = build_context.server.add_call(self._function, self._args, log,
                                            True)
        return build_context.rpc_client_command(msg)

    def __str__(self):
        py_args_repr = [repr(arg) for arg in self._args]
        return 'python: %s(%s)' % (str(self._function),
                                   ', '.join(py_args_repr))


_TASK_START_STR = 'task-start'
_TASK_END_STR = 'task-end'


def _start_name_s(task_name):
    """Return the name used in the makefile for the start of a task."""
    return _TASK_START_STR + task_name


def _end_name_s(task_name):
    """Return the name used in the makefile for the end of a task."""
    return _TASK_END_STR + task_name


def _install_tree_key(host_name):
    """Return a sort key for a tuple for an install tree."""
    return (host_name[0].name, host_name[1])


class BuildTask:
    """A BuildTask represents a step or steps in building a toolchain.

    A BuildTask may be a container for other such tasks, run either in
    series or in parallel, or it may represent a sequence of commands
    and Python steps to be run for the task in series.  BuildTasks may
    have dependencies on other such tasks, and on install trees
    created by such tasks; such dependencies may be order-only
    dependencies, if e.g. a library is to be used only if present in
    this configuration but it is not an error if the task or install
    tree depended on does not exist.  Dependencies of a task T must
    run before any commands or subtasks contained in T, while all
    those contained commands or subtasks must complete before anything
    that depends on task T.

    BuildTasks have hierarchical path-style names, beginning with '/'.

    """

    def __init__(self, relcfg, parent, name, parallel=False):
        """Initialize a BuildTask object.

        The task's name is given relative to its parent, and must be
        empty if there is no parent (the top-level task) but not
        otherwise.  If a task is specified as parallel, it is a
        container for other tasks, to be run in parallel; otherwise,
        it may be a container for commands or for tasks, but not both.

        """
        self.relcfg = relcfg
        self.context = relcfg.context
        self._parent = parent
        if '/' in name:
            self.context.error('invalid build task name: %s' % name)
        self._name = name
        if parent is None:
            self._fullname = name
            self._map = {}
            if name != '':
                self.context.error('top-level task has nonempty name: %s'
                                   % name)
            self._implicit_declare = set()
            self._implicit_contribute = {}
            self._implicit_define = {}
            self._install_provided = set()
        else:
            parent._require_not_finalized('__init__')
            self._fullname = '%s/%s' % (parent._fullname, name)
            self._map = parent._map
            if name == '':
                self.context.error('empty task name not at top level: %s'
                                   % self._fullname)
            self._implicit_declare = parent._implicit_declare
            self._implicit_contribute = parent._implicit_contribute
            self._implicit_define = parent._implicit_define
            self._install_provided = parent._install_provided
        if self._fullname in self._map:
            self.context.error('duplicate task name: %s' % self._fullname)
        self._map[self._fullname] = self
        self._parallel = parallel
        self._subtasks = []
        self._commands = []
        self._env = {}
        self._env_prepend = {}
        self._full_env = None
        self._depends = set()
        self._depends_install = set()
        self._provides_install = set()
        # The following are set at finalization, for tasks with
        # commands in the case of _number and for all tasks in the
        # case of _finalized and _num_tasks.
        self._number = -1
        self._finalized = False
        self._num_tasks = -1
        # The following are set at finalization, on the top-level task
        # only, and are not meaningful for other tasks.
        self._top_deps = None
        self._top_deps_list = None
        if parent is not None:
            parent._add_subtask(self)

    def _require_finalized(self, func):
        """Require a function to be called only after finalization."""
        if not self._finalized:
            self.context.error('%s called before finalization' % func)

    def _require_not_finalized(self, func):
        """Require a function to be called only before finalization."""
        if self._finalized:
            self.context.error('%s called after finalization' % func)

    def _add_subtask(self, subtask):
        """Add a subtask to this task.

        This is called automatically by the constructor for a child
        when a parent is specified, so users of this calls should not
        need to call this function directly.

        """
        self._require_not_finalized('_add_subtask')
        if self._commands:
            self.context.error('task %s has both commands or Python steps '
                               'and subtasks' % self._fullname)
        dep = None
        if self._subtasks and not self._parallel:
            dep = self._subtasks[-1]._fullname
        self._subtasks.append(subtask)
        if dep is not None:
            subtask.depend(dep)

    def add_command(self, command, cwd=None):
        """Add a command to this task."""
        self._require_not_finalized('add_command')
        if self._subtasks:
            self.context.error('task %s has both commands and subtasks'
                               % self._fullname)
        if self._parallel:
            self.context.error('parallel task %s has commands'
                               % self._fullname)
        self._commands.append(BuildCommand(self.context, command, cwd=cwd))

    def add_python(self, py_func, py_args):
        """Add a Python step to this task."""
        self._require_not_finalized('add_python')
        if self._subtasks:
            self.context.error('task %s has both Python steps and subtasks'
                               % self._fullname)
        if self._parallel:
            self.context.error('parallel task %s has Python steps'
                               % self._fullname)
        self._commands.append(BuildPython(self.context, py_func, py_args))

    def add_create_dir(self, directory):
        """Add commands to this task to create a directory.

        The directory may already be present; if so, it is not
        removed.

        """
        self._require_not_finalized('add_create_dir')
        self.add_command(['mkdir', '-p', directory])

    def add_empty_dir(self, directory):
        """Add commands to this task to remove and recreate a directory."""
        self._require_not_finalized('add_empty_dir')
        self.add_command(['rm', '-rf', directory])
        self.add_create_dir(directory)

    def add_empty_dir_parent(self, directory):
        """Add commands to this task to remove a directory and create its
        parent.

        """
        self._require_not_finalized('add_empty_dir_parent')
        self.add_command(['rm', '-rf', directory])
        self.add_create_dir(os.path.dirname(directory))

    def add_make(self, command, cwd):
        """Add a 'make' command to this task."""
        self._require_not_finalized('add_make')
        if self._subtasks:
            self.context.error('task %s has both commands and subtasks'
                               % self._fullname)
        if self._parallel:
            self.context.error('parallel task %s has commands'
                               % self._fullname)
        self._commands.append(BuildMake(self.context, command, cwd=cwd))

    def env_set(self, var, value):
        """Add an environment variable setting for this task.

        This overrides any setting of or prepending to this variable
        in a parent task, or any value previously set for this task
        for this variable.  A variable may not both be set and
        prepended to in the same task.

        """
        self._require_not_finalized('env_set')
        if '=' in var or '\n' in var or '\n' in value:
            self.context.error('bad character in environment variable '
                               'setting %s=%s' % (var, value))
        if var in self._env_prepend:
            self.context.error('variable %s both set and prepended to' % var)
        self._env[var] = value

    def env_prepend(self, var, value):
        """Add an environment variable prepending for this task.

        This is for colon-separated variables like PATH; the value
        given is a single string not containing ':'.  This and is
        prepended to anything else already prepended in this task or
        any value set or prepended in a parent task.  A variable may
        not both be set and prepended to in the same task.

        """
        self._require_not_finalized('env_prepend')
        if '=' in var or '\n' in var or '\n' in value or ':' in value:
            self.context.error('bad character in environment variable '
                               'setting %s prepending %s' % (var, value))
        if var in self._env:
            self.context.error('variable %s both set and prepended to' % var)
        if var not in self._env_prepend:
            self._env_prepend[var] = []
        self._env_prepend[var].append(value)

    def get_full_env(self):
        """Determine the full set of environment overrides for this task."""
        # This requires the task to be finalized because it uses
        # cached values that could be invalided by environment setting
        # changes before finalization.
        self._require_finalized('get_full_env')
        if self._full_env is not None:
            return self._full_env
        if self._parent:
            full_env = dict(self._parent.get_full_env())
        else:
            full_env = {}
        full_env.update(self._env)
        for key, val in self._env_prepend.items():
            if key not in full_env:
                if key in self.context.environ:
                    full_env[key] = self.context.environ[key]
            val_txt = ':'.join(reversed(val))
            if key in full_env:
                full_env[key] = '%s:%s' % (val_txt, full_env[key])
            else:
                full_env[key] = val_txt
        self._full_env = full_env
        return full_env

    def depend(self, dep_name):
        """Add a dependency on another task, by name."""
        self._require_not_finalized('depend')
        self._depends.add(dep_name)

    def depend_install(self, dep_host, dep_name):
        """Add a dependency on an install tree, by host and name."""
        self._require_not_finalized('depend_install')
        self._depends_install.add((dep_host, dep_name))

    def _provide_install_main(self, prov_host, prov_name):
        """Mark this task as providing an install tree.

        This internal function does not check for the tree having been
        declared, defined or contributed to as an implicit install
        tree, as is it used for tasks creating such implicit trees.

        """
        self._require_not_finalized('_provide_install_main')
        prov_tuple = (prov_host, prov_name)
        if prov_tuple in self._install_provided:
            self.context.error('install tree %s/%s already provided'
                               % (prov_host.name, prov_name))
        self._provides_install.add(prov_tuple)
        self._install_provided.add(prov_tuple)

    def provide_install(self, prov_host, prov_name):
        """Mark this task as providing an install tree."""
        self._require_not_finalized('provide_install')
        prov_tuple = (prov_host, prov_name)
        if prov_tuple in self._implicit_declare:
            self.context.error('install tree %s/%s already declared'
                               % (prov_host.name, prov_name))
        if prov_tuple in self._implicit_define:
            self.context.error('install tree %s/%s already defined'
                               % (prov_host.name, prov_name))
        if prov_tuple in self._implicit_contribute:
            self.context.error('install tree %s/%s already contributed to'
                               % (prov_host.name, prov_name))
        self._provide_install_main(prov_host, prov_name)

    def declare_implicit_install(self, host, name):
        """Declare the existence of an implicitly created install tree.

        This tree starts out empty and may have any number of other
        install trees added to it via contribute_implicit_install.

        Calling this on any task is equivalent to calling it on the
        top-level task.

        """
        self._require_not_finalized('declare_implicit_install')
        tree_tuple = (host, name)
        if tree_tuple in self._implicit_declare:
            self.context.error('install tree %s/%s already declared'
                               % (host.name, name))
        if tree_tuple in self._implicit_define:
            self.context.error('install tree %s/%s already defined'
                               % (host.name, name))
        if tree_tuple in self._install_provided:
            self.context.error('install tree %s/%s already provided'
                               % (host.name, name))
        self._implicit_declare.add(tree_tuple)

    def contribute_implicit_install(self, host, name, tree):
        """Add an FSTree object to an implicitly created install tree.

        That tree must be declared with declare_implicit_install,
        either before or after this function is called.

        Calling this on any task is equivalent to calling it on the
        top-level task.

        """
        self._require_not_finalized('contribute_implicit_install')
        tree_tuple = (host, name)
        if tree_tuple in self._implicit_define:
            self.context.error('install tree %s/%s already defined'
                               % (host.name, name))
        if tree_tuple in self._install_provided:
            self.context.error('install tree %s/%s already provided'
                               % (host.name, name))
        if tree_tuple in self._implicit_contribute:
            self._implicit_contribute[tree_tuple] = FSTreeUnion(
                self._implicit_contribute[tree_tuple], tree)
        else:
            self._implicit_contribute[tree_tuple] = tree

    def contribute_package(self, host, tree):
        """Add an FSTree object to the package for the given PkgHost.

        The package-input install tree used is created automatically
        by the package component.

        Calling this on any task is equivalent to calling it on the
        top-level task.

        """
        self._require_not_finalized('contribute_package')
        self.contribute_implicit_install(host, 'package-input', tree)

    def define_implicit_install(self, host, name, tree):
        """Define an implicitly created install tree with an FSTree object.

        This tree corresponds to exactly that object; it must not be
        declared with declare_implicit_install or added to with
        contribute_implicit_install.

        Calling this on any task is equivalent to calling it on the
        top-level task.

        """
        self._require_not_finalized('define_implicit_install')
        tree_tuple = (host, name)
        if tree_tuple in self._implicit_declare:
            self.context.error('install tree %s/%s already declared'
                               % (host.name, name))
        if tree_tuple in self._implicit_define:
            self.context.error('install tree %s/%s already defined'
                               % (host.name, name))
        if tree_tuple in self._implicit_contribute:
            self.context.error('install tree %s/%s already contributed to'
                               % (host.name, name))
        if tree_tuple in self._install_provided:
            self.context.error('install tree %s/%s already provided'
                               % (host.name, name))
        self._implicit_define[tree_tuple] = tree

    def start_name(self):
        """Return the name used in the makefile for the start of this task."""
        return _start_name_s(self._fullname)

    def end_name(self):
        """Return the name used in the makefile for the end of this task."""
        return _end_name_s(self._fullname)

    def log_name(self):
        """Return the name of the log file to use for this task."""
        self._require_finalized('log_name')
        if self._number == -1:
            self.context.error('log_name called for task %s with no commands'
                               % self._fullname)
        return '%04d%s-log.txt' % (self._number,
                                   self._fullname.replace('/', '-'))

    def record_deps(self, deps):
        """Record all dependencies for this task."""
        start_name = self.start_name()
        end_name = self.end_name()
        inst_prov = ['install-trees/%s/%s' % (t[0].name, t[1])
                     for t in sorted(self._provides_install,
                                     key=_install_tree_key)]
        inst_dep = ['install-trees/%s/%s' % (t[0].name, t[1])
                    for t in sorted(self._depends_install,
                                    key=_install_tree_key)]
        name_list = list(inst_prov)
        name_list.append(start_name)
        name_list.append(end_name)
        for name in name_list:
            if name not in deps:
                deps[name] = []
        start_deps = [_end_name_s(d) for d in sorted(self._depends)]
        if self._parent:
            start_deps.append(self._parent.start_name())
        start_deps.extend(inst_dep)
        deps[start_name].extend(start_deps)
        end_deps = [s.end_name() for s in self._subtasks]
        end_deps.append(start_name)
        deps[end_name].extend(end_deps)
        for prov in inst_prov:
            deps[prov].append(end_name)
        for sub in self._subtasks:
            sub.record_deps(deps)

    def _add_makefile_commands(self, makefile, build_context):
        """Add makefile commands for building this task."""
        self._require_finalized('_add_makefile_commands')
        context = self.context
        server = build_context.server
        if self._commands:
            task_desc_text = '[%04d/%04d] %s' % (self._number, self._num_tasks,
                                                 self._fullname)
            log = os.path.join(build_context.logdir, self.log_name())
            target = self.end_name()
            msg_start = server.add_call(build_context.task_start,
                                        [task_desc_text], log, False)
            start_cmd = build_context.wrapper_start_task(log, msg_start)
            makefile.add_command(target, command_to_make(context, start_cmd))
            env = self.get_full_env()
            for cmd in self._commands:
                msg_fail = server.add_call(build_context.task_fail_command,
                                           [task_desc_text, cmd, log],
                                           log, False)
                makefile.add_command(target, cmd.make_string(build_context,
                                                             log, msg_fail,
                                                             env))
            msg_end = server.add_call(build_context.task_end, [task_desc_text],
                                      log, False)
            end_cmd = build_context.wrapper_end_task(log, msg_end)
            makefile.add_command(target, command_to_make(context, end_cmd))
        for sub in self._subtasks:
            sub._add_makefile_commands(makefile, build_context)

    def _create_implicit_install_tasks(self):
        """Create tasks for implicitly created install trees.

        This function should be called only for the top-level task,
        only from the finalize function.

        """
        if self._fullname != '':
            self.context.error('_create_implicit_install_tasks called for '
                               'non-top-level task %s' % self._fullname)
        self._require_not_finalized('_create_implicit_install_tasks')
        for host_name in sorted(self._implicit_contribute.keys(),
                                key=_install_tree_key):
            if host_name not in self._implicit_declare:
                self.context.error('install tree %s/%s never declared'
                                   % (host_name[0].name, host_name[1]))
        all_trees = dict(self._implicit_define)
        all_trees.update(self._implicit_contribute)
        for host_name in self._implicit_declare:
            if host_name not in all_trees:
                all_trees[host_name] = FSTreeEmpty(self.context)
        for tree_host_name in all_trees:
            tree = all_trees[tree_host_name]
            host, name = tree_host_name
            host_task_name = 'install-trees-%s' % host.name
            host_task_full_name = '/%s' % host_task_name
            if host_task_full_name in self._map:
                host_task = self._map[host_task_full_name]
            else:
                host_task = BuildTask(self.relcfg, self, host_task_name, True)
            task = BuildTask(self.relcfg, host_task, name, False)
            task._provide_install_main(host, name)
            for dep in tree.install_trees:
                task.depend_install(*dep)
            path = self.relcfg.install_tree_path(host, name)
            task.add_empty_dir_parent(path)
            task.add_python(tree.export, [path])

    def finalize(self):
        """Finalize this task.

        This function should be called only for the top-level task;
        calling it more than once has the same effect as calling it
        once.  Finalization prevents any commands or dependencies
        being added to any task afterwards, creates tasks for
        implicitly created install trees, and assigns task numbers to
        tasks.

        """
        if self._fullname != '':
            self.context.error('finalize called for non-top-level task %s'
                               % self._fullname)
        if self._finalized:
            return
        self._create_implicit_install_tasks()
        self._top_deps = {}
        self.record_deps(self._top_deps)
        self._top_deps_list = tsort(self.context, self._top_deps)
        task_number = 1
        for target in self._top_deps_list:
            if target.startswith(_TASK_END_STR):
                t_name = target[len(_TASK_END_STR):]
                t_task = self._map[t_name]
                if t_task._commands:
                    t_task._number = task_number
                    task_number += 1
        num_tasks = task_number - 1
        for name in self._map:
            self._map[name]._finalized = True
            self._map[name]._num_tasks = num_tasks

    def makefile_text(self, build_context):
        """Return makefile text for build_context for building this task.

        This function should be called only for the top-level task.
        It finalizes all the tasks so that no more commands or
        dependencies can be added afterwards.

        """
        if self._fullname != '':
            self.context.error('makefile_text called for non-top-level '
                               'task %s' % self._fullname)
        self.finalize()
        makefile = Makefile(self.context, 'all')
        for target in self._top_deps_list:
            makefile.add_target(target)
        makefile.add_deps('all', [self.end_name()])
        for target in self._top_deps_list:
            makefile.add_deps(target, self._top_deps[target])
        self._add_makefile_commands(makefile, build_context)
        return makefile.makefile_text()
