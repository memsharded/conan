import os
import platform
import textwrap
import unittest

import pytest
from parameterized.parameterized import parameterized

from conan.tools.env.environment import environment_wrap_command
from conans.model.ref import ConanFileReference
from conans.paths import CONANFILE
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.tools import TestClient, GenConanfile
from conans.util.files import save


@pytest.fixture()
def client():
    openssl = textwrap.dedent(r"""
        import os
        from conans import ConanFile
        from conans.tools import save, chdir
        class Pkg(ConanFile):
            settings = "os"
            #options = {"shared": [True, False]}
            #default_options = {"shared": True}
            def package(self):
                with chdir(self.package_folder):
                    echo = "@echo off\necho MYOPENSSL={}!!".format(self.settings.os)
                    save("bin/myopenssl.bat", echo)
                    save("bin/myopenssl.sh", echo)
                    os.chmod("bin/myopenssl.sh", 0o777)
            """)

    cmake = textwrap.dedent(r"""
        import os
        from conans import ConanFile
        from conans.tools import save, chdir
        class Pkg(ConanFile):
            settings = "os"
            def requirements(self):
                self.requires("openssl/1.0", run=True)
            def package(self):
                with chdir(self.package_folder):
                    echo = "@echo off\necho MYCMAKE={}!!".format(self.settings.os)
                    save("mycmake.bat", echo + "\ncall myopenssl.bat")
                    save("mycmake.sh", echo + "\n myopenssl.sh")
                    os.chmod("mycmake.sh", 0o777)

            def package_info(self):
                # Custom buildenv not defined by cpp_info
                self.buildenv_info.prepend_path("PATH", self.package_folder)
                self.buildenv_info.define("MYCMAKEVAR", "MYCMAKEVALUE!!")
            """)

    gtest = textwrap.dedent(r"""
        import os
        from conans import ConanFile
        from conans.tools import save, chdir
        class Pkg(ConanFile):
            settings = "os"
            def package(self):
                with chdir(self.package_folder):
                    echo = "@echo off\necho MYGTEST={}!!".format(self.settings.os)
                    save("bin/mygtest.bat", echo)
                    save("bin/mygtest.sh", echo)
                    os.chmod("bin/mygtest.sh", 0o777)

            def package_info(self):
                self.runenv_info.define("MYGTESTVAR", "MyGTestValue{}".format(self.settings.os))
            """)
    client = TestClient()
    save(client.cache.default_profile_path, "[settings]\nos=Windows")
    save(client.cache.new_config_path, "tools.env.virtualenv:auto_use=True")
    client.save({"cmake/conanfile.py": cmake,
                 "gtest/conanfile.py": gtest,
                 "openssl/conanfile.py": openssl})

    client.run("create openssl openssl/1.0@")
    client.run("create cmake mycmake/1.0@")
    client.run("create gtest mygtest/1.0@")

    myrunner_bat = "@echo off\necho MYGTESTVAR=%MYGTESTVAR%!!\n"
    myrunner_sh = "echo MYGTESTVAR=$MYGTESTVAR!!\n"
    client.save({"myrunner.bat": myrunner_bat,
                 "myrunner.sh": myrunner_sh}, clean_first=True)
    os.chmod(os.path.join(client.current_folder, "myrunner.sh"), 0o777)
    return client


@pytest.mark.xfail(reason="Winbash is broken for multi-profile. Ongoing https://github.com/conan-io/conan/pull/9755")
def test_conanfile_txt(client):
    # conanfile.txt -(br)-> cmake
    client.save({"conanfile.txt": "[build_requires]\nmycmake/1.0"}, clean_first=True)
    client.run("install . -s:b os=Windows -s:h os=Linux")

    assert "mycmake/1.0" in client.out
    assert "openssl/1.0" in client.out
    ext = "bat" if platform.system() == "Windows" else "sh"  # TODO: Decide on logic .bat vs .sh
    cmd = environment_wrap_command(ConanFileMock(), "conanbuildenv", "mycmake.{}".format(ext),
                                   cwd=client.current_folder)
    client.run_command(cmd)

    assert "MYCMAKE=Windows!!" in client.out
    assert "MYOPENSSL=Windows!!" in client.out


@pytest.mark.xfail(reason="Winbash is broken for multi-profile. Ongoing https://github.com/conan-io/conan/pull/9755")
def test_complete(client):
    conanfile = textwrap.dedent("""
        import platform
        from conans import ConanFile
        class Pkg(ConanFile):
            requires = "openssl/1.0"
            build_requires = "mycmake/1.0"
            apply_env = False

            def build_requirements(self):
                self.test_requires("mygtest/1.0")

            def build(self):
                mybuild_cmd = "mycmake.bat" if platform.system() == "Windows" else "mycmake.sh"
                self.run(mybuild_cmd)
                mytest_cmd = "mygtest.bat" if platform.system() == "Windows" else "mygtest.sh"
                self.run(mytest_cmd, env="conanrunenv")
       """)

    client.save({"conanfile.py": conanfile})
    client.run("install . -s:b os=Windows -s:h os=Linux --build=missing")
    # Run the BUILD environment
    ext = "bat" if platform.system() == "Windows" else "sh"  # TODO: Decide on logic .bat vs .sh
    cmd = environment_wrap_command(ConanFileMock(), "conanbuildenv", "mycmake.{}".format(ext),
                                   cwd=client.current_folder)
    client.run_command(cmd)
    assert "MYCMAKE=Windows!!" in client.out
    assert "MYOPENSSL=Windows!!" in client.out

    # Run the RUN environment
    cmd = environment_wrap_command(ConanFileMock(), "conanrunenv",
                                   "mygtest.{ext} && .{sep}myrunner.{ext}".format(ext=ext,
                                                                                  sep=os.sep),
                                   cwd=client.current_folder)
    client.run_command(cmd)
    assert "MYGTEST=Linux!!" in client.out
    assert "MYGTESTVAR=MyGTestValueLinux!!" in client.out

    client.run("build . -s:b os=Windows -s:h os=Linux")
    assert "MYCMAKE=Windows!!" in client.out
    assert "MYOPENSSL=Windows!!" in client.out
    assert "MYGTEST=Linux!!" in client.out


tool_conanfile = """from conans import ConanFile

class Tool(ConanFile):
    name = "Tool"
    version = "0.1"

    def package_info(self):
        self.buildenv_info.define_path("TOOL_PATH", "MyToolPath")
"""

tool_conanfile2 = tool_conanfile.replace("0.1", "0.3")

conanfile = """
import os
from conans import ConanFile, tools
from conan.tools.env import VirtualBuildEnv

class MyLib(ConanFile):
    name = "MyLib"
    version = "0.1"
    {}

    def build(self):
        build_env = VirtualBuildEnv(self).vars()
        with build_env.apply():
            self.output.info("ToolPath: %s" % os.getenv("TOOL_PATH"))
"""

requires = conanfile.format('build_requires = "Tool/0.1@lasote/stable"')
requires_range = conanfile.format('build_requires = "Tool/[>0.0]@lasote/stable"')
requirements = conanfile.format("""def build_requirements(self):
        self.build_requires("Tool/0.1@lasote/stable")""")
override = conanfile.format("""build_requires = "Tool/0.2@user/channel"

    def build_requirements(self):
        self.build_requires("Tool/0.1@lasote/stable")""")


profile = """
[build_requires]
Tool/0.3@lasote/stable
nonexistingpattern*: SomeTool/1.2@user/channel
"""


@pytest.mark.xfail(reason="Legacy tests with wrong propagation asumptions")
class BuildRequiresTest(unittest.TestCase):

    def test_consumer(self):
        # https://github.com/conan-io/conan/issues/5425
        catch_ref = ConanFileReference.loads("catch/0.1@user/testing")
        libA_ref = ConanFileReference.loads("LibA/0.1@user/testing")

        t = TestClient()
        t.save({"conanfile.py":
                    GenConanfile().with_package_info(cpp_info={"libs": ["mylibcatch0.1lib"]},
                                                     env_info={"MYENV": ["myenvcatch0.1env"]})})
        t.run("create . catch/0.1@user/testing")
        t.save({"conanfile.py": GenConanfile().with_requirement(catch_ref, private=True)})
        print(t.load("conanfile.py"))
        t.run("create . LibA/0.1@user/testing")
        t.save({"conanfile.py": GenConanfile().with_require(libA_ref)
                                              .with_build_requires(catch_ref)})
        t.run("install .")
        self.assertIn("catch/0.1@user/testing from local cache", t.out)
        self.assertIn("catch/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Skip",
                      t.out)
        self.assertIn("catch/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache",
                      t.out)

    def test_build_requires_diamond(self):
        libA_ref = ConanFileReference.loads("libA/0.1@user/testing")
        libB_ref = ConanFileReference.loads("libB/0.1@user/testing")

        t = TestClient()
        t.save({"conanfile.py": GenConanfile()})
        t.run("create . libA/0.1@user/testing")

        t.save({"conanfile.py": GenConanfile().with_require(libA_ref)})
        t.run("create . libB/0.1@user/testing")

        t.save({"conanfile.py": GenConanfile().with_build_requires(libB_ref)
                                              .with_build_requires(libA_ref)})
        t.run("create . libC/0.1@user/testing")
        self.assertIn("libC/0.1@user/testing: Created package", t.out)

    def test_create_with_tests_and_build_requires(self):
        client = TestClient()
        # Generate and export the build_require recipe
        conanfile1 = """from conans import ConanFile
class MyBuildRequire(ConanFile):
    def package_info(self):
        self.buildenv_info.define("MYVAR", "1")
"""
        client.save({"conanfile.py": conanfile1})
        client.run("create . Build1/0.1@conan/stable")
        conanfile2 = """from conans import ConanFile
class MyBuildRequire(ConanFile):
    def package_info(self):
        self.buildenv_info.define("MYVAR2", "2")
"""
        client.save({"conanfile.py": conanfile2})
        client.run("create . Build2/0.1@conan/stable")

        # Create a recipe that will use a profile requiring the build_require
        client.save({"conanfile.py": """
from conan.tools.env import VirtualBuildEnv
from conans import ConanFile
import os

class MyLib(ConanFile):
    build_requires = "Build2/0.1@conan/stable"
    def build(self):
        build_env = VirtualBuildEnv(self).vars()
        with build_env.apply():
            assert(os.environ['MYVAR']=='1')
            assert(os.environ['MYVAR2']=='2')

""", "myprofile": '''
[build_requires]
Build1/0.1@conan/stable
''',
                    "test_package/conanfile.py": """from conans import ConanFile
import os
from conan.tools.env import VirtualBuildEnv
class MyTest(ConanFile):
    def build(self):
        build_env = VirtualBuildEnv(self).vars()
        with build_env.apply():
            assert(os.environ['MYVAR']=='1')
    def test(self):
        self.output.info("TESTING!!!")
"""}, clean_first=True)

        # Test that the build require is applyed to testing
        client.run("create . Lib/0.1@conan/stable --profile=./myprofile")
        self.assertEqual(1, str(client.out).count("Lib/0.1@conan/stable: "
                                                  "Applying build-requirement:"
                                                  " Build1/0.1@conan/stable"))
        self.assertIn("TESTING!!", client.out)

    def test_dependents(self):
        client = TestClient()
        boost = """from conans import ConanFile
class Boost(ConanFile):
    def package_info(self):
        self.buildenv_info.define_path("PATH", "myboostpath")
"""
        client.save({CONANFILE: boost})
        client.run("create . Boost/1.0@user/channel")
        other = """[build_requires]
Boost/1.0@user/channel
"""
        client.save({"conanfile.txt": other}, clean_first=True)
        client.run("install .")

        self.assertIn("""Build requirements
    Boost/1.0@user/channel""", client.out)

        other = """from conans import ConanFile
import os
class Other(ConanFile):
    requires = "Boost/1.0@user/channel"
    def build(self):
        self.output.info("OTHER PATH FOR BUILD %s" % os.getenv("PATH"))
    def package_info(self):
        self.env_info.PATH.append("myotherpath")
"""
        client.save({CONANFILE: other})
        client.run("create . Other/1.0@user/channel")
        lib = """from conans import ConanFile
import os
class Lib(ConanFile):
    build_requires = "Boost/1.0@user/channel", "Other/1.0@user/channel"
    def build(self):
        self.output.info("LIB PATH FOR BUILD %s" % os.getenv("PATH"))
"""
        client.save({CONANFILE: lib})
        client.run("create . Lib/1.0@user/channel")
        self.assertIn("LIB PATH FOR BUILD myotherpath%smyboostpath" % os.pathsep,
                      client.out)

    def test_applyname(self):
        # https://github.com/conan-io/conan/issues/4135
        client = TestClient()
        mingw = """from conans import ConanFile
class Tool(ConanFile):
    def package_info(self):
        self.buildenv_info.define_path("PATH", "mymingwpath")
"""
        myprofile = """
[build_requires]
consumer*: mingw/0.1@myuser/stable
"""
        app = """from conans import ConanFile
from conan.tools.env import VirtualBuildEnv
import os
class App(ConanFile):
    name = "consumer"
    def build(self):
        build_env = VirtualBuildEnv(self).vars()
        with build_env.apply():
            self.output.info("APP PATH FOR BUILD %s" % os.getenv("PATH"))
"""
        client.save({CONANFILE: mingw})
        client.run("create . mingw/0.1@myuser/stable")
        client.save({CONANFILE: app,
                     "myprofile": myprofile})
        client.run("build . -pr=myprofile")
        self.assertIn("conanfile.py (consumer/None): Applying build-requirement: "
                      "mingw/0.1@myuser/stable", client.out)
        self.assertIn("conanfile.py (consumer/None): APP PATH FOR BUILD mymingwpath",
                      client.out)

    def test_transitive(self):
        client = TestClient()
        mingw = """from conans import ConanFile
class Tool(ConanFile):
    def package_info(self):
        self.buildenv_info.append("MYVAR", "mymingwpath")
"""
        myprofile = """
[build_requires]
mingw/0.1@lasote/stable
"""
        gtest = """from conans import ConanFile
from conan.tools.env import VirtualBuildEnv
import os
class Gtest(ConanFile):
    def build(self):
        build_env = VirtualBuildEnv(self).vars()
        with build_env.apply():
            self.output.info("GTEST PATH FOR BUILD %s" % os.getenv("MYVAR"))
"""
        app = """from conans import ConanFile
from conan.tools.env import VirtualBuildEnv
import os
class App(ConanFile):
    build_requires = "gtest/0.1@lasote/stable"
    def build(self):
        build_env = VirtualBuildEnv(self).vars()
        with build_env.apply():
            self.output.info("APP PATH FOR BUILD %s" % os.getenv("MYVAR"))
"""
        client.save({CONANFILE: mingw})
        client.run("create . mingw/0.1@lasote/stable")
        client.save({CONANFILE: gtest})
        client.run("export . gtest/0.1@lasote/stable")
        client.save({CONANFILE: app,
                     "myprofile": myprofile})
        client.run("create . app/0.1@lasote/stable --build=missing -pr=myprofile -pr:b=myprofile")
        self.assertIn("app/0.1@lasote/stable: APP PATH FOR BUILD mymingwpath",
                      client.out)
        self.assertIn("gtest/0.1@lasote/stable: GTEST PATH FOR BUILD mymingwpath",
                      client.out)

    def test_profile_order(self):
        client = TestClient()
        mingw = """from conans import ConanFile
class Tool(ConanFile):
    def package_info(self):
        self.buildenv_info.append("MYVAR", "mymingwpath")
"""
        msys = """from conans import ConanFile
class Tool(ConanFile):
    def package_info(self):
        self.buildenv_info.append("MYVAR", "mymsyspath")
"""
        myprofile1 = """
[build_requires]
mingw/0.1@lasote/stable
msys/0.1@lasote/stable
"""
        myprofile2 = """
[build_requires]
msys/0.1@lasote/stable
mingw/0.1@lasote/stable
"""

        app = """from conans import ConanFile
from conan.tools.env import VirtualBuildEnv
import os
class App(ConanFile):
    def build(self):
        build_env = VirtualBuildEnv(self).vars()
        with build_env.apply():
            self.output.info("FOR BUILD %s" % os.getenv("MYVAR"))
"""
        client.save({CONANFILE: mingw})
        client.run("create . mingw/0.1@lasote/stable")
        client.save({CONANFILE: msys})
        client.run("create . msys/0.1@lasote/stable")
        client.save({CONANFILE: app,
                     "myprofile1": myprofile1,
                     "myprofile2": myprofile2})
        client.run("create . app/0.1@lasote/stable -pr=myprofile1")
        # mingw being the first one, has priority and its "append" mandates it is the last appended
        self.assertIn("app/0.1@lasote/stable: FOR BUILD mymsyspath mymingwpath", client.out)
        client.run("create . app/0.1@lasote/stable -pr=myprofile2")
        self.assertIn("app/0.1@lasote/stable: FOR BUILD mymingwpath mymsyspath", client.out)

    def test_require_itself(self):
        client = TestClient()
        mytool_conanfile = """from conans import ConanFile
class Tool(ConanFile):
    def build(self):
        self.output.info("BUILDING MYTOOL")
"""
        myprofile = """
[build_requires]
Tool/0.1@lasote/stable
"""
        client.save({CONANFILE: mytool_conanfile,
                     "profile.txt": myprofile})
        client.run("create . Tool/0.1@lasote/stable -pr=profile.txt")
        self.assertEqual(1, str(client.out).count("BUILDING MYTOOL"))

    @parameterized.expand([(requires, ), (requires_range, ), (requirements, ), (override, )])
    def test_build_requires(self, conanfile):
        client = TestClient()
        client.save({CONANFILE: tool_conanfile})
        client.run("export . lasote/stable")

        client.save({CONANFILE: conanfile}, clean_first=True)
        client.run("export . lasote/stable")

        client.run("install MyLib/0.1@lasote/stable --build missing")
        self.assertIn("Tool/0.1@lasote/stable: Generating the package", client.out)
        self.assertIn("ToolPath: MyToolPath", client.out)

        client.run("install MyLib/0.1@lasote/stable")
        self.assertNotIn("Tool", client.out)
        self.assertIn("MyLib/0.1@lasote/stable: Already installed!", client.out)

    @parameterized.expand([(requires, ), (requires_range, ), (requirements, ), (override, )])
    def test_profile_override(self, conanfile):
        client = TestClient()
        client.save({CONANFILE: tool_conanfile2}, clean_first=True)
        client.run("export . lasote/stable")

        client.save({CONANFILE: conanfile,
                     "profile.txt": profile,
                     "profile2.txt": profile.replace("0.3", "[>0.2]")}, clean_first=True)
        client.run("export . lasote/stable")

        client.run("install MyLib/0.1@lasote/stable --profile ./profile.txt --build missing")
        self.assertNotIn("Tool/0.1", client.out)
        self.assertNotIn("Tool/0.2", client.out)
        self.assertIn("Tool/0.3@lasote/stable: Generating the package", client.out)
        self.assertIn("ToolPath: MyToolPath", client.out)

        client.run("install MyLib/0.1@lasote/stable")
        self.assertNotIn("Tool", client.out)
        self.assertIn("MyLib/0.1@lasote/stable: Already installed!", client.out)

        client.run("install MyLib/0.1@lasote/stable --profile ./profile2.txt --build")
        self.assertNotIn("Tool/0.1", client.out)
        self.assertNotIn("Tool/0.2", client.out)
        self.assertIn("Tool/0.3@lasote/stable: Generating the package", client.out)
        self.assertIn("ToolPath: MyToolPath", client.out)

    def test_options(self):
        conanfile = """from conans import ConanFile
class package(ConanFile):
    name            = "first"
    version         = "0.0.0"
    options         = {"coverage": [True, False]}
    default_options = {"coverage": False}
    def build(self):
        self.output.info("Coverage: %s" % self.options.coverage)
    """
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("export . lasote/stable")

        consumer = """from conans import ConanFile

class package(ConanFile):
    name            = "second"
    version         = "0.0.0"
    default_options = {"first:coverage": True}
    build_requires  = "first/0.0.0@lasote/stable"
"""
        client.save({"conanfile.py": consumer})
        client.run("install . --build=missing -o Pkg:someoption=3")
        self.assertIn("first/0.0.0@lasote/stable: Coverage: True", client.out)

    def test_failed_assert(self):
        # https://github.com/conan-io/conan/issues/5685
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . common/1.0@test/test")

        req = textwrap.dedent("""
            from conans import ConanFile
            class BuildReqConan(ConanFile):
                requires = "common/1.0@test/test"
            """)
        client.save({"conanfile.py": req})
        client.run("export . req/1.0@test/test")
        client.run("export . build_req/1.0@test/test")

        build_req_req = textwrap.dedent("""
            from conans import ConanFile
            class BuildReqConan(ConanFile):
                requires = "common/1.0@test/test"
                build_requires = "build_req/1.0@test/test"
        """)
        client.save({"conanfile.py": build_req_req})
        client.run("export . build_req_req/1.0@test/test")

        consumer = textwrap.dedent("""
                    [requires]
                    req/1.0@test/test
                    [build_requires]
                    build_req_req/1.0@test/test
                """)
        client.save({"conanfile.txt": consumer}, clean_first=True)
        client.run("install . --build=missing")
        # This used to assert and trace, now it works
        self.assertIn("conanfile.txt: Applying build-requirement: build_req_req/1.0@test/test",
                      client.out)

    def test_missing_transitive_dependency(self):
        # https://github.com/conan-io/conan/issues/5682
        client = TestClient()
        zlib = textwrap.dedent("""
            from conans import ConanFile
            class ZlibPkg(ConanFile):
                def package_info(self):
                    self.cpp_info.libs = ["myzlib"]
            """)
        client.save({"conanfile.py": zlib})
        client.run("export . zlib/1.0@test/test")

        client.save({"conanfile.py": GenConanfile().with_require("zlib/1.0@test/test")})
        client.run("export . freetype/1.0@test/test")
        client.save({"conanfile.py": GenConanfile().with_require("freetype/1.0@test/test")})
        client.run("export . fontconfig/1.0@test/test")
        harfbuzz = textwrap.dedent("""
            from conans import ConanFile
            class harfbuzz(ConanFile):
                requires = "freetype/1.0@test/test", "fontconfig/1.0@test/test"
                def build(self):
                     self.output.info("ZLIBS LIBS: %s" %self.deps_cpp_info["zlib"].libs)
            """)
        client.save({"conanfile.py": harfbuzz})
        client.run("export . harfbuzz/1.0@test/test")

        client.save({"conanfile.py": GenConanfile()
                    .with_build_requires("fontconfig/1.0@test/test")
                    .with_build_requires("harfbuzz/1.0@test/test")})
        client.run("install . --build=missing")
        self.assertIn("ZLIBS LIBS: ['myzlib']", client.out)


def test_dependents_new_buildenv():
    client = TestClient()
    boost = textwrap.dedent("""
        from conans import ConanFile
        class Boost(ConanFile):
            def package_info(self):
                self.buildenv_info.define_path("PATH", "myboostpath")
        """)
    other = textwrap.dedent("""
        from conans import ConanFile
        class Other(ConanFile):
            def requirements(self):
                self.requires("boost/1.0")

            def package_info(self):
                self.buildenv_info.append_path("PATH", "myotherpath")
                self.buildenv_info.prepend_path("PATH", "myotherprepend")
        """)
    consumer = textwrap.dedent("""
       from conans import ConanFile
       from conan.tools.env import VirtualBuildEnv
       import os
       class Lib(ConanFile):
           requires = {}
           def generate(self):
               build_env = VirtualBuildEnv(self).vars()
               with build_env.apply():
                   self.output.info("LIB PATH %s" % os.getenv("PATH"))
       """)
    client.save({"boost/conanfile.py": boost,
                 "other/conanfile.py": other,
                 "consumer/conanfile.py": consumer.format('"boost/1.0", "other/1.0"'),
                 "profile_define": "[buildenv]\nPATH=(path)profilepath",
                 "profile_append": "[buildenv]\nPATH+=(path)profilepath",
                 "profile_prepend": "[buildenv]\nPATH=+(path)profilepath"})
    client.run("create boost boost/1.0@")
    client.run("create other other/1.0@")
    client.run("install consumer")
    result = os.pathsep.join(["myotherprepend", "myboostpath", "myotherpath"])
    assert "LIB PATH {}".format(result) in client.out

    # Now test if we declare in different order, still topological order should be respected
    client.save({"consumer/conanfile.py": consumer.format('"other/1.0", "boost/1.0"')})
    client.run("install consumer")
    assert "LIB PATH {}".format(result) in client.out

    client.run("install consumer -pr=profile_define")
    assert "LIB PATH profilepath" in client.out
    client.run("install consumer -pr=profile_append")
    result = os.pathsep.join(["myotherprepend", "myboostpath", "myotherpath", "profilepath"])
    assert "LIB PATH {}".format(result) in client.out
    client.run("install consumer -pr=profile_prepend")
    result = os.pathsep.join(["profilepath", "myotherprepend", "myboostpath", "myotherpath"])
    assert "LIB PATH {}".format(result) in client.out
