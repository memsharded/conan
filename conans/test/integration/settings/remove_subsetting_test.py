import os
import unittest

import pytest

from conans.test.utils.tools import TestClient
from conans.util.files import mkdir


class RemoveSubsettingTest(unittest.TestCase):

    def test_remove_options(self):
        # https://github.com/conan-io/conan/issues/2327
        # https://github.com/conan-io/conan/issues/2781
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    options = {"opt1": [True, False], "opt2": [True, False]}
    default_options = {"opt1": True, "opt2": False}
    def config_options(self):
        del self.options.opt2
    def build(self):
        assert "opt2" not in self.options
        self.options.opt2
"""
        client.save({"conanfile.py": conanfile})
        build_folder = os.path.join(client.current_folder, "build")
        mkdir(build_folder)
        client.current_folder = build_folder
        client.run("install ..")
        client.run("build ..", assert_error=True)
        self.assertIn("ConanException: option 'opt2' doesn't exist", client.out)
        self.assertIn("Possible options are ['opt1']", client.out)

    def test_remove_setting(self):
        # https://github.com/conan-io/conan/issues/2327
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    settings = "os", "build_type"
    def configure(self):
        del self.settings.build_type

    def source(self):
        self.settings.build_type
"""
        client.save({"conanfile.py": conanfile})
        build_folder = os.path.join(client.current_folder, "build")
        mkdir(build_folder)
        client.current_folder = build_folder

        client.run("source ..", assert_error=True)
        self.assertIn("'settings.build_type' doesn't exist", client.out)
        # This doesn't fail, it doesn't access build_type
        client.run("install ..")
        client.run("build ..")

    @pytest.mark.xfail(reason="Move this to CMakeToolchain")
    def test_remove_subsetting(self):
        # https://github.com/conan-io/conan/issues/2049
        client = TestClient()
        base = '''from conans import ConanFile
class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
'''
        test = """from conans import ConanFile, CMake
class ConanLib(ConanFile):
    settings = "compiler", "arch"

    def configure(self):
        del self.settings.compiler.libcxx

    def test(self):
        pass

    def build(self):
        cmake = CMake(self)
        self.output.info("TEST " + cmake.command_line)
"""
        client.save({"conanfile.py": base,
                     "test_package/conanfile.py": test})
        client.run("create . user/testing -s arch=x86_64 -s compiler=gcc "
                   "-s compiler.version=4.9 -s compiler.libcxx=libstdc++11")
        self.assertNotIn("LIBCXX", client.out)

    @pytest.mark.xfail(reason="Move this to CMakeToolchain")
    def test_remove_subsetting_build(self):
        # https://github.com/conan-io/conan/issues/2049
        client = TestClient()

        conanfile = """from conans import ConanFile, CMake
class ConanLib(ConanFile):
    settings = "compiler", "arch"

    def package(self):
        try:
            self.settings.compiler.libcxx
        except Exception as e:
            self.output.error("PACKAGE " + str(e))

    def configure(self):
        del self.settings.compiler.libcxx

    def build(self):
        try:
            self.settings.compiler.libcxx
        except Exception as e:
            self.output.error("BUILD " + str(e))
        cmake = CMake(self)
        self.output.info("BUILD " + cmake.command_line)
"""
        client.save({"conanfile.py": conanfile})
        client.run("build . -s arch=x86_64 -s compiler=gcc -s compiler.version=4.9 "
                   "-s compiler.libcxx=libstdc++11")
        self.assertIn("ERROR: BUILD 'settings.compiler.libcxx' doesn't exist for 'gcc'",
                      client.out)
        self.assertNotIn("LIBCXX", client.out)
