import unittest
from conans.test.utils.tools import TestClient
from conans.util.files import load
import os


class ConanBuildinfoVersionTest(unittest.TestCase):

    def version_test(self):
        # https://github.com/conan-io/conan/issues/2451
        client = TestClient()
        conanfile = """from conans import ConanFile
class FooConan(ConanFile):
    pass
"""
        client.save({"conanfile.py": conanfile})
        for pkgname in ("liba/1.1", "libb/1.1", "libc/1.1", "libd/1.1"):
            client.run("create . %s@user/channel" % pkgname)
        client.save({"conanfile.py": conanfile + "\n    requires = 'libb/1.1@user/channel'"})
        client.run("create . libe/1.1@user/channel")

        conanfile = """from conans import ConanFile
class FooConan(ConanFile):
    requires = 'liba/[>1.0.0]@user/channel', 'libe/1.1@user/channel'
    build_requires = 'libc/[>1.0.0]@user/channel', 'libd/1.1@user/channel'

    def build(self):
        for lib in ("liba", "libb", "libc", "libd", "libe"):
            self.output.info('%s OK: %s' % (lib, str(self.deps_cpp_info[lib].version)))

        for r in self.info.full_requires:
            self.output.info("Requirement!: %s" % str(r))
            
        for r in self.info.build_requires:
            self.output.info("Build Requirement!: %s" % str(r))

"""
        client.save({"conanfile.py": conanfile})
        client.run("install .")
        print load(os.path.join(client.current_folder, "conaninfo.txt"))
        client.run("build .")
        print client.out
        client.run("create . Pkg/0.1@user/channel")
        print client.out
        self.assertIn("Pkg/0.1@user/channel: liba OK: 1.1", client.out)
        self.assertIn("Pkg/0.1@user/channel: libb OK: 1.1", client.out)
        self.assertIn("Pkg/0.1@user/channel: libc OK: 1.1", client.out)
        self.assertIn("Pkg/0.1@user/channel: libd OK: 1.1", client.out)
        self.assertIn("Pkg/0.1@user/channel: libe OK: 1.1", client.out)
