import os
import textwrap

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
    t1 = TestClient(default_server_user=True)
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
                update_conandata(self, {"scm": {"commit": scm_commit, "url": scm_url}})
        """)
    t1.init_git_repo({'conanfile.py': conanfile})

    t1.run("create .")
    t1.run("upload * -r=default -c")

    c = TestClient(servers=t1.servers)
    c.run("workspace open --requires=pkg/0.1")
    assert c.load("conanfile.py") == conanfile

