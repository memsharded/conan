import textwrap
import unittest

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


conanfile_parent = """
from conans import ConanFile

class parentLib(ConanFile):
    name = "parent"
    version = "1.0"

    def package_info(self):
        self.cpp_info.cxxflags.append("-myflag")
        self.user_info.MyVar = "MyVarValue"
        self.buildenv_info.define("MyEnvVar", "MyEnvVarValue")
"""


conanfile = """
import os
from conans import ConanFile

class AConan(ConanFile):
    name = "lib"
    version = "1.0"

    # To save the folders and check later if the folder is the same
    copy_build_folder = None
    copy_source_folder = None
    copy_package_folder = None

    counter_package_calls = 0

    no_copy_source = %(no_copy_source)s
    requires = "parent/1.0@conan/stable"
    running_local_command = %(local_command)s

    def assert_in_local_cache(self):
        if self.running_local_command:
            assert(self.in_local_cache == False)

    def source(self):
        assert(self.source_folder == os.getcwd())
        self.assert_in_local_cache()

        # Prevented to use them, it's dangerous, because the source is run only for the first
        # config, so only the first build_folder/package_folder would be modified
        assert(self.build_folder is None)
        assert(self.package_folder is None)

        assert(self.source_folder is not None)
        self.copy_source_folder = self.source_folder

    def build(self):
        assert(self.build_folder == os.getcwd())

        self.assert_in_local_cache()

        if self.no_copy_source and self.in_local_cache:
            assert(self.copy_source_folder == self.source_folder)  # Only in install
            assert(self.install_folder == self.build_folder)
        else:
            assert(self.source_folder == self.build_folder)
            self.install_folder

        assert(self.package_folder is not None)
        self.copy_build_folder = self.build_folder

    def package(self):
        assert(self.install_folder is not None)
        assert(self.build_folder == os.getcwd())
        self.assert_in_local_cache()

        if self.in_local_cache:
            assert(self.copy_build_folder == self.build_folder)

        if self.no_copy_source and self.in_local_cache:
            assert(self.copy_source_folder == self.source_folder)  # Only in install
        else:
            assert(self.source_folder == self.build_folder)

        self.copy_package_folder = self.package_folder

    def package_info(self):
        assert(self.package_folder == os.getcwd())
        assert(self.in_local_cache == True)

        assert(self.source_folder is None)
        assert(self.build_folder is None)
        assert(self.install_folder is None)

    def imports(self):
        assert(self.imports_folder == os.getcwd())

    def deploy(self):
        assert(self.install_folder == os.getcwd())
"""


class TestFoldersAccess(unittest.TestCase):
    """"Tests the presence of self.source_folder, self.build_folder, self.package_folder
    in the conanfile methods. Also the availability of the self.deps_cpp_info, self.deps_user_info
    and self.deps_env_info. Also the 'in_local_cache' variable. """

    def setUp(self):
        self.client = TestClient()
        self.client.save({"conanfile.py": conanfile_parent})
        self.client.run("export . conan/stable")

    def test_source_local_command(self):
        c1 = conanfile % {"no_copy_source": False, "source_with_infos": False,
                          "local_command": True}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("source .")

        c1 = conanfile % {"no_copy_source": True, "source_with_infos": False,
                          "local_command": True}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("source .")

    def test_build_local_command(self):

        c1 = conanfile % {"no_copy_source": False, "source_with_infos": False,
                          "local_command": True}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("build .", assert_error=True)

        c1 = conanfile % {"no_copy_source": False, "source_with_infos": False,
                          "local_command": True}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("build . --build missing")

        c1 = conanfile % {"no_copy_source": True, "source_with_infos": False,
                          "local_command": True}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("build . --build missing")

    def test_deploy(self):
        c1 = conanfile % {"no_copy_source": False, "source_with_infos": True,
                          "local_command": False}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("create . user/testing --build missing")
        self.client.run("install lib/1.0@user/testing")  # Checks deploy

    def test_full_install(self):
        c1 = conanfile % {"no_copy_source": False, "source_with_infos": False,
                          "local_command": False}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("create . conan/stable --build")

        c1 = conanfile % {"no_copy_source": True, "source_with_infos": False,
                          "local_command": False}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("create . conan/stable --build")

        c1 = conanfile % {"no_copy_source": False, "source_with_infos": True,
                          "local_command": False}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("create . conan/stable --build")

        c1 = conanfile % {"no_copy_source": True, "source_with_infos": True,
                          "local_command": False}
        self.client.save({"conanfile.py": c1}, clean_first=True)
        self.client.run("create . conan/stable --build")


class RecipeFolderTest(unittest.TestCase):
    recipe_conanfile = textwrap.dedent("""
        from conans import ConanFile, load
        import os
        class Pkg(ConanFile):
            exports = "file.txt"
            def init(self):
                r = load(os.path.join(self.recipe_folder, "file.txt"))
                self.output.info("INIT: {}".format(r))
            def set_name(self):
                r = load(os.path.join(self.recipe_folder, "file.txt"))
                self.output.info("SET_NAME: {}".format(r))
            def configure(self):
                r = load(os.path.join(self.recipe_folder, "file.txt"))
                self.output.info("CONFIGURE: {}".format(r))
            def requirements(self):
                r = load(os.path.join(self.recipe_folder, "file.txt"))
                self.output.info("REQUIREMENTS: {}".format(r))
            def package(self):
                r = load(os.path.join(self.recipe_folder, "file.txt"))
                self.output.info("PACKAGE: {}".format(r))
            def package_info(self):
                r = load(os.path.join(self.recipe_folder, "file.txt"))
                self.output.info("PACKAGE_INFO: {}".format(r))
        """)

    def test_recipe_folder(self):
        client = TestClient()
        client.save({"conanfile.py": self.recipe_conanfile,
                     "file.txt": "MYFILE!"})
        client.run("export . pkg/0.1@user/testing")
        self.assertIn("INIT: MYFILE!", client.out)
        self.assertIn("SET_NAME: MYFILE!", client.out)
        client.save({}, clean_first=True)
        client.run("install pkg/0.1@user/testing --build")
        self.assertIn("pkg/0.1@user/testing: INIT: MYFILE!", client.out)
        self.assertNotIn("SET_NAME", client.out)
        self.assertIn("pkg/0.1@user/testing: CONFIGURE: MYFILE!", client.out)
        self.assertIn("pkg/0.1@user/testing: REQUIREMENTS: MYFILE!", client.out)
        self.assertIn("pkg/0.1@user/testing: PACKAGE: MYFILE!", client.out)
        self.assertIn("pkg/0.1@user/testing: PACKAGE_INFO: MYFILE!", client.out)

    def test_local_flow(self):
        client = TestClient()
        client.save({"conanfile.py": self.recipe_conanfile,
                     "file.txt": "MYFILE!"})
        client.run("install .")
        self.assertIn("INIT: MYFILE!", client.out)
        self.assertIn("SET_NAME: MYFILE!", client.out)
        self.assertIn("conanfile.py: CONFIGURE: MYFILE!", client.out)
        self.assertIn("conanfile.py: REQUIREMENTS: MYFILE!", client.out)

    @pytest.mark.xfail(reason="cache2.0 editables not considered yet")
    def test_editable(self):
        client = TestClient()
        client.save({"pkg/conanfile.py": self.recipe_conanfile,
                     "pkg/file.txt": "MYFILE!",
                     "consumer/conanfile.py":
                         GenConanfile().with_require("pkg/0.1@user/stable")})
        client.run("editable add pkg pkg/0.1@user/stable")

        client.run("install consumer")
        self.assertIn("pkg/0.1@user/stable: INIT: MYFILE!", client.out)
        self.assertIn("pkg/0.1@user/stable: CONFIGURE: MYFILE!", client.out)
        self.assertIn("pkg/0.1@user/stable: REQUIREMENTS: MYFILE!", client.out)
        self.assertIn("pkg/0.1@user/stable from user folder - Editable", client.out)
        self.assertIn("pkg/0.1@user/stable: PACKAGE_INFO: MYFILE!", client.out)
