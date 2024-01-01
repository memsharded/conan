import os

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
