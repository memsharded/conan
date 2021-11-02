import textwrap
import unittest


import pytest

from conans.test.utils.tools import TestClient, GenConanfile


class OptionsTest(unittest.TestCase):

    def test_general_scope_options_test_package(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                options = {"shared": ["1", "2"]}
                def configure(self):
                    self.output.info("BUILD SHARED: %s" % self.options.shared)
            """)
        test = GenConanfile().with_test("pass")
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@user/testing -o *:shared=1")
        self.assertIn("Pkg/0.1@user/testing: BUILD SHARED: 1", client.out)
        client.run("create . Pkg/0.1@user/testing -o shared=2")
        self.assertIn("Pkg/0.1@user/testing: BUILD SHARED: 2", client.out)
        # With test_package
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test})
        client.run("create . Pkg/0.1@user/testing -o *:shared=1")
        self.assertIn("Pkg/0.1@user/testing: BUILD SHARED: 1", client.out)
        client.run("create . Pkg/0.1@user/testing -o Pkg:shared=2")
        self.assertIn("Pkg/0.1@user/testing: BUILD SHARED: 2", client.out)
        client.run("create . Pkg/0.1@user/testing -o shared=1")
        self.assertIn("Pkg/0.1@user/testing: BUILD SHARED: 1", client.out)

    def test_general_scope_options_test_package_notdefined(self):
        client = TestClient()
        conanfile = GenConanfile()
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@user/testing -o *:shared=True")
        self.assertIn("Pkg/0.1@user/testing: Calling build()", client.out)
        client.run("create . Pkg/0.1@user/testing -o shared=False", assert_error=True)
        self.assertIn("option 'shared' doesn't exist", client.out)
        # With test_package
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": GenConanfile().with_test("pass")})
        client.run("create . Pkg/0.1@user/testing -o *:shared=True")
        self.assertIn("Pkg/0.1@user/testing: Calling build()", client.out)
        self.assertIn("Pkg/0.1@user/testing (test package): Calling build()", client.out)

    def test_general_scope_priorities(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                options = {"shared": ["1", "2", "3"], "other": [4, 5, 6]}
                def configure(self):
                    self.output.info("BUILD SHARED: %s OTHER: %s"
                                     % (self.options.shared, self.options.other))
            """)
        client.save({"conanfile.py": conanfile})
        # Consumer has priority
        client.run("create . pkg/0.1@ -o *:shared=1 -o shared=2 -o p*:other=4")
        self.assertIn("pkg/0.1: BUILD SHARED: 2 OTHER: 4", client.out)
        # Consumer has priority over pattern, even if the pattern specifies the package name
        client.run("create . pkg/0.1@ -o *:shared=1 -o pkg:shared=2 -o shared=3 -o p*:other=4")
        self.assertIn("pkg/0.1: BUILD SHARED: 3 OTHER: 4", client.out)
        client.run("create . pkg/0.1@ -o pkg:shared=2 -o p*:other=4 -o pk*:other=5")
        self.assertIn("pkg/0.1: BUILD SHARED: 2 OTHER: 5", client.out)

        # With test_package
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": GenConanfile().with_test("pass")})
        # Sorted (longest, alphabetical) patterns, have priority
        client.run("create . pkg/0.1@ -o *:shared=1 -o pkg:shared=2 -o other=4")
        self.assertIn("pkg/0.1: BUILD SHARED: 2 OTHER: 4", client.out)
        client.run("create . pkg/0.1@ -o pk*:shared=2 -o p*:shared=1 -o pkg:other=5")
        self.assertIn("pkg/0.1: BUILD SHARED: 1 OTHER: 5", client.out)
        client.run("create . pkg/0.1@ -o pk*:shared=2 -o p*:shared=1 -o pkg:other=5 -o *g:other=6")
        self.assertIn("pkg/0.1: BUILD SHARED: 1 OTHER: 6", client.out)

    def test_parsing(self):
        client = TestClient()
        conanfile = '''
from conans import ConanFile
class EqualerrorConan(ConanFile):
    name = "equal"
    version = "1.0.0"
    options = {"opt": "ANY"}
    default_options = {"opt": "b=c"}

    def build(self):
        self.output.warning("OPTION %s" % self.options.opt)
'''
        client.save({"conanfile.py": conanfile})
        client.run("export . user/testing")
        conanfile = '''
[requires]
equal/1.0.0@user/testing
[options]
equal:opt=a=b
'''
        client.save({"conanfile.txt": conanfile}, clean_first=True)
        client.run("install . --build=missing")
        self.assertIn("OPTION a=b", client.out)

    def test_general_scope_options(self):
        # https://github.com/conan-io/conan/issues/2538
        client = TestClient()
        conanfile_liba = textwrap.dedent("""
            from conans import ConanFile
            class LibA(ConanFile):
                options = {"shared": [True, False]}

                def configure(self):
                    self.output.info("shared=%s" % self.options.shared)
                """)
        client.save({"conanfile.py": conanfile_liba})
        client.run("create . libA/0.1@danimtb/testing -o *:shared=True")
        self.assertIn("libA/0.1@danimtb/testing: shared=True", client.out)

        conanfile_libb = textwrap.dedent("""
            from conans import ConanFile
            class LibB(ConanFile):
                options = {"shared": [True, False]}
                requires = "libA/0.1@danimtb/testing"

                def configure(self):
                    self.options["*"].shared = self.options.shared
                    self.output.info("shared=%s" % self.options.shared)
                """)

        for without_configure_line in [True, False]:
            if without_configure_line:
                conanfile = conanfile_libb.replace("self.options[", "#")
            else:
                conanfile = conanfile_libb
            client.save({"conanfile.py": conanfile})

            # Test info
            client.run("info . -o *:shared=True")
            self.assertIn("conanfile.py: shared=True", client.out)
            self.assertIn("libA/0.1@danimtb/testing: shared=True", client.out)
            # Test create
            client.run("create . libB/0.1@danimtb/testing -o *:shared=True")
            self.assertIn("libB/0.1@danimtb/testing: shared=True", client.out)
            self.assertIn("libA/0.1@danimtb/testing: shared=True", client.out)
            # Test install
            client.run("install . -o *:shared=True")
            self.assertIn("conanfile.py: shared=True", client.out)
            self.assertIn("libA/0.1@danimtb/testing: shared=True", client.out)

    @pytest.mark.xfail(reason="info.shared_library_package_id() to be removed")
    def test_overridable_shared_option(self):
        client = TestClient()
        conanfile = GenConanfile().with_option("shared", [True, False])\
                                  .with_default_option("shared", "False")
        client.save({"conanfile.py": conanfile})
        client.run("create . liba/0.1@user/testing -o liba:shared=False")
        client.run("create . liba/0.1@user/testing -o liba:shared=True")
        consumer = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                requires = "liba/0.1@user/testing"
                options = {"shared": [True, False]}
                default_options = {"shared": False}
                def configure(self):
                    if self.options.shared:
                        self.options["*"].shared = True

                def package_id(self):
                    self.info.shared_library_package_id()
        """)
        client.save({"conanfile.py": consumer})

        # LibA STATIC
        for options in ("",
                        "-o pkg:shared=False",
                        "-o liba:shared=False",
                        "-o pkg:shared=True  -o liba:shared=False",
                        "-o pkg:shared=False -o liba:shared=False"):
            client.run("create . pkg/0.1@user/testing %s" % options)
            self.assertIn("liba/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache",
                          client.out)

        # LibA SHARED
        for options in ("-o pkg:shared=True",
                        "-o pkg:shared=True -o liba:shared=True",
                        "-o pkg:shared=False -o liba:shared=True"):
            client.run("create . pkg/0.1@user/testing %s" % options)
            self.assertIn("liba/0.1@user/testing:2a623e3082a38f90cd2c3d12081161412de331b0 - Cache",
                          client.out)

        # Pkg STATIC
        for options in ("",
                        "-o pkg:shared=False",
                        "-o liba:shared=False",
                        "-o liba:shared=True",
                        "-o pkg:shared=False  -o liba:shared=False",
                        "-o pkg:shared=False -o liba:shared=False"):
            client.run("create . pkg/0.1@user/testing %s" % options)
            self.assertIn("pkg/0.1@user/testing:c74ab38053f265e63a1f3d819a41bc4b8332a6fc - Build",
                          client.out)

        # Pkg SHARED, libA SHARED
        for options in ("-o pkg:shared=True",
                        "-o pkg:shared=True  -o liba:shared=True"):
            client.run("create . pkg/0.1@user/testing %s" % options)
            self.assertIn("pkg/0.1@user/testing:fcaf52c0d66c3d68e6b6ae6330acafbcaae7dacf - Build",
                          client.out)

        # Pkg SHARED, libA STATIC
        options = "-o pkg:shared=True  -o liba:shared=False"
        client.run("create . pkg/0.1@user/testing %s" % options)
        self.assertIn("pkg/0.1@user/testing:bf0155900ebfab70eaba45bb209cb719e180e3a4 - Build",
                      client.out)

    @pytest.mark.xfail(reason="info.shared_library_package_id() to be removed")
    def test_overridable_no_shared_option(self):
        client = TestClient()
        conanfile = GenConanfile()
        client.save({"conanfile.py": conanfile})
        client.run("create . liba/0.1@user/testing")
        consumer = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                requires = "liba/0.1@user/testing"
                options = {"shared": [True, False]}
                default_options = {"shared": False}
                def configure(self):
                    if self.options.shared:
                        self.options["*"].shared = True

                def package_id(self):
                    self.info.shared_library_package_id()
        """)
        client.save({"conanfile.py": consumer})
        # LibA STATIC
        for options in ("",
                        "-o pkg:shared=False",
                        "-o pkg:shared=True"):
            client.run("create . pkg/0.1@user/testing %s" % options)
            self.assertIn("liba/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache",
                          client.out)

    @pytest.mark.xfail(reason="info.shared_library_package_id() to be removed")
    def test_missing_shared_option_package_id(self):
        client = TestClient()

        consumer = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                def package_id(self):
                    self.info.shared_library_package_id()
            """)
        client.save({"conanfile.py": consumer})
        client.run("create . pkg/0.1@user/testing")
        self.assertIn("pkg/0.1@user/testing: Created package ", client.out)
