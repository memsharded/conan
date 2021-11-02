import os
import textwrap
import unittest

from mock import patch
from requests import Response

from conans.client import tools
from conans.test.utils.tools import TestClient, TestRequester
from conans.util.files import save


@patch.dict('os.environ', {})
class ProxiesConfTest(unittest.TestCase):

    def test_requester_with_host_specific_proxies(self):
        class MyHttpRequester(TestRequester):

            def get(self, _, **kwargs):
                resp = Response()
                # resp._content = b'{"results": []}'
                resp.status_code = 200
                resp._content = b''
                print(kwargs["proxies"])
                return resp

        client = TestClient(requester_class=MyHttpRequester)
        conf = textwrap.dedent("""
            [proxies]
            https=http://conan.url
              only.for.this.conan.url = http://special.url
              only.for.that.conan.url = http://user:pass@extra.special.url
            http=
              only.for.the.other.conan.url = http://other.special.url
                    """)
        save(client.cache.conan_conf_path, conf)
        conanfile = textwrap.dedent("""
              from conans import ConanFile
              from conan.tools.files import download

              class Pkg(ConanFile):
                  settings = "os", "compiler"

                  def source(self):
                      download(self, "MyUrl", "filename.txt")
        """)
        client.save({"conanfile.py": conanfile})
        client.run("create . foo/1.0@")
        assert "{'https': 'http://conan.url', " \
               "'https://only.for.this.conan.url': 'http://special.url', " \
               "'https://only.for.that.conan.url': 'http://user:pass@extra.special.url', " \
               "'http://only.for.the.other.conan.url': 'http://other.special.url'}" in client.out

    def test_new_proxy_exclude(self):

        class MyHttpRequester(TestRequester):

            def get(self, _, **kwargs):
                resp = Response()
                # resp._content = b'{"results": []}'
                resp.status_code = 200
                resp._content = b''
                print("is excluded!" if "proxies" not in kwargs else "is not excluded!")
                return resp

        client = TestClient(requester_class=MyHttpRequester)
        conf = """
[proxies]
https=None
no_proxy_match=MyExcludedUrl*, *otherexcluded_one*
http=http://conan.url
        """
        save(client.cache.conan_conf_path, conf)
        for url in ("**otherexcluded_one***", "MyUrl", "MyExcludedUrl***", "**MyExcludedUrl***"):
            conanfile = textwrap.dedent("""
                      from conans import ConanFile
                      from conan.tools.files import download

                      class Pkg(ConanFile):
                          settings = "os", "compiler"

                          def source(self):
                              download(self, "{}", "filename.txt")
                      """).format(url)
            client.save({"conanfile.py": conanfile})
            client.run("create . foo/1.0@")
            if url in ("MyUrl", "**MyExcludedUrl***"):
                assert "is not excluded!" in client.out
            else:
                assert "is excluded!" in client.out

    def test_environ_kept(self):

        conanfile = textwrap.dedent("""
                from conans import ConanFile
                from conan.tools.files import download

                class Pkg(ConanFile):
                    settings = "os", "compiler"

                    def source(self):
                        download(self, "http://foo.bar/file", "filename.txt")
                """)

        class MyHttpRequester(TestRequester):

            def get(self, _, **kwargs):
                resp = Response()
                # resp._content = b'{"results": []}'
                resp.status_code = 200
                resp._content = b''
                assert "HTTP_PROXY" in os.environ
                print("My requester!")
                return resp

        client = TestClient(requester_class=MyHttpRequester)
        conf = """
[proxies]
        """
        save(client.cache.conan_conf_path, conf)

        client.save({"conanfile.py": conanfile})

        with tools.environment_append({"HTTP_PROXY": "my_system_proxy"}):
            client.run("create . foo/1.0@")

        assert "My requester!" in client.out

    def test_environ_removed(self):
        conanfile = textwrap.dedent("""
                from conans import ConanFile
                from conan.tools.files import download

                class Pkg(ConanFile):
                    settings = "os", "compiler"

                    def source(self):
                        download(self, "http://MyExcludedUrl/file", "filename.txt")
                """)

        class MyHttpRequester(TestRequester):

            def get(self, _, **kwargs):
                resp = Response()
                # resp._content = b'{"results": []}'
                resp.status_code = 200
                resp._content = b''
                assert "HTTP_PROXY" not in os.environ
                assert "http_proxy" not in os.environ
                print("My requester!")
                return resp

        client = TestClient(requester_class=MyHttpRequester)
        conf = """
[proxies]
no_proxy_match=MyExcludedUrl*
"""
        save(client.cache.conan_conf_path, conf)

        with tools.environment_append({"http_proxy": "my_system_proxy"}):
            client.save({"conanfile.py": conanfile})
            client.run("create . foo/1.0@")
            assert "My requester!" in client.out

        with tools.environment_append({"HTTP_PROXY": "my_system_proxy"}):
            self.assertEqual(os.environ["HTTP_PROXY"], "my_system_proxy")
