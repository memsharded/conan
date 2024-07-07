import os
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.scm import create_local_git_repo
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conans.util.files import save


class TestHomeRoot:
    @pytest.mark.parametrize("ext, content", [("py", "home_folder = 'myhome'"),
                                              ("yml", "home_folder: myhome")])
    def test_workspace_home(self, ext, content):
        folder = temp_folder()
        cwd = os.path.join(folder, "sub1", "sub2")
        save(os.path.join(folder, f"conanws.{ext}"), content)
        c = TestClient(current_folder=cwd)
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
        c = TestClient(current_folder=cwd)
        c.run("config home")
        assert os.path.join(folder, "newmyhome") in c.stdout

    def test_workspace_root(self):
        c = TestClient()
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
        c = TestClient()
        c.save({"conanws.py": "name='myws'",
                "dep1/conanfile.py": GenConanfile("dep1", "0.1"),
                "dep2/conanfile.py": GenConanfile("dep2", "0.1"),
                "dep3/conanfile.py": GenConanfile("dep3", "0.1")})
        c.run("workspace add dep1")
        assert "Reference 'dep1/0.1' added to workspace" in c.out
        c.run("editable list")
        assert "Workspace: myws" in c.out
        assert "dep1/0.1" in c.out
        assert "dep2" not in c.out
        c.run("workspace add dep2")
        assert "Reference 'dep2/0.1' added to workspace" in c.out
        c.run("editable list")
        assert "dep1/0.1" in c.out
        assert "dep2/0.1" in c.out

        c.run("workspace info --format=json")
        print(c.out)
        print(c.current_folder)


def test_workspace_open_packages():
    folder = temp_folder()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.scm import Git
        from conan.tools.files import update_conandata

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def export(self):
                git = Git(self, self.recipe_folder)
                scm_url, scm_commit = git.get_url_and_commit()
                branch = git.get_branch()
                self.output.info(f"Branch {branch}")
                update_conandata(self, {"scm": {"commit": scm_commit, "url": scm_url,
                                                "branch": branch}})
        """)
    url, commit = create_local_git_repo(files={"conanfile.py": conanfile}, folder=folder,
                                        branch="mybranch")
    t1 = TestClient(default_server_user=True)
    t1.run_command('git clone "{}" .'.format(url))
    t1.run("create .")
    t1.run("upload * -r=default -c")

    c = TestClient(servers=t1.servers)
    c.run("workspace open --requires=pkg/0.1")
    assert c.load("conanfile.py") == conanfile


def test_workspace_add_packages():
    c = TestClient()
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
    c.run("editable list")
    assert "pkga/0.1" in c.out
    assert "pkgb/0.1" in c.out
    with c.chdir(temp_folder()):  # If we move to another folder, outside WS, no editables
        c.run("editable list")
        assert "pkga/0.1" not in c.out
        assert "pkgb/0.1" not in c.out

    c.run("workspace remove pkga")
    c.run("editable list")
    assert "pkga/0.1" not in c.out
    assert "pkgb/0.1" in c.out

    c.run("workspace remove pkgb")
    c.run("editable list")
    assert "pkga/0.1" not in c.out
    assert "pkgb/0.1" not in c.out


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
