import os
import unittest
from collections import OrderedDict

import pytest

from conans.paths import CONANFILE
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import mkdir


class SourceTest(unittest.TestCase):

    def test_local_flow_patch(self):
        # https://github.com/conan-io/conan/issues/2327
        conanfile = """from conans import ConanFile, tools
from conans.tools import save
import os
class TestexportConan(ConanFile):
    exports = "mypython.py"
    exports_sources = "patch.patch"

    def source(self):
        save("hello/hello.h", "my hello header!")
        patch = os.path.join(self.source_folder, "patch.patch")
        self.output.info("PATCH: %s" % tools.load(patch))
        header = os.path.join(self.source_folder, "hello/hello.h")
        self.output.info("HEADER: %s" % tools.load(header))
        python = os.path.join(self.source_folder, "mypython.py")
        self.output.info("PYTHON: %s" % tools.load(python))
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "patch.patch": "mypatch",
                     "mypython.py": "mypython"})
        client.run("source .")
        self.assertIn("conanfile.py: PATCH: mypatch", client.out)
        self.assertIn("conanfile.py: HEADER: my hello header!", client.out)
        self.assertIn("conanfile.py: PYTHON: mypython", client.out)
        client.run("source . -sf=mysrc")
        self.assertIn("conanfile.py: Executing exports to", client.out)
        self.assertIn("conanfile.py: PATCH: mypatch", client.out)
        self.assertIn("conanfile.py: HEADER: my hello header!", client.out)
        self.assertIn("conanfile.py: PYTHON: mypython", client.out)
        self.assertTrue(os.path.exists(os.path.join(client.current_folder,
                                                    "mysrc", "patch.patch")))
        self.assertTrue(os.path.exists(os.path.join(client.current_folder,
                                                    "mysrc", "mypython.py")))
        self.assertTrue(os.path.exists(os.path.join(client.current_folder,
                                                    "mysrc", "hello/hello.h")))

    def test_apply_patch(self):
        # https://github.com/conan-io/conan/issues/2327
        # Test if a patch can be applied in source() both in create
        # and local flow
        client = TestClient()
        conanfile = """from conans import ConanFile
from conans.tools import load
import os
class Pkg(ConanFile):
    exports_sources = "*"
    def source(self):
        if self.develop:
            patch = os.path.join(self.source_folder, "mypatch")
            self.output.info("PATCH: %s" % load(patch))
"""
        client.save({"conanfile.py": conanfile,
                     "mypatch": "this is my patch"})
        client.run("source .")
        self.assertIn("PATCH: this is my patch", client.out)
        client.run("source . -sf=mysrc")
        self.assertIn("PATCH: this is my patch", client.out)
        client.run("create . Pkg/0.1@user/testing")
        self.assertIn("PATCH: this is my patch", client.out)

    def test_source_warning_os_build(self):
        # https://github.com/conan-io/conan/issues/2368
        conanfile = '''from conans import ConanFile
class ConanLib(ConanFile):
    pass
'''
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("source .")
        self.assertNotIn("This package defines both 'os' and 'os_build'", client.out)

    def test_source_reference(self):
        client = TestClient()
        client.run("source lib/1.0@conan/stable", assert_error=True)
        self.assertIn("'conan source' doesn't accept a reference anymore", client.out)

    def test_source_with_path_errors(self):
        client = TestClient()
        client.save({"conanfile.txt": "contents"}, clean_first=True)

        # Path with conanfile.txt
        client.run("source conanfile.txt", assert_error=True)
        self.assertIn(
            "A conanfile.py is needed, %s is not acceptable"
            % os.path.join(client.current_folder, "conanfile.txt"),
            client.out)

    def test_source_local_cwd(self):
        conanfile = '''
import os
from conans import ConanFile

class ConanLib(ConanFile):
    name = "Hello"
    version = "0.1"

    def source(self):
        self.output.info("Running source!")
        self.output.info("cwd=>%s" % os.getcwd())
'''
        client = TestClient()
        client.save({CONANFILE: conanfile})
        subdir = os.path.join(client.current_folder, "subdir")
        os.mkdir(subdir)
        client.run("install . --install-folder subdir")
        client.run("source . --source-folder subdir")
        self.assertIn("conanfile.py (Hello/0.1): Configuring sources", client.out)
        self.assertIn("conanfile.py (Hello/0.1): cwd=>%s" % subdir, client.out)

    def test_local_source_src_not_exist(self):
        conanfile = '''
import os
from conans import ConanFile
class ConanLib(ConanFile):
    name = "Hello"
    version = "0.1"
'''
        client = TestClient()
        client.save({CONANFILE: conanfile})
        # Automatically created
        client.run("source conanfile.py --source-folder=src")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "src")))

    def test_repeat_args_fails(self):
        conanfile = '''
from conans import ConanFile
class ConanLib(ConanFile):

    def source(self):
        pass
'''
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("source ./conanfile.py --source-folder sf")
        with self.assertRaisesRegex(Exception, "Command failed"):
            client.run("source . --source-folder sf --source-folder sf")
        with self.assertRaisesRegex(Exception, "Command failed"):

            client.run("source conanfile.py --source-folder sf --install-folder if "
                       "--install-folder rr")

    def test_local_source(self):
        conanfile = '''
from conans import ConanFile
from conans.util.files import save

class ConanLib(ConanFile):

    def source(self):
        self.output.info("Running source!")
        err
        save("file1.txt", "Hello World")
'''
        # First, failing source()
        client = TestClient()
        client.save({CONANFILE: conanfile})

        client.run("source .", assert_error=True)
        self.assertIn("conanfile.py: Running source!", client.out)
        self.assertIn("ERROR: conanfile.py: Error in source() method, line 9", client.out)

        # Fix the error and repeat
        client.save({CONANFILE: conanfile.replace("err", "")})
        client.run("source .")
        self.assertIn("conanfile.py: Configuring sources in", client.out)
        self.assertIn("conanfile.py: Running source!", client.out)
        self.assertEqual("Hello World", client.load("file1.txt"))

    def test_retrieve_exports_sources(self):
        # For Conan 2.0 if we install a package from a remote and we want to upload to other
        # remote we need to download the sources, as we consider revisions inmutable, let's
        # iterate through the remotes to get the sources from the first match
        servers = OrderedDict()
        for index in range(2):
            servers[f"server{index}"] = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                                   users={"user": "password"})

        users = {"server0": [("user", "password")],
                 "server1": [("user", "password")]}

        client = TestClient(servers=servers, inputs=3*["user", "password"])
        client.save({"conanfile.py": GenConanfile().with_exports_sources("*"),
                     "sources.cpp": "sources"})
        client.run("create . hello/0.1@")
        client.run("upload hello/0.1@ --all -r server0")
        client.run("remove * -f")

        # install from server0 that has the sources, upload to server1 (does not have the package)
        # download the sources from server0
        client.run("install hello/0.1@ -r server0")
        client.run("upload hello/0.1@ --all -r server1")
        self.assertIn("Downloading conan_sources.tgz", client.out)
        self.assertIn("Sources downloaded from 'server0'", client.out)

        # install from server1 that has the sources, upload to server1
        # Will not download sources, revision already in server
        client.run("remove * -f")
        client.run("install hello/0.1@ -r server1")
        client.run("upload hello/0.1@ --all -r server1")
        assert "hello/0.1#02da70a3eeda6a0f01a16b75607a2e73 already in server, skipping upload" in \
               client.out
        self.assertNotIn("Downloading conan_sources.tgz", client.out)
        self.assertNotIn("Sources downloaded from 'server0'", client.out)

        # install from server0 and build
        # download sources from server0
        client.run("remove * -f")
        client.run("install hello/0.1@ -r server0 --build")
        self.assertIn("Downloading conan_sources.tgz", client.out)
        self.assertIn("Sources downloaded from 'server0'", client.out)
