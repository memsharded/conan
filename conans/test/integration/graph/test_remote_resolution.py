import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_build_requires_ranges():
    # app -> pkga ----------> pkgb ------------> pkgc
    #          \-cmake/[*]     \ -cmake/1.0        \-cmake/[*]
    # The resolution of cmake/[*] is invariant, it will always resolved to cmake/0.5, not
    # one to cmake/0.5 and the next one to cmake/1.0 because in between there was an explicit
    # dependency to cmake/1.0
    client = TestClient(default_server_user=True)
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . cmake/0.5@")
    client.run("create . cmake/1.0@")
    client.run("upload cmake/1.0* -c --all -r default")
    client.run("remove cmake/1.0* -f")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            {}
            build_requires = "cmake/{}"
            def generate(self):
                for r, d in self.dependencies.items():
                    self.output.info("REQUIRE {{}}: {{}}".format(r.ref, d))
                dep = self.dependencies.get("cmake", build=True, run=True)
                self.output.info("CMAKEVER: {{}}!!".format(dep.ref.version))
            """)
    client.save({"pkgc/conanfile.py": conanfile.format("", "[*]"),
                 "pkgb/conanfile.py": conanfile.format("requires = 'pkgc/1.0'", "1.0"),
                 "pkga/conanfile.py": conanfile.format("requires = 'pkgb/1.0'", "[*]"),
                 })
    client.run("export pkgc pkgc/1.0@")
    client.run("export pkgb pkgb/1.0@")
    client.run("export pkga pkga/1.0@")

    client.run("install pkga/1.0@ --build=missing")
    assert "pkgc/1.0: REQUIRE cmake/0.5: cmake/0.5" in client.out
    assert "pkgc/1.0: CMAKEVER: 0.5!!" in client.out
    assert "pkgb/1.0: REQUIRE cmake/1.0: cmake/1.0" in client.out
    assert "pkgb/1.0: CMAKEVER: 1.0!!" in client.out
    assert "pkga/1.0: REQUIRE cmake/0.5: cmake/0.5" in client.out
    assert "pkga/1.0: CMAKEVER: 0.5!!" in client.out
