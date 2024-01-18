import os
import textwrap

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.scm import create_local_git_repo
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import save


class TestHomeRoot:
    def test_workspace_home(self):
        folder = temp_folder()
        cwd = os.path.join(folder, "sub1", "sub2")
        conanws = "home_folder = 'myhome'"
        save(os.path.join(folder, "conanws.py"), conanws)
        c = TestClient(current_folder=cwd)
        c.run("config home")
        assert os.path.join(folder, "myhome") in c.stdout

    def test_workspace_home_py(self):
        folder = temp_folder()
        cwd = os.path.join(folder, "sub1", "sub2")
        conanws = "home_folder: myhome"
        save(os.path.join(folder, "conanws.yml"), conanws)
        c = TestClient(current_folder=cwd)
        c.run("config home")
        assert os.path.join(folder, "myhome") in c.stdout

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
    c.run("install app")
    meta_cmake = textwrap.dedent("""\
        cmake_minimum_required(VERSION 3.24)
        project(meta)

        include(ExternalProject)
        ExternalProject_Add(pkga SOURCE_DIR ${CMAKE_CURRENT_LIST_DIR}/pkga
                                 CMAKE_ARGS "-DCMAKE_TOOLCHAIN_FILE=${CMAKE_CURRENT_LIST_DIR}/pkga/build/generators/conan_toolchain.cmake"
                                 BINARY_DIR ${CMAKE_CURRENT_LIST_DIR}/pkga/build
                                 INSTALL_COMMAND ""
                                 )

        ExternalProject_Add(pkgb SOURCE_DIR ${CMAKE_CURRENT_LIST_DIR}/pkgb
                                 CMAKE_ARGS "-DCMAKE_TOOLCHAIN_FILE=${CMAKE_CURRENT_LIST_DIR}/pkgb/build/generators/conan_toolchain.cmake"
                                 BINARY_DIR ${CMAKE_CURRENT_LIST_DIR}/pkgb/build
                                 INSTALL_COMMAND ""
                                 DEPENDS pkga)
        ExternalProject_Add(app SOURCE_DIR ${CMAKE_CURRENT_LIST_DIR}/app
                                CMAKE_ARGS "-DCMAKE_TOOLCHAIN_FILE=${CMAKE_CURRENT_LIST_DIR}/app/build/generators/conan_toolchain.cmake"
                                BINARY_DIR ${CMAKE_CURRENT_LIST_DIR}/app/build
                                INSTALL_COMMAND ""
                                DEPENDS pkgb
                                )
        """)
    c.save({"CMakeLists.txt": meta_cmake})
    print(c.current_folder)
    c.run_command("cmake . -B build")
    print(c.out)
    c.run_command("cmake --build build --config Release")
    print(c.out)

