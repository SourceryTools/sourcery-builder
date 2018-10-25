# Support release configurations.

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

"""Support release configurations."""

import functools
import os.path

import sourcery.buildcfg
from sourcery.fstree import FSTreeCopy
import sourcery.pkghost
import sourcery.vc

__all__ = ['ConfigVar', 'ConfigVarGroup', 'ComponentInConfig',
           'add_release_config_arg', 'ReleaseConfigLoader',
           'ReleaseConfigPathLoader', 'ReleaseConfigTextLoader',
           'ReleaseConfig']


class ConfigVar(object):
    """A ConfigVar is a release config variable.

    Before a variable is set in a release config, a ConfigVar must
    first have been defined for that variable (globally or as a
    variable for a particular component).  Some variables may have
    defaults that are set by code if not set explicitly by the release
    configuration.

    """

    def __init__(self, value):
        """Initialize a ConfigVar object."""
        if isinstance(value, ConfigVar):
            self._value = value._value
            self._explicit = value._explicit
        else:
            self._value = value
            self._explicit = False

    def set(self, value):
        """Set the value of a ConfigVar object."""
        self._value = value
        self._explicit = True

    def set_implicit(self, value):
        """Set the value of a ConfigVar object.

        Unlike the set method, this does not mark it as explicitly
        set.  This is intended for components overriding the default
        for a variable shared between components, and for defaults
        determined by code run after a release config has been read,
        not for direct use by release configs.

        """
        self._value = value

    def get(self):
        """Get the value of a ConfigVar object."""
        return self._value

    def get_explicit(self):
        """Return whether a ConfigVar object was explicitly set."""
        return self._explicit


class ConfigVarGroup(object):
    """A collection of related configuration variables.

    Some variables may be directly held in a ConfigVarGroup.  A
    ConfigVarGroup may also contain other ConfigVarGroups, for
    variables associated with a particular component, or variables
    associated with an instance of a component that is used multiple
    times.

    """

    def __init__(self, context, copy=None):
        """Initialize a ConfigVarGroup object."""
        self.context = context
        self._vars = {}
        self._vargroups = {}
        if copy is not None:
            for var in copy._vars:
                self._vars[var] = ConfigVar(copy._vars[var])
            for var in copy._vargroups:
                self._vargroups[var] = ConfigVarGroup(copy._vargroups[var])

    def __getattr__(self, name):
        """Return a member of a ConfigVarGroup."""
        if name in self._vars:
            return self._vars[name]
        if name in self._vargroups:
            return self._vargroups[name]
        raise AttributeError(name)

    def add_var(self, name, value):
        """Add a variable to a ConfigVarGroup."""
        if name in self._vars:
            self.context.error('duplicate variable %s' % name)
        if name in self._vargroups:
            self.context.error('variable %s duplicates group' % name)
        self._vars[name] = ConfigVar(value)

    def add_group(self, name, copy):
        """Add a ConfigVarGroup to a ConfigVarGroup.

        For example, for variables for a component.

        """
        if name in self._vargroups:
            self.context.error('duplicate variable group %s' % name)
        if name in self._vars:
            self.context.error('variable group %s duplicates variable' % name)
        self._vargroups[name] = ConfigVarGroup(self.context, copy)
        return self._vargroups[name]

    def list_vars(self):
        """Return a list of the variables in this ConfigVarGroup."""
        return sorted(self._vars.keys())

    def add_release_config_vars(self):
        """Set up a ConfigVarGroup to store variables for a release config.

        It is assumed the ConfigVarGroup is empty before this function
        is called.

        """
        self.add_var('build', None)
        self.add_var('hosts', None)
        self.add_var('target', None)
        self.add_var('installdir', '/opt/toolchain')
        self.add_var('script_full', self.context.script_full)
        self.add_var('interp', self.context.interp)
        self.add_var('env_set', {})
        for component in self.context.components:
            group = self.add_group(component, None)
            group.add_var('configure_opts', [])
            group.add_var('vc', None)
            group.add_var('version', None)
            group.add_var('source_type', None)
            group.add_var('srcdirname', component)
            cls = self.context.components[component]
            cls.add_release_config_vars(group)


class ComponentInConfig(object):
    """An instance of a component in a release config.

    Normally a config contains a component once only.  However,
    sometimes a component may be contained multiple times because the
    same sources are used in different ways (e.g., building a compiler
    for multiple targets).  In that case, the config has multiple
    instances of this class for that component.

    """

    def __init__(self, orig_name, copy_name, vars_group, cls):
        """Initialize a ComponentInConfig object.

        orig_name is the name of the component in question and
        copy_name is the name used for this copy of it.

        """
        self.orig_name = orig_name
        self.copy_name = copy_name
        self.vars = vars_group
        self.cls = cls


def add_release_config_arg(parser):
    """Add a release config argument to an ArgumentParser."""
    parser.add_argument('release_config',
                        help='The release configuration to read')


class ReleaseConfigLoader(object):
    """How to load a release config.

    A release config may be loaded from a file specified by path, but
    a script (wrapping the basic Sourcery Builder functionality) may
    also wish to find configs in some standard directory, or have a
    more complicated system for mapping a release config name to the
    actual file containing the config.  For testing purposes, a
    release config may also be specified directly as text in Python
    code rather than loaded from a file.

    """

    def load_config(self, relcfg, name):
        """Load the named config.

        This only implements the core functionality of reading a
        config from a file or other source.  The ReleaseConfig
        object's preliminary initialization is done by
        ReleaseConfig.__init__, as is subsequent setting of derived
        values of release config variables.

        """

        contents = self.get_config_text(name)
        cfg_vars = {'cfg': relcfg}
        self.add_cfg_vars_extra()
        context_wrap = [(sourcery.buildcfg, 'BuildCfg'),
                        (sourcery.pkghost, 'PkgHost'),
                        (sourcery.vc, 'GitVC'),
                        (sourcery.vc, 'SvnVC'),
                        (sourcery.vc, 'TarVC')]
        context_wrap_extra = self.get_context_wrap_extra()
        context_wrap.extend(context_wrap_extra)
        for mod, clsname in context_wrap:
            cls = getattr(mod, clsname)
            if clsname in cfg_vars:
                relcfg.context.error('duplicate class name %s' % clsname)
            cfg_vars[clsname] = functools.partial(cls, relcfg.context)
        exec(contents, globals(), cfg_vars)  # pylint: disable=exec-used

    def get_config_text(self, name):
        """Return the text of the release config specified."""
        raise NotImplementedError

    def add_cfg_vars_extra(self):
        """Add any extra variables to set when loading a config.

        Subclasses loading from a file would set the name 'include'
        here for configs to be able to include files shared with other
        configs.

        """

    def get_context_wrap_extra(self):  # pylint: disable=no-self-use
        """Return any extra classes to be wrapped when loading a config.

        Returned values are a tuple (module, class name).  The
        wrappers pass a first argument that is the context for the
        release config, to avoid excess verbosity from release configs
        passing such arguments to many class constructors.

        """
        return []


class ReleaseConfigPathLoader(ReleaseConfigLoader):
    """Load a release config from an absolute or relative path."""

    def get_config_text(self, name):
        with open(name, 'r', encoding='utf-8') as file:
            return file.read()

    def add_cfg_vars_extra(self):
        pass


class ReleaseConfigTextLoader(ReleaseConfigLoader):
    """Load a release config from a string."""

    def get_config_text(self, name):
        return name


class ReleaseConfig(object):
    """Configuration information for a toolchain.

    A ReleaseConfig holds all the configuration information required
    for checking out, building and testing a toolchain.  Some
    information, such as directories to use when building, may be
    passed as command-line arguments to sourcery-builder scripts, but
    this should not affect the generated binaries for releases;
    options that may affect the generated binaries should only be
    accepted in development, not for release builds.

    """

    def __init__(self, context, release_config, loader, args):
        """Initialize the ReleaseConfig from a file."""
        self.args = args
        self.context = context
        self._vg = ConfigVarGroup(context)
        self._vg.add_release_config_vars()
        self._components = set()
        loader.load_config(self, release_config)
        build_orig = self.build.get()
        if not isinstance(build_orig, sourcery.pkghost.PkgHost):
            self.build.set_implicit(sourcery.pkghost.PkgHost(context,
                                                             build_orig))
        if not self.hosts.get_explicit():
            self.hosts.set_implicit((self.build.get(),))
        hlist_new = []
        for host in self.hosts.get():
            if not isinstance(host, sourcery.pkghost.PkgHost):
                if host == build_orig:
                    host = self.build.get()
                else:
                    host = sourcery.pkghost.PkgHost(context, host)
            hlist_new.append(host)
        if hlist_new[0] != self.build.get():
            self.context.error('first host not the same as build system')
        self.hosts.set_implicit(hlist_new)
        installdir = self.installdir.get()
        installdir_rel = installdir[1:]
        self._vg.add_var('installdir_rel', installdir_rel)
        self._vg.add_var('bindir', os.path.join(installdir, 'bin'))
        self._vg.add_var('bindir_rel', os.path.join(installdir_rel, 'bin'))
        self._vg.add_var('sysroot', '%s/%s/libc' % (installdir,
                                                    self.target.get()))
        self._vg.add_var('sysroot_rel', '%s/%s/libc' % (installdir_rel,
                                                        self.target.get()))
        self._vg.add_var('info_dir_rel', os.path.join(installdir_rel,
                                                      'share/info/dir'))
        self._components_full = []
        self._components_full_byname = {}
        for component in sorted(self._components):
            c_vars = self.get_component_vars(component)
            cls = context.components[component]
            c_in_cfg = ComponentInConfig(component, component, c_vars, cls)
            self._components_full.append(c_in_cfg)
            self._components_full_byname[component] = c_in_cfg
            if c_vars.source_type.get() != 'none':
                c_srcdir = '%s-%s' % (c_vars.srcdirname.get(),
                                      c_vars.version.get())
                c_vars.add_var('srcdir', os.path.join(args.srcdir, c_srcdir))
        self._components_full = tuple(self._components_full)

    def __getattr__(self, name):
        """Return a variable or group thereof from a release config."""
        return getattr(self._vg, name)

    def list_vars(self):
        """Return a list of the variables in a release config."""
        return self._vg.list_vars()

    def add_component(self, name):
        """Add a component to a release config.

        It is OK to add a component that is already present.

        """
        if name not in self.context.components:
            self.context.error('unknown component %s' % name)
        self._components.add(name)

    def list_components(self):
        """Return a list of the components in a release config."""
        return self._components_full

    def list_source_components(self):
        """Return a list of the components in a release config with sources."""
        return [c for c in self._components_full
                if c.vars.source_type.get() != 'none']

    def get_component(self, component):
        """Get the ComponentInConfig object for a component."""
        return self._components_full_byname[component]

    def get_component_vars(self, component):
        """Get the ConfigVarGroup for per-component variables."""
        if component not in self._components:
            self.context.error('component %s not in config' % component)
        return getattr(self, component)

    def get_component_var(self, component, var):
        """Get the value of a per-component variable."""
        c_vars = self.get_component_vars(component)
        return getattr(c_vars, var).get()

    def objdir_path(self, host, name):
        """Return the name to use for an object directory.

        The host argument may be a PkgHost or a BuildCfg."""
        if host is None:
            return os.path.join(self.args.objdir, name)
        elif isinstance(host, sourcery.pkghost.PkgHost):
            return os.path.join(self.args.objdir,
                                'pkg-%s-%s' % (name, host.name))
        else:
            return os.path.join(self.args.objdir, '%s-%s' % (name, host.name))

    def install_tree_path(self, host, name):
        """Return the name to use for an install tree.

        The host argument may be a PkgHost or a BuildCfg."""
        base = self.objdir_path(host, 'install-trees')
        return os.path.join(base, name)

    def install_tree_fstree(self, host, name):
        """Return an FSTree for an install tree.

        The host argument may be a PkgHost or a BuildCfg."""
        path = self.install_tree_path(host, name)
        return FSTreeCopy(self.context, path, [(host, name)])
