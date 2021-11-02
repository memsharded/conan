import os
import textwrap
import unittest

import pytest

from conans.model.ref import PackageReference, ConanFileReference
from conans.paths import CONANFILE
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient
from conans.util.files import mkdir


conanfile_scope_env = """
from conans import ConanFile

class AConan(ConanFile):
    requires = "Hello/0.1@lasote/testing"

    def build(self):
        self.output.info("INCLUDE PATH: %s" %
            self.deps_cpp_info.include_paths[0].replace('\\\\', '/'))
        self.output.info("HELLO ROOT PATH: %s" %
            self.deps_cpp_info["Hello"].rootpath.replace('\\\\', '/'))
        self.output.info("HELLO INCLUDE PATHS: %s" %
            self.deps_cpp_info["Hello"].include_paths[0].replace('\\\\', '/'))
"""

conanfile_dep = """
import os
from conans import ConanFile
from conans.tools import mkdir

class AConan(ConanFile):
    name = "Hello"
    version = "0.1"

    def package(self):
        mkdir(os.path.join(self.package_folder, "include"))
"""


class ConanBuildTest(unittest.TestCase):

    @pytest.mark.xfail(reason="deps_cpp_info access removed")
    def test_build(self):
        """ Try to reuse variables loaded from txt generator => deps_cpp_info
        """
        client = TestClient()
        client.save({CONANFILE: conanfile_dep})
        client.run("export . lasote/testing")

        client.save({CONANFILE: conanfile_scope_env}, clean_first=True)
        client.run("install . --build=missing")

        client.save({"my_conanfile.py": conanfile_scope_env})
        client.run("build ./my_conanfile.py --build=missing")
        pref = client.get_latest_prev(ConanFileReference.loads("Hello/0.1@lasote/testing"),
                                      NO_SETTINGS_PACKAGE_ID)
        package_folder = client.get_latest_pkg_layout(pref).package().replace("\\", "/")
        self.assertIn("my_conanfile.py: INCLUDE PATH: %s/include" % package_folder, client.out)
        self.assertIn("my_conanfile.py: HELLO ROOT PATH: %s" % package_folder, client.out)
        self.assertIn("my_conanfile.py: HELLO INCLUDE PATHS: %s/include"
                      % package_folder, client.out)

    def test_build_different_folders(self):
        conanfile = """
import os
from conans import ConanFile

class AConan(ConanFile):

    def build(self):
        self.output.warning("Build folder=>%s" % self.build_folder)
        self.output.warning("Src folder=>%s" % self.source_folder)
        self.output.warning("Package folder=>%s" % self.package_folder)
        assert(os.path.exists(self.build_folder))
        assert(os.path.exists(self.source_folder))
        # package_folder will be created manually or by the CMake helper when local invocation
        assert(not os.path.exists(self.package_folder))
"""

        client = TestClient()
        client.save({CONANFILE: conanfile})
        with client.chdir("build1"):
            client.run("install ..")
        # Try relative to cwd
        client.run("build . --build-folder build2 --install-folder build1 "
                   "--package-folder build1/pkg")
        self.assertIn("Build folder=>%s" % os.path.join(client.current_folder, "build2"),
                      client.out)
        self.assertIn("Package folder=>%s" % os.path.join(client.current_folder, "build1", "pkg"),
                      client.out)
        self.assertIn("Src folder=>%s" % client.current_folder, client.out)

        # Try default package folder
        client.run("build conanfile.py --build-folder build1 --package-folder package1")
        self.assertIn("Build folder=>%s" % os.path.join(client.current_folder, "build1"),
                      client.out)
        self.assertIn("Package folder=>%s" % os.path.join(client.current_folder, "package"),
                      client.out)
        self.assertIn("Src folder=>%s" % client.current_folder, client.out)

        # Try absolute package folder
        client.run("build . --build-folder build1 --package-folder '%s'" %
                   os.path.join(client.current_folder, "mypackage"))
        self.assertIn("Build folder=>%s" % os.path.join(client.current_folder, "build1"),
                      client.out)
        self.assertIn("Package folder=>%s" % os.path.join(client.current_folder, "mypackage"),
                      client.out)
        self.assertIn("Src folder=>%s" % client.current_folder, client.out)

        # Try absolute build and relative package
        conanfile_dir = client.current_folder
        bdir = os.path.join(client.current_folder, "other/mybuild")
        with client.chdir(bdir):
            client.run("install '%s'" % conanfile_dir)
        client.run("build ./conanfile.py --build-folder '%s' --package-folder relpackage" % bdir)

        self.assertIn("Build folder=>%s" % os.path.join(client.current_folder, "other/mybuild"),
                      client.out)
        self.assertIn("Package folder=>%s" % os.path.join(client.current_folder, "relpackage"),
                      client.out)
        self.assertIn("Src folder=>%s" % client.current_folder, client.out)

        # Try different source
        with client.chdir("other/build"):
            client.run("install ../..")
        # src is not created automatically, it makes no sense
        client.run("build . --source-folder '%s' --build-folder other/build" %
                   os.path.join(client.current_folder, "mysrc"), assert_error=True)

        mkdir(os.path.join(client.current_folder, "mysrc"))

        client.run("build . --source-folder '%s' --build-folder other/build"
                   % os.path.join(client.current_folder, "mysrc"))
        self.assertIn("Build folder=>%s" % os.path.join(client.current_folder, "other", "build"),
                      client.out)
        self.assertIn("Package folder=>%s" % os.path.join(client.current_folder, "other", "build"),
                      client.out)
        self.assertIn("Src folder=>%s" % os.path.join(client.current_folder, "mysrc"), client.out)

    @pytest.mark.xfail(reason="deps_cpp_info access removed")
    def test_build_dots_names(self):
        """ Try to reuse variables loaded from txt generator => deps_cpp_info
        """
        client = TestClient()
        conanfile_dep = """
from conans import ConanFile

class AConan(ConanFile):
    pass
"""
        client.save({CONANFILE: conanfile_dep})
        client.run("create . Hello.Pkg/0.1@lasote/testing")
        client.run("create . Hello-Tools/0.1@lasote/testing")
        conanfile_scope_env = """
from conans import ConanFile

class AConan(ConanFile):
    requires = "Hello.Pkg/0.1@lasote/testing", "Hello-Tools/0.1@lasote/testing"

    def build(self):
        self.output.info("HELLO ROOT PATH: %s" %
            self.deps_cpp_info["Hello.Pkg"].rootpath.replace('\\\\', '/'))
        self.output.info("HELLO ROOT PATH: %s" %
            self.deps_cpp_info["Hello-Tools"].rootpath.replace('\\\\', '/'))
"""
        client.save({CONANFILE: conanfile_scope_env}, clean_first=True)
        client.run("build conanfile.py --build=missing")

        self.assertIn("Hello.Pkg/0.1/lasote/testing", client.out)
        self.assertIn("Hello-Tools/0.1/lasote/testing", client.out)

    @pytest.mark.xfail(reason="deps_cpp_info access removed")
    def test_build_with_deps_env_info(self):
        client = TestClient()
        conanfile = """
from conans import ConanFile, CMake

class AConan(ConanFile):
    name = "lib"
    version = "1.0"

    def package_info(self):
        self.buildenv_info.define("MYVAR", "23")

"""
        client.save({CONANFILE: conanfile})
        client.run("export . lasote/stable")

        conanfile = """
from conans import ConanFile
from conan.tools.env import VirtualBuildEnv
import os

class AConan(ConanFile):
    build_requires = "lib/1.0@lasote/stable"

    def build(self):
        build_env = VirtualBuildEnv(self).vars()
        with build_env.apply():
            assert(os.environ["MYVAR"] == "23")
"""
        client.save({CONANFILE: conanfile}, clean_first=True)
        client.run("build . --build missing")

    def test_build_single_full_reference(self):
        client = TestClient()
        conanfile = """
from conans import ConanFile

class FooConan(ConanFile):
    name = "foo"
    version = "1.0"
"""
        client.save({CONANFILE: conanfile})
        client.run("create --build foo/1.0@user/stable . user/stable")
        self.assertIn("foo/1.0@user/stable: Forced build from source", client.out)

    def test_build_multiple_full_reference(self):
        client = TestClient()
        conanfile = """
from conans import ConanFile

class FooConan(ConanFile):
    name = "foo"
    version = "1.0"
"""
        client.save({CONANFILE: conanfile})
        client.run("create . user/stable")

        conanfile = """
from conans import ConanFile

class BarConan(ConanFile):
    name = "bar"
    version = "1.0"
    requires = "foo/1.0@user/stable"
"""
        client.save({CONANFILE: conanfile}, clean_first=True)
        client.run("create --build foo/1.0@user/stable --build bar/1.0@user/testing . user/testing")
        self.assertIn("foo/1.0@user/stable: Forced build from source", client.out)
        self.assertIn("bar/1.0@user/testing: Forced build from source", client.out)

    def test_debug_build_release_deps(self):
        # https://github.com/conan-io/conan/issues/2899
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Conan(ConanFile):
                name = "{name}"
                {requires}
                settings = "build_type"
                def build(self):
                    self.output.info("BUILD: %s BuildType=%s!"
                                     % (self.name, self.settings.build_type))
                def package_info(self):
                    self.output.info("PACKAGE_INFO: %s BuildType=%s!"
                                     % (self.name, self.settings.build_type))
            """)
        client.save({CONANFILE: conanfile.format(name="Dep", requires="")})
        client.run("create . Dep/0.1@user/testing -s build_type=Release")
        client.save({CONANFILE: conanfile.format(name="MyPkg",
                                                 requires="requires = 'Dep/0.1@user/testing'")})
        client.run("build . -s MyPkg:build_type=Debug -s build_type=Release")
        self.assertIn("Dep/0.1@user/testing: PACKAGE_INFO: Dep BuildType=Release!", client.out)
        self.assertIn("conanfile.py (MyPkg/None): BUILD: MyPkg BuildType=Debug!",
                      client.out)
