
import json
import os
import textwrap

import pytest


from conan.internal.workspace import Workspace
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.scm import create_local_git_repo
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conans.util.files import save


Workspace.TEST_ENABLED = "will_break_next"


class TestHomeRoot:
    @pytest.mark.parametrize("ext, content", [("py", "home_folder = 'myhome'"),
                                              ("yml", "home_folder: myhome")])
    def test_workspace_home(self, ext, content):
        folder = temp_folder()
        cwd = os.path.join(folder, "sub1", "sub2")
        save(os.path.join(folder, f"conanws.{ext}"), content)
        c = TestClient(current_folder=cwd, light=True)

        c.run("config home")
        assert os.path.join(folder, "myhome") in c.stdout

    def test_workspace_home_user_py(self):
        folder = temp_folder()
        cwd = os.path.join(folder, "sub1", "sub2")
        conanwspy = textwrap.dedent("""
            def home_folder():
                return "new" + conanws_data["home_folder"]
            """)
        save(os.path.join(folder, f"conanws.py"), conanwspy)
        save(os.path.join(folder, "conanws.yml"), "home_folder: myhome")
        c = TestClient(current_folder=cwd, light=True)
        c.run("config home")
        assert os.path.join(folder, "newmyhome") in c.stdout

    def test_workspace_root(self):
        c = TestClient(light=True)
        # Just check the root command works
        c.run("workspace root", assert_error=True)
        assert "ERROR: No workspace defined, conanws.py file not found" in c.out
        c.save({"conanws.py": ""})
        c.run("workspace root")
        assert c.current_folder in c.stdout

        c.save({"conanws.yml": ""}, clean_first=True)
        c.run("workspace root")
        assert c.current_folder in c.stdout


class TestAddRemove:

    def test_add(self):
        c = TestClient(light=True)
        c.save({"conanws.py": "name='myws'",
                "dep1/conanfile.py": GenConanfile("dep1", "0.1"),
                "dep2/conanfile.py": GenConanfile("dep2", "0.1"),
                "dep3/conanfile.py": GenConanfile("dep3", "0.1")})
        c.run("workspace add dep1")
        assert "Reference 'dep1/0.1' added to workspace" in c.out
        c.run("workspace info")
        assert "dep1/0.1" in c.out
        assert "dep2" not in c.out
        c.run("editable list")  # No editables in global
        assert "dep1" not in c.out
        assert "dep2" not in c.out
        c.run("workspace add dep2")
        assert "Reference 'dep2/0.1' added to workspace" in c.out
        c.run("workspace info")
        assert "dep1/0.1" in c.out
        assert "dep2/0.1" in c.out

        with c.chdir(temp_folder()):  # If we move to another folder, outside WS, no editables
            c.run("editable list")
            assert "dep1" not in c.out
            assert "dep2" not in c.out

        c.run("workspace info")
        assert "dep1/0.1" in c.out
        assert "dep2/0.1" in c.out

        c.run("workspace remove dep1")
        c.run("workspace info")
        assert "dep1/0.1" not in c.out
        assert "dep2/0.1" in c.out

        c.run("workspace remove dep2")
<<<<<<< HEAD
        c.run("editable list")
        assert "dep1/0.1" not in c.out
        assert "dep2/0.1" not in c.out


class TestOpenAdd:
    def test_without_git(self):
        t = TestClient(default_server_user=True)
=======
        c.run("workspace info")
        assert "dep1/0.1" not in c.out
        assert "dep2/0.1" not in c.out

    def test_add_from_outside(self):
        c = TestClient(light=True)
        c.save({"sub/conanws.py": "name='myws'",
                "sub/dep1/conanfile.py": GenConanfile("dep1", "0.1"),
                "sub/dep2/conanfile.py": GenConanfile("dep2", "0.1")})
        with c.chdir("sub"):
            c.run("workspace add dep1")
            assert "Reference 'dep1/0.1' added to workspace" in c.out
            c.run("workspace add dep2")
            assert "Reference 'dep2/0.1' added to workspace" in c.out
            c.run("workspace info")
            assert "dep1/0.1" in c.out
            assert "dep2/0.1" in c.out
        assert c.load_home("editable_packages.json") is None

        c.run("editable list")
        assert "dep1" not in c.out
        assert "dep2" not in c.out
        assert c.load_home("editable_packages.json") is None
        with c.chdir("sub"):
            c.run("editable add dep1")
            assert c.load_home("editable_packages.json") is not None
            c.run("editable list")
            assert "dep1/0.1" in c.out
            assert "dep2/0.1" not in c.out
            c.run("workspace info")
            assert "dep1" in c.out
            assert "dep2" in c.out

        c.run("editable list")
        assert "dep1/0.1" in c.out
        assert "dep2" not in c.out

    @pytest.mark.parametrize("api", [False, True])
    def test_dynamic_editables(self, api):
        c = TestClient(light=True)
        conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.files import load
            class Lib(ConanFile):
                def set_name(self):
                    self.name = load(self, os.path.join(self.recipe_folder, "name.txt"))
                def set_version(self):
                    self.version = load(self, os.path.join(self.recipe_folder, "version.txt"))
            """)
        if not api:
            workspace = textwrap.dedent("""\
                import os
                name = "myws"

                workspace_folder = os.path.dirname(os.path.abspath(__file__))

                def editables():
                    result = {}
                    for f in os.listdir(workspace_folder):
                        if os.path.isdir(os.path.join(workspace_folder, f)):
                            name = open(os.path.join(workspace_folder, f, "name.txt")).read().strip()
                            version = open(os.path.join(workspace_folder, f,
                                                        "version.txt")).read().strip()
                            p = os.path.join(f, "conanfile.py").replace("\\\\", "/")
                            result[f"{name}/{version}"] = {"path": p}
                    return result
                """)
        else:
            workspace = textwrap.dedent("""\
               import os
               name = "myws"

               def editables(*args, **kwargs):
                   result = {}
                   for f in os.listdir(workspace_api.folder):
                       if os.path.isdir(os.path.join(workspace_api.folder, f)):
                           f = os.path.join(f, "conanfile.py").replace("\\\\", "/")
                           conanfile = workspace_api.load(f)
                           result[f"{conanfile.name}/{conanfile.version}"] = {"path": f}
                   return result
               """)

        c.save({"conanws.py": workspace,
                "dep1/conanfile.py": conanfile,
                "dep1/name.txt": "pkg",
                "dep1/version.txt": "2.1"})
        c.run("workspace info --format=json")
        info = json.loads(c.stdout)
        assert info["editables"] == {"pkg/2.1": {"path": "dep1/conanfile.py"}}
        c.save({"dep1/name.txt": "other",
                "dep1/version.txt": "14.5"})
        c.run("workspace info --format=json")
        info = json.loads(c.stdout)
        assert info["editables"] == {"other/14.5": {"path": "dep1/conanfile.py"}}
        c.run("install --requires=other/14.5")
        # Doesn't fail
        assert "other/14.5 - Editable" in c.out
        with c.chdir("dep1"):
            c.run("install --requires=other/14.5")
            # Doesn't fail
            assert "other/14.5 - Editable" in c.out

    def test_error_uppercase(self):
        c = TestClient(light=True)
        c.save({"conanws.py": "name='myws'",
                "conanfile.py": GenConanfile("Pkg", "0.1")})
        c.run("workspace add .", assert_error=True)
        assert "ERROR: Conan packages names 'Pkg/0.1' must be all lowercase" in c.out
        c.save({"conanfile.py": GenConanfile()})
        c.run("workspace add . --name=Pkg --version=0.1", assert_error=True)
        assert "ERROR: Conan packages names 'Pkg/0.1' must be all lowercase" in c.out

    def test_add_open_error(self):
        c = TestClient(light=True)
        c.save({"conanws.py": "name='myws'",
                "dep/conanfile.py": GenConanfile("dep", "0.1")})
        c.run("workspace add dep")
        c.run("workspace open dep/0.1", assert_error=True)
        assert "ERROR: Can't open a dependency that is already an editable: dep/0.1" in c.out


class TestOpenAdd:
    def test_without_git(self):
        t = TestClient(default_server_user=True, light=True)
>>>>>>> develop2
        t.save({"conanfile.py": GenConanfile("pkg", "0.1")})
        t.run("create .")
        t.run("upload * -r=default -c")

        c = TestClient(servers=t.servers, light=True)
        c.run(f"workspace open pkg/0.1")
        assert "name = 'pkg'" in c.load("pkg/conanfile.py")

        # The add should work the same
<<<<<<< HEAD
        c2 = TestClient(servers=t.servers)
        c2.save({"conanws.py": ""})
        c2.run(f"workspace add --ref=pkg/0.1")
        assert "name = 'pkg'" in c2.load("pkg/conanfile.py")
        c2.run("editable list")
        assert "pkg/0.1" in c2.out

    def test_without_git_export_sources(self):
        t = TestClient(default_server_user=True)
=======
        c2 = TestClient(servers=t.servers, light=True)
        c2.save({"conanws.py": ""})
        c2.run(f"workspace add --ref=pkg/0.1")
        assert "name = 'pkg'" in c2.load("pkg/conanfile.py")
        c2.run("workspace info")
        assert "pkg/0.1" in c2.out

    def test_without_git_export_sources(self):
        t = TestClient(default_server_user=True, light=True)
>>>>>>> develop2
        t.save({"conanfile.py": GenConanfile("pkg", "0.1").with_exports_sources("*.txt"),
                "CMakeLists.txt": "mycmake"})
        t.run("create .")
        t.run("upload * -r=default -c")

        c = TestClient(servers=t.servers)
        c.run("workspace open pkg/0.1")
        assert "name = 'pkg'" in c.load("pkg/conanfile.py")
        assert "mycmake" in c.load("pkg/CMakeLists.txt")

    def test_workspace_git_scm(self):
        folder = temp_folder()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.scm import Git

            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                def export(self):
                    git = Git(self)
                    git.coordinates_to_conandata()
            """)
        url, commit = create_local_git_repo(files={"conanfile.py": conanfile}, folder=folder,
                                            branch="mybranch")
        t1 = TestClient(default_server_user=True, light=True)
        t1.run_command('git clone "file://{}" .'.format(url))
        t1.run("create .")
        t1.run("upload * -r=default -c")

<<<<<<< HEAD
        c = TestClient(servers=t1.servers)
        c.run("workspace open pkg/0.1")
        assert c.load("pkg/conanfile.py") == conanfile

        c2 = TestClient(servers=t1.servers)
        c2.save({"conanws.py": ""})
        c2.run(f"workspace add --ref=pkg/0.1")
        assert 'name = "pkg"' in c2.load("pkg/conanfile.py")
        c2.run("editable list")
        assert "pkg/0.1" in c2.out

    def test_workspace_build_editables(self):
        c = TestClient()
=======
        c = TestClient(servers=t1.servers, light=True)
        c.run("workspace open pkg/0.1")
        assert c.load("pkg/conanfile.py") == conanfile

        c2 = TestClient(servers=t1.servers, light=True)
        c2.save({"conanws.py": ""})
        c2.run(f"workspace add --ref=pkg/0.1")
        assert 'name = "pkg"' in c2.load("pkg/conanfile.py")
        c2.run("workspace info")
        assert "pkg/0.1" in c2.out

    def test_workspace_build_editables(self):
        c = TestClient(light=True)
>>>>>>> develop2
        c.save({"conanws.yml": ""})

        c.save({"pkga/conanfile.py": GenConanfile("pkga", "0.1").with_build_msg("BUILD PKGA!"),
                "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_build_msg("BUILD PKGB!")
                                                                .with_requires("pkga/0.1")})
        c.run("workspace add pkga")
        c.run("workspace add pkgb")

        c.run("install --requires=pkgb/0.1 --build=editable")
        c.assert_listed_binary({"pkga/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709",
                                             "EditableBuild"),
                                "pkgb/0.1": ("47a5f20ec8fb480e1c5794462089b01a3548fdc5",
                                             "EditableBuild")})
        assert "pkga/0.1: WARN: BUILD PKGA!" in c.out
        assert "pkgb/0.1: WARN: BUILD PKGB!" in c.out
<<<<<<< HEAD


class TestConfig:
    def test_profiles(self):
        """
        What configuration makes sense as local?
        - Custom profiles? But how they apply to dependencies
        - Settings.yml
        - Global.conf
        - Hooks YES
        - Plugins:
           - compatibility.py

        """
        c = TestClient()
        c.save({"conanws.yml": "config_folder: myconfig",
                "myconfig/profiles/myprofile": ""})
        c.run("profile path myprofile")
        print(c.out)


@pytest.mark.tool("cmake", "3.28")
def test_meta_project_cmake():
    c = TestClient()
    c.save({"conanws.yml": ""})
    with c.chdir("pkga"):
        c.run("new cmake_lib -d name=pkga -d version=0.1")
        c.run("workspace add .")
    with c.chdir("pkgb"):
        c.run("new cmake_lib -d name=pkgb -d version=0.1 -d requires=pkga/0.1")
        c.run("workspace add .")
    with c.chdir("app"):
        c.run("new cmake_exe -d name=app -d version=0.1 -d requires=pkgb/0.1")
        c.run("workspace add .")
    c.run("install app --build=editable")

    meta_cmake = textwrap.dedent("""\
        cmake_minimum_required(VERSION 3.24)
        project(meta)

        function(add_subdir subdir dependencies dir_targets)
            set(_bin_dir ${CMAKE_CURRENT_LIST_DIR}/${subdir}/build)
            set(CMAKE_PREFIX_PATH ${_bin_dir}/generators ${CMAKE_PREFIX_PATH})
            add_subdirectory(${subdir} ${_bin_dir})
            get_property(_local_targets DIRECTORY ${subdir} PROPERTY BUILDSYSTEM_TARGETS)
            if(dependencies)
                foreach(_local_target ${_local_targets})
                    add_dependencies(${_local_target} "${dependencies}")
                endforeach()
            endif()
            set(${dir_targets} ${_local_targets} PARENT_SCOPE)
        endfunction()

        add_subdir(pkga "" pkga_targets)
        add_subdir(pkgb ${pkga_targets} pkgb_targets)
        add_subdir(app ${pkgb_targets} app_targets)
        """)
    c.save({"CMakeLists.txt": meta_cmake})
    print(c.current_folder)
    c.run_command("cmake . -B build")
    c.run_command("cmake --build build --config Release")
    print(c.out)

    content = c.load("pkga/src/pkga.cpp")
    content = content.replace("Hello World", "BYE!!!!!!! WORLD")
    c.save({"pkga/src/pkga.cpp": content})
    c.run_command("cmake --build build --config Release")
    print(c.out)
    c.run_command(r"app\build\Release\app.exe")
    print(c.out)
    assert "BYE!!!!!!! WORLD Release!" in c.out

    # Second time it works
    c.run_command("cmake --build build --config Release")
    print(c.out)
    c.run_command(r"app\build\Release\app.exe")
    assert "BYE!!!!!!! WORLD Release!" in c.out
