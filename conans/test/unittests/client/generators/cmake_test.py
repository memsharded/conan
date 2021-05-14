import os
import re
import unittest

from mock import patch, Mock

import conans
from conans.client.build.cmake import CMake
from conans.client.build.cmake_flags import CMakeDefinitionsBuilder
from conans.client.conf import get_default_settings_yml
from conans.client.generators.cmake import CMakeGenerator
from conans.errors import ConanException
from conans.model.build_info import CppInfo
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


class _MockSettings(object):
    build_type = None
    os = None
    os_build = None
    fields = []

    def __init__(self, build_type=None):
        class BuildType(str):
            values_range = ["Debug", "Release"]
        self.build_type = BuildType(build_type)

    @property
    def compiler(self):
        raise ConanException("mock: not available")

    def constraint(self, _):
        return self

    def get_safe(self, name):
        if name == "build_type":
            return self.build_type
        if name == "os":
            return self.os
        if name == "os_build":
            return self.os_build
        return None

    def items(self):
        return {}


class CMakeGeneratorTest(unittest.TestCase):

    @staticmethod
    def _extract_macro(name, text):
        pattern = r".*(macro\(%s\).*?endmacro\(\)).*" % name
        return re.sub(pattern, r"\1", text, flags=re.DOTALL)

    def test_variables_setup(self):
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), EnvValues())
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "dummy_root_folder1")
        cpp_info.defines = ["MYDEFINE1"]
        conanfile.deps_cpp_info.add(ref.name, cpp_info)
        ref = ConanFileReference.loads("MyPkg2/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "dummy_root_folder2")
        cpp_info.defines = ["MYDEFINE2"]
        conanfile.deps_cpp_info.add(ref.name, cpp_info)
        conanfile.deps_user_info["LIB1"].myvar = "myvalue"
        conanfile.deps_user_info["LIB1"].myvar2 = "myvalue2"
        conanfile.deps_user_info["lib2"].MYVAR2 = "myvalue4"
        generator = CMakeGenerator(conanfile)
        content = generator.content
        cmake_lines = content.splitlines()
        self.assertIn('set(CONAN_DEFINES_MYPKG "-DMYDEFINE1")', cmake_lines)
        self.assertIn('set(CONAN_DEFINES_MYPKG2 "-DMYDEFINE2")', cmake_lines)
        self.assertIn('set(CONAN_COMPILE_DEFINITIONS_MYPKG "MYDEFINE1")', cmake_lines)
        self.assertIn('set(CONAN_COMPILE_DEFINITIONS_MYPKG2 "MYDEFINE2")', cmake_lines)

        self.assertIn('set(CONAN_USER_LIB1_myvar "myvalue")', cmake_lines)
        self.assertIn('set(CONAN_USER_LIB1_myvar2 "myvalue2")', cmake_lines)
        self.assertIn('set(CONAN_USER_LIB2_MYVAR2 "myvalue4")', cmake_lines)

    def test_paths_cmake(self):
        settings_mock = _MockSettings()
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(settings_mock, EnvValues())
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        tmp_folder = temp_folder()
        save(os.path.join(tmp_folder, "lib", "mylib.lib"), "")
        save(os.path.join(tmp_folder, "include", "myheader.h"), "")
        cpp_info = CppInfo(ref.name, tmp_folder)
        cpp_info.release.libs = ["hello"]
        cpp_info.debug.libs = ["hello_D"]
        conanfile.deps_cpp_info.add(ref.name, cpp_info)
        generator = CMakeGenerator(conanfile)
        content = generator.content
        content = content.replace(tmp_folder.replace("\\", "/"), "root_folder")
        cmake_lines = content.splitlines()
        self.assertIn('set(CONAN_INCLUDE_DIRS_MYPKG_RELEASE "root_folder/include")', cmake_lines)
        self.assertIn('set(CONAN_LIB_DIRS_MYPKG_RELEASE "root_folder/lib")', cmake_lines)

    def test_multi_flag(self):
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), EnvValues())
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "dummy_root_folder1")
        cpp_info.includedirs.append("other_include_dir")
        cpp_info.cxxflags = ["-DGTEST_USE_OWN_TR1_TUPLE=1", "-DGTEST_LINKED_AS_SHARED_LIBRARY=1"]
        conanfile.deps_cpp_info.add(ref.name, cpp_info)
        ref = ConanFileReference.loads("MyPkg2/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "dummy_root_folder2")
        cpp_info.cflags = ["-DSOMEFLAG=1"]
        conanfile.deps_cpp_info.add(ref.name, cpp_info)
        generator = CMakeGenerator(conanfile)
        content = generator.content
        cmake_lines = content.splitlines()
        self.assertIn('set(CONAN_C_FLAGS_MYPKG2 "-DSOMEFLAG=1")', cmake_lines)
        self.assertIn('set(CONAN_CXX_FLAGS_MYPKG "-DGTEST_USE_OWN_TR1_TUPLE=1'
                      ' -DGTEST_LINKED_AS_SHARED_LIBRARY=1")', cmake_lines)
        self.assertIn('set(CONAN_C_FLAGS "-DSOMEFLAG=1 ${CONAN_C_FLAGS}")', cmake_lines)
        self.assertIn('set(CONAN_CXX_FLAGS "-DGTEST_USE_OWN_TR1_TUPLE=1'
                      ' -DGTEST_LINKED_AS_SHARED_LIBRARY=1 ${CONAN_CXX_FLAGS}")', cmake_lines)

    def test_escaped_flags(self):
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), EnvValues())
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "dummy_root_folder1")
        cpp_info.includedirs.append("other_include_dir")
        cpp_info.cxxflags = ["-load", r"C:\foo\bar.dll"]
        cpp_info.cflags = ["-load", r"C:\foo\bar2.dll"]
        cpp_info.defines = ['MY_DEF=My string', 'MY_DEF2=My other string']
        conanfile.deps_cpp_info.add(ref.name, cpp_info)
        generator = CMakeGenerator(conanfile)
        content = generator.content
        cmake_lines = content.splitlines()
        self.assertIn(r'set(CONAN_C_FLAGS_MYPKG "-load C:\\foo\\bar2.dll")', cmake_lines)
        self.assertIn(r'set(CONAN_CXX_FLAGS_MYPKG "-load C:\\foo\\bar.dll")', cmake_lines)
        self.assertIn(r'set(CONAN_DEFINES_MYPKG "-DMY_DEF=My string"', cmake_lines)
        self.assertIn('\t\t\t"-DMY_DEF2=My other string")', cmake_lines)

    def test_aux_cmake_test_setup(self):
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), EnvValues())
        generator = CMakeGenerator(conanfile)
        aux_cmake_test_setup = generator.content

        # extract the conan_basic_setup macro
        macro = self._extract_macro("conan_basic_setup", aux_cmake_test_setup)
        self.assertEqual("""macro(conan_basic_setup)
    set(options TARGETS NO_OUTPUT_DIRS SKIP_RPATH KEEP_RPATHS SKIP_STD SKIP_FPIC)
    cmake_parse_arguments(ARGUMENTS "${options}" "${oneValueArgs}" "${multiValueArgs}" ${ARGN} )

    if(CONAN_EXPORTED)
        conan_message(STATUS "Conan: called by CMake conan helper")
    endif()

    if(CONAN_IN_LOCAL_CACHE)
        conan_message(STATUS "Conan: called inside local cache")
    endif()

    if(NOT ARGUMENTS_NO_OUTPUT_DIRS)
        conan_message(STATUS "Conan: Adjusting output directories")
        conan_output_dirs_setup()
    endif()

    if(NOT ARGUMENTS_TARGETS)
        conan_message(STATUS "Conan: Using cmake global configuration")
        conan_global_flags()
    else()
        conan_message(STATUS "Conan: Using cmake targets configuration")
        conan_define_targets()
    endif()

    if(ARGUMENTS_SKIP_RPATH)
        # Change by "DEPRECATION" or "SEND_ERROR" when we are ready
        conan_message(WARNING "Conan: SKIP_RPATH is deprecated, it has been renamed to KEEP_RPATHS")
    endif()

    if(NOT ARGUMENTS_SKIP_RPATH AND NOT ARGUMENTS_KEEP_RPATHS)
        # Parameter has renamed, but we keep the compatibility with old SKIP_RPATH
        conan_set_rpath()
    endif()

    if(NOT ARGUMENTS_SKIP_STD)
        conan_set_std()
    endif()

    if(NOT ARGUMENTS_SKIP_FPIC)
        conan_set_fpic()
    endif()

    conan_check_compiler()
    conan_set_libcxx()
    conan_set_vs_runtime()
    conan_set_find_paths()
    conan_include_build_modules()
    conan_set_find_library_paths()
endmacro()""", macro)

        # extract the conan_set_find_paths macro
        macro = self._extract_macro("conan_set_find_paths", aux_cmake_test_setup)
        self.assertEqual("""macro(conan_set_find_paths)
    # CMAKE_MODULE_PATH does not have Debug/Release config, but there are variables
    # CONAN_CMAKE_MODULE_PATH_DEBUG to be used by the consumer
    # CMake can find findXXX.cmake files in the root of packages
    set(CMAKE_MODULE_PATH ${CONAN_CMAKE_MODULE_PATH} ${CMAKE_MODULE_PATH})

    # Make find_package() to work
    set(CMAKE_PREFIX_PATH ${CONAN_CMAKE_MODULE_PATH} ${CMAKE_PREFIX_PATH})

    # Set the find root path (cross build)
    set(CMAKE_FIND_ROOT_PATH ${CONAN_CMAKE_FIND_ROOT_PATH} ${CMAKE_FIND_ROOT_PATH})
    if(CONAN_CMAKE_FIND_ROOT_PATH_MODE_PROGRAM)
        set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM ${CONAN_CMAKE_FIND_ROOT_PATH_MODE_PROGRAM})
    endif()
    if(CONAN_CMAKE_FIND_ROOT_PATH_MODE_LIBRARY)
        set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ${CONAN_CMAKE_FIND_ROOT_PATH_MODE_LIBRARY})
    endif()
    if(CONAN_CMAKE_FIND_ROOT_PATH_MODE_INCLUDE)
        set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ${CONAN_CMAKE_FIND_ROOT_PATH_MODE_INCLUDE})
    endif()
endmacro()""", macro)

    def test_name_and_version_are_generated(self):
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), EnvValues())
        conanfile.name = "MyPkg"
        conanfile.version = "1.1.0"
        generator = CMakeGenerator(conanfile)
        content = generator.content
        cmake_lines = content.splitlines()
        self.assertIn('set(CONAN_PACKAGE_NAME MyPkg)', cmake_lines)
        self.assertIn('set(CONAN_PACKAGE_VERSION 1.1.0)', cmake_lines)

    def test_settings_are_generated(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "12"
        settings.compiler.runtime = "MD"
        settings.arch = "x86"
        settings.build_type = "Debug"
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), EnvValues())
        conanfile.settings = settings
        generator = CMakeGenerator(conanfile)
        content = generator.content
        cmake_lines = content.splitlines()
        self.assertIn('set(CONAN_SETTINGS_BUILD_TYPE "Debug")', cmake_lines)
        self.assertIn('set(CONAN_SETTINGS_ARCH "x86")', cmake_lines)
        self.assertIn('set(CONAN_SETTINGS_COMPILER "Visual Studio")', cmake_lines)
        self.assertIn('set(CONAN_SETTINGS_COMPILER_VERSION "12")', cmake_lines)
        self.assertIn('set(CONAN_SETTINGS_COMPILER_RUNTIME "MD")', cmake_lines)
        self.assertIn('set(CONAN_SETTINGS_OS "Windows")', cmake_lines)

    def test_cmake_definitions_apple(self):
        # https://github.com/conan-io/conan/issues/7875
        settings_mock = _MockSettings(build_type="Release")
        settings_mock.os = "iOS"
        settings_mock.os_build = "Macos"
        conanfile = ConanFile(Mock(), None)
        conanfile.install_folder = "/c/foo/testing"
        conanfile.initialize(settings_mock, EnvValues())
        definitions_builder = CMakeDefinitionsBuilder(conanfile)
        definitions = definitions_builder.get_definitions("3.13")
        self.assertEqual("Darwin", definitions["CMAKE_SYSTEM_NAME"])
        definitions = definitions_builder.get_definitions("3.14")
        self.assertEqual("iOS", definitions["CMAKE_SYSTEM_NAME"])
        definitions = definitions_builder.get_definitions(None)
        self.assertEqual("Darwin", definitions["CMAKE_SYSTEM_NAME"])

    def test_cmake_definitions_cmake_not_in_path(self):
        def raise_get_version():
            raise ConanException('Error retrieving CMake version')

        with patch.object(conans.client.build.cmake.CMake, "get_version",
                          side_effect=raise_get_version):
            settings_mock = _MockSettings(build_type="Release")
            conanfile = ConanFile(Mock(), None)
            install_folder = "/c/foo/testing"
            setattr(conanfile, "install_folder", install_folder)
            conanfile.initialize(settings_mock, EnvValues())
            assert CMake(conanfile)

    def test_apple_frameworks(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Macos"
        settings.compiler = "apple-clang"
        settings.compiler.version = "9.1"
        settings.compiler.libcxx = "libc++"
        settings.arch = "x86_64"
        settings.build_type = "Debug"
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), EnvValues())
        conanfile.settings = settings

        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "dummy_root_folder1")
        cpp_info.frameworkdirs.extend(["path/to/Frameworks1", "path/to/Frameworks2"])
        cpp_info.frameworks = ["OpenGL", "OpenCL"]
        cpp_info.filter_empty = False
        conanfile.deps_cpp_info.add(ref.name, cpp_info)

        generator = CMakeGenerator(conanfile)
        content = generator.content
        self.assertIn('find_library(CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND NAME ${_FRAMEWORK} PATHS'
                      ' ${CONAN_FRAMEWORK_DIRS${SUFFIX}} CMAKE_FIND_ROOT_PATH_BOTH)', content)
        self.assertIn('set(CONAN_FRAMEWORK_DIRS "dummy_root_folder1/Frameworks"\n'
                      '\t\t\t"dummy_root_folder1/path/to/Frameworks1"\n'
                      '\t\t\t"dummy_root_folder1/path/to/Frameworks2" '
                      '${CONAN_FRAMEWORK_DIRS})', content)
        self.assertIn('set(CONAN_LIBS ${CONAN_LIBS} ${CONAN_SYSTEM_LIBS} '
                      '${CONAN_FRAMEWORKS_FOUND})', content)


class CMakeCppInfoNameTest(unittest.TestCase):
    """
    Test cpp_info.name values are applied in generators instead of the reference name
    """

    def setUp(self):
        self.conanfile = ConanFile(Mock(), None)
        settings = _MockSettings(build_type="Debug")
        self.conanfile.initialize(settings, EnvValues())
        ref = ConanFileReference.loads("my_pkg/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "dummy_root_folder1")
        cpp_info.name = "MyPkG"
        self.conanfile.deps_cpp_info.add(ref.name, cpp_info)
        ref = ConanFileReference.loads("my_pkg2/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "dummy_root_folder2")
        cpp_info.name = "MyPkG2"
        cpp_info.public_deps = ["my_pkg"]
        self.conanfile.deps_cpp_info.add(ref.name, cpp_info)

    def test_cmake(self):
        generator = CMakeGenerator(self.conanfile)
        content = generator.content
        self.assertIn("set(CONAN_DEPENDENCIES my_pkg my_pkg2)", content)
        content = content.replace("set(CONAN_DEPENDENCIES my_pkg my_pkg2)", "")
        self.assertNotIn("my_pkg", content)
        self.assertNotIn("MY_PKG", content)
        self.assertIn('add_library(CONAN_PKG::MyPkG INTERFACE IMPORTED)', content)
        self.assertIn('add_library(CONAN_PKG::MyPkG2 INTERFACE IMPORTED)', content)
        self.assertNotIn('CONAN_PKG::my_pkg', content)
        self.assertNotIn('CONAN_PKG::my_pkg2', content)


class CMakeCppInfoNamesTest(unittest.TestCase):
    """
    Test cpp_info.names["generator"] values are applied in generators instead of the cpp_info.name
    """

    def setUp(self):
        self.conanfile = ConanFile(Mock(), None)
        settings = _MockSettings(build_type="Debug")
        self.conanfile.initialize(settings, EnvValues())
        ref = ConanFileReference.loads("my_pkg/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "dummy_root_folder1")
        cpp_info.name = "MyPkG"
        cpp_info.names["cmake"] = "MyCMakeName"
        cpp_info.names["cmake_multi"] = "MyCMakeMultiName"
        cpp_info.names["cmake_find_package"] = "MyCMakeFindPackageName"
        cpp_info.names["cmake_find_package_multi"] = "MyCMakeFindPackageMultiName"
        self.conanfile.deps_cpp_info.add(ref.name, cpp_info)
        ref = ConanFileReference.loads("my_pkg2/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "dummy_root_folder2")
        cpp_info.name = "MyPkG2"
        cpp_info.names["cmake"] = "MyCMakeName2"
        cpp_info.names["cmake_multi"] = "MyCMakeMultiName2"
        cpp_info.names["cmake_find_package"] = "MyCMakeFindPackageName2"
        cpp_info.names["cmake_find_package_multi"] = "MyCMakeFindPackageMultiName2"
        cpp_info.public_deps = ["my_pkg"]
        self.conanfile.deps_cpp_info.add(ref.name, cpp_info)

    def test_cmake(self):
        generator = CMakeGenerator(self.conanfile)
        content = generator.content
        self.assertNotIn("MyPkG", content)
        self.assertNotIn("MyPkG2", content)
        self.assertIn('add_library(CONAN_PKG::MyCMakeName INTERFACE IMPORTED)', content)
        self.assertIn('add_library(CONAN_PKG::MyCMakeName2 INTERFACE IMPORTED)', content)


class CMakeBuildModulesTest(unittest.TestCase):

    def setUp(self):
        settings_mock = _MockSettings(build_type="Release")
        self.conanfile = ConanFile(Mock(), None)
        self.conanfile.initialize(settings_mock, EnvValues())
        ref = ConanFileReference.loads("my_pkg/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "dummy_root_folder1")
        cpp_info.filter_empty = False  # For testing purposes only
        cpp_info.name = ref.name
        cpp_info.build_modules["cmake"] = ["my-module.cmake"]
        cpp_info.build_modules["cmake_multi"] = ["my-module.cmake"]
        cpp_info.build_modules["cmake_find_package"] = ["my-module.cmake"]
        cpp_info.build_modules["cmake_find_package_multi"] = ["my-module.cmake"]
        self.conanfile.deps_cpp_info.add(ref.name, cpp_info)
        ref = ConanFileReference.loads("my_pkg2/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "dummy_root_folder2")
        cpp_info.filter_empty = False  # For testing purposes only
        cpp_info.name = ref.name
        cpp_info.build_modules["cmake"] = ["other-mod.cmake", "not-a-cmake-module.pc"]
        cpp_info.build_modules["cmake_multi"] = ["other-mod.cmake", "not-a-cmake-module.pc"]
        cpp_info.build_modules["cmake_find_package"] = ["other-mod.cmake", "not-a-cmake-module.pc"]
        cpp_info.build_modules["cmake_find_package_multi"] = ["other-mod.cmake",
                                                              "not-a-cmake-module.pc"]
        cpp_info.release.build_modules["cmake"] = ["release-mod.cmake"]
        cpp_info.release.build_modules["cmake_multi"] = ["release-mod.cmake"]
        cpp_info.release.build_modules["cmake_find_package"] = ["release-mod.cmake"]
        cpp_info.release.build_modules["cmake_find_package_multi"] = ["release-mod.cmake"]
        self.conanfile.deps_cpp_info.add(ref.name, cpp_info)

    def test_cmake(self):
        generator = CMakeGenerator(self.conanfile)
        content = generator.content
        self.assertIn('set(CONAN_BUILD_MODULES_PATHS "dummy_root_folder1/my-module.cmake"'
                      '\n\t\t\t"dummy_root_folder2/other-mod.cmake"'
                      '\n\t\t\t"dummy_root_folder2/not-a-cmake-module.pc" '
                      '${CONAN_BUILD_MODULES_PATHS})',
                      content)
        self.assertIn('set(CONAN_BUILD_MODULES_PATHS_MY_PKG "dummy_root_folder1/my-module.cmake")',
                      content)
        self.assertIn('set(CONAN_BUILD_MODULES_PATHS_MY_PKG2 "dummy_root_folder2/other-mod.cmake"'
                      '\n\t\t\t"dummy_root_folder2/not-a-cmake-module.pc")',
                      content)
        self.assertIn("macro(conan_include_build_modules)", content)
        self.assertIn("conan_include_build_modules()", content)
