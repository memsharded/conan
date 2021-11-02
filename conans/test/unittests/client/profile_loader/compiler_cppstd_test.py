# coding=utf-8

import os
import textwrap
import unittest

from jinja2 import Template

from conans.client.cache.cache import ClientCache
from conans.client.conf import get_default_settings_yml
from conans.client.profile_loader import profile_from_args
from conans.errors import ConanException
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


class SettingsCppStdTests(unittest.TestCase):

    def setUp(self):
        self.tmp_folder = temp_folder()
        self.cache = ClientCache(self.tmp_folder)

    def _save_profile(self, compiler_cppstd=None, filename="default"):
        fullpath = os.path.join(self.cache.profiles_path, filename)

        t = Template(textwrap.dedent("""
            [settings]
            os=Macos
            arch=x86_64
            compiler=apple-clang
            {% if compiler_cppstd %}compiler.cppstd={{ compiler_cppstd }}{% endif %}
            compiler.libcxx=libc++
            compiler.version=10.0
            """))

        save(fullpath, t.render(compiler_cppstd=compiler_cppstd))
        return filename

    def test_no_compiler_cppstd(self):
        # https://github.com/conan-io/conan/issues/5128
        fullpath = os.path.join(self.cache.profiles_path, "default")
        t = textwrap.dedent("""
            [settings]
            os=Macos
            arch=x86_64
            compiler=apple-clang
            compiler.libcxx=libc++
            compiler.version=10.0
            compiler.cppstd = 14
            """)
        save(self.cache.settings_path, get_default_settings_yml().replace("cppstd", "foobar"))
        save(fullpath, t)
        r = profile_from_args(["default", ], [], [], [], [], cwd=self.tmp_folder, cache=self.cache)
        with self.assertRaisesRegex(ConanException,
                                   "'settings.compiler.cppstd' doesn't exist for 'apple-clang'"):
            r.process_settings(self.cache)

    def test_no_value(self):
        self._save_profile()

        r = profile_from_args(["default", ], [], [], [], [], cwd=self.tmp_folder, cache=self.cache)
        r.process_settings(self.cache)
        self.assertNotIn("compiler.cppstd", r.settings)

    def test_value_none(self):
        self._save_profile(compiler_cppstd="None")

        r = profile_from_args(["default", ], [], [], [], [], cwd=self.tmp_folder, cache=self.cache)
        r.process_settings(self.cache)
        self.assertEqual(r.settings["compiler.cppstd"], "None")
        self.assertNotIn("cppstd", r.settings)

    def test_value_valid(self):
        self._save_profile(compiler_cppstd="11")

        r = profile_from_args(["default", ], [], [], [], [], cwd=self.tmp_folder, cache=self.cache)
        r.process_settings(self.cache)
        self.assertEqual(r.settings["compiler.cppstd"], "11")
        self.assertNotIn("cppstd", r.settings)

    def test_value_invalid(self):
        self._save_profile(compiler_cppstd="13")

        r = profile_from_args(["default", ], [], [], [], [], cwd=self.tmp_folder, cache=self.cache)
        with self.assertRaisesRegex(ConanException, "Invalid setting '13' is not a valid "
                                                    "'settings.compiler.cppstd' value"):
            r.process_settings(self.cache)
        self.assertNotIn("cppstd", r.settings)
