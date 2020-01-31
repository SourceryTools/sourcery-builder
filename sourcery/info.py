# Report information about a release configuration.

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

"""Report information about a release configuration."""

__all__ = ['info_text']


def _info_line(var, value):
    """Return a single line of information output."""
    return '%-30s %s' % (var, value)


def _info_vars_text(relcfg, internal):
    """Return lines of text for variables, internal or not."""
    out_lines = []
    components = relcfg.list_components()
    for var in relcfg.list_vars():
        var_obj = getattr(relcfg, var)
        if var_obj.get_internal() == internal:
            out_lines.append(_info_line(var, repr(var_obj.get())))
    for component in components:
        cmp_lines = []
        for var in component.vars.list_vars():
            var_obj = getattr(component.vars, var)
            if var_obj.get_internal() == internal:
                var_name = '%s.%s' % (component.copy_name, var)
                cmp_lines.append(_info_line(var_name, repr(var_obj.get())))
        if cmp_lines:
            out_lines.append('')
            out_lines.extend(cmp_lines)
    return out_lines


def info_text(relcfg, verbose, internal_vars):
    """Return text to print with information about a config."""
    out_lines = []
    components = relcfg.list_components()
    out_lines.append(_info_line('Components:',
                                ' '.join(c.copy_name for c in components)))
    out_lines.append('')
    for component in components:
        if component.vars.source_type.get() == 'none':
            value = '(no source)'
        else:
            value = component.vars.version.get()
        out_lines.append(_info_line(component.copy_name, value))
    if verbose:
        out_lines.append('')
        out_lines.append('Variables:')
        out_lines.append('')
        out_lines.extend(_info_vars_text(relcfg, False))
    if internal_vars:
        out_lines.append('')
        out_lines.append('Internal variables:')
        out_lines.append('')
        out_lines.extend(_info_vars_text(relcfg, True))
    return '\n'.join(out_lines)
