import json
import os
import textwrap
import unittest

import pytest

from conans.client import tools
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID, GenConanfile
from conans.util.files import load, save


class CreateTest(unittest.TestCase):

    def test_dependencies_order_matches_requires(self):
        client = TestClient()
        save(client.cache.default_profile_path, "")
        save(client.cache.settings_path, "build_type: [Release, Debug]\narch: [x86]")
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . PkgA/0.1@user/testing")
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . PkgB/0.1@user/testing")
        conanfile = textwrap.dedent("""
            [requires]
            PkgB/0.1@user/testing
            PkgA/0.1@user/testing
            """)
        client.save({"conanfile.txt": conanfile}, clean_first=True)
        client.run("install . -g MSBuildDeps -s build_type=Release -s arch=x86")
        conandeps = client.load("conandeps.props")
        assert conandeps.find("PkgB") < conandeps.find("PkgA")

    def test_transitive_same_name(self):
        # https://github.com/conan-io/conan/issues/1366
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("HelloBar", "0.1"),
                     "test_package/conanfile.py": GenConanfile().with_test("pass")})
        client.run("create . lasote/testing")
        self.assertIn("HelloBar/0.1@lasote/testing: Forced build from source", client.out)

        conanfile = GenConanfile("Hello", "0.1").with_require("HelloBar/0.1@lasote/testing")
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": GenConanfile().with_test("pass")})
        client.run("create . lasote/stable")
        self.assertNotIn("HelloBar/0.1@lasote/testing: Forced build from source", client.out)

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_create(self):
        client = TestClient()
        client.save({"conanfile.py": """from conans import ConanFile
class MyPkg(ConanFile):
    def source(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def configure(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def requirements(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def build(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def package(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def package_info(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def system_requirements(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
        self.output.info("Running system requirements!!")
"""})
        client.run("create . Pkg/0.1@lasote/testing")
        self.assertIn("Configuration (profile_host):[settings]",
                      "".join(str(client.out).splitlines()))
        self.assertIn("Pkg/0.1@lasote/testing: Generating the package", client.out)
        self.assertIn("Running system requirements!!", client.out)
        client.run("search")
        self.assertIn("Pkg/0.1@lasote/testing", client.out)

        # Create with only user will raise an error because of no name/version
        client.run("create conanfile.py lasote/testing", assert_error=True)
        self.assertIn("ERROR: conanfile didn't specify name", client.out)
        # Same with only user, (default testing)
        client.run("create . lasote", assert_error=True)
        self.assertIn("Invalid parameter 'lasote', specify the full reference or user/channel",
                      client.out)

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_create_name_command_line(self):
        client = TestClient()
        client.save({"conanfile.py": """from conans import ConanFile
class MyPkg(ConanFile):
    name = "Pkg"
    def source(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def configure(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def requirements(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def build(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def package(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def package_info(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def system_requirements(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
        self.output.info("Running system requirements!!")
"""})
        client.run("create . 0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: Generating the package", client.out)
        self.assertIn("Running system requirements!!", client.out)
        client.run("search")
        self.assertIn("Pkg/0.1@lasote/testing", client.out)



    def test_error_create_name_version(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("Hello").with_version("1.2")})
        client.run("create . Hello/1.2@lasote/stable")
        client.run("create ./ Pkg/1.2@lasote/stable", assert_error=True)
        self.assertIn("ERROR: Package recipe with name Pkg!=Hello", client.out)
        client.run("create . Hello/1.1@lasote/stable", assert_error=True)
        self.assertIn("ERROR: Package recipe with version 1.1!=1.2", client.out)

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_create_user_channel(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("Pkg").with_version("0.1")})
        client.run("create . lasote/channel")
        self.assertIn("Pkg/0.1@lasote/channel: Generating the package", client.out)
        client.run("search")
        self.assertIn("Pkg/0.1@lasote/channel", client.out)

        client.run("create . lasote", assert_error=True)  # testing default
        self.assertIn("Invalid parameter 'lasote', specify the full reference or user/channel",
                      client.out)

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_create_in_subfolder(self):
        client = TestClient()
        client.save({"subfolder/conanfile.py": GenConanfile().with_name("Pkg").with_version("0.1")})
        client.run("create subfolder lasote/channel")
        self.assertIn("Pkg/0.1@lasote/channel: Generating the package", client.out)
        client.run("search")
        self.assertIn("Pkg/0.1@lasote/channel", client.out)

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_create_in_subfolder_with_different_name(self):
        # Now with a different name
        client = TestClient()
        client.save({"subfolder/Custom.py": GenConanfile().with_name("Pkg").with_version("0.1")})
        client.run("create subfolder/Custom.py lasote/channel")
        self.assertIn("Pkg/0.1@lasote/channel: Generating the package", client.out)
        client.run("search")
        self.assertIn("Pkg/0.1@lasote/channel", client.out)

    def test_create_test_package(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("Pkg").with_version("0.1"),
                     "test_package/conanfile.py":
                         GenConanfile().with_test('self.output.info("TESTING!!!")')})
        client.run("create . lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: Generating the package", client.out)
        self.assertIn("Pkg/0.1@lasote/testing (test package): TESTING!!!", client.out)

    def test_create_skip_test_package(self):
        # Skip the test package stage if explicitly disabled with --test-folder=None
        # https://github.com/conan-io/conan/issues/2355
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("Pkg").with_version("0.1"),
                     "test_package/conanfile.py":
                         GenConanfile().with_test('self.output.info("TESTING!!!")')})
        client.run("create . lasote/testing --test-folder=None")
        self.assertIn("Pkg/0.1@lasote/testing: Generating the package", client.out)
        self.assertNotIn("TESTING!!!", client.out)

    def test_create_package_requires(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . Dep/0.1@user/channel")
        client.run("create . Other/1.0@user/channel")

        conanfile = GenConanfile().with_require("Dep/0.1@user/channel")
        test_conanfile = """from conans import ConanFile
class MyPkg(ConanFile):
    requires = "Other/1.0@user/channel"
    def build(self):
        for r in self.requires.values():
            self.output.info("build() Requires: %s" % str(r.ref))
        import os
        for dep in self.dependencies.host.values():
            self.output.info("build() cpp_info dep: %s" % dep)

    def test(self):
        pass
        """

        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test_conanfile})

        client.run("create . Pkg/0.1@lasote/testing")

        self.assertIn("Pkg/0.1@lasote/testing (test package): build() "
                      "Requires: Other/1.0@user/channel", client.out)
        self.assertIn("Pkg/0.1@lasote/testing (test package): build() "
                      "Requires: Pkg/0.1@lasote/testing", client.out)
        self.assertIn("Pkg/0.1@lasote/testing (test package): build() cpp_info dep: Other",
                      client.out)
        self.assertIn("Pkg/0.1@lasote/testing (test package): build() cpp_info dep: Dep",
                      client.out)
        self.assertIn("Pkg/0.1@lasote/testing (test package): build() cpp_info dep: Pkg",
                      client.out)

    def test_build_policy(self):
        # https://github.com/conan-io/conan/issues/1956
        client = TestClient()
        conanfile = str(GenConanfile()) + '\n    build_policy = "always"'
        test_package = GenConanfile().with_test("pass")
        client.save({"conanfile.py": conanfile, "test_package/conanfile.py": test_package})
        client.run("create . Bar/0.1@user/stable")
        self.assertIn("Bar/0.1@user/stable: Forced build from source", client.out)

        # Transitive too
        client.save({"conanfile.py": GenConanfile().with_require("Bar/0.1@user/stable")})
        client.run("create . pkg/0.1@user/stable")
        self.assertIn("Bar/0.1@user/stable: Forced build from source", client.out)

    def test_build_folder_handling(self):
        conanfile = GenConanfile().with_name("Hello").with_version("0.1")
        test_conanfile = GenConanfile().with_test("pass")
        client = TestClient()
        default_build_dir = os.path.join(client.current_folder, "test_package", "build")

        # Test the default behavior.
        client.save({"conanfile.py": conanfile, "test_package/conanfile.py": test_conanfile},
                    clean_first=True)
        client.run("create . lasote/stable")
        self.assertTrue(os.path.exists(default_build_dir))

        # Test if the specified build folder is respected.
        client.save({"conanfile.py": conanfile, "test_package/conanfile.py": test_conanfile},
                    clean_first=True)
        client.run("create -tbf=build_folder . lasote/stable")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "build_folder")))
        self.assertFalse(os.path.exists(default_build_dir))

        # Test if using a temporary test folder can be enabled via the environment variable.
        client.save({"conanfile.py": conanfile, "test_package/conanfile.py": test_conanfile},
                    clean_first=True)
        with tools.environment_append({"CONAN_TEMP_TEST_FOLDER": "True"}):
            client.run("create . lasote/stable")
        self.assertFalse(os.path.exists(default_build_dir))

        # # Test if using a temporary test folder can be enabled via the config file.
        conan_conf = textwrap.dedent("""
                                    [storage]
                                    path = ./data
                                    [general]
                                    temp_test_folder=True
                                """)
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)
        client.run("create . lasote/stable")
        self.assertFalse(os.path.exists(default_build_dir))

        # Test if the specified build folder is respected also when the use of
        # temporary test folders is enabled in the config file.
        client.run("create -tbf=test_package/build_folder . lasote/stable")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "test_package",
                                                    "build_folder")))
        self.assertFalse(os.path.exists(default_build_dir))

    def test_package_folder_build_error(self):
        """
        Check package folder is not created if the build step fails
        """
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class MyPkg(ConanFile):

                def build(self):
                    raise ConanException("Build error")
            """)
        client.save({"conanfile.py": conanfile})
        ref = ConanFileReference("pkg", "0.1", "danimtb", "testing")
        client.run("create . %s" % ref.full_str(), assert_error=True)
        pref = client.get_latest_prev(ref, NO_SETTINGS_PACKAGE_ID)
        self.assertIn("Build error", client.out)
        package_folder = client.get_latest_pkg_layout(pref).package()
        self.assertFalse(os.path.exists(package_folder))

    def test_create_with_name_and_version(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run('create . lib/1.0@')
        self.assertIn("lib/1.0: Created package revision", client.out)

    def test_create_with_only_user_channel(self):
        """This should be the recommended way and only from Conan 2.0"""
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("lib").with_version("1.0")})
        client.run('create . @user/channel')
        self.assertIn("lib/1.0@user/channel: Created package revision", client.out)

        client.run('create . user/channel')
        self.assertIn("lib/1.0@user/channel: Created package revision", client.out)

    def test_requires_without_user_channel(self):
        client = TestClient()
        conanfile = textwrap.dedent('''
            from conans import ConanFile

            class HelloConan(ConanFile):
                name = "HelloBar"
                version = "0.1"

                def package_info(self):
                    self.output.warning("Hello, I'm HelloBar")
            ''')

        client.save({"conanfile.py": conanfile})
        client.run("create .")

        client.save({"conanfile.py": GenConanfile().with_require("HelloBar/0.1")})
        client.run("create . consumer/1.0@")
        self.assertIn("HelloBar/0.1: WARN: Hello, I'm HelloBar", client.out)
        self.assertIn("consumer/1.0: Created package revision", client.out)

    def test_conaninfo_contents_without_user_channel(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("Hello").with_version("0.1")})
        client.run("create .")
        client.save({"conanfile.py": GenConanfile().with_name("Bye").with_version("0.1")
                                                   .with_require("Hello/0.1")})
        client.run("create .")

        ref = ConanFileReference.loads("Bye/0.1")

        refs = client.cache.get_latest_rrev(ref)
        pkgs = client.cache.get_package_ids(refs)
        prev = client.cache.get_latest_prev(pkgs[0])
        package_folder = client.cache.pkg_layout(prev).package()

        conaninfo = load(os.path.join(package_folder, "conaninfo.txt"))
        # The user and channel nor None nor "_/" appears in the conaninfo
        self.assertNotIn("None", conaninfo)
        self.assertNotIn("_/", conaninfo)
        self.assertNotIn("/_", conaninfo)
        self.assertIn("[requires]\n    Hello/0.1\n", conaninfo)

    @pytest.mark.xfail(reason="--json output has been disabled")
    def test_compoents_json_output(self):
        self.client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class MyTest(ConanFile):
                name = "pkg"
                version = "0.1"
                settings = "build_type"

                def package_info(self):
                    self.cpp_info.components["pkg1"].libs = ["libpkg1"]
                    self.cpp_info.components["pkg2"].libs = ["libpkg2"]
                    self.cpp_info.components["pkg2"].requires = ["pkg1"]
            """)
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . --json jsonfile.json")
        path = os.path.join(self.client.current_folder, "jsonfile.json")
        content = self.client.load(path)
        data = json.loads(content)
        cpp_info_data = data["installed"][0]["packages"][0]["cpp_info"]
        self.assertIn("libpkg1", cpp_info_data["components"]["pkg1"]["libs"])
        self.assertNotIn("requires", cpp_info_data["components"]["pkg1"])
        self.assertIn("libpkg2", cpp_info_data["components"]["pkg2"]["libs"])
        self.assertListEqual(["pkg1"], cpp_info_data["components"]["pkg2"]["requires"])
