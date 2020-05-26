# coding=utf-8

import os
import textwrap
from collections import OrderedDict, defaultdict

from jinja2 import Template

from conans.client.build.cmake_flags import get_generator, get_generator_platform, \
    CMakeDefinitionsBuilder, get_toolset
from conans.client.generators.cmake_common import CMakeCommonMacros
from conans.util.files import save


# https://stackoverflow.com/questions/30503631/cmake-in-which-order-are-files-parsed-cache-toolchain-etc
# https://cmake.org/cmake/help/v3.6/manual/cmake-toolchains.7.html
# https://github.com/microsoft/vcpkg/tree/master/scripts/buildsystems


class Definitions(OrderedDict):
    _configuration_types = None

    def __init__(self):
        super(Definitions, self).__init__()
        self._configuration_types = {}

    def __getattribute__(self, config):
        try:
            return super(Definitions, self).__getattribute__(config)
        except AttributeError:
            return self._configuration_types.setdefault(config, dict())

    @property
    def configuration_types(self):
        # Reverse index for the configuration_types variables
        ret = defaultdict(list)
        for conf, definitions in self._configuration_types.items():
            for k, v in definitions.items():
                ret[k].append((conf, v))
        return ret


class CMakeToolchain(object):
    filename = "conan_toolchain.cmake"

    _conan_set_libcxx = textwrap.dedent("""
        macro(conan_set_libcxx)
            if(DEFINED CONAN_LIBCXX)
                conan_message(STATUS "Conan: C++ stdlib: ${CONAN_LIBCXX}")
                if(CONAN_COMPILER STREQUAL "clang" OR CONAN_COMPILER STREQUAL "apple-clang")
                    if(CONAN_LIBCXX STREQUAL "libstdc++" OR CONAN_LIBCXX STREQUAL "libstdc++11" )
                        set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} -stdlib=libstdc++")
                    elseif(CONAN_LIBCXX STREQUAL "libc++")
                        set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} -stdlib=libc++")
                    endif()
                endif()
                if(CONAN_COMPILER STREQUAL "sun-cc")
                    if(CONAN_LIBCXX STREQUAL "libCstd")
                        set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} -library=Cstd")
                    elseif(CONAN_LIBCXX STREQUAL "libstdcxx")
                        set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} -library=stdcxx4")
                    elseif(CONAN_LIBCXX STREQUAL "libstlport")
                        set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} -library=stlport4")
                    elseif(CONAN_LIBCXX STREQUAL "libstdc++")
                        set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} -library=stdcpp")
                    endif()
                endif()
                if(CONAN_LIBCXX STREQUAL "libstdc++11")
                    add_definitions(-D_GLIBCXX_USE_CXX11_ABI=1)
                elseif(CONAN_LIBCXX STREQUAL "libstdc++")
                    add_definitions(-D_GLIBCXX_USE_CXX11_ABI=0)
                endif()
            endif()
        endmacro()
    """)

    _conan_set_compiler = textwrap.dedent("""
        macro(conan_set_compiler)
            if(CONAN_COMPILER STREQUAL "gcc")
                conan_message(STATUS "Conan: Adjust compiler: ${CONAN_COMPILER} ${CONAN_COMPILER_VERSION}")
                set(CMAKE_C_COMPILER gcc-${CONAN_COMPILER_VERSION})
                #set(CMAKE_C_COMPILER_VERSION 7.4.0) # ${CONAN_COMPILER_VERSION})
                set(CMAKE_CXX_COMPILER g++-${CONAN_COMPILER_VERSION})
                #set(CMAKE_CXX_COMPILER_VERSION 7.4.0) # ${CONAN_COMPILER_VERSION})
            elseif(CONAN_COMPILER STREQUAL "clang")
                conan_message(STATUS "Conan: Adjust compiler: ${CONAN_COMPILER} ${CONAN_COMPILER_VERSION}")
                set(CMAKE_C_COMPILER clang-${CONAN_COMPILER_VERSION})
                #set(CMAKE_C_COMPILER_VERSION 7.4.0) # ${CONAN_COMPILER_VERSION})
                set(CMAKE_CXX_COMPILER clang++-${CONAN_COMPILER_VERSION})
                #set(CMAKE_CXX_COMPILER_VERSION 7.4.0) # ${CONAN_COMPILER_VERSION})
            endif()
        endmacro()
    """)

    _template_toolchain = textwrap.dedent("""
        # Conan generated toolchain file
        cmake_minimum_required(VERSION 3.0)  # Needed for targets

        # Avoid including toolchain file several times (bad if appending to variables like
        #   CMAKE_CXX_FLAGS. See https://github.com/android/ndk/issues/323
        if(CONAN_TOOLCHAIN_INCLUDED)
          return()
        endif()
        set(CONAN_TOOLCHAIN_INCLUDED true)

        message("Using Conan toolchain through ${CMAKE_TOOLCHAIN_FILE}.")

        ########### Utility macros and functions ###########
        {{ cmake_macros_and_functions }}
        ########### End of Utility macros and functions ###########

        # Configure
        # -- CMake::command_line
        {% if generator_platform %}set(CMAKE_GENERATOR_PLATFORM "{{ generator_platform }}" CACHE STRING "" FORCE){% endif %}
        {% if toolset %}set(CMAKE_GENERATOR_TOOLSET "{{ toolset }}" CACHE STRING "" FORCE){% endif%}

        # --  - CMake.flags --> CMakeDefinitionsBuilder::get_definitions
        {%- for it, value in definitions.items() %}
        {%- if it.startswith('CONAN_') and not it == 'CONAN_LINK_RUNTIME %}
        set({{ it }} "{{ value }}")
        {%- else %}
        set({{ it }} "{{ value }}" CACHE STRING "Value assigned from the Conan toolchain" FORCE)
        {%- endif %}
        {%- endfor %}

        # Set some environment variables
        {%- for it, value in environment.items() %}
        set(ENV{{ '{' }}{{ it }}{{ '}' }} "{{ value }}")
        {%- endfor %}

        get_property( _CMAKE_IN_TRY_COMPILE GLOBAL PROPERTY IN_TRY_COMPILE )
        if(NOT _CMAKE_IN_TRY_COMPILE)
            if(CMAKE_VERSION VERSION_LESS "3.15")
                message(WARNING
                    " CMake version less than 3.15 doesn't support CMAKE_PROJECT_INCLUDE variable\\n"
                    " used by Conan toolchain to work. In order to get the same behavior you will\\n"
                    " need to manually include the generated file after your 'project()' call in the\\n"
                    " main CMakeLists.txt file:\\n"
                    " \\n"
                    "     project(YourProject C CXX)\\n"
                    "     include(\\"{{conan_project_include_cmake}}\\")\\n"
                    " \\n"
                    " This file contains some definitions and extra adjustments that depend on\\n"
                    " the build_type and it cannot be done in the toolchain.")
            else()
                set(CMAKE_PROJECT_INCLUDE "{{ conan_project_include_cmake }}")  # Will be executed after the 'project()' command
            endif()

            # We are going to adjust automagically many things as requested by Conan
            #   these are the things done by 'conan_basic_setup()'
            {% if options.set_rpath %}conan_set_rpath(){% endif %}
            {% if options.set_std %}conan_set_std(){% endif %}
            {% if options.set_fpic %}conan_set_fpic(){% endif %}

            {% if options.set_libcxx %}conan_set_libcxx(){% endif %}
            {% if options.set_find_paths %}conan_set_find_paths(){% endif %}
            {% if options.set_find_library_paths %}conan_set_find_library_paths(){% endif %}

            set(CMAKE_CXX_FLAGS_INIT "${CONAN_CXX_FLAGS}" CACHE STRING "" FORCE)
            set(CMAKE_C_FLAGS_INIT "${CONAN_C_FLAGS}" CACHE STRING "" FORCE)
            set(CMAKE_SHARED_LINKER_FLAGS_INIT "${CONAN_SHARED_LINKER_FLAGS}" CACHE STRING "" FORCE)
            set(CMAKE_EXE_LINKER_FLAGS_INIT "${CONAN_EXE_LINKER_FLAGS}" CACHE STRING "" FORCE)
        endif()

        {% if options.set_compiler %}conan_set_compiler(){% endif %}
    """)

    _template_project_include = textwrap.dedent("""
        # When using a Conan toolchain, this file is included as the last step of all `project()` calls.
        #  https://cmake.org/cmake/help/latest/variable/CMAKE_PROJECT_INCLUDE.html

        if (NOT CONAN_TOOLCHAIN_INCLUDED)
            message(FATAL_ERROR "This file is expected to be used together with the Conan toolchain")
        endif()

        ########### Utility macros and functions ###########
        {{ cmake_macros_and_functions }}
        ########### End of Utility macros and functions ###########

        # Now the debug/release stuff
        # CMAKE_BUILD_TYPE: Use it only if it isn't a multi-config generator
        get_property(_GENERATOR_IS_MULTI_CONFIG GLOBAL PROPERTY GENERATOR_IS_MULTI_CONFIG )
        if(NOT _GENERATOR_IS_MULTI_CONFIG)
            set(CMAKE_BUILD_TYPE "{{ CMAKE_BUILD_TYPE }}" CACHE STRING "Choose the type of build." FORCE)
        endif()
        unset(_GENERATOR_IS_MULTI_CONFIG)

        # Variables scoped to a configuration
        {%- for it, values in configuration_types_definitions.items() -%}
            {%- set generator_expression = namespace(str='') %}
            {%- for conf, value in values -%}
                {%- set generator_expression.str = generator_expression.str + '$<IF:$<CONFIG:' + conf + '>,"' + value|string + '",' %}
                {#- {%- if loop.last %}{% set generator_expression.str = generator_expression.str + '"' + it + '-NOTFOUND"' %}{% endif %} -#}
                {%- if loop.last %}{% set generator_expression.str = generator_expression.str + '""' %}{% endif %}
            {%- endfor -%}
            {% for i in range(values|count) %}{%- set generator_expression.str = generator_expression.str + '>' %}{% endfor %}
        set({{ it }} {{ generator_expression.str }})
        {%- endfor %}

        # Adjustments that depends on the build_type
        {% if options.set_vs_runtime %}conan_set_vs_runtime(){% endif %}
    """)

    def __init__(self, conanfile,
                 generator=None,
                 cmake_system_name=True,
                 parallel=True,
                 build_type=None,
                 toolset=None,
                 make_program=None,
                 # cmake_program=None,  # TODO: cmake program should be considered in the environment
                 generator_platform=None
                 ):
        self._conanfile = conanfile
        del conanfile

        self.set_rpath = True
        self.set_std = True
        self.set_fpic = True
        self.set_libcxx = True
        self.set_find_paths = True
        self.set_find_library_paths = True
        self.set_compiler = True
        self.set_vs_runtime = True

        generator = generator or get_generator(self._conanfile)
        self._generator_platform = generator_platform or \
                                   get_generator_platform(self._conanfile.settings, generator)
        self._toolset = toolset or get_toolset(self._conanfile.settings)
        self._build_type = build_type or self._conanfile.settings.get_safe("build_type")

        builder = CMakeDefinitionsBuilder(self._conanfile,
                                          cmake_system_name=cmake_system_name,
                                          make_program=make_program, parallel=parallel,
                                          generator=generator,
                                          set_cmake_flags=False,
                                          forced_build_type=build_type,
                                          output=self._conanfile.output)
        self.definitions = Definitions()
        self.definitions.update(builder.get_definitions())
        self.definitions.pop("CMAKE_BUILD_TYPE", None)

        # Some variables can go to the environment
        # TODO: Do we need this or can we move it to environment stuff
        self.environment = {}
        if "pkg_config" in self._conanfile.generators and "PKG_CONFIG_PATH" not in os.environ:
            self.environment.update({
                "PKG_CONFIG_PATH": self._conanfile.install_folder
            })

    def dump(self, install_folder):
        # The user can modify these dictionaries, add them to the context in the very last moment
        context = {
            "CMAKE_BUILD_TYPE": self._build_type,
            "generator_platform": self._generator_platform,
            "toolset": self._toolset,
            "definitions": self.definitions,
            "environment": self.environment,
            "options": {"set_rpath": self.set_rpath,
                        "set_std": self.set_std,
                        "set_fpic": self.set_fpic,
                        "set_libcxx": self.set_libcxx,
                        "set_find_paths": self.set_find_paths,
                        "set_find_library_paths": self.set_find_library_paths,
                        "set_compiler": self.set_compiler,
                        "set_vs_runtime": self.set_vs_runtime}
        }

        conan_project_include_cmake = os.path.join(install_folder, "conan_project_include.cmake")
        t = Template(self._template_project_include)
        content = t.render(configuration_types_definitions=self.definitions.configuration_types,
                           cmake_macros_and_functions="\n".join([
                               CMakeCommonMacros.conan_set_vs_runtime_preserve_build_type
                           ]),
                           **context)
        save(conan_project_include_cmake, content)

        # TODO: I need the profile_host and profile_build here!
        # TODO: What if the compiler is a build require?
        # TODO: Add all the stuff related to settings (ALL settings or just _MY_ settings?)
        # TODO: I would want to have here the path to the compiler too
        t = Template(self._template_toolchain)
        content = t.render(conan_project_include_cmake=conan_project_include_cmake.replace("\\", "/"),
                           cmake_macros_and_functions="\n".join([
                               CMakeCommonMacros.conan_message,
                               CMakeCommonMacros.conan_get_policy,
                               CMakeCommonMacros.conan_set_rpath,
                               CMakeCommonMacros.conan_set_std,
                               CMakeCommonMacros.conan_set_fpic,
                               self._conan_set_libcxx,
                               CMakeCommonMacros.conan_set_find_paths,
                               CMakeCommonMacros.conan_set_find_library_paths,
                               self._conan_set_compiler
                           ]),
                           **context)
        save(os.path.join(install_folder, self.filename), content)
