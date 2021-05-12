import os
import textwrap
import unittest

from parameterized.parameterized import parameterized

from conans.client.tools.files import replace_in_file
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, TestServer, GenConanfile


class ConanAliasTest(unittest.TestCase):

    def test_alias_different_name(self):
        client = TestClient()
        client.run("alias myalias/1.0@user/channel lib/1.0@user/channel", assert_error=True)
        self.assertIn("An alias can only be defined to a package with the same name",
                      client.out)

    def test_repeated_alias(self):
        client = TestClient()
        client.run("alias Hello/0.X@lasote/channel Hello/0.1@lasote/channel")
        client.run("alias Hello/0.X@lasote/channel Hello/0.2@lasote/channel")
        client.run("alias Hello/0.X@lasote/channel Hello/0.3@lasote/channel")

    def test_existing_python_requires(self):
        # https://github.com/conan-io/conan/issues/8702
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . test-python-requires/0.1@user/testing")
        client.save({"conanfile.py": """from conans import ConanFile
class Pkg(ConanFile):
    python_requires = 'test-python-requires/0.1@user/testing'"""})
        client.run("create . Pkg/0.1@user/testing")
        client.run("alias Pkg/0.1@user/testing Pkg/0.2@user/testing", assert_error=True)
        self.assertIn("ERROR: Reference 'Pkg/0.1@user/testing' is already a package",
                      client.out)

    def test_not_override_package(self):
        """ Do not override a package with an alias

            If we create an alias with the same name as an existing package, it will
            override the package without any warning.
        """
        t = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                description = "{}"
            """)

        # Create two packages
        reference1 = "PkgA/0.1@user/testing"
        t.save({"conanfile.py": conanfile.format(reference1)})
        t.run("export . {}".format(reference1))

        reference2 = "PkgA/0.2@user/testing"
        t.save({"conanfile.py": conanfile.format(reference2)})
        t.run("export . {}".format(reference2))

        # Now create an alias overriding one of them
        alias = reference2
        t.run("alias {alias} {reference}".format(alias=alias, reference=reference1),
              assert_error=True)
        self.assertIn("ERROR: Reference '{}' is already a package".format(alias), t.out)

        # Check that the package is not damaged
        t.run("inspect {} -a description".format(reference2))
        self.assertIn("description: {}".format(reference2), t.out)

        # Remove it, and create the alias again (twice, override an alias is allowed)
        t.run("remove {} -f".format(reference2))
        t.run("alias {alias} {reference}".format(alias=alias, reference=reference1))
        t.run("alias {alias} {reference}".format(alias=alias, reference=reference1))

        t.run("inspect {} -a description".format(reference2))
        self.assertIn("description: None", t.out)  # The alias conanfile doesn't have description
