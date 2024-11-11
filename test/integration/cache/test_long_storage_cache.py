import os

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_long_storage_cache():
    c = TestClient()
    long_path = os.path.join(c.cache_folder, "long_storage")
    c.save_home({"global.conf": 'core.cache:long_storage_packages=["*tool*"]\n'
                                f"core.cache:long_storage_path={long_path}"})
    c.save({"conanfile.py": GenConanfile()})
    c.run("create . --name=pkg --version=0.1")
    c.run("create . --name=tool --version=0.1")
    c.run("list *")
    print(c.out)
    c.run("remove * -c")
    print(c.out)
    c.run("list *")
    print(c.out)
