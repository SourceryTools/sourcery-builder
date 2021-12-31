# Base class for sourcery-builder components.

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

"""Base class for sourcery-builder components."""

__all__ = ['Component']


class Component:
    """Base class from which each component's class inherits."""

    @staticmethod
    def add_release_config_vars(group):
        """Set up release config variables for this component.

        Add any release config variables specific to this component.
        Override any variables that are defined for all components but
        where the default is inappropriate to this one.

        """

    @staticmethod
    def add_dependencies(relcfg):
        """Add any components this one depends on to the release config.

        This is called after ReleaseConfig.__init__ has done its setup
        of component-independent variables (which means it cannot be
        used to add any required bootstrap components), but before it
        has done any setup of per-component variables.  It can use any
        release config variables available at that point, but cannot
        use component sources because they may not be checked out.

        The expected context in which component dependencies are
        useful is where there is a common include file shared by
        multiple release configs that use different subsets of the
        components from it; those configs can add just those
        components that are user-visible parts of the release and
        others such as host libraries are then added automatically
        through dependencies.

        """

    files_to_touch = []
    """Files to touch after checkout.

    The names are interpreted as Python glob patterns (recursive, so
    '**' can be used to find files of a given name in any
    subdirectory).  Files are only touched if they exist.  Files are
    touched at the same time or in the order given.

    """

    @staticmethod
    def postcheckout(context, component):
        """Touch files after checkout.

        This is passed the ComponentInConfig object.  This hook is for
        the case where the component sources provide their own script
        to touch files to put timestamps in the right order.  It must
        not do anything other than changing timestamps of files.
        files_to_touch is used first, then the postcheckout hook is
        run (but normally there is no use for setting both).

        """

    sysrooted_libc = False
    """Whether this component is a libc implementation using sysroot
    directory arrangements.

    If sysroot directory arrangements are used, arrangements within
    each sysroot correspond to directory arrangements for libraries
    used for native compilation on a system with this libc; there may
    be multiple sysroot subdirectories, each of which uses such
    arrangements.  If they are not used (typically for any case other
    than libraries for Unix-like operating systems), there is no
    concept of such native directory arrangements, and no subdirectory
    sysroots; however, compilers may still be configured as sysrooted,
    with symbolic links in place during the compiler build, so that
    headers and libraries can be found at locations other than the
    configured prefix during the compiler build.

    Components that are not a libc should leave this as the default
    False.

    """

    @staticmethod
    def add_build_tasks_for_host(cfg, host, component, host_group):
        """Add any host-specific build tasks associated with this component.

        Such tasks should be added with 'host_group' (a group
        containing tasks to be run in parallel) as their parent; 'cfg'
        is the release config and 'host' is the corresponding PkgHost
        object.  'component' is the ComponentInConfig object.

        """

    @staticmethod
    def add_build_tasks_for_first_host(cfg, host, component, host_group):
        """Add any host-specific build tasks associated with this component
        that should run for the first host only.

        Such tasks should be added with 'host_group' (a group
        containing tasks to be run in parallel) as their parent; 'cfg'
        is the release config and 'host' is the corresponding PkgHost
        object.  'component' is the ComponentInConfig object.

        """

    @staticmethod
    def add_build_tasks_for_other_hosts(cfg, host, component, host_group):
        """Add any host-specific build tasks associated with this component
        that should run for host other than the first host only.

        Such tasks should be added with 'host_group' (a group
        containing tasks to be run in parallel) as their parent; 'cfg'
        is the release config and 'host' is the corresponding PkgHost
        object.  'component' is the ComponentInConfig object.

        """

    @staticmethod
    def add_build_tasks_for_first_host_multilib(cfg, host, component,
                                                host_group, multilib):
        """Add any host-specific build tasks associated with this component
        that should run for the first host only, for the given
        multilib.

        Such tasks should be added with 'host_group' (a group
        containing tasks to be run in parallel) as their parent; 'cfg'
        is the release config and 'host' is the corresponding PkgHost
        object.  'component' is the ComponentInConfig object.

        This is called for each multilib, and should just return for
        inappropriate multilibs (for example, if the component is a
        libc implementation, it would return without adding build
        tasks for any multilibs for other libcs; if it's building some
        other program to be installed in the sysroot, it would return
        without adding build tasks for multilibs using a
        previously-built sysroot).

        """

    @staticmethod
    def add_build_tasks_for_other_hosts_multilib(cfg, host, component,
                                                 host_group, multilib):
        """Add any host-specific build tasks associated with this component
        that should run for host other than the first host only, for
        the given multilib.

        Such tasks should be added with 'host_group' (a group
        containing tasks to be run in parallel) as their parent; 'cfg'
        is the release config and 'host' is the corresponding PkgHost
        object.  'component' is the ComponentInConfig object.

        This is called for each multilib, and should just return for
        inappropriate multilibs (for example, if the component is a
        libc implementation, it would return for any multilibs for
        other libcs).

        Multilib-specific tasks typically relate to target code, which
        only needs to be built for one host.  Thus, this function
        would typically only deal with contributing install trees,
        built for the first host, to the package for some other host,
        not with building anything itself.

        """

    @staticmethod
    def add_build_tasks_init(cfg, component, init_group):
        """Add any initialization build tasks associated with this component.

        Initialization tasks are host-independent and run before all
        other tasks, without any dependencies needing to be specified
        explicitly.  Such tasks should be added with 'init_group' (a
        group containing tasks to be run in parallel) as their parent;
        'cfg' is the release config.  'component' is the
        ComponentInConfig object.

        """

    @staticmethod
    def add_build_tasks_host_indep(cfg, component, host_indep_group):
        """Add any host-independent build tasks associated with this component.

        Such tasks should be added with 'host_indep_group' (a group
        containing tasks to be run in parallel) as their parent; 'cfg'
        is the release config.  'component' is the ComponentInConfig
        object.

        """

    @staticmethod
    def add_build_tasks_fini(cfg, component, fini_group):
        """Add any finalization build tasks associated with this component.

        Finalization tasks are host-independent and run after all
        other tasks, without any dependencies needing to be specified
        explicitly.  Such tasks should be added with 'fini_group' (a
        group containing tasks to be run in parallel) as their parent;
        'cfg' is the release config.  'component' is the
        ComponentInConfig object.

        """

    @staticmethod
    def configure_opts(cfg, host):  # pylint: disable=unused-argument
        """Return component-specific configure options.

        These go after standard configure options and before standard
        configure variables.  This function is a convenience hook for
        components whose add_build_tasks_for_host functions use common
        support for configure-based components, and is not relevant
        for components built in other ways whose
        add_build_tasks_for_host functions do not make use, directly
        or indirectly, of this function.  The host passed is the
        BuildCfg object.

        """
        return []
