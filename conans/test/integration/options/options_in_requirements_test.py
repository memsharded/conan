import os
import unittest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient


class ChangeOptionsInRequirementsTest(unittest.TestCase):

    def test_basic(self):
        client = TestClient()
        zlib = '''
from conans import ConanFile

class ConanLib(ConanFile):
    name = "zlib"
    version = "0.1"
    options = {"shared": [True, False]}
    default_options={"shared": False}
'''

        files = {"conanfile.py": zlib}
        client.save(files)
        client.run("export . lasote/testing")

        boost = """from conans import ConanFile
from conans import tools
import platform, os, sys

class BoostConan(ConanFile):
    name = "BoostDbg"
    version = "1.0"
    options = {"shared": [True, False]}
    default_options ={"shared": False}

    def configure(self):
        self.options["zlib"].shared = self.options.shared

    def requirements(self):
        self.requires("zlib/0.1@lasote/testing")
"""
        files = {"conanfile.py": boost}
        client.save(files, clean_first=True)
        client.run("create . lasote/testing -o BoostDbg:shared=True --build=missing")
        ref = ConanFileReference.loads("zlib/0.1@lasote/testing")
        pref = client.get_latest_prev(ref)
        pkg_folder = client.get_latest_pkg_layout(pref).package()
        conaninfo = client.load(os.path.join(pkg_folder, "conaninfo.txt"))
        self.assertIn("shared=True", conaninfo)
