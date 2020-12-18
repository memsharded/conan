import os
import re
import textwrap
import warnings
from collections import OrderedDict

from jinja2 import DictLoader, Environment

from conans.util.files import save, load


def get_vars_config(variables, config):
    result = OrderedDict()
    for k, v in variables.items():
        result[k] = OrderedDict([(config, v)])
    return result


class CMakeToolchainBase(object):
    filename = "conan_toolchain.cmake"
    project_include_filename = "conan_project_include.cmake"

    _toolchain_macros_tpl = textwrap.dedent("""
        {% macro iterate_configs(vars_config, action) -%}
            {% for var, config_values in vars_config.items() -%}
                {%- set genexpr = namespace(str='') %}
                {% for conf, value in config_values.items() -%}
                    {%- set genexpr.str = genexpr.str +
                                      '$<$<CONFIG:' + conf + '>:' + value|string + '>' %}
                {%- endfor %}
                {% if action=='set' %}
                set({{ var }} "{{ genexpr.str }}" CACHE STRING "Var conantoolchain defined")
                {% elif action=='add_compile_definitions' %}
                add_compile_definitions({{ var }}="{{ genexpr.str }}")
                {% endif %}
            {%- endfor %}
        {% endmacro %}
        """)

    _base_toolchain_tpl = textwrap.dedent("""
        {% import 'toolchain_macros' as toolchain_macros %}

        # Conan automatically generated toolchain file
        # DO NOT EDIT MANUALLY, it will be overwritten

        # Avoid including toolchain file several times (bad if appending to variables like
        #   CMAKE_CXX_FLAGS. See https://github.com/android/ndk/issues/323
        if(CONAN_TOOLCHAIN_INCLUDED)
          return()
        endif()
        set(CONAN_TOOLCHAIN_INCLUDED TRUE)

        {% block before_try_compile %}
            {# build_type (Release, Debug, etc) is only defined for single-config generators #}
            {%- if build_type %}
            set(CMAKE_BUILD_TYPE "{{ build_type }}" CACHE STRING "Choose the type of build." FORCE)
            {%- endif %}
        {% endblock %}

        get_property( _CMAKE_IN_TRY_COMPILE GLOBAL PROPERTY IN_TRY_COMPILE )
        if(_CMAKE_IN_TRY_COMPILE)
            message(STATUS "Running toolchain IN_TRY_COMPILE")
            return()
        endif()

        message("Using Conan toolchain through ${CMAKE_TOOLCHAIN_FILE}.")

        {% if conan_project_include_cmake %}
        if(CMAKE_VERSION VERSION_LESS "3.15")
            message(WARNING
                " CMake version less than 3.15 doesn't support CMAKE_PROJECT_INCLUDE variable\\n"
                " used by Conan toolchain to work. In order to get the same behavior you will\\n"
                " need to manually include the generated file after your 'project()' call in the\\n"
                " main CMakeLists.txt file:\\n"
                " \\n"
                "     project(YourProject C CXX)\\n"
                "     include(\\"\\${CMAKE_BINARY_DIR}/conan_project_include.cmake\\")\\n"
                " \\n"
                " This file contains some definitions and extra adjustments that depend on\\n"
                " the build_type and it cannot be done in the toolchain.")
        else()
            # Will be executed after the 'project()' command
            set(CMAKE_PROJECT_INCLUDE "{{ conan_project_include_cmake }}")
        endif()
        {% endif %}

        {% block main %}
            # We are going to adjust automagically many things as requested by Conan
            #   these are the things done by 'conan_basic_setup()'
            set(CMAKE_EXPORT_NO_PACKAGE_REGISTRY ON)
            # To support the cmake_find_package generators
            {% if cmake_module_path -%}
            set(CMAKE_MODULE_PATH {{ cmake_module_path }} ${CMAKE_MODULE_PATH})
            {%- endif %}
            {% if cmake_prefix_path -%}
            set(CMAKE_PREFIX_PATH {{ cmake_prefix_path }} ${CMAKE_PREFIX_PATH})
            {%- endif %}
        {% endblock %}

        # Variables
        {{ toolchain_macros.iterate_configs(variables_config, action='set') }}

        # Preprocessor definitions per configuration
        {{ toolchain_macros.iterate_configs(preprocessor_definitions_config,
                                            action='add_compile_definitions') }}
        """)

    def __init__(self, conanfile, **kwargs):
        self._conanfile = conanfile
        self.variables = OrderedDict()
        self.preprocessor_definitions = OrderedDict()

        # To find the generated cmake_find_package finders
        self.cmake_prefix_path = "${CMAKE_BINARY_DIR}"
        self.cmake_module_path = "${CMAKE_BINARY_DIR}"

        self.build_type = None
        self.configuration = self._conanfile.settings.get_safe("build_type")

    def _get_templates(self):
        return {
            'toolchain_macros': self._toolchain_macros_tpl,
            'base_toolchain': self._base_toolchain_tpl
        }

    def _variables(self):
        # Parsing existing toolchain file to get existing configured runtimes
        config_dict = {}
        if os.path.exists(self.filename):
            existing_include = load(self.filename)
            sets = re.findall(r"set\(([\S]*) (.*) CACHE STRING \"Var conantoolchain defined\"\)",
                              existing_include)
            for set_def in sets:
                var_name = set_def[0]
                var_value = set_def[1]
                print("VAR!!!!! ", var_name, var_value)
                matches = re.findall(r"\$<\$<CONFIG:([A-Za-z]*)>:(.*)>", var_value)
                config_dict[var_name] = dict(matches)
        print("READ VARIABLES ", config_dict)
        return config_dict

    def _existing_preprocessor(self):
        # Parsing existing toolchain file to get existing configured runtimes
        config_dict = {}
        if os.path.exists(self.filename):
            existing_include = load(self.filename)
            sets = re.findall(r"add_compile_definitions\(([\S]*)=(.*)\)",
                              existing_include)
            for set_def in sets:
                var_name = set_def[0]
                var_value = set_def[1]
                print("PREPROCESSOR!!!!! ", var_name, var_value)
                matches = re.findall(r"\$<\$<CONFIG:([A-Za-z]*)>:(.*)>", var_value)
                config_dict[var_name] = dict(matches)
        print("READ PREPROCESSOR ", config_dict)
        return config_dict

    def _get_template_context_data(self):
        """ Returns two dictionaries, the context for the '_template_toolchain' and
            the context for the '_template_project_include' templates.
        """
        existing_vars = self._variables()
        variables = get_vars_config(self.variables, self.configuration)
        for var, config_values in variables.items():
            existing_vars.setdefault(var, OrderedDict()).update(config_values)
        print("EXISTING VARS ", existing_vars)

        existing_preprocessor = self._existing_preprocessor()
        definitions = get_vars_config(self.preprocessor_definitions, self.configuration)
        for var, config_values in definitions.items():
            existing_preprocessor.setdefault(var, OrderedDict()).update(config_values)
        print("EXISTING PREPROCESSOR ", existing_preprocessor)
        ctxt_toolchain = {
            "variables_config": existing_vars,
            "preprocessor_definitions_config": existing_preprocessor,
            "cmake_prefix_path": self.cmake_prefix_path,
            "cmake_module_path": self.cmake_module_path,
            "build_type": self.build_type,
        }
        return ctxt_toolchain, {}

    def write_toolchain_files(self):
        # Warning
        msg = ("\n*****************************************************************\n"
               "******************************************************************\n"
               "'write_toolchain_files()' has been deprecated and moved.\n"
               "It will be removed in next Conan release.\n"
               "Use 'generate()' method instead.\n"
               "********************************************************************\n"
               "********************************************************************\n")
        from conans.client.output import Color, ConanOutput
        ConanOutput(self._conanfile.output._stream,
                    color=self._conanfile.output._color).writeln(msg, front=Color.BRIGHT_RED)
        warnings.warn(msg)
        self.generate()

    def generate(self):
        # Prepare templates to be loaded
        dict_loader = DictLoader(self._get_templates())
        env = Environment(loader=dict_loader)

        ctxt_toolchain, ctxt_project_include = self._get_template_context_data()
        if ctxt_project_include:
            # Make it absolute, wrt to current folder, set by the caller
            conan_project_include_cmake = os.path.abspath(self.project_include_filename)
            conan_project_include_cmake = conan_project_include_cmake.replace("\\", "/")
            t = env.get_template(self.project_include_filename)
            content = t.render(**ctxt_project_include)
            save(conan_project_include_cmake, content)

            ctxt_toolchain.update({'conan_project_include_cmake': conan_project_include_cmake})

        t = env.get_template(self.filename)
        content = t.render(**ctxt_toolchain)
        save(self.filename, content)
