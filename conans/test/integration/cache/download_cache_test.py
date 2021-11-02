import os
import textwrap
import time
import unittest
from collections import Counter
from threading import Thread

from bottle import static_file, request

from conans.client.downloaders.cached_file_downloader import CachedFileDownloader
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, StoppableThreadBottle
from conans.util.files import load, save, set_dirty


class DownloadCacheTest(unittest.TestCase):

    def test_download_skip(self):
        client = TestClient(default_server_user=True)
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                exports = "*"
                def package(self):
                    self.copy("*")
            """)
        client.save({"conanfile.py": conanfile,
                     "header.h": "header"})
        client.run("create . mypkg/0.1@user/testing")
        client.run("upload * --all --confirm -r default")
        cache_folder = temp_folder()
        log_trace_file = os.path.join(temp_folder(), "mylog.txt")
        conan_conf = textwrap.dedent("""
            [storage]
            path = ./data
            download_cache = {}
            [log]
            trace_file = {}
        """.format(cache_folder, log_trace_file))
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)

        client.run("remove * -f")
        client.run("install mypkg/0.1@user/testing")
        content = load(log_trace_file)
        self.assertEqual(6, content.count('"_action": "DOWNLOAD"'))
        # 6 files cached, plus "locks" folder = 7
        self.assertEqual(7, len(os.listdir(cache_folder)))

        os.remove(log_trace_file)
        client.run("remove * -f")
        client.run("install mypkg/0.1@user/testing")
        content = load(log_trace_file)
        self.assertEqual(0, content.count('"_action": "DOWNLOAD"'))
        self.assertIn("DOWNLOADED_RECIPE", content)
        self.assertIn("DOWNLOADED_PACKAGE", content)

        # removing the config downloads things
        conan_conf = textwrap.dedent("""
            [storage]
            path = ./data
            [log]
            trace_file = {}
            """.format(log_trace_file))
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)
        os.remove(log_trace_file)
        client.run("remove * -f")
        client.run("install mypkg/0.1@user/testing")
        content = load(log_trace_file)

        self.assertEqual(6, content.count('"_action": "DOWNLOAD"'))

        # restoring config cache works again
        os.remove(log_trace_file)
        conan_conf = textwrap.dedent("""
            [storage]
            path = ./data
            download_cache = {}
            [log]
            trace_file = {}
            """.format(cache_folder, log_trace_file))
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)

        client.run("remove * -f")
        client.run("install mypkg/0.1@user/testing")
        content = load(log_trace_file)
        self.assertEqual(0, content.count('"_action": "DOWNLOAD"'))

    def test_dirty_download(self):
        # https://github.com/conan-io/conan/issues/8578
        client = TestClient(default_server_user=True)
        cache_folder = temp_folder()

        conan_conf = textwrap.dedent("""
                    [storage]
                    path = ./data
                    download_cache = {}
                    [log]
                    """.format(cache_folder))
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)

        client.save({"conanfile.py": GenConanfile().with_package_file("file.txt", "content")})
        client.run("create . pkg/0.1@")
        client.run("upload * --all -c -r default")
        client.run("remove * -f")
        client.run("install pkg/0.1@")
        for f in os.listdir(cache_folder):
            # damage the file
            path = os.path.join(cache_folder, f)
            if os.path.isfile(path):
                save(path, "broken!")
                set_dirty(path)

        client.run("remove * -f")
        client.run("install pkg/0.1@")
        assert "pkg/0.1: Downloaded package" in client.out

    def test_user_downloads_cached_newtools(self):
        http_server = StoppableThreadBottle()

        file_path = os.path.join(temp_folder(), "myfile.txt")
        save(file_path, "some content")
        file_path_query = os.path.join(temp_folder(), "myfile2.txt")
        save(file_path_query, "some query")

        @http_server.server.get("/myfile.txt")
        def get_file():
            f = file_path_query if request.query else file_path
            return static_file(os.path.basename(f), os.path.dirname(f))

        http_server.run_server()

        client = TestClient()
        cache_folder = temp_folder()
        save(client.cache.new_config_path, "tools.files.download:download_cache=%s" % cache_folder)
        # badchecksums are not cached
        conanfile = textwrap.dedent("""
           from conans import ConanFile
           from conan.tools.files import download
           class Pkg(ConanFile):
               def source(self):
                   download(self, "http://localhost:%s/myfile.txt", "myfile.txt", md5="kk")
           """ % http_server.port)
        client.save({"conanfile.py": conanfile})
        client.run("source .", assert_error=True)
        self.assertIn("ConanException: md5 signature failed for", client.out)
        self.assertIn("Provided signature: kk", client.out)
        self.assertIn("Computed signature: 9893532233caff98cd083a116b013c0b", client.out)
        # There are 2 things in the cache, the "locks" folder and the .dirty file because failure
        self.assertEqual(2, len(os.listdir(cache_folder)))  # Nothing was cached

        # This is the right checksum
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conan.tools.files import download
            class Pkg(ConanFile):
                def source(self):
                    md5 = "9893532233caff98cd083a116b013c0b"
                    md5_2 = "0dc8a17658b1c7cfa23657780742a353"
                    download(self, "http://localhost:{0}/myfile.txt", "myfile.txt", md5=md5)
                    download(self, "http://localhost:{0}/myfile.txt?q=2", "myfile2.txt", md5=md5_2)
            """).format(http_server.port)
        client.save({"conanfile.py": conanfile})
        client.run("source .")
        local_path = os.path.join(client.current_folder, "myfile.txt")
        self.assertTrue(os.path.exists(local_path))
        self.assertEqual("some content", client.load("myfile.txt"))
        local_path2 = os.path.join(client.current_folder, "myfile2.txt")
        self.assertTrue(os.path.exists(local_path2))
        self.assertEqual("some query", client.load("myfile2.txt"))

        # 2 files cached, plus "locks" folder = 3
        # "locks" folder + 2 files cached + .dirty file from previous failure
        self.assertEqual(4, len(os.listdir(cache_folder)))

        # remove remote file
        os.remove(file_path)
        os.remove(local_path)
        os.remove(local_path2)
        # Will use the cached one
        client.run("source .")
        self.assertTrue(os.path.exists(local_path))
        self.assertTrue(os.path.exists(local_path2))
        self.assertEqual("some content", client.load("myfile.txt"))
        self.assertEqual("some query", client.load("myfile2.txt"))

        # disabling cache will make it fail
        os.remove(local_path)
        os.remove(local_path2)
        save(client.cache.new_config_path, "")
        client.run("source .", assert_error=True)
        self.assertIn("ERROR: conanfile.py: Error in source() method, line 8", client.out)
        self.assertIn("Not found: http://localhost", client.out)

    def test_revision0_v2_skip(self):
        client = TestClient(default_server_user=True)
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                exports = "*"
                def package(self):
                    self.copy("*")
                def deploy(self):
                    self.copy("*")
            """)
        client.save({"conanfile.py": conanfile,
                     "header.h": "header"})
        client.run("create . mypkg/0.1@user/testing")
        client.run("upload * --all --confirm -r default")

        client2 = TestClient(servers=client.servers)
        cache_folder = temp_folder()

        conan_conf = textwrap.dedent("""
            [storage]
            path = ./data
            download_cache = {}
            [log]
            """.format(cache_folder))
        client2.save({"conan.conf": conan_conf}, path=client2.cache.cache_folder)

        client2.run("install mypkg/0.1@user/testing")
        self.assertEqual("header", client2.load("header.h"))

        # modify non-revisioned pkg
        client.save({"conanfile.py": conanfile,
                     "header.h": "header2"})
        client.run("create . mypkg/0.1@user/testing")
        client.run("upload * --all --confirm -r default")

        client2.run("remove * -f")
        client2.run("install mypkg/0.1@user/testing")
        self.assertEqual("header2", client2.load("header.h"))


class CachedDownloaderUnitTest(unittest.TestCase):
    def setUp(self):
        cache_folder = temp_folder()

        class FakeFileDownloader(object):
            def __init__(self):
                self.calls = Counter()

            def download(self, url, file_path=None, *args, **kwargs):
                if "slow" in url:
                    time.sleep(0.5)
                self.calls[url] += 1
                if file_path:
                    save(file_path, url)
                else:
                    return url

        self.file_downloader = FakeFileDownloader()
        self.cached_downloader = CachedFileDownloader(cache_folder, self.file_downloader)

    def test_concurrent_locks(self):
        folder = temp_folder()

        def download(index):
            if index % 2:
                content = self.cached_downloader.download("slow_testurl")
                content = content.decode("utf-8")
            else:
                file_path = os.path.join(folder, "myfile%s.txt" % index)
                self.cached_downloader.download("slow_testurl", file_path)
                content = load(file_path)
            self.assertEqual(content, "slow_testurl")
            self.assertEqual(self.file_downloader.calls["slow_testurl"], 1)

        ps = []
        for i in range(8):
            thread = Thread(target=download, args=(i,))
            thread.start()
            ps.append(thread)

        for p in ps:
            p.join()

        self.assertEqual(self.file_downloader.calls["slow_testurl"], 1)

    def test_basic(self):
        folder = temp_folder()
        file_path = os.path.join(folder, "myfile.txt")
        self.cached_downloader.download("testurl", file_path)
        self.assertEqual(self.file_downloader.calls["testurl"], 1)
        self.assertEqual("testurl", load(file_path))

        # Try again, the count will be the same
        self.cached_downloader.download("testurl", file_path)
        self.assertEqual(self.file_downloader.calls["testurl"], 1)
        # Try direct content
        content = self.cached_downloader.download("testurl")
        self.assertEqual(content.decode("utf-8"), "testurl")
        self.assertEqual(self.file_downloader.calls["testurl"], 1)

        # Try another file
        file_path = os.path.join(folder, "myfile2.txt")
        self.cached_downloader.download("testurl2", file_path)
        self.assertEqual(self.file_downloader.calls["testurl2"], 1)
        self.assertEqual("testurl2", load(file_path))
        self.cached_downloader.download("testurl2", file_path)
        self.assertEqual(self.file_downloader.calls["testurl"], 1)
        self.assertEqual(self.file_downloader.calls["testurl2"], 1)

    def test_content_first(self):
        # first calling content without path also caches
        content = self.cached_downloader.download("testurl")
        self.assertEqual(content.decode("utf-8"), "testurl")  # content is binary here
        self.assertEqual(self.file_downloader.calls["testurl"], 1)
        # Now the file
        folder = temp_folder()
        file_path = os.path.join(folder, "myfile.txt")
        self.cached_downloader.download("testurl", file_path)
        self.assertEqual(self.file_downloader.calls["testurl"], 1)
        self.assertEqual("testurl", load(file_path))
