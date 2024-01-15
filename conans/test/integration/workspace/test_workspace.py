import os
import textwrap

from conans.test.utils.scm import create_local_git_repo
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import save


def test_workspace_home():
    folder = temp_folder()
    cwd = os.path.join(folder, "sub1", "sub2")
    conanws = "home_folder = 'myhome'"
    save(os.path.join(folder, "conanws.py"), conanws)
    c = TestClient(current_folder=cwd)
    c.run("config home")
    assert os.path.join(folder, "myhome") in c.stdout


def test_workspace_root():
    c = TestClient()
    # Just check the root command works
    c.run("workspace root", assert_error=True)
    assert "ERROR: No workspace defined, conanws.py file not found" in c.out
    c.save({"conanws.py": ""})
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
    server = TestServer(users={"admin": "password"})
    for pkg in ("pkga", "pkgb"):
        folder = temp_folder()
        requires = 'requires="pkga/0.1"' if pkg == "pkgb" else ""
        conanfile = textwrap.dedent(f"""
            from conan import ConanFile
            from conan.tools.scm import Git
            from conan.tools.files import update_conandata

            class Pkg(ConanFile):
                name = "{pkg}"
                version = "0.1"

                {requires}

                def export(self):
                    git = Git(self, self.recipe_folder)
                    scm_url, scm_commit = git.get_url_and_commit()
                    branch = git.get_branch()
                    update_conandata(self, {{"scm":{{"commit": scm_commit, "url": scm_url,
                                                    "branch": branch}}}})

                def build(self):
                    self.output.info(f"Building {{self.name}}!!!")
            """)
        url, commit = create_local_git_repo(files={"conanfile.py": conanfile}, folder=folder,
                                            branch=f"{pkg}_branch")
        t1 = TestClient(servers={"default": server}, inputs=["admin", "password"])
        t1.run_command('git clone "{}" .'.format(url))
        t1.run("create .")
        t1.run("upload * -r=default -c")

    c = TestClient(servers={"default": server}, inputs=["admin", "password"])
    c.save({"conanws.py": ""})

    with c.chdir("pkga"):
        c.run("workspace open --requires=pkga/0.1")
        c.run("workspace add .")
    with c.chdir("pkgb"):
        c.run("workspace open --requires=pkgb/0.1")
        c.run("workspace add .")
    c.run("remove * -c")
    c.run("list *")
    print(c.out)

    c.run("install --requires=pkgb/0.1 --build=editable")
    c.assert_listed_binary({"pkga/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709",
                                         "EditableBuild"),
                            "pkgb/0.1": ("47a5f20ec8fb480e1c5794462089b01a3548fdc5",
                                         "EditableBuild")})
    assert "pkga/0.1: Building pkga!!!" in c.out
    assert "pkgb/0.1: Building pkgb!!!" in c.out
    c.run("editable list")
    print(c.out)
