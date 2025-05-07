import textwrap

from conan.test.assets.sources import gen_function_h, gen_function_cpp
from conan.test.utils.tools import TestClient
from test.functional.toolchains.cmake.cmakedeps2.test_cmakeconfigdeps_new import new_value


def test_components_different_filenames():
    c = TestClient()
    vector_h = gen_function_h(name="vector")
    vector_cpp = gen_function_cpp(name="vector", includes=["vector"])
    module_h = gen_function_h(name="module")
    module_cpp = gen_function_cpp(name="module", includes=["module", "vector"], calls=["vector"])

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class Matrix(ConanFile):
            name = "matrix"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain"
            exports_sources = "src/*", "CMakeLists.txt"
            package_type = "static-library"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                cmake = CMake(self)
                cmake.install()

            def package_info(self):
                self.cpp_info.components["vector"].libs = ["vector"]
                self.cpp_info.components["vector"].set_property("cmake_file_name", "MyVector")
                self.cpp_info.components["module"].libs = ["module"]
                self.cpp_info.components["module"].set_property("cmake_file_name", "MyModule")
                self.cpp_info.components["module"].requires = ["vector"]
        """)

    cmakelists = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.15)
        project(matrix CXX)

        add_library(module src/module.cpp)
        add_library(vector src/vector.cpp)
        target_link_libraries(module PRIVATE vector)

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
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.15)
        project(app CXX)

        find_package(MyModule CONFIG REQUIRED)

        add_executable(app src/app.cpp)
        target_link_libraries(app PRIVATE matrix::module)

        install(TARGETS app)
        """)
    app_cpp = textwrap.dedent("""
        #include "module.h"
        int main() { module(); }
        """)
    c.save({"CMakeLists.txt": cmake,
            "src/app.cpp": app_cpp})
    c.run(f"create . -c tools.cmake.cmakedeps:new={new_value}")
    print(c.out)

    assert "Conan: Target declared imported STATIC library 'matrix::_vector'" in c.out
    assert "Conan: Target declared imported STATIC library 'matrix::_module'" in c.out
    assert "Conan: Target declared imported INTERFACE library 'MyMatrix::MyMatrix'" in c.out
    assert "matrix::matrix" not in c.out

    assert "vector: Release!" in c.out
    assert "module: Release!" in c.out
    assert "vector: Release!" in c.out
