import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_transitive_py_requires():
    # https://github.com/conan-io/conan/issues/5529
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class PackageInfo(ConanFile):
            python_requires = "dep/[>0.0]@user/channel"
        """)
    consumer = textwrap.dedent("""
        from conans import ConanFile
        class MyConanfileBase(ConanFile):
            python_requires = "pkg/0.1@user/channel"
        """)
    client.save({"dep/conanfile.py": GenConanfile(),
                 "pkg/conanfile.py": conanfile,
                 "consumer/conanfile.py": consumer})

    client.run("export dep dep/0.1@user/channel")
    client.run("export pkg pkg/0.1@user/channel")
    client.run("lock create consumer/conanfile.py --lockfile-out=conan.lock")

    client.run("export dep dep/0.2@user/channel")

    client.run("install consumer/conanfile.py --lockfile=conan.lock")
    assert "dep/0.1@user/channel" in client.out
    assert "dep/0.2" not in client.out

    client.run("install consumer/conanfile.py")
    assert "dep/0.2@user/channel" in client.out
    assert "dep/0.1" not in client.out


def test_transitive_matching():
    client = TestClient()
    tool = textwrap.dedent("""
        from conans import ConanFile
        class PackageInfo(ConanFile):
            python_requires = "dep/{}"
        """)
    pkg = textwrap.dedent("""
        from conans import ConanFile
        class MyConanfileBase(ConanFile):
            python_requires = "{}/0.1"
            def configure(self):
                for k, p in self.python_requires.items():
                    self.output.info("%s: %s!!" % (k, p.ref))
        """)
    client.save({"dep/conanfile.py": GenConanfile(),
                 "toola/conanfile.py": tool.format("0.1"),
                 "toolb/conanfile.py": tool.format("0.2"),
                 "pkga/conanfile.py": pkg.format("toola"),
                 "pkgb/conanfile.py": pkg.format("toolb"),
                 "app/conanfile.py": GenConanfile().with_requires("pkga/0.1", "pkgb/0.1")})

    client.run("export dep dep/0.1@")
    client.run("export dep dep/0.2@")
    client.run("export toola toola/0.1@")
    client.run("export toolb toolb/0.1@")
    client.run("create pkga pkga/0.1@")
    client.run("create pkgb pkgb/0.1@")
    client.run("lock create app/conanfile.py --lockfile-out=conan.lock")

    # TODO: create a new revision for dep/0.2, make sure it is not used
    # FIXME: Conan locks still do not support revisions
    # client.save({"dep/conanfile.py": new_conanfile})
    # client.run("export dep dep/0.2@")

    client.run("install app/conanfile.py --lockfile=conan.lock")
    assert "pkga/0.1: toola: toola/0.1!!" in client.out
    assert "pkgb/0.1: toolb: toolb/0.1!!" in client.out
    assert "pkga/0.1: dep: dep/0.1!!" in client.out
    assert "pkgb/0.1: dep: dep/0.2!!" in client.out

    # TODO: This should use the changes of the new revision
    client.run("install app/conanfile.py")
    assert "pkga/0.1: toola: toola/0.1!!" in client.out
    assert "pkgb/0.1: toolb: toolb/0.1!!" in client.out
    assert "pkga/0.1: dep: dep/0.1!!" in client.out
    assert "pkgb/0.1: dep: dep/0.2!!" in client.out


def test_transitive_matching_ranges():
    client = TestClient()
    tool = textwrap.dedent("""
        from conans import ConanFile
        class PackageInfo(ConanFile):
            python_requires = "dep/{}"
        """)
    pkg = textwrap.dedent("""
        from conans import ConanFile
        class MyConanfileBase(ConanFile):
            python_requires = "tool/{}"
            def configure(self):
                for k, p in self.python_requires.items():
                    self.output.info("%s: %s!!" % (k, p.ref))
        """)
    client.save({"dep/conanfile.py": GenConanfile(),
                 "tool1/conanfile.py": tool.format("[<0.2]"),
                 "tool2/conanfile.py": tool.format("[>0.0]"),
                 "pkga/conanfile.py": pkg.format("[<0.2]"),
                 "pkgb/conanfile.py": pkg.format("[>0.0]"),
                 "app/conanfile.py": GenConanfile().with_requires("pkga/[*]", "pkgb/[*]")})

    client.run("export dep dep/0.1@")
    client.run("export dep dep/0.2@")
    client.run("export tool1 tool/0.1@")
    client.run("export tool2 tool/0.2@")
    client.run("create pkga pkga/0.1@")
    client.run("create pkgb pkgb/0.1@")
    client.run("lock create app/conanfile.py --lockfile-out=conan.lock")

    client.run("export dep dep/0.2@")
    client.run("export tool1 tool/0.3@")
    client.run("export pkga pkga/0.2@")
    client.run("export pkgb pkgb/0.2@")

    client.run("install app/conanfile.py --lockfile=conan.lock")
    assert "pkga/0.1: tool: tool/0.1!!" in client.out
    assert "pkga/0.1: dep: dep/0.1!!" in client.out
    assert "pkgb/0.1: tool: tool/0.2!!" in client.out
    assert "pkgb/0.1: dep: dep/0.2!!" in client.out
