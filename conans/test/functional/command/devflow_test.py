import os
import unittest

import pytest

from conans.client import tools
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient
from conans.util.files import load, mkdir, rmdir

conanfile = '''
from conans import ConanFile
from conans.util.files import save, load
import os

class ConanFileToolsTest(ConanFile):
    name = "Pkg"
    version = "0.1"
    exports_sources = "*"

    def build(self):
        self.output.info("Source files: %s" % load(os.path.join(self.source_folder, "file.h")))
        save("myartifact.lib", "artifact contents!")
        save("subdir/myartifact2.lib", "artifact2 contents!")

    def package(self):
        self.copy("*.h")
        self.copy("*.lib")
'''


class DevInSourceFlowTest(unittest.TestCase):

    def _assert_pkg(self, folder):
        self.assertEqual(sorted(['file.h', 'myartifact.lib', 'subdir', 'conaninfo.txt',
                                 'conanmanifest.txt']),
                         sorted(os.listdir(folder)))
        self.assertEqual(load(os.path.join(folder, "myartifact.lib")),
                         "artifact contents!")
        self.assertEqual(load(os.path.join(folder, "subdir/myartifact2.lib")),
                         "artifact2 contents!")

    def test_parallel_folders(self):
        client = TestClient()
        repo_folder = os.path.join(client.current_folder, "recipe")
        build_folder = os.path.join(client.current_folder, "build")
        package_folder = os.path.join(client.current_folder, "pkg")
        mkdir(repo_folder)
        mkdir(build_folder)
        mkdir(package_folder)
        client.current_folder = repo_folder  # equivalent to git clone recipe
        client.save({"conanfile.py": conanfile,
                     "file.h": "file_h_contents!"})

        client.current_folder = build_folder
        client.run("install ../recipe")
        client.run("build ../recipe")

        client.current_folder = repo_folder
        client.run("export . lasote/testing")
        client.run("export-pkg . Pkg/0.1@lasote/testing -bf=../build")

        ref = ConanFileReference.loads("Pkg/0.1@lasote/testing")
        pref = client.get_latest_prev(ref)
        cache_package_folder = client.get_latest_pkg_layout(pref).package()
        self._assert_pkg(cache_package_folder)

    def test_insource_build(self):
        client = TestClient()
        repo_folder = client.current_folder
        package_folder = os.path.join(client.current_folder, "pkg")
        mkdir(package_folder)
        client.save({"conanfile.py": conanfile,
                     "file.h": "file_h_contents!"})

        client.run("install .")
        client.run("build .")
        client.current_folder = repo_folder
        client.run("export . lasote/testing")
        client.run("export-pkg . Pkg/0.1@lasote/testing -bf=.")

        ref = ConanFileReference.loads("Pkg/0.1@lasote/testing")
        pref = client.get_latest_prev(ref)
        cache_package_folder = client.get_latest_pkg_layout(pref).package()
        self._assert_pkg(cache_package_folder)

    def test_child_build(self):
        client = TestClient()
        build_folder = os.path.join(client.current_folder, "build")
        mkdir(build_folder)
        package_folder = os.path.join(build_folder, "package")
        mkdir(package_folder)
        client.save({"conanfile.py": conanfile,
                     "file.h": "file_h_contents!"})

        client.current_folder = build_folder
        client.run("install ..")
        client.run("build ..")

        client.current_folder = build_folder
        client.run("export-pkg .. Pkg/0.1@lasote/testing --source-folder=.. ")

        ref = ConanFileReference.loads("Pkg/0.1@lasote/testing")
        pref = client.get_latest_prev(ref)
        cache_package_folder = client.get_latest_pkg_layout(pref).package()
        self._assert_pkg(cache_package_folder)


conanfile_out = '''
from conans import ConanFile
from conans.util.files import save, load
import os

class ConanFileToolsTest(ConanFile):
    name = "Pkg"
    version = "0.1"

    def source(self):
        save("file.h", "file_h_contents!")

    def build(self):
        self.output.info("Source files: %s" % load(os.path.join(self.source_folder, "file.h")))
        save("myartifact.lib", "artifact contents!")

    def package(self):
        self.copy("*.h")
        self.copy("*.lib")
'''


class DevOutSourceFlowTest(unittest.TestCase):

    def _assert_pkg(self, folder):
        self.assertEqual(sorted(['file.h', 'myartifact.lib', 'conaninfo.txt', 'conanmanifest.txt']),
                         sorted(os.listdir(folder)))

    def test_parallel_folders(self):
        client = TestClient()
        repo_folder = os.path.join(client.current_folder, "recipe")
        src_folder = os.path.join(client.current_folder, "src")
        build_folder = os.path.join(client.current_folder, "build")
        package_folder = os.path.join(build_folder, "package")
        mkdir(repo_folder)
        mkdir(src_folder)
        mkdir(build_folder)
        mkdir(package_folder)
        client.current_folder = repo_folder  # equivalent to git clone recipe
        client.save({"conanfile.py": conanfile_out})

        client.current_folder = build_folder
        client.run("install ../recipe")
        client.current_folder = src_folder
        client.run("install ../recipe")
        client.run("source ../recipe")
        client.current_folder = build_folder
        client.run("build ../recipe --source-folder=../src")
        client.current_folder = repo_folder
        client.run("export . lasote/testing")
        client.run("export-pkg . Pkg/0.1@lasote/testing -bf=../build -sf=../src")

        ref = ConanFileReference.loads("Pkg/0.1@lasote/testing")
        pref = client.get_latest_prev(ref)
        cache_package_folder = client.get_latest_pkg_layout(pref).package()
        self._assert_pkg(cache_package_folder)

    def test_insource_build(self):
        client = TestClient()
        repo_folder = client.current_folder
        package_folder = os.path.join(client.current_folder, "pkg")
        mkdir(package_folder)
        client.save({"conanfile.py": conanfile_out})

        client.run("install .")
        client.run("source .")
        client.run("build . ")

        client.current_folder = repo_folder
        client.run("export . lasote/testing")
        client.run("export-pkg . Pkg/0.1@lasote/testing -bf=.")

        ref = ConanFileReference.loads("Pkg/0.1@lasote/testing")
        pref = client.get_latest_prev(ref)
        cache_package_folder = client.get_latest_pkg_layout(pref).package()
        self._assert_pkg(cache_package_folder)

    def test_child_build(self):
        client = TestClient()
        repo_folder = client.current_folder
        build_folder = os.path.join(client.current_folder, "build")
        mkdir(build_folder)
        package_folder = os.path.join(build_folder, "package")
        mkdir(package_folder)
        client.save({"conanfile.py": conanfile_out})

        client.current_folder = build_folder
        client.run("install ..")
        client.run("source ..")
        client.run("build .. --source-folder=.")
        client.current_folder = repo_folder

        client.run("export-pkg . Pkg/0.1@lasote/testing -bf=./build")

        ref = ConanFileReference.loads("Pkg/0.1@lasote/testing")
        pref = client.get_latest_prev(ref)
        cache_package_folder = client.get_latest_pkg_layout(pref).package()
        self._assert_pkg(cache_package_folder)
