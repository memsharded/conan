import os
import platform
import textwrap

import pytest

from conans.client.tools import replace_in_file
from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.genconanfile import GenConanfile

from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID


@pytest.fixture
def client():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conans.tools import save
        import os
        class Pkg(ConanFile):
            settings = "build_type", "os", "arch", "compiler"
            {}
            def package(self):
                save(os.path.join(self.package_folder, "include", "%s.h" % self.name),
                     '#define MYVAR%s "%s"' % (self.name, self.settings.build_type))
        """)

    c.save({"conanfile.py": conanfile.format("")})
    c.run("create . liba/0.1@ -s build_type=Release")
    c.run("create . liba/0.1@ -s build_type=Debug")
    c.save({"conanfile.py": conanfile.format("requires = 'liba/0.1'")})
    c.run("create . libb/0.1@ -s build_type=Release")
    c.run("create . libb/0.1@ -s build_type=Debug")
    return c


@pytest.mark.tool_cmake
def test_transitive_multi(client):
    # TODO: Make a full linking example, with correct header transitivity

    # Save conanfile and example
    conanfile = textwrap.dedent("""
        [requires]
        libb/0.1

        [generators]
        CMakeDeps
        CMakeToolchain
        """)
    example_cpp = gen_function_cpp(name="main", includes=["libb", "liba"],
                                   preprocessor=["MYVARliba", "MYVARlibb"])
    client.save({"conanfile.txt": conanfile,
                 "CMakeLists.txt": gen_cmakelists(appname="example",
                                                  appsources=["example.cpp"], find_package=["libb"]),
                 "example.cpp": example_cpp}, clean_first=True)

    with client.chdir("build"):
        for bt in ("Debug", "Release"):
            client.run("install .. user/channel -s build_type={}".format(bt))

        # Test that we are using find_dependency with the NO_MODULE option
        # to skip finding first possible FindBye somewhere
        assert "find_dependency(${_DEPENDENCY} REQUIRED NO_MODULE)" \
               in client.load("libb-config.cmake")

        if platform.system() == "Windows":
            client.run_command('cmake .. -DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake')
            client.run_command('cmake --build . --config Debug')
            client.run_command('cmake --build . --config Release')

            client.run_command('Debug\\example.exe')
            assert "main: Debug!" in client.out
            assert "MYVARliba: Debug" in client.out
            assert "MYVARlibb: Debug" in client.out

            client.run_command('Release\\example.exe')
            assert "main: Release!" in client.out
            assert "MYVARliba: Release" in client.out
            assert "MYVARlibb: Release" in client.out
        else:
            # The TOOLCHAIN IS MESSING WITH THE BUILD TYPE and then ignores the -D so I remove it
            replace_in_file(os.path.join(client.current_folder, "conan_toolchain.cmake"),
                            "CMAKE_BUILD_TYPE", "DONT_MESS_WITH_BUILD_TYPE")
            for bt in ("Debug", "Release"):
                client.run_command('cmake .. -DCMAKE_BUILD_TYPE={} '
                                   '-DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake'.format(bt))
                client.run_command('cmake --build . --clean-first')

                client.run_command('./example')
                assert "main: {}!".format(bt) in client.out
                assert "MYVARliba: {}".format(bt) in client.out
                assert "MYVARlibb: {}".format(bt) in client.out


@pytest.mark.tool_cmake
def test_system_libs():
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conans.tools import save
        import os

        class Test(ConanFile):
            name = "Test"
            version = "0.1"
            settings = "build_type"
            def package(self):
                save(os.path.join(self.package_folder, "lib/lib1.lib"), "")
                save(os.path.join(self.package_folder, "lib/liblib1.a"), "")

            def package_info(self):
                self.cpp_info.libs = ["lib1"]
                if self.settings.build_type == "Debug":
                    self.cpp_info.system_libs.append("sys1d")
                else:
                    self.cpp_info.system_libs.append("sys1")
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create . -s build_type=Release")
    client.run("create . -s build_type=Debug")

    conanfile = textwrap.dedent("""
        [requires]
        Test/0.1

        [generators]
        CMakeDeps
        """)
    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(consumer NONE)
        set(CMAKE_PREFIX_PATH ${CMAKE_BINARY_DIR})
        set(CMAKE_MODULE_PATH ${CMAKE_BINARY_DIR})
        find_package(Test)
        message("System libs release: ${Test_SYSTEM_LIBS_RELEASE}")
        message("Libraries to Link release: ${Test_LIBS_RELEASE}")
        message("System libs debug: ${Test_SYSTEM_LIBS_DEBUG}")
        message("Libraries to Link debug: ${Test_LIBS_DEBUG}")
        get_target_property(tmp Test::Test INTERFACE_LINK_LIBRARIES)
        message("Target libs: ${tmp}")
        """)

    for build_type in ["Release", "Debug"]:
        client.save({"conanfile.txt": conanfile, "CMakeLists.txt": cmakelists}, clean_first=True)
        client.run("install conanfile.txt -s build_type=%s" % build_type)
        client.run_command('cmake . -DCMAKE_BUILD_TYPE={0}'.format(build_type))

        library_name = "sys1d" if build_type == "Debug" else "sys1"
        # FIXME: Note it is CONAN_LIB::Test_lib1_RELEASE, not "lib1" as cmake_find_package
        if build_type == "Release":
            assert "System libs release: %s" % library_name in client.out
            assert "Libraries to Link release: lib1" in client.out
            target_libs = ("$<$<CONFIG:Release>:CONAN_LIB::Test_lib1_RELEASE;sys1;"
                           "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                           "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                           "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>;>")
        else:
            assert "System libs debug: %s" % library_name in client.out
            assert "Libraries to Link debug: lib1" in client.out
            target_libs = ("$<$<CONFIG:Debug>:CONAN_LIB::Test_lib1_DEBUG;sys1d;"
                           "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                           "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                           "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>;>")
        assert "Target libs: %s" % target_libs in client.out


@pytest.mark.tool_cmake
def test_do_not_mix_cflags_cxxflags():
    # TODO: Verify with components too
    client = TestClient()
    cpp_info = {"cflags": ["one", "two"], "cxxflags": ["three", "four"]}
    client.save({"conanfile.py": GenConanfile("upstream", "1.0").with_package_info(cpp_info=cpp_info,
                                                                                   env_info={})})
    client.run("create .")

    consumer_conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake

        class Consumer(ConanFile):
            name = "consumer"
            version = "1.0"
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "CMakeLists.txt"
            requires = "upstream/1.0"
            generators = "CMakeDeps", "CMakeToolchain"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
        """)
    cmakelists = textwrap.dedent("""
       cmake_minimum_required(VERSION 3.15)
       project(consumer NONE)
       find_package(upstream CONFIG REQUIRED)
       get_target_property(tmp upstream::upstream INTERFACE_COMPILE_OPTIONS)
       message("compile options: ${tmp}")
       message("cflags: ${upstream_COMPILE_OPTIONS_C_RELEASE}")
       message("cxxflags: ${upstream_COMPILE_OPTIONS_CXX_RELEASE}")
       """)
    client.save({"conanfile.py": consumer_conanfile,
                 "CMakeLists.txt": cmakelists}, clean_first=True)
    client.run("create .")
    assert "compile options: $<$<CONFIG:Release>:" \
           "$<$<COMPILE_LANGUAGE:CXX>:three;four>;$<$<COMPILE_LANGUAGE:C>:one;two>>" in client.out
    assert "cflags: one;two" in client.out
    assert "cxxflags: three;four" in client.out


def test_custom_configuration(client):
    """  The configuration may differ from the build context and the host context"""
    conanfile = textwrap.dedent("""
       from conans import ConanFile
       from conan.tools.cmake import CMakeDeps

       class Consumer(ConanFile):
           name = "consumer"
           version = "1.0"
           settings = "os", "compiler", "arch", "build_type"
           requires = "liba/0.1"
           build_requires = "liba/0.1"
           generators = "CMakeToolchain"

           def generate(self):
               cmake = CMakeDeps(self)
               cmake.configuration = "Debug"
               cmake.build_context_activated = ["liba"]
               cmake.build_context_suffix["liba"] = "_build"
               cmake.generate()
       """)

    client.save({"conanfile.py": conanfile})
    client.run("install . -pr:h default -s:b build_type=RelWithDebInfo"
               " -pr:b default -s:b arch=x86 --build missing")
    curdir = client.current_folder
    data_name_context_build = "liba_build-relwithdebinfo-x86-data.cmake"
    data_name_context_host = "liba-debug-x86_64-data.cmake"
    assert os.path.exists(os.path.join(curdir, data_name_context_build))
    assert os.path.exists(os.path.join(curdir, data_name_context_host))

    assert "set(liba_build_INCLUDE_DIRS_RELWITHDEBINFO" in \
           open(os.path.join(curdir, data_name_context_build)).read()
    assert "set(liba_INCLUDE_DIRS_DEBUG" in \
           open(os.path.join(curdir, data_name_context_host)).read()


def test_buildirs_working():
    """  If a recipe declares cppinfo.buildirs those dirs will be exposed to be consumer
    to allow a cmake "include" function call after a find_package"""
    c = TestClient()
    conanfile = str(GenConanfile().with_name("my_lib").with_version("1.0")
                                  .with_import("import os").with_import("from conans import tools"))
    conanfile += """
    def package(self):
        tools.save(os.path.join(self.package_folder, "my_build_dir", "my_cmake_script.cmake"),
                   'set(MYVAR "Like a Rolling Stone")')

    def package_info(self):
        self.cpp_info.builddirs=["my_build_dir"]
    """

    c.save({"conanfile.py": conanfile})
    c.run("create .")

    consumer_conanfile = GenConanfile().with_name("consumer").with_version("1.0")\
        .with_cmake_build().with_require("my_lib/1.0") \
        .with_settings("os", "arch", "build_type", "compiler") \
        .with_exports_sources("*.txt")
    cmake = gen_cmakelists(find_package=["my_lib"])
    cmake += """
    message("CMAKE_MODULE_PATH: ${CMAKE_MODULE_PATH}")
    include("my_cmake_script")
    message("MYVAR=>${MYVAR}")
    """
    c.save({"conanfile.py": consumer_conanfile, "CMakeLists.txt": cmake})
    c.run("create .")
    assert "MYVAR=>Like a Rolling Stone" in c.out


@pytest.mark.tool_cmake
def test_cpp_info_link_objects():
    client = TestClient()
    obj_ext = "obj" if platform.system() == "Windows" else "o"
    cpp_info = {"objects": [os.path.join("lib", "myobject.{}".format(obj_ext))]}
    object_cpp = gen_function_cpp(name="myobject")
    object_h = gen_function_h(name="myobject")
    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(MyObject)
        file(GLOB HEADERS *.h)
        add_library(myobject OBJECT myobject.cpp)
        if( WIN32 )
            set(OBJ_PATH "myobject.dir/Release/myobject${CMAKE_C_OUTPUT_EXTENSION}")
        else()
            set(OBJ_PATH "CMakeFiles/myobject.dir/myobject.cpp${CMAKE_C_OUTPUT_EXTENSION}")
        endif()
        install(FILES ${CMAKE_CURRENT_BINARY_DIR}/${OBJ_PATH}
                DESTINATION ${CMAKE_INSTALL_PREFIX}/lib
                RENAME myobject${CMAKE_C_OUTPUT_EXTENSION})
        install(FILES ${HEADERS}
                DESTINATION ${CMAKE_INSTALL_PREFIX}/include)
    """)

    test_package_cpp = gen_function_cpp(name="main", includes=["myobject"], calls=["myobject"])
    test_package_cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(example)
        find_package(myobject REQUIRED)
        add_executable(example example.cpp)
        target_link_libraries(example myobject::myobject)
    """)

    client.save({"CMakeLists.txt": cmakelists,
                 "conanfile.py": GenConanfile("myobject", "1.0").with_package_info(cpp_info=cpp_info,
                                                                                   env_info={})
                                                                .with_exports_sources("*")
                                                                .with_cmake_build()
                                                                .with_package("cmake = CMake(self)",
                                                                              "cmake.install()"),
                 "myobject.cpp": object_cpp,
                 "myobject.h": object_h,
                 "test_package/conanfile.py": GenConanfile().with_cmake_build()
                                                            .with_import("import os")
                                                            .with_test('path = "{}".format(self.settings.build_type) '
                                                                       'if self.settings.os == "Windows" else "."')
                                                            .with_test('self.run("{}{}example".format(path, os.sep))'),
                 "test_package/example.cpp": test_package_cpp,
                 "test_package/CMakeLists.txt": test_package_cmakelists})

    client.run("create . -s build_type=Release")
    assert "myobject: Release!" in client.out


def test_private_transitive():
    # https://github.com/conan-io/conan/issues/9514
    client = TestClient()
    client.save({"dep/conanfile.py": GenConanfile(),
                 "pkg/conanfile.py": GenConanfile().with_requirement("dep/0.1", visible=False),
                 "consumer/conanfile.py": GenConanfile().with_requires("pkg/0.1")
                                                        .with_settings("os", "build_type", "arch")})
    client.run("create dep dep/0.1@")
    client.run("create pkg pkg/0.1@")
    client.run("install consumer -g CMakeDeps -s arch=x86_64 -s build_type=Release")
    assert f"dep/0.1:{NO_SETTINGS_PACKAGE_ID} - Skip" in client.out
    data_cmake = client.load("pkg-release-x86_64-data.cmake")
    assert "set(pkg_FIND_DEPENDENCY_NAMES ${pkg_FIND_DEPENDENCY_NAMES} )" in data_cmake
