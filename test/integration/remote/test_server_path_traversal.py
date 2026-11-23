"""
conan_server must never read or write files outside of its storage, whatever the path or the
reference fields in the URL.

GHSA-hcjc-vqhm-w6p2: file GET routes served any file to callers without an account
GHSA-qrpq-hr9g-8jq9: file PUT routes created or replaced any file
"""
import base64
import http.client
import os

import pytest

from conan.test.utils.server_launcher import TestServerLauncher
from conan.test.utils.test_files import temp_folder

SECRET = "jwt_secret = very-secret"


class _Client:
    """ Raw HTTP client, "requests" or "curl" normalize the dot-dot segments of the URL"""

    def __init__(self, port):
        self.port = port

    def request(self, method, url, body=None, token=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            conn.request(method, url, body=body, headers=headers)
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()

    def login(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        auth = base64.b64encode(b"demo:demo").decode()
        conn.request("GET", "/v2/users/authenticate", headers={"Authorization": f"Basic {auth}"})
        response = conn.getresponse()
        assert response.status == 200
        token = response.read().decode()
        conn.close()
        return token


@pytest.fixture(scope="module")
def server():
    # One server for all the tests, starting and stopping it is most of the time of the tests
    base = temp_folder()
    launcher = TestServerLauncher(base_path=base, users={"demo": "demo"},
                                  read_permissions=[("*/*@*/*", "*")],
                                  write_permissions=[("*/*@*/*", "demo")])
    launcher.port = 0  # a free port, the default 9300 would clash between parallel tests
    launcher.start()
    # A file outside of the server storage, like the server.conf of a real server
    secret = os.path.join(base, "server_secret.conf")
    with open(secret, "w") as f:
        f.write(SECRET)
    launcher.secret = secret
    launcher.store = launcher.server_store.store
    # The recipe must exist to upload its packages
    os.makedirs(os.path.join(launcher.store, "pkg", "1.0", "_", "_", "abc", "export"))
    client = _Client(launcher.port)
    yield launcher, client
    launcher.stop()


def _up_to(launcher, depth, target):
    """ URL path (as many ../ as needed + the target path, like a curl --path-as-is) that
    reaches target when joined to a folder ``depth`` levels under the storage"""
    start = os.path.join(launcher.store, *["x"] * depth)
    rel = os.path.relpath(target, start)
    return rel.replace("\\", "/")


# Recipe and package files routes, with the depth of their folders under the storage:
# <store>/pkg/1.0/_/_/abc/export  and  <store>/pkg/1.0/_/_/abc/package/pid/def
RECIPE = "/v2/conans/pkg/1.0/_/_/revisions/abc/files/"
PACKAGE = "/v2/conans/pkg/1.0/_/_/revisions/abc/packages/pid/revisions/def/files/"
RECIPE_DEPTH, PACKAGE_DEPTH = 6, 8


class TestFilePathTraversal:
    """ The {path} part of the URL """

    @pytest.mark.parametrize("route, depth", [(RECIPE, RECIPE_DEPTH), (PACKAGE, PACKAGE_DEPTH)])
    @pytest.mark.parametrize("encoded", [False, True])
    def test_get_without_account(self, server, route, depth, encoded):
        # GHSA-hcjc-vqhm-w6p2: default config has read permissions for everybody, no token
        launcher, client = server
        traversal = _up_to(launcher, depth, launcher.secret)
        if encoded:
            traversal = traversal.replace("..", "%2e%2e")
        status, body = client.request("GET", route + traversal)
        assert (status, b"Invalid file path" in body) == (403, True)
        assert SECRET.encode() not in body

    @pytest.mark.parametrize("route", [RECIPE, PACKAGE])
    @pytest.mark.parametrize("filename", ["..%5C..%5Cserver_secret.conf",  # backslash, Windows
                                          "%2Fserver_secret.conf",  # absolute
                                          "a//b", "a/", "a/../../../b"])
    def test_get_other_forms(self, server, route, filename):
        launcher, client = server
        status, body = client.request("GET", route + filename)
        assert (status, b"Invalid" in body) == (403, True)
        assert SECRET.encode() not in body

    @pytest.mark.parametrize("route, depth", [(RECIPE, RECIPE_DEPTH), (PACKAGE, PACKAGE_DEPTH)])
    def test_put_create_and_replace(self, server, route, depth):
        # GHSA-qrpq-hr9g-8jq9
        launcher, client = server
        token = client.login()
        traversal = _up_to(launcher, depth, launcher.secret)
        status, body = client.request("PUT", route + traversal, body=b"REPLACED", token=token)
        assert (status, b"Invalid file path" in body) == (403, True)
        with open(launcher.secret) as f:
            assert f.read() == SECRET

        new_file = os.path.join(os.path.dirname(launcher.secret), "created.txt")
        traversal = _up_to(launcher, depth, new_file)
        status, body = client.request("PUT", route + traversal, body=b"x", token=token)
        assert (status, b"Invalid file path" in body) == (403, True)
        assert not os.path.exists(new_file)

    def test_put_normal_upload_still_works(self, server):
        launcher, client = server
        token = client.login()
        for route in (RECIPE, PACKAGE):
            status, _ = client.request("PUT", route + "metadata/sub/mylogs.txt", body=b"x",
                                       token=token)
            assert status == 200
            status, body = client.request("GET", route + "metadata/sub/mylogs.txt")
            assert (status, body) == (200, b"x")


class TestReferenceTraversal:
    """ name, version, user, channel, revision... are also URL segments, ".." is a valid one """

    def test_get_files_outside_storage(self, server):
        # with 3 dot-dot the recipe folder is <parent of base>/chn/abc/export
        launcher, client = server
        folder = os.path.normpath(os.path.join(launcher.store, "..", "..", "..", "chn", "abc",
                                               "export"))
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "secret.txt"), "w") as f:
            f.write(SECRET)
        status, body = client.request("GET",
                                      "/v2/conans/../../../chn/revisions/abc/files/secret.txt")
        assert (status, b"Invalid" in body) == (403, True)
        assert SECRET.encode() not in body

    @pytest.mark.parametrize("url", [
        "/v2/conans/%2e%2e/%2e%2e/%2e%2e/chn/revisions/abc/files/pwned.txt",
        "/v2/conans/pkg/1.0/_/_/revisions/../files/pwned.txt",
        "/v2/conans/pkg/1.0/_/_/revisions/abc/packages/../revisions/def/files/pwned.txt",
        "/v2/conans/pkg/1.0/_/_/revisions/abc/packages/pid/revisions/../files/pwned.txt",
    ])
    def test_put_outside_storage(self, server, url):
        launcher, client = server
        token = client.login()
        status, body = client.request("PUT", url, body=b"x", token=token)
        assert (status, b"Invalid" in body) == (403, True)
        store_parent = os.path.normpath(os.path.join(launcher.store, "..", "..", ".."))
        found = [os.path.join(dp, f) for dp, _, fs in os.walk(store_parent) for f in fs
                 if f == "pwned.txt"]
        assert found == []

    @pytest.mark.parametrize("segment", ["a%5Cb", "a%00b"])
    @pytest.mark.parametrize("field", [0, 1, 2, 3])
    def test_backslash_and_nul(self, server, segment, field):
        # They are not route separators for bottle, but they are in a Windows server or
        # break the file system calls
        launcher, client = server
        parts = ["pkg", "1.0", "usr", "chn"]
        parts[field] = segment
        url = "/v2/conans/" + "/".join(parts) + "/revisions/abc/files/conanfile.py"
        status, body = client.request("GET", url)
        assert (status, b"Invalid" in body) == (403, True)
