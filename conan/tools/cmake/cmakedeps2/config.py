import textwrap

import jinja2
from jinja2 import Template


class ConfigTemplate2:
    """
    FooConfig.cmake
    foo-config.cmake
    """
    def __init__(self, cmakedeps, conanfile):
        self._cmakedeps = cmakedeps
        self._conanfile = conanfile

    def content(self):
        t = Template(self._template, trim_blocks=True, lstrip_blocks=True,
                     undefined=jinja2.StrictUndefined)
        return t.render(self._context)

    @property
    def filename(self):
        f = self._cmakedeps.get_cmake_filename(self._conanfile)
        return f"{f}-config.cmake" if f == f.lower() else f"{f}Configcmake"

    @property
    def _context(self):
        f = self._cmakedeps.get_cmake_filename(self._conanfile)
        targets_include = f"{f}Targets.cmake"
        pkg_name = self._conanfile.ref.name
        return {"pkg_name": pkg_name,
                "config_suffix": self._cmakedeps.config_suffix,
                "targets_include_file": targets_include}

    @property
    def _template(self):
        return textwrap.dedent("""\
        {%- macro pkg_var(pkg_name, var, config_suffix) -%}
             {{'${'+pkg_name+'_'+var+config_suffix+'}'}}
        {%- endmacro -%}
        # Requires CMake > 3.15
        if(${CMAKE_VERSION} VERSION_LESS "3.15")
            message(FATAL_ERROR "The 'CMakeDeps' generator only works with CMake >= 3.15")
        endif()

        include(${CMAKE_CURRENT_LIST_DIR}/{{ targets_include_file }})

        get_property(isMultiConfig GLOBAL PROPERTY GENERATOR_IS_MULTI_CONFIG)
        if(NOT isMultiConfig AND NOT CMAKE_BUILD_TYPE)
           message(FATAL_ERROR "Please, set the CMAKE_BUILD_TYPE variable when calling to CMake "
                               "adding the '-DCMAKE_BUILD_TYPE=<build_type>' argument.")
        endif()
        """)
