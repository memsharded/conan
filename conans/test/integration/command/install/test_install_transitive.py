import os
import re

import pytest

from conans.model.info import ConanInfo
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONANFILE_TXT, CONANINFO
from conans.test.utils.tools import TestClient,  GenConanfile
from conans.util.files import save


@pytest.fixture()
def client():
    c = TestClient()
    save(c.cache.settings_path, "os: [Windows, Macos, Linux, FreeBSD]\nos_build: [Windows, Macos]")
    save(c.cache.default_profile_path, "[settings]\nos=Windows")

    def base_conanfile(name):
        return GenConanfile(name, "0.1").with_option("language", [0, 1])\
            .with_default_option("language", 0).with_settings("os")

    c.save({"conanfile.py": base_conanfile("Hello0")})
    c.run("export . lasote/stable")
    c.save({"conanfile.py": base_conanfile("Hello1").with_requires("Hello0/0.1@lasote/stable")})
    c.run("export . lasote/stable")
    c.save({"conanfile.py": base_conanfile("Hello2").with_requires("Hello1/0.1@lasote/stable")})
    c.run("export . lasote/stable")
    return c


def test_install_combined(client):
    client.run("install . --build=missing")
    client.run("install . --build=missing --build Hello1")
    assert "Hello0/0.1@lasote/stable: Already installed!" in client.out
    assert "Hello1/0.1@lasote/stable: Forced build from source" in client.out


def test_install_transitive_cache(client):
    client.run("install Hello2/0.1@lasote/stable --build=missing")
    assert "Hello0/0.1@lasote/stable: Generating the package" in client.out
    assert "Hello1/0.1@lasote/stable: Generating the package" in client.out
    assert "Hello2/0.1@lasote/stable: Generating the package" in client.out


@pytest.mark.xfail(reason="build_modes.report_matches() not working now")
def test_partials(client):
    client.run("install . --build=missing")
    client.run("install ./ --build=Bye")
    assert "No package matching 'Bye' pattern found." in client.out

    for package in ["Hello0", "Hello1"]:
        client.run("install . --build=%s" % package)
        assert "No package matching" not in client.out


@pytest.mark.xfail(reason="changing package-ids")
def test_reuse(client):
    # FIXME: package-ids will change
    for lang, id0, id1 in [(0, "3475bd55b91ae904ac96fde0f106a136ab951a5e",
                               "c27896c40136be4bb5fd9c759d9abffaee6756a0"),
                           (1, "f43bd822487baa4ed2426c279c27b2811870499a",
                               "9f15cc4352ab4f46f118942394adc52a2cdbcffc")]:

        client.run("install . -o *:language=%d --build missing" % lang)
        assert "Configuration:[settings]", "".join(str(client.out).splitlines())
        ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")

        hello0 = client.get_latest_pkg_layout(PackageReference(ref, id0)).package()
        hello0_info = os.path.join(hello0, CONANINFO)
        hello0_conan_info = ConanInfo.load_file(hello0_info)
        assert lang == hello0_conan_info.options.language

        pref1 = PackageReference(ConanFileReference.loads("Hello1/0.1@lasote/stable"), id1)
        hello1 = client.get_latest_pkg_layout(pref1).package()
        hello1_info = os.path.join(hello1, CONANINFO)
        hello1_conan_info = ConanInfo.load_file(hello1_info)
        assert lang == hello1_conan_info.options.language


def test_upper_option(client):
    client.run("install conanfile.py -o Hello2:language=1 -o Hello1:language=0 "
               "-o Hello0:language=1 --build missing")
    package_id = re.search(r"Hello0/0.1@lasote/stable:(\S+)", str(client.out)).group(1)
    package_id2 = re.search(r"Hello1/0.1@lasote/stable:(\S+)", str(client.out)).group(1)
    ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")
    pref = client.get_latest_prev(ref, package_id)
    hello0 = client.get_latest_pkg_layout(pref).package()

    hello0_info = os.path.join(hello0, CONANINFO)
    hello0_conan_info = ConanInfo.load_file(hello0_info)
    assert 1 == hello0_conan_info.options.language

    pref1 = client.get_latest_prev(ConanFileReference.loads("Hello1/0.1@lasote/stable"), package_id2)
    hello1 = client.get_latest_pkg_layout(pref1).package()
    hello1_info = os.path.join(hello1, CONANINFO)
    hello1_conan_info = ConanInfo.load_file(hello1_info)
    assert 0 == hello1_conan_info.options.language


def test_inverse_upper_option(client):
    client.run("install . -o language=0 -o Hello1:language=1 -o Hello0:language=0 --build missing")
    package_id = re.search(r"Hello0/0.1@lasote/stable:(\S+)", str(client.out)).group(1)
    package_id2 = re.search(r"Hello1/0.1@lasote/stable:(\S+)", str(client.out)).group(1)
    ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")
    pref = client.get_latest_prev(ref, package_id)
    hello0 = client.get_latest_pkg_layout(pref).package()

    hello0_info = os.path.join(hello0, CONANINFO)
    hello0_conan_info = ConanInfo.load_file(hello0_info)
    assert "language=0" == hello0_conan_info.options.dumps()

    pref1 = client.get_latest_prev(ConanFileReference.loads("Hello1/0.1@lasote/stable"),
                                   package_id2)
    hello1 = client.get_latest_pkg_layout(pref1).package()
    hello1_info = os.path.join(hello1, CONANINFO)
    hello1_conan_info = ConanInfo.load_file(hello1_info)
    assert "language=1" == hello1_conan_info.options.dumps()


def test_upper_option_txt(client):
    files = {CONANFILE_TXT: """[requires]
        Hello1/0.1@lasote/stable

        [options]
        Hello0:language=1
        Hello1:language=0
        """}
    client.save(files, clean_first=True)

    client.run("install . --build missing")
    package_id = re.search(r"Hello0/0.1@lasote/stable:(\S+)", str(client.out)).group(1)
    package_id2 = re.search(r"Hello1/0.1@lasote/stable:(\S+)", str(client.out)).group(1)
    ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")
    pref = client.get_latest_prev(ref, package_id)
    hello0 = client.get_latest_pkg_layout(pref).package()
    hello0_info = os.path.join(hello0, CONANINFO)
    hello0_conan_info = ConanInfo.load_file(hello0_info)
    assert 1 == hello0_conan_info.options.language

    pref1 = client.get_latest_prev(ConanFileReference.loads("Hello1/0.1@lasote/stable"), package_id2)
    hello1 = client.get_latest_pkg_layout(pref1).package()
    hello1_info = os.path.join(hello1, CONANINFO)
    hello1_conan_info = ConanInfo.load_file(hello1_info)
    assert 0 == hello1_conan_info.options.language
