# Support building autoconf-based components.

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

"""Support building autoconf-based components."""

import os.path

from sourcery.buildtask import BuildTask


__all__ = ['add_host_cfg_build_tasks', 'add_host_lib_cfg_build_tasks',
           'add_host_tool_cfg_build_tasks']


def add_host_cfg_build_tasks(relcfg, host, component, parent, name, srcdir,
                             prefix, pkg_cfg_opts, target, make_target,
                             install_target, parallel):
    """Add and return a group of tasks using configure / make / make install.

    The parent task passed is the main task group for the host, or any
    other group within which this group is to be contained.  The host
    passed is a BuildCfg object.  The component passed is the
    ComponentInConfig object.  The name passed is a name to use for
    build directories and install trees as well as for task names; if
    None, the name of the component (copy) is used (this is
    appropriate unless a component is built multiple times for one
    host, e.g. multiple GCC builds for bootstrapping a cross
    compiler).  If srcdir is None, the source directory of that
    component is used (this is appropriate unless configuring a
    subdirectory, e.g. for gdbserver).  If prefix is None, the path to
    the install tree is used as the configured prefix (this is only
    appropriate for host libraries not referring to files in their
    configured prefix at runtime).  A --target configure option is
    passed unless target is None.  Any configure options from the
    configure_opts variable and component hook are added
    automatically.  If make_target is not None, it is the target
    passed to make for the main build step; install_target likewise
    specifies the target for the install step.

    If additional steps are required after installation, the caller
    should add a postinstall task or tasks to the group returned.

    """
    build = relcfg.build.get().build_cfg
    if name is None:
        name = component.copy_name
    if srcdir is None:
        srcdir = component.vars.srcdir.get()
    objdir = relcfg.objdir_path(host, name)
    instdir = relcfg.install_tree_path(host, name)
    if prefix is None:
        cfg_prefix = instdir
        destdir = None
    else:
        cfg_prefix = prefix
        destdir = instdir
    task_group = BuildTask(relcfg, parent, name)
    task_group.provide_install(host, name)
    init_task = BuildTask(relcfg, task_group, 'init')
    init_task.add_empty_dir(objdir)
    init_task.add_empty_dir(instdir)
    cfg_task = BuildTask(relcfg, task_group, 'configure')
    cfg_cmd = [os.path.join(srcdir, 'configure'),
               '--build=%s' % build.triplet,
               '--host=%s' % host.triplet,
               '--prefix=%s' % cfg_prefix]
    if target is not None:
        cfg_cmd.append('--target=%s' % target)
    cfg_cmd.extend(pkg_cfg_opts)
    cfg_cmd.extend(component.vars.configure_opts.get())
    cfg_cmd.extend(component.cls.configure_opts(relcfg, host))
    cfg_cmd.extend(host.configure_vars())
    cfg_cmd.extend(['CC_FOR_BUILD=%s'
                    % ' '.join(build.tool('c-compiler')),
                    'CXX_FOR_BUILD=%s'
                    % ' '.join(build.tool('c++-compiler'))])
    cfg_task.add_command(cfg_cmd, cwd=objdir)
    build_task = BuildTask(relcfg, task_group, 'build')
    if parallel:
        build_cmd = []
    else:
        build_cmd = ['-j1']
    if make_target is not None:
        build_cmd.append(make_target)
    build_task.add_make(build_cmd, objdir)
    install_task = BuildTask(relcfg, task_group, 'install')
    install_cmd = ['-j1', install_target]
    if destdir is not None:
        install_cmd.append('DESTDIR=%s' % destdir)
    install_task.add_make(install_cmd, objdir)
    return task_group


def add_host_lib_cfg_build_tasks(relcfg, host, component, parent, name=None,
                                 srcdir=None, prefix=None, pkg_cfg_opts=(),
                                 make_target=None, install_target='install',
                                 parallel=True):
    """Add and return a group of tasks using configure / make / make
    install, for a host library.

    Host libraries always use --disable-shared, and never specify a
    target.  Normally they do not specify a prefix either.

    """
    cfg_opts = ['--disable-shared']
    cfg_opts.extend(pkg_cfg_opts)
    return add_host_cfg_build_tasks(relcfg, host, component, parent, name,
                                    srcdir, prefix, cfg_opts, None,
                                    make_target, install_target, parallel)


def add_host_tool_cfg_build_tasks(relcfg, host, component, parent, name=None,
                                  srcdir=None, pkg_cfg_opts=(), target='',
                                  make_target=None, install_target='install',
                                  parallel=True):
    """Add and return a group of tasks using configure / make / make
    install, for a host tool to be installed and distributed.

    The configured prefix for a host tool is always installdir from
    the release config.  Normally the target is that from the release
    config, but that may be overridden, or None passed to disable
    using a --target configure option.

    """
    if target == '':
        target = relcfg.target.get()
    return add_host_cfg_build_tasks(relcfg, host, component, parent, name,
                                    srcdir, relcfg.installdir.get(),
                                    pkg_cfg_opts, target, make_target,
                                    install_target, parallel)
