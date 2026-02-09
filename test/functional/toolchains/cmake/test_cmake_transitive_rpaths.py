import platform
import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Linux",
                    reason="Linux/gcc required for -rpath/-rpath-link testing")
@pytest.mark.tool("cmake", "3.27")
def test_cmake_transitive_rpath_private_internal():
    c = TestClient(path_with_spaces=False)

    foo_h = textwrap.dedent("""
            #pragma once
            int foo(int x, int y);
        """)
    foo_cpp = textwrap.dedent("""
            #include "foo.h"
            int foo(int x, int y) {
                return x + y;
            }
        """)
    bar_h = textwrap.dedent("""
            #pragma once
            int bar(int x, int y);
        """)
    bar_cpp = textwrap.dedent("""
            #include "bar.h"
            #include "foo.h"
            int bar(int x, int y) {
                return foo(x, y) * 2;
            }
        """)

    foobar_cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 4.2)
        project(foobar CXX)

        add_library(foo src/foo.cpp)
        target_include_directories(foo PUBLIC include)
        set_target_properties(foo PROPERTIES PUBLIC_HEADER "include/foo.h")

        add_library(bar src/bar.cpp)
        target_include_directories(bar PUBLIC include)
        set_target_properties(bar PROPERTIES PUBLIC_HEADER "include/bar.h")
        target_link_libraries(bar PRIVATE foo)

        install(TARGETS foo bar)
        """)

    foobar_conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout


        class foobarRecipe(ConanFile):
            name = "foobar"
            version = "1.0"
            package_type = "library"
            settings = "os", "compiler", "build_type", "arch"
            options = {"shared": [True, False]}
            default_options = {"shared": True}

            exports_sources = "CMakeLists.txt", "src/*", "include/*"

            generators = "CMakeDeps", "CMakeToolchain"

            def layout(self):
                cmake_layout(self)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                cmake = CMake(self)
                cmake.install()

            def package_info(self):
                self.cpp_info.default_components = ["bar"]
                self.cpp_info.components["foo"].libs = ["foo"]
                self.cpp_info.components["bar"].libs = ["bar"]
                self.cpp_info.components["bar"].requires = ["foo"]
        """)

    consumer_conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout

        class consumerRecipe(ConanFile):
            name = "consumer"
            version = "1.0"
            package_type = "library"
            settings = "os", "compiler", "build_type", "arch"
            options = {"shared": [True, False]}
            default_options = {"shared": True}
            generators = "CMakeConfigDeps", "CMakeToolchain"
            exports_sources = "CMakeLists.txt", "src/*", "include/*"

            def layout(self):
                cmake_layout(self)

            def requirements(self):
                self.requires("foobar/1.0")

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                cmake = CMake(self)
                cmake.install()

            def package_info(self):
                self.cpp_info.libs = ["consumer"]
        """)

    consumer_cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 4.2)
        project(consumer CXX)

        find_package(foobar CONFIG REQUIRED)

        add_library(consumer src/consumer.cpp)
        target_include_directories(consumer PUBLIC include)
        target_link_libraries(consumer PRIVATE foobar::foobar) # foobar_LIBRARIES is foobar::foobar
        set_target_properties(consumer PROPERTIES PUBLIC_HEADER "include/consumer.h")
        install(TARGETS consumer)

        add_executable(my_app src/my_app.cpp)
        target_link_libraries(my_app PRIVATE consumer)
        """)

    consumer_cpp = textwrap.dedent("""
        #include "consumer.h"
        #include "bar.h"
        int consumer(int x, int y) {return bar(x, y) * 2;}
        """)

    consumer_h = textwrap.dedent("""
        #pragma once
        int consumer(int x, int y);
        """)

    my_app_cpp = textwrap.dedent("""
        #include "consumer.h"
        int main() { return consumer(2, 3) == 20 ? 0 : 1; }
        """)

    extra_conf = "-c tools.compilation:verbosity=verbose"
    # extra_conf += " -c tools.build:add_rpath_link=True"  # removing this should break the test

    with c.chdir("foobar"):
        c.save({"include/foo.h": foo_h,
                "include/bar.h": bar_h,
                "src/foo.cpp": foo_cpp,
                "src/bar.cpp": bar_cpp,
                "CMakeLists.txt": foobar_cmakelists,
                "conanfile.py": foobar_conanfile})
        c.run(f"create . {extra_conf} ")

    with c.chdir("consumer"):
        c.save({"src/consumer.cpp": consumer_cpp,
                "include/consumer.h": consumer_h,
                "src/my_app.cpp": my_app_cpp,
                "CMakeLists.txt": consumer_cmakelists,
                "conanfile.py": consumer_conanfile})
        c.run(f"build . {extra_conf}")


@pytest.mark.skipif(platform.system() != "Linux",
                    reason="Linux/gcc required for -rpath/-rpath-link testing")
@pytest.mark.tool("cmake", "3.27")
def test_cmake_transitive_rpath_private_inpkg():
    c = TestClient(path_with_spaces=False)

    foo_h = textwrap.dedent("""
            #pragma once
            int foo(int x, int y);
        """)
    foo_cpp = textwrap.dedent("""
            #include "foo.h"
            int foo(int x, int y) {
                return x + y;
            }
        """)
    bar_h = textwrap.dedent("""
            #pragma once
            int bar(int x, int y);
        """)
    bar_cpp = textwrap.dedent("""
            #include "bar.h"
            #include "foo.h"
            int bar(int x, int y) {
                return foo(x, y) * 2;
            }
        """)

    foobar_cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 4.2)
        project(foobar CXX)

        add_library(foo src/foo.cpp)
        target_include_directories(foo PUBLIC
          $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
          $<INSTALL_INTERFACE:include>
        )
        set_target_properties(foo PROPERTIES PUBLIC_HEADER "include/foo.h")

        add_library(bar src/bar.cpp)
        target_include_directories(bar PUBLIC
          $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
          $<INSTALL_INTERFACE:include>
        )
        set_target_properties(bar PROPERTIES PUBLIC_HEADER "include/bar.h")
        target_link_libraries(bar PRIVATE foo)

        add_library(foobar INTERFACE)
        target_link_libraries(foobar INTERFACE bar foo)

        install(TARGETS foo bar foobar EXPORT foobarConfig)
        export(TARGETS foo bar foobar
            NAMESPACE foobar::
            FILE "${CMAKE_CURRENT_BINARY_DIR}/foobarConfig.cmake"
        )
        install(EXPORT foobarConfig
            DESTINATION "foobar/cmake"
            NAMESPACE foobar::
        )
        """)

    foobar_conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout


        class foobarRecipe(ConanFile):
            name = "foobar"
            version = "1.0"
            package_type = "library"
            settings = "os", "compiler", "build_type", "arch"
            options = {"shared": [True, False]}
            default_options = {"shared": True}

            exports_sources = "CMakeLists.txt", "src/*", "include/*"

            generators = "CMakeDeps", "CMakeToolchain"

            def layout(self):
                cmake_layout(self)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                cmake = CMake(self)
                cmake.install()

            def package_info(self):
                self.cpp_info.set_property("cmake_find_mode", "none")
                self.cpp_info.builddirs = ["foobar/cmake"]

        """)

    consumer_conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout

        class consumerRecipe(ConanFile):
            name = "consumer"
            version = "1.0"
            package_type = "library"
            settings = "os", "compiler", "build_type", "arch"
            options = {"shared": [True, False]}
            default_options = {"shared": True}
            generators = "CMakeConfigDeps", "CMakeToolchain"
            exports_sources = "CMakeLists.txt", "src/*", "include/*"

            def layout(self):
                cmake_layout(self)

            def requirements(self):
                self.requires("foobar/1.0")

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                cmake = CMake(self)
                cmake.install()

            def package_info(self):
                self.cpp_info.libs = ["consumer"]
        """)

    consumer_cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 4.2)
        project(consumer CXX)

        find_package(foobar CONFIG REQUIRED)

        add_library(consumer src/consumer.cpp)
        target_include_directories(consumer PUBLIC include)
        target_link_libraries(consumer PUBLIC foobar::foobar) # foobar_LIBRARIES is foobar::foobar
        set_target_properties(consumer PROPERTIES PUBLIC_HEADER "include/consumer.h")
        install(TARGETS consumer)

        add_executable(my_app src/my_app.cpp)
        target_link_libraries(my_app PRIVATE consumer)
        """)

    consumer_cpp = textwrap.dedent("""
        #include "consumer.h"
        #include "bar.h"
        int consumer(int x, int y) {return bar(x, y) * 2;}
        """)

    consumer_h = textwrap.dedent("""
        #pragma once
        int consumer(int x, int y);
        """)

    my_app_cpp = textwrap.dedent("""
        #include "consumer.h"
        int main() { return consumer(2, 3) == 20 ? 0 : 1; }
        """)

    extra_conf = "-c tools.compilation:verbosity=verbose"
    # extra_conf += " -c tools.build:add_rpath_link=True"  # removing this should break the test

    with c.chdir("foobar"):
        c.save({"include/foo.h": foo_h,
                "include/bar.h": bar_h,
                "src/foo.cpp": foo_cpp,
                "src/bar.cpp": bar_cpp,
                "CMakeLists.txt": foobar_cmakelists,
                "conanfile.py": foobar_conanfile})
        c.run(f"create . {extra_conf} ")
        print(c.out)

    with c.chdir("consumer"):
        c.save({"src/consumer.cpp": consumer_cpp,
                "include/consumer.h": consumer_h,
                "src/my_app.cpp": my_app_cpp,
                "CMakeLists.txt": consumer_cmakelists,
                "conanfile.py": consumer_conanfile})
        c.run(f"build . {extra_conf}")
