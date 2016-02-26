import unittest
from conans.test.tools import TestClient
from conans.util.files import load
from conan.conans.paths import CONANINFO
import os
import platform


file_content = '''
from conans import ConanFile, CMake

class ConanFileToolsTest(ConanFile):
    name = "test"
    version = "1.9"
    settings = "os", "compiler", "arch", "build_type"
    url = "1"
    license = "2"
    export = ["CMakeLists.txt", "main.c"]
    generators = ["cmake"]

    def build(self):
        self.output.warn("Building...")
        cmake = CMake(self.settings)
        self.output.warn(cmake.command_line)
        command = cmake.command_line.replace('-G "Visual Studio 12 Win64"', "")
        self.run('cmake . %s' % command)
        self.run("cmake --build . %s" %  cmake.build_config)
    '''
cmakelists = '''PROJECT(conanzlib)
cmake_minimum_required(VERSION 2.8)
include(conanbuildinfo.cmake)
CONAN_BASIC_SETUP()
MESSAGE("CXX FLAGS=> ${CMAKE_CXX_FLAGS}")
get_directory_property( DirDefs DIRECTORY ${CMAKE_SOURCE_DIR} COMPILE_DEFINITIONS)
foreach( d ${DirDefs} )
    message( STATUS "Found Define: " ${d} )
endforeach()
'''


def nowintest(func):
    if platform.system() == "Windows":
        func.__test__ = False
    return func


class StdlibSettingTest(unittest.TestCase):

    def setUp(self):
        self.files = {"conanfile.py": file_content, "CMakeLists.txt": cmakelists}

    @nowintest
    def not_using_stdlib_setting_test(self):
        client = TestClient()
        client.save(self.files)
        client.run("export lasote/testing")
        client.run('install -s os=Linux -s compiler=gcc')
        conaninfo = load(os.path.join(client.current_folder, CONANINFO))
        not_full_settings = conaninfo[:conaninfo.find("[full_settings]")]
        full_settings = conaninfo[conaninfo.find("[full_settings]"):]
        self.assertNotIn('stdlib', not_full_settings)
        self.assertIn('stdlib', full_settings)
        client.run('build', ignore_error=True)

    @nowintest
    def test_declared_stdlib_but_not_passed(self):
        self.files["conanfile.py"] = self.files["conanfile.py"].replace('"build_type"', '"build_type", "stdlib"')
        client = TestClient()
        client.save(self.files)
        client.run("export lasote/testing")
        client.run('install -s os=Linux -s compiler=gcc', ignore_error=False)
        client.run('build')
        self.assertIn("-stdlib=libstdc++", str(client.user_io.out))
        self.assertIn("Found Define: _GLIBCXX_USE_CXX11_ABI=0", str(client.user_io.out))

    @nowintest
    def test_declared_stdlib_and_passed(self):
        self.files["conanfile.py"] = self.files["conanfile.py"].replace('"build_type"', '"build_type", "stdlib"')
        client = TestClient()
        client.save(self.files)
        client.run("export lasote/testing")
        client.run('install -s stdlib=libstdc++ -s os=Linux -s compiler=gcc', ignore_error=False)
        client.run('build')
        self.assertIn("-stdlib=libstdc++", str(client.user_io.out))
        self.assertIn("Found Define: _GLIBCXX_USE_CXX11_ABI=0", str(client.user_io.out))

        client.run('install -s stdlib=libstdc++11 -s os=Linux -s compiler=gcc', ignore_error=False)
        client.run('build')
        self.assertIn("-stdlib=libstdc++", str(client.user_io.out))
        self.assertIn("Found Define: _GLIBCXX_USE_CXX11_ABI=1", str(client.user_io.out))

        client.run('install -s stdlib=libc++ -s os=Linux -s compiler=gcc', ignore_error=False)
        client.run('build')
        self.assertIn("-stdlib=libc++", str(client.user_io.out))
        self.assertNotIn("Found Define: _GLIBCXX_USE_CXX11", str(client.user_io.out))
