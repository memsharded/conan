import os
import textwrap

from conans.test.utils.scm import create_local_git_repo
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import save


def test_workspace_home():
    folder = temp_folder()
    cwd = os.path.join(folder, "sub1", "sub2")
    conanws = "home_folder = 'myhome'"
    save(os.path.join(folder, "conanws.py"), conanws)
    c = TestClient(current_folder=cwd)
    c.run("config home")
    assert os.path.join(folder, "myhome") in c.stdout


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
    print(t1.out)
    t1.run("upload * -r=default -c")

    c = TestClient(servers=t1.servers)
    c.run("workspace open --requires=pkg/0.1")
    print(c.out)
    print(c.current_folder)
    assert c.load("conanfile.py") == conanfile
