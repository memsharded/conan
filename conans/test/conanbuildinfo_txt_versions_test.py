import unittest
from conans.test.utils.tools import TestClient


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

        conanfile = """from conans import ConanFile
class FooConan(ConanFile):
    requires = 'liba/[>1.0.0]@user/channel', 'libb/1.1@user/channel'
    build_requires = 'libc/[>1.0.0]@user/channel', 'libd/1.1@user/channel'

    def build(self):
        for lib in ("liba", "libb", "libc", "libd"):
            self.output.info('%s OK: %s' % (lib, str(self.deps_cpp_info[lib].version)))

"""
        client.save({"conanfile.py": conanfile})
        client.run("install .")
        client.run("build .")
        print client.out
        client.run("create . Pkg/0.1@user/channel")
        print client.out
