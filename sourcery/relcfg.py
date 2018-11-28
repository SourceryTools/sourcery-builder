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

import collections.abc
import functools
import os.path

import sourcery.buildcfg
from sourcery.fstree import FSTreeCopy
import sourcery.pkghost
from sourcery.pkghost import PkgHost
import sourcery.vc
from sourcery.vc import VC

__all__ = ['ConfigVarType', 'ConfigVarTypeList', 'ConfigVarTypeDict',
           'ConfigVarTypeStrEnum', 'ConfigVar', 'ConfigVarGroup',
           'ComponentInConfig', 'add_release_config_arg',
           'ReleaseConfigLoader', 'ReleaseConfigPathLoader',
           'ReleaseConfigTextLoader', 'ReleaseConfig']


class ConfigVarType:
    """A ConfigVarType describes the values to which a ConfigVar may be set.

    A ConfigVarType may just restrict the values to being instances of
    particular types, or it may also provide checking and conversion
    logic applied to the value specified (for example, to convert a
    list to a tuple, or to verify the values of members of some type).

    The restrictions only apply to values passed to setting methods,
    and not to the initial value specified when the variable is
    created.  Thus the initial value may be None (or another special
    value) even if that value is not valid for initial setting.

    ConfigVarType is not intended to cover all possible restrictions
    on values of release config variables, and cannot cover
    restrictions that relate the value of one variable to the value of
    other variables, but provides a preliminary sanity check on values
    specified in release configs to catch some kinds of mistakes.
    Logic in or called from ReleaseConfig.__init__ may check for other
    restrictions on the values of variables.

    """

    def __init__(self, context, *args):
        """Initialize a ConfigVarType object.

        The arguments passed, after the context, are valid types for
        this variable.

        """
        self.context = context
        self._types = tuple(args)

    def check(self, name, value):
        """Check whether a value is valid for the specified type.

        Returns the value after any conversions needed.

        """
        if not isinstance(value, self._types):
            self.context.error('bad type for value of release config '
                               'variable %s' % name)
        return value


class ConfigVarTypeList(ConfigVarType):
    """A ConfigVarTypeList describes a list-typed ConfigVar.

    A type is specified for elements of the list.  A list or tuple may
    be passed and is converted to a tuple.  Arbitrary iterables are
    not allowed, to avoid mistakes passing a string when a list of
    strings is expected.

    """

    def __init__(self, elt_type):
        super().__init__(elt_type.context, list, tuple)
        self._elt_type = elt_type

    def check(self, name, value):
        value = super().check(name, value)
        return tuple(self._elt_type.check(name, elt) for elt in value)


class ConfigVarTypeDict(ConfigVarType):
    """A ConfigVarTypeDict describes a dict-typed ConfigVar.

    Types are specified for keys and values of the dict.  Any mapping
    may be passed and is copied.

    """

    def __init__(self, key_type, value_type):
        super().__init__(key_type.context, collections.abc.Mapping)
        self._key_type = key_type
        self._value_type = value_type

    def check(self, name, value):
        value = super().check(name, value)
        return {self._key_type.check(name, key):
                self._value_type.check(name, elt_value)
                for key, elt_value in value.items()}


class ConfigVarTypeStrEnum(ConfigVarType):
    """A ConfigVarTypeStrEnum describes a ConfigVar taking values in a
    given set of strings.

    """

    def __init__(self, context, values):
        super().__init__(context, str)
        self._values = set(values)

    def check(self, name, value):
        value = super().check(name, value)
        if value not in self._values:
            self.context.error('bad value for release config variable %s'
                               % name)
        return value


class ConfigVar:
    """A ConfigVar is a release config variable.

    Before a variable is set in a release config, a ConfigVar must
    first have been defined for that variable (globally or as a
    variable for a particular component).  Some variables may have
    defaults that are set by code if not set explicitly by the release
    configuration.

    """

    def __init__(self, context, name, var_type, value, doc, internal=False):
        """Initialize a ConfigVar object."""
        self.context = context
        self._name = name
        self._finalized = False
        if isinstance(value, ConfigVar):
            self._type = value._type
            self._value = value._value
            self._explicit = value._explicit
            self.__doc__ = value.__doc__
            self._internal = value._internal
        else:
            self._type = var_type
            self._value = value
            self._explicit = False
            self.__doc__ = doc
            self._internal = internal

    def _require_not_finalized(self):
        """Require a function to be called only before finalization."""
        if self._finalized:
            self.context.error('release config variable %s modified after '
                               'finalization' % self._name)

    def set(self, value):
        """Set the value of a ConfigVar object."""
        self._require_not_finalized()
        self._value = self._type.check(self._name, value)
        self._explicit = True

    def set_implicit(self, value):
        """Set the value of a ConfigVar object.

        Unlike the set method, this does not mark it as explicitly
        set.  This is intended for components overriding the default
        for a variable shared between components, and for defaults
        determined by code run after a release config has been read,
        not for direct use by release configs.

        """
        self._require_not_finalized()
        self._value = self._type.check(self._name, value)

    def get(self):
        """Get the value of a ConfigVar object."""
        return self._value

    def get_explicit(self):
        """Return whether a ConfigVar object was explicitly set."""
        return self._explicit

    def get_internal(self):
        """Return whether a ConfigVar object is an internal variable.

        Internal variables are only set by logic in the ReleaseConfig
        class after a release config has been read, never directly by
        release configs.

        """
        return self._internal

    def finalize(self):
        """Finalize this variable.

        Finalization disallows future changes to a variable's value,
        and is run automatically after reading a release config.

        """
        self._finalized = True


class ConfigVarGroup:
    """A collection of related configuration variables.

    Some variables may be directly held in a ConfigVarGroup.  A
    ConfigVarGroup may also contain other ConfigVarGroups, for
    variables associated with a particular component, or variables
    associated with an instance of a component that is used multiple
    times.

    """

    def __init__(self, context, name, copy=None):
        """Initialize a ConfigVarGroup object."""
        self.context = context
        self._name = name
        self._finalized = False
        self._vars = {}
        self._vargroups = {}
        if name:
            self._name_prefix = '%s.' % name
        else:
            self._name_prefix = ''
        if copy is not None:
            for var in copy._vars:
                var_name = '%s%s' % (self._name_prefix, var)
                self._vars[var] = ConfigVar(context, var_name, None,
                                            copy._vars[var], None)
            for var in copy._vargroups:
                group_name = '%s%s' % (self._name_prefix, var)
                self._vargroups[var] = ConfigVarGroup(self.context,
                                                      group_name,
                                                      copy._vargroups[var])

    def __getattr__(self, name):
        """Return a member of a ConfigVarGroup."""
        if name in self._vars:
            return self._vars[name]
        if name in self._vargroups:
            return self._vargroups[name]
        raise AttributeError(name)

    def add_var(self, name, var_type, value, doc, internal=False):
        """Add a variable to a ConfigVarGroup."""
        if self._finalized:
            self.context.error('variable %s defined after finalization' % name)
        if name in self._vars:
            self.context.error('duplicate variable %s' % name)
        if name in self._vargroups:
            self.context.error('variable %s duplicates group' % name)
        var_name = '%s%s' % (self._name_prefix, name)
        self._vars[name] = ConfigVar(self.context, var_name, var_type, value,
                                     doc, internal)

    def add_group(self, name, copy):
        """Add a ConfigVarGroup to a ConfigVarGroup.

        For example, for variables for a component.

        """
        if self._finalized:
            self.context.error('variable group %s defined after finalization'
                               % name)
        if name in self._vargroups:
            self.context.error('duplicate variable group %s' % name)
        if name in self._vars:
            self.context.error('variable group %s duplicates variable' % name)
        group_name = '%s%s' % (self._name_prefix, name)
        self._vargroups[name] = ConfigVarGroup(self.context, group_name, copy)
        return self._vargroups[name]

    def list_vars(self):
        """Return a list of the variables in this ConfigVarGroup."""
        return sorted(self._vars.keys())

    def list_groups(self):
        """Return a list of the groups in this ConfigVarGroup."""
        return sorted(self._vargroups.keys())

    def finalize(self):
        """Finalize this ConfigVarGroup.

        Finalization disallows future changes to this group, or groups
        or variables therein, and is run automatically after reading a
        release config.

        """
        self._finalized = True
        for var in self._vars:
            self._vars[var].finalize()
        for var in self._vargroups:
            self._vargroups[var].finalize()

    def add_release_config_vars(self):
        """Set up a ConfigVarGroup to store variables for a release config.

        It is assumed the ConfigVarGroup is empty before this function
        is called.

        """
        self.add_var('build',
                     ConfigVarType(self.context, PkgHost, str),
                     None,
                     """A PkgHost object for the system on which this config
                     is to be built.

                     A GNU triplet may be specfied as a string, and is
                     converted automatically into a PkgHost.""")
        self.add_var('hosts',
                     ConfigVarTypeList(
                         ConfigVarType(self.context, PkgHost, str)),
                     None,
                     """A list of PkgHost objects for the hosts for which this
                     config builds tools.

                     If not specified, the default is the build system only.
                     In any case, the first entry in this list must be the
                     same PkgHost object as specified for the build system.
                     Hosts may be specified as strings for GNU triplets, and
                     those are automatically converted into PkgHost objects;
                     if the build system is specified as a string, a host
                     specified as the same string is converted into the same
                     PkgHost object.""")
        self.add_var('target', ConfigVarType(self.context, str), None,
                     """A GNU triplet string for the target for which
                     compilation tools built by this config generate code.

                     Some configs may build tools for more than one target
                     (for example, offloading compilers); this string only
                     describes the main target.  This is a string, not a
                     BuildCfg, since the tools may support several multilibs,
                     each of which has its own BuildCfg.""")
        self.add_var('installdir', ConfigVarType(self.context, str),
                     '/opt/toolchain',
                     """The configured prefix for the host tools built by this
                     config.

                     This does not affect code built for the target; that
                     typically would use a prefix of /usr, independent of the
                     prefix used on the host.  Also, as installed tools are
                     generally relocatable, this is just a build-time default
                     prefix, and users may install in a different prefix.""")
        self.add_var('script_full', ConfigVarType(self.context, str),
                     self.context.script_full,
                     """The expected full path to the script running the build.

                     For release builds, the script running the build is
                     expected to come from a checkout of the build scripts, as
                     created by the checkout command, rather than from some
                     other copy of the scripts that may not be checked out
                     from the desired location and would not be properly
                     packaged in source packages.  Site-specific packages
                     wrapping Sourcery Builder, or configs intended for use in
                     such environments, set this appropriately to enable such
                     checks for release builds.""")
        self.add_var('interp', ConfigVarType(self.context, str),
                     self.context.interp,
                     """The expected full path to the Python interpreter
                     running the build script.

                     For release builds, site-specific packages wrapping
                     Sourcery Builder, or configs intended for use in such
                     environments, set this, like script_full, to enable checks
                     for release builds that the expected Python interpreter is
                     used for the build.""")
        self.add_var('env_set',
                     ConfigVarTypeDict(ConfigVarType(self.context, str),
                                       ConfigVarType(self.context, str)),
                     {},
                     """Environment variables to set for building this config.

                     This may include settings of PATH and LD_LIBRARY_PATH;
                     such settings are required here to ensure a fully
                     controlled build environment with proper isolation from
                     the shell environment of the user running the build.
                     Other environment variables required by the whole build
                     may also be set here.  Environment variables required only
                     by some build tasks may be set by build code at the level
                     of those build tasks.""")
        for component in self.context.components:
            group = self.add_group(component, None)
            group.add_var('configure_opts',
                          ConfigVarTypeList(ConfigVarType(self.context, str)),
                          (),
                          """Options to pass to 'configure' for this component.

                          If this component does not use a configure-based
                          build, this variable is ignored.""")
            group.add_var('vc', ConfigVarType(self.context, VC),
                          None,
                          """The version control location (a VC object) from
                          which sources for this component are checked out.

                          If source_type for a component is 'none', this does
                          not need to be specified.""")
            group.add_var('version', ConfigVarType(self.context, str), None,
                          """A version number or name for this component, as
                          used in source directory names.

                          The value of this variable has no semantic
                          significance beyond its use in source directory
                          names.  If source_type for a component is 'none',
                          this does not need to be specified.""")
            group.add_var('source_type',
                          ConfigVarTypeStrEnum(self.context,
                                               {'open', 'closed', 'none'}),
                          None,
                          """One of 'open', 'closed' or 'none',

                          If 'open', sources for this component are packaged in
                          the source package, which is expected to be
                          distributed to recipients of the binary packages.
                          If 'closed' sources are instead packaged in the
                          backup package, which is not distributed.  If 'none',
                          this component has no source directory (such
                          components may, for example, serve to represent part
                          of the implementation of the build with no sources
                          outside of Sourcery Builder).""")
            group.add_var('srcdirname', ConfigVarType(self.context, str),
                          component,
                          """A prefix to use in names of source directories.

                          This is used together with the specified version
                          number to produce source directory names.  The
                          default is the name of the component.""")
            cls = self.context.components[component]
            cls.add_release_config_vars(group)


class ComponentInConfig:
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


class ReleaseConfigLoader:
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


class ReleaseConfig:
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
        self._vg = ConfigVarGroup(context, '')
        self._vg.add_release_config_vars()
        self._components = set()
        loader.load_config(self, release_config)
        build_orig = self.build.get()
        if not isinstance(build_orig, PkgHost):
            self.build.set_implicit(PkgHost(context, build_orig))
        if not self.hosts.get_explicit():
            self.hosts.set_implicit((self.build.get(),))
        hlist_new = []
        for host in self.hosts.get():
            if not isinstance(host, PkgHost):
                if host == build_orig:
                    host = self.build.get()
                else:
                    host = PkgHost(context, host)
            hlist_new.append(host)
        if hlist_new[0] != self.build.get():
            self.context.error('first host not the same as build system')
        self.hosts.set_implicit(hlist_new)
        installdir = self.installdir.get()
        installdir_rel = installdir[1:]
        self._vg.add_var('installdir_rel', ConfigVarType(self.context, str),
                         installdir_rel,
                         """installdir without the leading '/'.""",
                         internal=True)
        self._vg.add_var('bindir', ConfigVarType(self.context, str),
                         os.path.join(installdir, 'bin'),
                         """Configured directory for host binaries (starting
                         with installdir).""",
                         internal=True)
        self._vg.add_var('bindir_rel', ConfigVarType(self.context, str),
                         os.path.join(installdir_rel, 'bin'),
                         """bindir without the leading '/'.""",
                         internal=True)
        self._vg.add_var('sysroot', ConfigVarType(self.context, str),
                         '%s/%s/libc' % (installdir, self.target.get()),
                         """Configured directory for target sysroot (starting
                         with installdir).

                         This sysroot is the top-level sysroot, which may have
                         many sysroot subdirectories used for different
                         multilibs.""",
                         internal=True)
        self._vg.add_var('sysroot_rel', ConfigVarType(self.context, str),
                         '%s/%s/libc' % (installdir_rel, self.target.get()),
                         """sysroot without the leading '/'.""",
                         internal=True)
        self._vg.add_var('info_dir_rel', ConfigVarType(self.context, str),
                         os.path.join(installdir_rel, 'share/info/dir'),
                         """Configured location of the info directory (starting
                         with installdir_rel).

                         The main purpose of this variable is for use in code
                         that removes the info directory to avoid conflicts
                         between copies installed by different toolchain
                         components.""",
                         internal=True)
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
                c_vars.add_var('srcdir', ConfigVarType(self.context, str),
                               os.path.join(args.srcdir, c_srcdir),
                               """Source directory for this component.""",
                               internal=True)
        self._components_full = tuple(self._components_full)
        self._vg.finalize()

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
        return tuple(c for c in self._components_full
                     if c.vars.source_type.get() != 'none')

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
        elif isinstance(host, PkgHost):
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
