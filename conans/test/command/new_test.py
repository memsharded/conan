import unittest
from conans.test.utils.tools import TestClient
import os
from conans.util.files import load


class NewTest(unittest.TestCase):

    def new_test(self):
        client = TestClient()
        client.run('new MyPackage/1.3@myuser/testing -t')
        root = client.current_folder
        self.assertTrue(os.path.exists(os.path.join(root, "conanfile.py")))
        content = load(os.path.join(root, "conanfile.py"))
        self.assertIn('name = "MyPackage"', content)
        self.assertIn('version = "1.3"', content)
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/conanfile.py")))
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/CMakeLists.txt")))
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/example.cpp")))
        # assert they are correct at least
        client.run("export myuser/testing")
        client.run("info test_package")
        self.assertIn("MyPackage/1.3@myuser/testing", client.user_io.out)

    def new_error_test(self):
        """ packages with short name
        """
        client = TestClient()
        error = client.run('new A/1.3@myuser/testing', ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: 'A' is too short. Valid names must contain at least 2 characters.",
                      client.user_io.out)
        error = client.run('new A2/1.3@myuser/u', ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: 'u' is too short. Valid names must contain at least 2 characters.",
                      client.user_io.out)

    def new_dash_test(self):
        """ packages with dash
        """
        client = TestClient()
        client.run('new My-Package/1.3@myuser/testing -t')
        root = client.current_folder
        self.assertTrue(os.path.exists(os.path.join(root, "conanfile.py")))
        content = load(os.path.join(root, "conanfile.py"))
        self.assertIn('name = "My-Package"', content)
        self.assertIn('version = "1.3"', content)
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/conanfile.py")))
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/CMakeLists.txt")))
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/example.cpp")))
        # assert they are correct at least
        client.run("export myuser/testing")
        client.run("info test_package")
        self.assertIn("My-Package/1.3@myuser/testing", client.user_io.out)

    def new_header_test(self):
        client = TestClient()
        client.run('new MyPackage/1.3@myuser/testing -t -i')
        root = client.current_folder
        self.assertTrue(os.path.exists(os.path.join(root, "conanfile.py")))
        content = load(os.path.join(root, "conanfile.py"))
        self.assertIn('name = "MyPackage"', content)
        self.assertIn('version = "1.3"', content)
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/conanfile.py")))
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/CMakeLists.txt")))
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/example.cpp")))
        # assert they are correct at least
        client.run("export myuser/testing")
        client.run("info test_package")
        self.assertIn("MyPackage/1.3@myuser/testing", client.user_io.out)

    def new_sources_test(self):
        client = TestClient()
        client.run('new MyPackage/1.3@myuser/testing -t -s')
        root = client.current_folder
        self.assertTrue(os.path.exists(os.path.join(root, "conanfile.py")))
        content = load(os.path.join(root, "conanfile.py"))
        self.assertIn('name = "MyPackage"', content)
        self.assertIn('version = "1.3"', content)
        self.assertIn('exports_sources', content)
        self.assertNotIn('source()', content)
        # assert they are correct at least
        client.run("export myuser/testing")
        client.run("info test_package")
        self.assertIn("MyPackage/1.3@myuser/testing", client.user_io.out)

    def new_purec_test(self):
        client = TestClient()
        client.run('new MyPackage/1.3@myuser/testing -c -t')
        root = client.current_folder
        self.assertTrue(os.path.exists(os.path.join(root, "conanfile.py")))
        content = load(os.path.join(root, "conanfile.py"))
        self.assertIn('name = "MyPackage"', content)
        self.assertIn('version = "1.3"', content)
        self.assertIn('del self.settings.compiler.libcxx', content)
        # assert they are correct at least
        client.run("export myuser/testing")
        client.run("info test_package")
        self.assertIn("MyPackage/1.3@myuser/testing", client.user_io.out)

    def new_without_test(self):
        client = TestClient()
        client.run('new MyPackage/1.3@myuser/testing')
        root = client.current_folder
        self.assertTrue(os.path.exists(os.path.join(root, "conanfile.py")))
        self.assertFalse(os.path.exists(os.path.join(root, "test_package/conanfile.py")))
        self.assertFalse(os.path.exists(os.path.join(root, "test_package/CMakeLists.txt")))
        self.assertFalse(os.path.exists(os.path.join(root, "test_package/example.cpp")))

    def new_ci_test(self):
        client = TestClient()
        client.run('new MyPackage/1.3@myuser/testing -cis -ciw -cilg -cilc -cio -ciu=myurl')
        root = client.current_folder
        build_py = load(os.path.join(root, "build.py"))
        self.assertIn('builder.add_common_builds(shared_option_name="MyPackage:shared")',
                      build_py)
        self.assertIn('visual_versions=["12", "14", "15"]', build_py)
        self.assertIn('gcc_versions=["4.9", "5.4", "6.3"]', build_py)
        self.assertIn('apple_clang_versions=["7.3", "8.0", "8.1"]', build_py)
        appveyor = load(os.path.join(root, "appveyor.yml"))
        self.assertIn("CONAN_UPLOAD: myurl", appveyor)
        self.assertIn('CONAN_REFERENCE: "MyPackage/1.3"', appveyor)
        self.assertIn('CONAN_USERNAME: "myuser"', appveyor)
        self.assertIn('CONAN_CHANNEL: "testing"', appveyor)
        self.assertIn('CONAN_CURRENT_PAGE: VisualStudio_15_x86_64', appveyor)

        travis = load(os.path.join(root, ".travis.yml"))
        self.assertIn("- CONAN_UPLOAD: myurl", travis)
        self.assertIn('- CONAN_REFERENCE: "MyPackage/1.3"', travis)
        self.assertIn('- CONAN_USERNAME: "myuser"', travis)
        self.assertIn('- CONAN_CHANNEL: "testing"', travis)
        self.assertIn('env: CONAN_GCC_VERSIONS=5.4 CONAN_CURRENT_PAGE=gcc_54 CONAN_USE_DOCKER=1',
                      travis)

    def new_ci_test_partial(self):
        client = TestClient()
        root = client.current_folder
        error = client.run('new MyPackage/1.3@myuser/testing -cis', ignore_error=True)
        self.assertTrue(error)

        client.run('new MyPackage/1.3@myuser/testing -cil')
        self.assertTrue(os.path.exists(os.path.join(root, "build.py")))
        self.assertTrue(os.path.exists(os.path.join(root, ".travis.yml")))
        self.assertTrue(os.path.exists(os.path.join(root, ".travis/install.sh")))
        self.assertTrue(os.path.exists(os.path.join(root, ".travis/run.sh")))
        self.assertFalse(os.path.exists(os.path.join(root, "appveyor.yml")))

        client = TestClient()
        root = client.current_folder
        client.run('new MyPackage/1.3@myuser/testing -ciw')
        self.assertTrue(os.path.exists(os.path.join(root, "build.py")))
        self.assertFalse(os.path.exists(os.path.join(root, ".travis.yml")))
        self.assertFalse(os.path.exists(os.path.join(root, ".travis/install.sh")))
        self.assertFalse(os.path.exists(os.path.join(root, ".travis/run.sh")))
        self.assertTrue(os.path.exists(os.path.join(root, "appveyor.yml")))

        client = TestClient()
        root = client.current_folder
        client.run('new MyPackage/1.3@myuser/testing -cio')
        self.assertTrue(os.path.exists(os.path.join(root, "build.py")))
        self.assertTrue(os.path.exists(os.path.join(root, ".travis.yml")))
        self.assertTrue(os.path.exists(os.path.join(root, ".travis/install.sh")))
        self.assertTrue(os.path.exists(os.path.join(root, ".travis/run.sh")))
        self.assertFalse(os.path.exists(os.path.join(root, "appveyor.yml")))
