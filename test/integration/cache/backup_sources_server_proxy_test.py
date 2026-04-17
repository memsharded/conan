"""
Integration tests for the core.sources:server_backup feature.

The feature adds a pull-through cache mode: the Conan client POSTs the original
download URL(s) and sha256 to a Conan server, which fetches-on-demand from the
internet, caches the result by sha256, and streams the file back to the client.

Test layout
-----------
  file_server  – a TestFileServer that acts as the "internet" source.  Its
                 fake_url + store together define what URLs exist.  Removing a
                 file from the store simulates the internet going down for that
                 resource.
  conan_server – a TestServer (conan_server) that provides the
                 POST /v2/sources/backup/<sha256> endpoint.
  client       – a TestClient configured with core.sources:server_backup pointing
                 at conan_server.

Because SourcesService uses a configurable _download_fn (default: requests.get),
we inject a thin wrapper around TestFileServer.app so the server-side download
routes through the in-process WSGI app instead of a real TCP connection.
No mock.patch is used.
"""
import os
import textwrap

import pytest

from conan.test.utils.file_server import TestFileServer
from conan.test.utils.tools import TestClient, TestServer
from conan.internal.util.files import save, load, remove


# sha256("Hello, world!")
_HELLO_SHA256 = "315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3"
_HELLO_CONTENT = b"Hello, world!"


def _make_downloader(file_server):
    """Return a callable compatible with requests.get(url, stream=True) that
    routes requests to *file_server* via its in-process WSGI app.

    Removing a file from file_server.store makes this function return a 404,
    effectively simulating the internet going down for that resource.
    """
    def _download(url, stream=False, **kwargs):
        path = url.replace(file_server.fake_url, "")
        resp = file_server.app.get(path, expect_errors=True)

        class _Response:
            ok = resp.status_int == 200
            status_code = resp.status_int

            def raise_for_status(self_):
                if not self_.ok:
                    raise Exception(f"HTTP {resp.status_int}: {path}")

            def iter_content(self_, chunk_size=1):
                body = resp.body if isinstance(resp.body, bytes) else resp.body.encode()
                return [body]

        return _Response()

    return _download


def _inject_downloader(conan_server, file_server):
    """Wire file_server as the internet source for conan_server's SourcesService."""
    conan_server.test_server.ra.api_v2.sources_service._download_fn = \
        _make_downloader(file_server)


@pytest.fixture()
def setup():
    """Common fixtures: a file_server (internet), a conan_server, and a client."""
    file_server = TestFileServer()
    conan_server = TestServer()
    _inject_downloader(conan_server, file_server)
    client = TestClient(servers={"backup": conan_server}, inputs=["admin", "password"])
    client.save_home(
        {"global.conf": f"core.sources:server_backup={conan_server.fake_url}\n"}
    )
    return file_server, conan_server, client


class TestServerBackupConanSource:

    def test_conan_source_downloads_via_server(self, setup):
        """conan source fetches the file through the backup server."""
        file_server, conan_server, client = setup
        save(os.path.join(file_server.store, "myfile.txt"), "Hello, world!")

        conanfile = textwrap.dedent(f"""
            from conan import ConanFile
            from conan.tools.files import download
            class Pkg(ConanFile):
                def source(self):
                    download(self, "{file_server.fake_url}/myfile.txt", "myfile.txt",
                             sha256="{_HELLO_SHA256}")
        """)
        client.save({"conanfile.py": conanfile})
        client.run("source .")

        assert load(os.path.join(client.current_folder, "myfile.txt")) == "Hello, world!"
        assert "server backup" in client.out

    def test_server_caches_file_and_serves_when_origin_is_gone(self, setup):
        """After the first download the server caches the file.  When the origin
        is taken offline (file removed from file_server.store), the second request
        still succeeds because the server serves from its own cache."""
        file_server, conan_server, client = setup
        save(os.path.join(file_server.store, "myfile.txt"), "Hello, world!")

        conanfile = textwrap.dedent(f"""
            from conan import ConanFile
            from conan.tools.files import download
            class Pkg(ConanFile):
                def source(self):
                    download(self, "{file_server.fake_url}/myfile.txt", "myfile.txt",
                             sha256="{_HELLO_SHA256}")
        """)
        client.save({"conanfile.py": conanfile})

        # First run: server fetches from origin and caches.
        client.run("source .")
        assert load(os.path.join(client.current_folder, "myfile.txt")) == "Hello, world!"

        # Verify server-side cache was populated.
        server_cache_path = os.path.join(
            conan_server.test_server.ra.api_v2.sources_backup_folder,
            "s", _HELLO_SHA256
        )
        assert os.path.exists(server_cache_path)
        assert open(server_cache_path, "rb").read() == _HELLO_CONTENT

        # Take the internet down: remove the file from the origin server.
        remove(os.path.join(file_server.store, "myfile.txt"))

        # Second run: server must serve from its cache without hitting origin.
        client.run("source .")
        assert load(os.path.join(client.current_folder, "myfile.txt")) == "Hello, world!"


class TestServerBackupConanCreate:

    def test_conan_create_downloads_via_server(self, setup):
        """conan create triggers source() which downloads via backup server."""
        file_server, conan_server, client = setup
        save(os.path.join(file_server.store, "myfile.txt"), "Hello, world!")

        conanfile = textwrap.dedent(f"""
            from conan import ConanFile
            from conan.tools.files import download
            class Pkg(ConanFile):
                name = "pkg"
                version = "1.0"
                def source(self):
                    download(self, "{file_server.fake_url}/myfile.txt", "myfile.txt",
                             sha256="{_HELLO_SHA256}")
        """)
        client.save({"conanfile.py": conanfile})
        client.run("create .")

        assert "pkg/1.0" in client.out
        assert "server backup" in client.out

    def test_conan_create_multiple_mirrors(self, setup):
        """When multiple URLs are provided as mirrors, the server tries each in
        order and succeeds on the first working one."""
        file_server, conan_server, client = setup
        # Only the second mirror exists.
        save(os.path.join(file_server.store, "myfile.txt"), "Hello, world!")

        conanfile = textwrap.dedent(f"""
            from conan import ConanFile
            from conan.tools.files import download
            class Pkg(ConanFile):
                name = "pkg"
                version = "1.0"
                def source(self):
                    download(self,
                             ["{file_server.fake_url}/missing.txt",
                              "{file_server.fake_url}/myfile.txt"],
                             "myfile.txt",
                             sha256="{_HELLO_SHA256}")
        """)
        client.save({"conanfile.py": conanfile})
        client.run("create .")

        assert "pkg/1.0" in client.out


class TestServerBackupConanInstall:

    def test_conan_install_build_from_source_via_server(self, setup):
        """conan install --build triggers source() which downloads via backup
        server, then builds and packages the result."""
        file_server, conan_server, client = setup
        save(os.path.join(file_server.store, "myfile.txt"), "Hello, world!")

        conanfile = textwrap.dedent(f"""
            from conan import ConanFile
            from conan.tools.files import download, copy
            class Pkg(ConanFile):
                name = "pkg"
                version = "1.0"
                def source(self):
                    download(self, "{file_server.fake_url}/myfile.txt", "myfile.txt",
                             sha256="{_HELLO_SHA256}")
                def package(self):
                    copy(self, "myfile.txt", self.build_folder, self.package_folder)
        """)
        client.save({"conanfile.py": conanfile})

        # First create to get the package into the cache.
        client.run("create .")
        assert "pkg/1.0" in client.out

        # Remove the local package so install is forced to rebuild from source.
        client.run("remove pkg/1.0:* -c")

        # Origin is still available; install --build should download via server.
        client.run("install --requires=pkg/1.0 --build=pkg*")
        assert "pkg/1.0" in client.out


class TestServerBackupErrors:

    def test_error_when_server_backup_unreachable(self):
        """If server_backup is set but the server is not reachable, a clear error
        is raised — no silent fallback to the origin URL."""
        client = TestClient(light=True)
        client.save_home(
            {"global.conf": "core.sources:server_backup=http://nonexistent-server.local\n"}
        )
        conanfile = textwrap.dedent(f"""
            from conan import ConanFile
            from conan.tools.files import download
            class Pkg(ConanFile):
                def source(self):
                    download(self, "http://example.com/myfile.txt", "myfile.txt",
                             sha256="{_HELLO_SHA256}")
        """)
        client.save({"conanfile.py": conanfile})
        client.run("source .", assert_error=True)
        assert "Error contacting source backup server" in client.out
