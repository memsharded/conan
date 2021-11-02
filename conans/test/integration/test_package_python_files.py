import os
import textwrap

from conans.util.files import load
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID


def test_package_python_files():
    client = TestClient(default_server_user=True)
    conan_conf = textwrap.dedent("""
                    [storage]
                    path = ./data
                    [general]
                    keep_python_files=True
            """.format())
    client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            exports_sources = "*"
            def package(self):
                self.copy("*")
        """)
    client.save({"conanfile.py": conanfile,
                 "myfile.pyc": "",
                 "myfile.pyo": "",
                 ".DS_Store": ""})
    client.run("create . pkg/0.1@")
    ref = ConanFileReference.loads("pkg/0.1")
    ref_layout = client.get_latest_ref_layout(ref)
    export = ref_layout.export()
    export_sources = ref_layout.export_sources()
    assert os.path.isfile(os.path.join(export_sources, "myfile.pyc"))
    assert os.path.isfile(os.path.join(export_sources, "myfile.pyo"))
    assert os.path.isfile(os.path.join(export_sources, ".DS_Store"))
    manifest = load(os.path.join(export, "conanmanifest.txt"))
    assert "myfile.pyc" in manifest
    assert "myfile.pyo" in manifest
    assert ".DS_Store" not in manifest
    pref = client.get_latest_prev(ref, NO_SETTINGS_PACKAGE_ID)
    pkg_folder = client.get_latest_pkg_layout(pref).package()
    assert os.path.isfile(os.path.join(pkg_folder, "myfile.pyc"))
    assert os.path.isfile(os.path.join(pkg_folder, "myfile.pyo"))
    assert os.path.isfile(os.path.join(pkg_folder, ".DS_Store"))
    manifest = load(os.path.join(pkg_folder, "conanmanifest.txt"))
    assert "myfile.pyc" in manifest
    assert "myfile.pyo" in manifest
    assert ".DS_Store" not in manifest

    client.run("upload * --all -r=default --confirm")
    client.run("remove * -f")
    client.run("download pkg/0.1@")

    assert os.path.isfile(os.path.join(export_sources, "myfile.pyc"))
    assert os.path.isfile(os.path.join(export_sources, "myfile.pyo"))
    assert not os.path.isfile(os.path.join(export_sources, ".DS_Store"))
    manifest = load(os.path.join(export, "conanmanifest.txt"))
    assert "myfile.pyc" in manifest
    assert "myfile.pyo" in manifest
    assert ".DS_Store" not in manifest
    assert os.path.isfile(os.path.join(pkg_folder, "myfile.pyc"))
    assert os.path.isfile(os.path.join(pkg_folder, "myfile.pyo"))
    assert not os.path.isfile(os.path.join(pkg_folder, ".DS_Store"))
    manifest = load(os.path.join(pkg_folder, "conanmanifest.txt"))
    assert "myfile.pyc" in manifest
    assert "myfile.pyo" in manifest
    assert ".DS_Store" not in manifest
