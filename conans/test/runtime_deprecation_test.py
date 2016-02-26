import unittest
from conans.test.tools import TestClient
from conans.util.files import load
from conan.conans.paths import CONANINFO
import os


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
CONAN_BASIC_SETUP()'''


class CompilerRuntimeDeprecation(unittest.TestCase):

    def setUp(self):
        self.files = {"conanfile.py": file_content,
                      "CMakeLists.txt": cmakelists,
                      "main.c": "int main(){};"}

    def test_using_old_runtime_setting(self):
        client = TestClient()
        client.save(self.files)
        client.run("export lasote/testing")
        client.run('install -s compiler="Visual Studio" -s compiler.version="12" -s compiler.runtime="MTd"')
        self.assertIn("'compiler.runtime' setting has been deprecated", str(client.user_io.out))
        conaninfo = load(os.path.join(client.current_folder, CONANINFO))
        self.assertIn('compiler.runtime=MTd', conaninfo)
        client.run('build', ignore_error=True)
        # The error is showed in cmake too
        self.assertIn('-DRUNTIME_DEPRECATION_WARNING=ON', str(client.user_io.out))
        self.assertIn("CMake Warning at conanbuildinfo.cmake", str(client.user_io.out))
        self.assertIn("'compiler.runtime' setting has been deprecated", str(client.user_io.out))

    def test_using_old_runtime_setting_declaring_new(self):
        self.files["conanfile.py"] = self.files["conanfile.py"].replace('"build_type"', '"build_type", "msvcrt"')
        client = TestClient()
        client.save(self.files)
        client.run("export lasote/testing")
        client.run('install -s compiler="Visual Studio" -s compiler.version="12" -s compiler.runtime="MTd"', ignore_error=True)
        self.assertIn("'settings.msvcrt' value not defined", str(client.user_io.out))

    def test_using_new_runtime_setting_declaring_new(self):
        self.files["conanfile.py"] = self.files["conanfile.py"].replace('"build_type"', '"build_type", "msvcrt"')
        client = TestClient()
        client.save(self.files)
        client.run("export lasote/testing")
        client.run('install -s compiler="Visual Studio" -s compiler.version="12" -s msvcrt="MD"', ignore_error=True)
        self.assertNotIn("'settings.msvcrt' value not defined", str(client.user_io.out))
        self.assertIn("Generated cmake created conanbuildinfo.cmake", str(client.user_io.out))
        client.run('build', ignore_error=True)
        # The error is showed in cmake too
        self.assertNotIn('-DRUNTIME_DEPRECATION_WARNING=ON', str(client.user_io.out))
        self.assertIn('-DCONAN_LINK_RUNTIME=/MD', str(client.user_io.out))
        self.assertNotIn("CMake Warning at conanbuildinfo.cmake", str(client.user_io.out))
        self.assertNotIn("'compiler.runtime' setting has been deprecated", str(client.user_io.out))
