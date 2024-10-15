import platform
import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.tool("cmake")
class TestExes:
    def test_exe(self):
        conanfile = textwrap.dedent(r"""
            import os
            from conan import ConanFile
            from conan.tools.cmake import CMake

            class Test(ConanFile):
                name = "mytool"
                version = "0.1"
                package_type = "application"
                settings = "os", "arch", "compiler", "build_type"
                generators = "CMakeToolchain"
                exports_sources = "*"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()

                def package(self):
                    cmake = CMake(self)
                    cmake.install()

                def package_info(self):
                    self.cpp_info.exe = "mytool"
                    self.cpp_info.set_property("cmake_target_name", "MyTool::myexe")
                    self.cpp_info.location = os.path.join("bin", "mytool")
            """)
        main = textwrap.dedent("""
            #include <iostream>
            #include <fstream>

            int main() {
                std::cout << "Mytool generating out.c!!!!!" << std::endl;
                std::ofstream f("out.c");
            }
            """)
        c = TestClient()
        c.run("new cmake_exe -d name=mytool -d version=0.1")
        c.save({"conanfile.py": conanfile,
                "src/main.cpp": main})
        c.run("create .")

        consumer = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import CMakeDeps, CMakeToolchain, CMake, cmake_layout
            class Consumer(ConanFile):
                settings = "os", "compiler", "arch", "build_type"
                tool_requires = "mytool/0.1"

                def generate(self):
                    deps = CMakeDeps(self)
                    deps.generate()
                    tc = CMakeToolchain(self)
                    tc.generate()

                def layout(self):
                    cmake_layout(self)
                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()
            """)
        cmake = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            project(consumer C)

            find_package(mytool)
            add_custom_command(OUTPUT out.c COMMAND MyTool::myexe)
            add_library(myLib out.c)
            """)
        c.save({"conanfile.py": consumer,
                "CMakeLists.txt": cmake}, clean_first=True)
        c.run("build . -c tools.cmake.cmakedeps:new=will_break_next")
        assert "Conan: Target declared imported executable 'MyTool::myexe'" in c.out
        assert "Mytool generating out.c!!!!!" in c.out

    def test_exe_components(self):
        conanfile = textwrap.dedent(r"""
            import os
            from conan import ConanFile
            from conan.tools.cmake import CMake

            class Test(ConanFile):
                name = "mytool"
                version = "0.1"
                package_type = "application"
                settings = "os", "arch", "compiler", "build_type"
                generators = "CMakeToolchain"
                exports_sources = "*"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()

                def package(self):
                    cmake = CMake(self)
                    cmake.install()

                def package_info(self):
                    self.cpp_info.components["my1exe"].exe = "mytool1"
                    self.cpp_info.components["my1exe"].set_property("cmake_target_name", "MyTool::my1exe")
                    self.cpp_info.components["my1exe"].location = os.path.join("bin", "mytool1")
                    self.cpp_info.components["my2exe"].exe = "mytool2"
                    self.cpp_info.components["my2exe"].set_property("cmake_target_name", "MyTool::my2exe")
                    self.cpp_info.components["my2exe"].location = os.path.join("bin", "mytool2")
            """)
        main = textwrap.dedent("""
            #include <iostream>
            #include <fstream>

            int main() {{
                std::cout << "Mytool{number} generating out{number}.c!!!!!" << std::endl;
                std::ofstream f("out{number}.c");
            }}
            """)
        cmake = textwrap.dedent("""
            set(CMAKE_CXX_COMPILER_WORKS 1)
            set(CMAKE_CXX_ABI_COMPILED 1)
            cmake_minimum_required(VERSION 3.15)
            project(proj CXX)

            add_executable(mytool1 src/main1.cpp)
            add_executable(mytool2 src/main2.cpp)

            install(TARGETS mytool1 DESTINATION "." RUNTIME DESTINATION bin)
            install(TARGETS mytool2 DESTINATION "." RUNTIME DESTINATION bin)
            """)
        c = TestClient()
        c.save({"conanfile.py": conanfile,
                "CMakeLists.txt": cmake,
                "src/main1.cpp": main.format(number=1),
                "src/main2.cpp": main.format(number=2)
                })
        c.run("create .")

        consumer = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import CMakeDeps, CMakeToolchain, CMake, cmake_layout
            class Consumer(ConanFile):
                settings = "os", "compiler", "arch", "build_type"
                tool_requires = "mytool/0.1"

                def generate(self):
                    deps = CMakeDeps(self)
                    deps.generate()
                    tc = CMakeToolchain(self)
                    tc.generate()
                def layout(self):
                    cmake_layout(self)
                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()
            """)
        cmake = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            project(consumer C)

            find_package(mytool)
            add_custom_command(OUTPUT out1.c COMMAND MyTool::my1exe)
            add_custom_command(OUTPUT out2.c COMMAND MyTool::my2exe)
            add_library(myLib out1.c out2.c)
            """)
        c.save({"conanfile.py": consumer,
                "CMakeLists.txt": cmake}, clean_first=True)
        c.run("build . -c tools.cmake.cmakedeps:new=will_break_next")
        assert "Conan: Target declared imported executable 'MyTool::my1exe'" in c.out
        assert "Mytool1 generating out1.c!!!!!" in c.out
        assert "Conan: Target declared imported executable 'MyTool::my2exe'" in c.out
        assert "Mytool2 generating out2.c!!!!!" in c.out


@pytest.mark.tool("cmake")
class TestLibs:
    def test_libs(self, matrix_client):
        c = matrix_client
        c.run("new cmake_lib -d name=app -d version=0.1 -d requires=matrix/1.0")
        c.run("build . -c tools.cmake.cmakedeps:new=will_break_next")
        assert "Conan: Target declared imported STATIC library 'matrix::matrix'" in c.out

    @pytest.mark.parametrize("shared", [False, True])
    def test_libs_transitive(self, transitive_libraries, shared):
        c = transitive_libraries
        c.run("new cmake_lib -d name=app -d version=0.1 -d requires=engine/1.0")
        shared = "-o engine/*:shared=True" if shared else ""
        c.run(f"build . {shared} -c tools.cmake.cmakedeps:new=will_break_next")
        if shared:
            assert "matrix::matrix" not in c.out  # It is hidden as static behind the engine
            assert "Conan: Target declared imported SHARED library 'engine::engine'" in c.out
        else:
            assert "Conan: Target declared imported STATIC library 'matrix::matrix'" in c.out
            assert "Conan: Target declared imported STATIC library 'engine::engine'" in c.out

    def test_multilevel_shared(self):
        # TODO: make this shared fixtures in conftest for multi-level shared testing
        c = TestClient(default_server_user=True)
        c.run("new cmake_lib -d name=matrix -d version=0.1")
        c.run("create . -o *:shared=True -c tools.cmake.cmakedeps:new=will_break_next")

        c.save({}, clean_first=True)
        c.run("new cmake_lib -d name=engine -d version=0.1 -d requires=matrix/0.1")
        c.run("create . -o *:shared=True -c tools.cmake.cmakedeps:new=will_break_next")

        c.save({}, clean_first=True)
        c.run("new cmake_lib -d name=gamelib -d version=0.1 -d requires=engine/0.1")
        c.run("create . -o *:shared=True -c tools.cmake.cmakedeps:new=will_break_next")

        c.save({}, clean_first=True)
        c.run("new cmake_exe -d name=game -d version=0.1 -d requires=gamelib/0.1")
        c.run("create . -o *:shared=True -c tools.cmake.cmakedeps:new=will_break_next")

        assert "matrix/0.1: Hello World Release!"
        assert "engine/0.1: Hello World Release!"
        assert "gamelib/0.1: Hello World Release!"
        assert "game/0.1: Hello World Release!"

        # Make sure it works downloading to another cache
        c.run("upload * -r=default -c")
        c.run("remove * -c")

        c2 = TestClient(servers=c.servers)
        c2.run("new cmake_exe -d name=game -d version=0.1 -d requires=gamelib/0.1")
        c2.run("create . -o *:shared=True -c tools.cmake.cmakedeps:new=will_break_next")

        assert "matrix/0.1: Hello World Release!"
        assert "engine/0.1: Hello World Release!"
        assert "gamelib/0.1: Hello World Release!"
        assert "game/0.1: Hello World Release!"

    def test_libs_components(self, matrix_client_components):
        """
        explicit usage of components
        """
        c = matrix_client_components

        # TODO: Check that find_package(.. COMPONENTS nonexisting) fails
        c.run("new cmake_exe -d name=app -d version=0.1 -d requires=matrix/1.0")
        cmake = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            project(app CXX)

            find_package(matrix CONFIG REQUIRED)
            add_executable(app src/app.cpp)
            # standard one, and a custom cmake_target_name one
            target_link_libraries(app PRIVATE matrix::module MatrixHeaders)
            """)
        app_cpp = textwrap.dedent("""
            #include "module.h"
            #include "headers.h"
            int main() { module(); headers();}
            """)
        c.save({"CMakeLists.txt": cmake,
                "src/app.cpp": app_cpp})
        c.run("build . -c tools.cmake.cmakedeps:new=will_break_next")
        assert "Conan: Target declared imported STATIC library 'matrix::vector'" in c.out
        assert "Conan: Target declared imported STATIC library 'matrix::module'" in c.out
        if platform.system() == "Windows":
            c.run_command(r".\build\Release\app.exe")
            assert "Matrix headers __cplusplus: __cplusplus2014" in c.out

    def test_libs_components_default(self, matrix_client_components):
        """
        Test that the default components are used when no component is specified
        """
        c = matrix_client_components

        c.run("new cmake_exe -d name=app -d version=0.1 -d requires=matrix/1.0")

        app_cpp = textwrap.dedent("""
            #include "module.h"
            int main() { module();}
            """)
        cmake = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            project(app CXX)

            find_package(matrix CONFIG REQUIRED)
            add_executable(app src/app.cpp)
            target_link_libraries(app PRIVATE matrix::matrix)
            """)
        c.save({"src/app.cpp": app_cpp,
                "CMakeLists.txt": cmake})
        c.run("build . -c tools.cmake.cmakedeps:new=will_break_next")
        assert "Conan: Target declared imported STATIC library 'matrix::vector'" in c.out
        assert "Conan: Target declared imported STATIC library 'matrix::module'" in c.out
        assert "Conan: Target declared imported INTERFACE library 'MatrixHeaders'" in c.out

    def test_libs_components_default_error(self, matrix_client_components):
        """
        Same as above, but it fails, because headers is not in the default components
        """
        c = matrix_client_components

        c.run("new cmake_exe -d name=app -d version=0.1 -d requires=matrix/1.0")

        app_cpp = textwrap.dedent("""
            #include "module.h"
            #include "headers.h"
            int main() { module();}
            """)
        cmake = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            project(app CXX)

            find_package(matrix CONFIG REQUIRED)
            add_executable(app src/app.cpp)
            target_link_libraries(app PRIVATE matrix::matrix)
            """)
        c.save({"src/app.cpp": app_cpp,
                "CMakeLists.txt": cmake})
        c.run("build . -c tools.cmake.cmakedeps:new=will_break_next", assert_error=True)
        assert "Error in build() method, line 35" in c.out
        assert "Conan: Target declared imported STATIC library 'matrix::vector'" in c.out
        assert "Conan: Target declared imported STATIC library 'matrix::module'" in c.out
        cmake = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            project(app CXX)

            find_package(matrix CONFIG REQUIRED)
            add_executable(app src/app.cpp)
            target_link_libraries(app PRIVATE matrix::matrix MatrixHeaders)
            """)
        c.save({"CMakeLists.txt": cmake})
        c.run("build . -c tools.cmake.cmakedeps:new=will_break_next")
        assert "Running CMake.build()" in c.out  # Now it doesn't fail

    def test_libs_components_transitive(self, matrix_client_components):
        """
        explicit usage of components
        matrix::module -> matrix::vector

        engine::bots -> engine::physix
        engine::physix -> matrix::vector
        engine::world -> engine::physix, matrix::module
        """
        c = matrix_client_components

        from conan.test.assets.sources import gen_function_h
        bots_h = gen_function_h(name="bots")
        from conan.test.assets.sources import gen_function_cpp
        bots_cpp = gen_function_cpp(name="bots", includes=["bots", "physix"], calls=["physix"])
        physix_h = gen_function_h(name="physix")
        physix_cpp = gen_function_cpp(name="physix", includes=["physix", "vector"], calls=["vector"])
        world_h = gen_function_h(name="world")
        world_cpp = gen_function_cpp(name="world", includes=["world", "physix", "module"],
                                     calls=["physix", "module"])

        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import CMake
            from conan.tools.files import copy

            class Engine(ConanFile):
              name = "engine"
              version = "1.0"
              settings = "os", "compiler", "build_type", "arch"
              generators = "CMakeToolchain"
              exports_sources = "src/*", "CMakeLists.txt"

              requires = "matrix/1.0"
              generators = "CMakeDeps", "CMakeToolchain"

              def build(self):
                  cmake = CMake(self)
                  cmake.configure()
                  cmake.build()

              def package(self):
                  cmake = CMake(self)
                  cmake.install()

              def package_info(self):
                  self.cpp_info.components["bots"].libs = ["bots"]
                  self.cpp_info.components["bots"].includedirs = ["include"]
                  self.cpp_info.components["bots"].libdirs = ["lib"]
                  self.cpp_info.components["bots"].requires = ["physix"]

                  self.cpp_info.components["physix"].libs = ["physix"]
                  self.cpp_info.components["physix"].includedirs = ["include"]
                  self.cpp_info.components["physix"].libdirs = ["lib"]
                  self.cpp_info.components["physix"].requires = ["matrix::vector"]

                  self.cpp_info.components["world"].libs = ["world"]
                  self.cpp_info.components["world"].includedirs = ["include"]
                  self.cpp_info.components["world"].libdirs = ["lib"]
                  self.cpp_info.components["world"].requires = ["physix", "matrix::module"]
                  """)

        cmakelists = textwrap.dedent("""
               set(CMAKE_CXX_COMPILER_WORKS 1)
               set(CMAKE_CXX_ABI_COMPILED 1)
               cmake_minimum_required(VERSION 3.15)
               project(matrix CXX)

               find_package(matrix CONFIG REQUIRED)

               add_library(physix src/physix.cpp)
               add_library(bots src/bots.cpp)
               add_library(world src/world.cpp)

               target_link_libraries(physix PRIVATE matrix::vector)
               target_link_libraries(bots PRIVATE physix)
               target_link_libraries(world PRIVATE physix matrix::module)

               set_target_properties(bots PROPERTIES PUBLIC_HEADER "src/bots.h")
               set_target_properties(physix PROPERTIES PUBLIC_HEADER "src/physix.h")
               set_target_properties(world PROPERTIES PUBLIC_HEADER "src/world.h")
               install(TARGETS physix bots world)
               """)
        c.save({"src/physix.h": physix_h,
                "src/physix.cpp": physix_cpp,
                "src/bots.h": bots_h,
                "src/bots.cpp": bots_cpp,
                "src/world.h": world_h,
                "src/world.cpp": world_cpp,
                "CMakeLists.txt": cmakelists,
                "conanfile.py": conanfile})
        c.run("create .")

        c.save({}, clean_first=True)
        c.run("new cmake_exe -d name=app -d version=0.1 -d requires=engine/1.0")
        cmake = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            project(app CXX)

            find_package(engine CONFIG REQUIRED)

            add_executable(app src/app.cpp)
            target_link_libraries(app PRIVATE engine::bots)

            install(TARGETS app)
            """)
        app_cpp = textwrap.dedent("""
            #include "bots.h"
            int main() { bots();}
            """)
        c.save({"CMakeLists.txt": cmake,
                "src/app.cpp": app_cpp})
        c.run("create . -c tools.cmake.cmakedeps:new=will_break_next")
        assert "Conan: Target declared imported STATIC library 'matrix::vector'" in c.out
        assert "Conan: Target declared imported STATIC library 'matrix::module'" in c.out
        assert "Conan: Target declared imported INTERFACE library 'matrix::matrix'" in c.out
        assert "Conan: Target declared imported STATIC library 'engine::bots'" in c.out
        assert "Conan: Target declared imported STATIC library 'engine::physix'" in c.out
        assert "Conan: Target declared imported STATIC library 'engine::world'" in c.out
        assert "Conan: Target declared imported INTERFACE library 'engine::engine'" in c.out

        assert "bots: Release!" in c.out
        assert "physix: Release!" in c.out
        assert "vector: Release!" in c.out

    def test_libs_components_multilib(self):
        """
        cpp_info.libs = ["lib1", "lib2"]
        """
        c = TestClient()

        from conan.test.assets.sources import gen_function_h
        vector_h = gen_function_h(name="vector")
        from conan.test.assets.sources import gen_function_cpp
        vector_cpp = gen_function_cpp(name="vector", includes=["vector"])
        module_h = gen_function_h(name="module")
        module_cpp = gen_function_cpp(name="module", includes=["module"])

        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import CMake

            class Matrix(ConanFile):
                name = "matrix"
                version = "1.0"
                settings = "os", "compiler", "build_type", "arch"
                generators = "CMakeToolchain"
                exports_sources = "src/*", "CMakeLists.txt"

                generators = "CMakeDeps", "CMakeToolchain"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()

                def package(self):
                    cmake = CMake(self)
                    cmake.install()

                def package_info(self):
                    self.cpp_info.set_property("cmake_target_name", "MyMatrix::MyMatrix")
                    self.cpp_info.libs = ["module", "vector"]
                  """)

        cmakelists = textwrap.dedent("""
            set(CMAKE_CXX_COMPILER_WORKS 1)
            set(CMAKE_CXX_ABI_COMPILED 1)
            cmake_minimum_required(VERSION 3.15)
            project(matrix CXX)

            add_library(module src/module.cpp)
            add_library(vector src/vector.cpp)

            set_target_properties(vector PROPERTIES PUBLIC_HEADER "src/vector.h")
            set_target_properties(module PROPERTIES PUBLIC_HEADER "src/module.h")
            install(TARGETS module vector)
            """)
        c.save({"src/module.h": module_h,
                "src/module.cpp": module_cpp,
                "src/vector.h": vector_h,
                "src/vector.cpp": vector_cpp,
                "CMakeLists.txt": cmakelists,
                "conanfile.py": conanfile})
        c.run("create .")

        c.save({}, clean_first=True)
        c.run("new cmake_exe -d name=app -d version=0.1 -d requires=matrix/1.0")
        cmake = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            project(app CXX)

            find_package(matrix CONFIG REQUIRED)

            add_executable(app src/app.cpp)
            target_link_libraries(app PRIVATE MyMatrix::MyMatrix)

            install(TARGETS app)
            """)
        app_cpp = textwrap.dedent("""
            #include "vector.h"
            #include "module.h"
            int main() { vector();module();}
            """)
        c.save({"CMakeLists.txt": cmake,
                "src/app.cpp": app_cpp})
        c.run("create . -c tools.cmake.cmakedeps:new=will_break_next")
        assert "Conan: Target declared imported STATIC library 'matrix::_vector'" in c.out
        assert "Conan: Target declared imported STATIC library 'matrix::_module'" in c.out
        assert "Conan: Target declared imported INTERFACE library 'MyMatrix::MyMatrix'" in c.out
        assert "Conan: Target declared imported INTERFACE library 'matrix::matrix'" in c.out

        assert "vector: Release!" in c.out
        assert "module: Release!" in c.out
        assert "vector: Release!" in c.out


@pytest.mark.tool("cmake")
@pytest.mark.parametrize("tool_requires", [True, False])
def test_build_modules_custom_script(tool_requires):
    """
    it works both as a tool_requires and as a regular requirement
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy

        class Conan(ConanFile):
            name = "myfunctions"
            version = "1.0"
            exports_sources = ["*.cmake"]

            def package(self):
                copy(self, "*.cmake", self.source_folder, self.package_folder)

            def package_info(self):
                self.cpp_info.set_property("cmake_build_modules", ["myfunction.cmake"])
        """)

    myfunction = textwrap.dedent("""
        function(myfunction)
            message("Hello myfunction!!!!")
        endfunction()
        """)
    client.save({"conanfile.py": conanfile, "myfunction.cmake": myfunction})
    client.run("create .")

    requires = "tool_requires" if tool_requires else "requires"
    consumer = textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class Conan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain", "CMakeDeps"
            {requires} = "myfunctions/1.0"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
        """)
    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(test)
        find_package(myfunctions CONFIG REQUIRED)
        myfunction()
        """)
    client.save({"conanfile.py": consumer,
                 "CMakeLists.txt": cmakelists},
                clean_first=True)
    client.run("build . -c tools.cmake.cmakedeps:new=will_break_next")
    assert "Hello myfunction!!!!" in client.out
