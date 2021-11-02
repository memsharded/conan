# -*- coding: utf-8 -*-
import os
import platform
import subprocess
import unittest

import pytest
from mock.mock import mock_open, patch
from parameterized import parameterized

from conans.cli.api.conan_api import ConanAPIV2
from conans.client import tools
from conans.client.cache.cache import CONAN_CONF
from conans.client.conf import get_default_client_conf
from conans.cli.output import ConanOutput
from conans.client.conf.detect_vs import vswhere
from conans.client.tools.files import replace_in_file
from conans.errors import ConanException
from conans.model.layout import Infos
from conans.test.utils.mocks import ConanFileMock, RedirectedTestOutput
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, redirect_output
from conans.util.files import load, md5, save
from conans.util.runners import check_output_runner


class ConfigMock:
    def __init__(self):
        self.retry = 0
        self.retry_wait = 0


class RunnerMock(object):
    def __init__(self, return_ok=True, output=None):
        self.command_called = None
        self.return_ok = return_ok
        self.output = output

    def __call__(self, command, output, win_bash=False, subsystem=None):  # @UnusedVariable
        self.command_called = command
        self.win_bash = win_bash
        self.subsystem = subsystem
        if self.output and output and hasattr(output, "write"):
            output.write(self.output)
        return 0 if self.return_ok else 1


class ReplaceInFileTest(unittest.TestCase):
    def setUp(self):
        text = u'J\xe2nis\xa7'
        self.tmp_folder = temp_folder()

        self.win_file = os.path.join(self.tmp_folder, "win_encoding.txt")
        text = text.encode("Windows-1252", "ignore")
        with open(self.win_file, "wb") as handler:
            handler.write(text)

        self.bytes_file = os.path.join(self.tmp_folder, "bytes_encoding.txt")
        with open(self.bytes_file, "wb") as handler:
            handler.write(text)

    def test_replace_in_file(self):
        replace_in_file(self.win_file, "nis", "nus")
        replace_in_file(self.bytes_file, "nis", "nus")

        content = tools.load(self.win_file)
        self.assertNotIn("nis", content)
        self.assertIn("nus", content)

        content = tools.load(self.bytes_file)
        self.assertNotIn("nis", content)
        self.assertIn("nus", content)


class ToolsTest(unittest.TestCase):

    def test_replace_paths(self):
        folder = temp_folder()
        path = os.path.join(folder, "file")
        replace_with = "MYPATH"
        expected = 'Some other contentsMYPATH"finally all text'

        save(path, 'Some other contentsc:\\Path\\TO\\file.txt"finally all text')
        ret = tools.replace_path_in_file(path, "C:/Path/to/file.txt", replace_with,
                                         windows_paths=True)
        self.assertEqual(load(path), expected)
        self.assertTrue(ret)

        save(path, 'Some other contentsC:/Path\\TO\\file.txt"finally all text')
        ret = tools.replace_path_in_file(path, "C:/PATH/to/FILE.txt", replace_with,
                                         windows_paths=True)
        self.assertEqual(load(path), expected)
        self.assertTrue(ret)

        save(path, 'Some other contentsD:/Path\\TO\\file.txt"finally all text')
        ret = tools.replace_path_in_file(path, "C:/PATH/to/FILE.txt", replace_with, strict=False,
                                         windows_paths=True)
        self.assertEqual(load(path), 'Some other contentsD:/Path\\TO\\file.txt"finally all text')
        self.assertFalse(ret)

        # Multiple matches
        s = 'Some other contentsD:/Path\\TO\\file.txt"finally all textd:\\PATH\\to\\file.TXTMoretext'
        save(path, s)
        ret = tools.replace_path_in_file(path, "D:/PATH/to/FILE.txt", replace_with, strict=False,
                                         windows_paths=True)
        self.assertEqual(load(path), 'Some other contentsMYPATH"finally all textMYPATHMoretext')
        self.assertTrue(ret)

        # Automatic windows_paths
        save(path, s)
        ret = tools.replace_path_in_file(path, "D:/PATH/to/FILE.txt", replace_with, strict=False)
        if platform.system() == "Windows":
            self.assertEqual(load(path), 'Some other contentsMYPATH"finally all textMYPATHMoretext')
            self.assertTrue(ret)
        else:
            self.assertFalse(ret)

    def test_load_save(self):
        folder = temp_folder()
        path = os.path.join(folder, "file")
        save(path, u"äüïöñç")
        content = load(path)
        self.assertEqual(content, u"äüïöñç")

    def test_md5(self):
        result = md5(u"äüïöñç")
        self.assertEqual("dfcc3d74aa447280a7ecfdb98da55174", result)

    def test_cpu_count(self):
        output = ConanOutput()
        cpus = tools.cpu_count(output=output)
        self.assertIsInstance(cpus, int)
        self.assertGreaterEqual(cpus, 1)
        with tools.environment_append({"CONAN_CPU_COUNT": "34"}):
            self.assertEqual(tools.cpu_count(output=output), 34)
        with tools.environment_append({"CONAN_CPU_COUNT": "null"}):
            with self.assertRaisesRegex(ConanException, "Invalid CONAN_CPU_COUNT value"):
                tools.cpu_count(output=output)

    @patch("conans.client.tools.oss.CpuProperties.get_cpu_period")
    @patch("conans.client.tools.oss.CpuProperties.get_cpu_quota")
    def test_cpu_count_in_container(self, get_cpu_quota_mock, get_cpu_period_mock):
        get_cpu_quota_mock.return_value = 12000
        get_cpu_period_mock.return_value = 1000

        output = ConanOutput()
        cpus = tools.cpu_count(output=output)
        self.assertEqual(12, cpus)

    def test_get_env_unit(self):
        """
        Unit tests tools.get_env
        """
        # Test default
        self.assertIsNone(
            tools.get_env("NOT_DEFINED", environment={}),
            None
        )
        # Test defined default
        self.assertEqual(
            tools.get_env("NOT_DEFINED_KEY", default="random_default", environment={}),
            "random_default"
        )
        # Test return defined string
        self.assertEqual(
            tools.get_env("FROM_STR", default="", environment={"FROM_STR": "test_string_value"}),
            "test_string_value"
        )
        # Test boolean conversion
        self.assertEqual(
            tools.get_env("BOOL_FROM_STR", default=False, environment={"BOOL_FROM_STR": "1"}),
            True
        )
        self.assertEqual(
            tools.get_env("BOOL_FROM_STR", default=True, environment={"BOOL_FROM_STR": "0"}),
            False
        )
        self.assertEqual(
            tools.get_env("BOOL_FROM_STR", default=False, environment={"BOOL_FROM_STR": "True"}),
            True
        )
        self.assertEqual(
            tools.get_env("BOOL_FROM_STR", default=True, environment={"BOOL_FROM_STR": ""}),
            False
        )
        # Test int conversion
        self.assertEqual(
            tools.get_env("TO_INT", default=2, environment={"TO_INT": "1"}),
            1
        )
        # Test float conversion
        self.assertEqual(
            tools.get_env("TO_FLOAT", default=2.0, environment={"TO_FLOAT": "1"}),
            1.0
        ),
        # Test list conversion
        self.assertEqual(
            tools.get_env("TO_LIST", default=[], environment={"TO_LIST": "1,2,3"}),
            ["1", "2", "3"]
        )
        self.assertEqual(
            tools.get_env("TO_LIST_NOT_TRIMMED", default=[], environment={"TO_LIST_NOT_TRIMMED":
                                                                          " 1 , 2 , 3 "}),
            ["1", "2", "3"]
        )


    def test_get_env_in_conanfile(self):
        """
        Test get_env is available and working in conanfile
        """
        client = TestClient()

        conanfile = """from conans import ConanFile, tools

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"

    def build(self):
        run_tests = tools.get_env("CONAN_RUN_TESTS", default=False)
        print("test_get_env_in_conafile CONAN_RUN_TESTS=%r" % run_tests)
        assert(run_tests == True)
        """
        client.save({"conanfile.py": conanfile})

        with tools.environment_append({"CONAN_RUN_TESTS": "1"}):
            client.run("install .")
            client.run("build .")

    def test_global_tools_overrided(self):
        client = TestClient()

        conanfile = """
from conans import ConanFile, tools

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"

    def build(self):
        assert(tools._global_requester != None)
        """
        client.save({"conanfile.py": conanfile})

        client.run("install .")
        client.run("build .")

        # Not test the real commmand get_command if it's setting the module global vars
        tmp = temp_folder()
        conf = get_default_client_conf().replace("\n[proxies]", "\n[proxies]\nhttp = http://myproxy.com")
        save(os.path.join(tmp, CONAN_CONF), conf)
        with tools.environment_append({"CONAN_USER_HOME": tmp}):
            conan_api = ConanAPIV2()
        conan_api.remotes.list()
        from conans.tools import _global_requester
        self.assertEqual(_global_requester.proxies, {"http": "http://myproxy.com"})

    def test_environment_nested(self):
        with tools.environment_append({"A": "1", "Z": "40"}):
            with tools.environment_append({"A": "1", "B": "2"}):
                with tools.environment_append({"A": "2", "B": "2"}):
                    self.assertEqual(os.getenv("A"), "2")
                    self.assertEqual(os.getenv("B"), "2")
                    self.assertEqual(os.getenv("Z"), "40")
                self.assertEqual(os.getenv("A", None), "1")
                self.assertEqual(os.getenv("B", None), "2")
            self.assertEqual(os.getenv("A", None), "1")
            self.assertEqual(os.getenv("Z", None), "40")

        self.assertEqual(os.getenv("A", None), None)
        self.assertEqual(os.getenv("B", None), None)
        self.assertEqual(os.getenv("Z", None), None)

    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires vswhere")
    def test_vswhere_description_strip(self):
        myoutput = """
[
  {
    "instanceId": "17609d7c",
    "installDate": "2018-06-11T02:15:04Z",
    "installationName": "VisualStudio/15.7.3+27703.2026",
    "installationPath": "",
    "installationVersion": "15.7.27703.2026",
    "productId": "Microsoft.VisualStudio.Product.Enterprise",
    "productPath": "",
    "isPrerelease": false,
    "displayName": "Visual Studio Enterprise 2017",
    "description": "生産性向上と、さまざまな規模のチーム間の調整のための Microsoft DevOps ソリューション",
    "channelId": "VisualStudio.15.Release",
    "channelUri": "https://aka.ms/vs/15/release/channel",
    "enginePath": "",
    "releaseNotes": "https://go.microsoft.com/fwlink/?LinkId=660692#15.7.3",
    "thirdPartyNotices": "https://go.microsoft.com/fwlink/?LinkId=660708",
    "updateDate": "2018-06-11T02:15:04.7009868Z",
    "catalog": {
      "buildBranch": "d15.7",
      "buildVersion": "15.7.27703.2026",
      "id": "VisualStudio/15.7.3+27703.2026",
      "localBuild": "build-lab",
      "manifestName": "VisualStudio",
      "manifestType": "installer",
      "productDisplayVersion": "15.7.3",
      "productLine": "Dev15",
      "productLineVersion": "2017",
      "productMilestone": "RTW",
      "productMilestoneIsPreRelease": "False",
      "productName": "Visual Studio",
      "productPatchVersion": "3",
      "productPreReleaseMilestoneSuffix": "1.0",
      "productRelease": "RTW",
      "productSemanticVersion": "15.7.3+27703.2026",
      "requiredEngineVersion": "1.16.1187.57215"
    },
    "properties": {
      "campaignId": "",
      "canceled": "0",
      "channelManifestId": "VisualStudio.15.Release/15.7.3+27703.2026",
      "nickname": "",
      "setupEngineFilePath": ""
    }
  },
  {
    "instanceId": "VisualStudio.12.0",
    "installationPath": "",
    "installationVersion": "12.0"
  }
]

"""
        myoutput = myoutput.encode()
        myrunner = mock_open()
        myrunner.check_output = lambda x: myoutput
        with patch('conans.client.conf.detect_vs.subprocess', myrunner):
            json = vswhere()
            self.assertNotIn("descripton", json)

    @parameterized.expand([
        ["Linux", "x86", None, "x86-linux-gnu"],
        ["Linux", "x86_64", None, "x86_64-linux-gnu"],
        ["Linux", "armv6", None, "arm-linux-gnueabi"],
        ["Linux", "sparc", None, "sparc-linux-gnu"],
        ["Linux", "sparcv9", None, "sparc64-linux-gnu"],
        ["Linux", "mips", None, "mips-linux-gnu"],
        ["Linux", "mips64", None, "mips64-linux-gnu"],
        ["Linux", "ppc32", None, "powerpc-linux-gnu"],
        ["Linux", "ppc64", None, "powerpc64-linux-gnu"],
        ["Linux", "ppc64le", None, "powerpc64le-linux-gnu"],
        ["Linux", "armv5te", None, "arm-linux-gnueabi"],
        ["Linux", "arm_whatever", None, "arm-linux-gnueabi"],
        ["Linux", "armv7hf", None, "arm-linux-gnueabihf"],
        ["Linux", "armv6", None, "arm-linux-gnueabi"],
        ["Linux", "armv7", None, "arm-linux-gnueabi"],
        ["Linux", "armv8_32", None, "aarch64-linux-gnu_ilp32"],
        ["Linux", "armv5el", None, "arm-linux-gnueabi"],
        ["Linux", "armv5hf", None, "arm-linux-gnueabihf"],
        ["Linux", "s390", None, "s390-ibm-linux-gnu"],
        ["Linux", "s390x", None, "s390x-ibm-linux-gnu"],
        ["Android", "x86", None, "i686-linux-android"],
        ["Android", "x86_64", None, "x86_64-linux-android"],
        ["Android", "armv6", None, "arm-linux-androideabi"],
        ["Android", "armv7", None, "arm-linux-androideabi"],
        ["Android", "armv7hf", None, "arm-linux-androideabi"],
        ["Android", "armv8", None, "aarch64-linux-android"],
        ["Windows", "x86", "Visual Studio", "i686-windows-msvc"],
        ["Windows", "x86", "gcc", "i686-w64-mingw32"],
        ["Windows", "x86_64", "gcc", "x86_64-w64-mingw32"],
        ["Darwin", "x86_64", None, "x86_64-apple-darwin"],
        ["Macos", "x86", None, "i686-apple-darwin"],
        ["iOS", "armv7", None, "arm-apple-ios"],
        ["iOS", "x86", None, "i686-apple-ios"],
        ["iOS", "x86_64", None, "x86_64-apple-ios"],
        ["watchOS", "armv7k", None, "arm-apple-watchos"],
        ["watchOS", "armv8_32", None, "aarch64-apple-watchos"],
        ["watchOS", "x86", None, "i686-apple-watchos"],
        ["watchOS", "x86_64", None, "x86_64-apple-watchos"],
        ["tvOS", "armv8", None, "aarch64-apple-tvos"],
        ["tvOS", "armv8.3", None, "aarch64-apple-tvos"],
        ["tvOS", "x86", None, "i686-apple-tvos"],
        ["tvOS", "x86_64", None, "x86_64-apple-tvos"],
        ["Emscripten", "asm.js", None, "asmjs-local-emscripten"],
        ["Emscripten", "wasm", None, "wasm32-local-emscripten"],
        ["AIX", "ppc32", None, "rs6000-ibm-aix"],
        ["AIX", "ppc64", None, "powerpc-ibm-aix"],
        ["Neutrino", "armv7", None, "arm-nto-qnx"],
        ["Neutrino", "armv8", None, "aarch64-nto-qnx"],
        ["Neutrino", "sh4le", None, "sh4-nto-qnx"],
        ["Neutrino", "ppc32be", None, "powerpcbe-nto-qnx"],
        ["Linux", "e2k-v2", None, "e2k-unknown-linux-gnu"],
        ["Linux", "e2k-v3", None, "e2k-unknown-linux-gnu"],
        ["Linux", "e2k-v4", None, "e2k-unknown-linux-gnu"],
        ["Linux", "e2k-v5", None, "e2k-unknown-linux-gnu"],
        ["Linux", "e2k-v6", None, "e2k-unknown-linux-gnu"],
        ["Linux", "e2k-v7", None, "e2k-unknown-linux-gnu"],
    ])
    def test_get_gnu_triplet(self, os, arch, compiler, expected_triplet):
        triplet = tools.get_gnu_triplet(os, arch, compiler)
        self.assertEqual(triplet, expected_triplet,
                         "triplet did not match for ('%s', '%s', '%s')" % (os, arch, compiler))

    def test_get_gnu_triplet_on_windows_without_compiler(self):
        with self.assertRaises(ConanException):
            tools.get_gnu_triplet("Windows", "x86")

    def test_check_output_runner(self):
        original_temp = temp_folder()
        patched_temp = os.path.join(original_temp, "dir with spaces")
        payload = "hello world"
        with patch("tempfile.mktemp") as mktemp:
            mktemp.return_value = patched_temp
            output = check_output_runner(["echo", payload], stderr=subprocess.STDOUT)
            self.assertIn(payload, str(output))

    def test_unix_to_dos_conanfile(self):
        client = TestClient()
        conanfile = """
import os
from conans import ConanFile, tools

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports_sources = "file.txt"

    def build(self):
        assert("\\r\\n" in tools.load("file.txt"))
        tools.dos2unix("file.txt")
        assert("\\r\\n" not in tools.load("file.txt"))
        tools.unix2dos("file.txt")
        assert("\\r\\n" in tools.load("file.txt"))
"""
        client.save({"conanfile.py": conanfile, "file.txt": "hello\r\n"})
        client.run("create . user/channel")


class CollectLibTestCase(unittest.TestCase):

    def test_collect_libs(self):
        output = RedirectedTestOutput()
        with redirect_output(output):
            conanfile = ConanFileMock()
            # Without package_folder
            conanfile.package_folder = None
            result = tools.collect_libs(conanfile)
            self.assertEqual([], result)

            # Default behavior
            conanfile.package_folder = temp_folder()
            mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
            save(mylib_path, "")
            conanfile.cpp = Infos()
            result = tools.collect_libs(conanfile)
            self.assertEqual(["mylib"], result)

            # Custom folder
            customlib_path = os.path.join(conanfile.package_folder, "custom_folder", "customlib.lib")
            save(customlib_path, "")
            result = tools.collect_libs(conanfile, folder="custom_folder")
            self.assertEqual(["customlib"], result)

            # Custom folder doesn't exist
            result = tools.collect_libs(conanfile, folder="fake_folder")
            self.assertEqual([], result)
            self.assertIn("Lib folder doesn't exist, can't collect libraries:", output.getvalue())
            output.clear()

            # Use cpp_info.libdirs
            conanfile.cpp_info.libdirs = ["lib", "custom_folder"]
            result = tools.collect_libs(conanfile)
            self.assertEqual(["customlib", "mylib"], result)

            # Custom folder with multiple libdirs should only collect from custom folder
            self.assertEqual(["lib", "custom_folder"], conanfile.cpp_info.libdirs)
            result = tools.collect_libs(conanfile, folder="custom_folder")
            self.assertEqual(["customlib"], result)

            # Warn same lib different folders
            conanfile = ConanFileMock()
            conanfile.package_folder = temp_folder()
            conanfile.cpp = Infos()
            custom_mylib_path = os.path.join(conanfile.package_folder, "custom_folder", "mylib.lib")
            lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
            save(custom_mylib_path, "")
            save(lib_mylib_path, "")
            conanfile.cpp_info.libdirs = ["lib", "custom_folder"]

            output.clear()
            result = tools.collect_libs(conanfile)
            self.assertEqual(["mylib"], result)
            self.assertIn("Library 'mylib' was either already found in a previous "
                          "'conanfile.cpp_info.libdirs' folder or appears several times with a "
                          "different file extension", output.getvalue())

            # Warn lib folder does not exist with correct result
            conanfile = ConanFileMock()
            conanfile.package_folder = temp_folder()
            conanfile.cpp = Infos()
            lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
            save(lib_mylib_path, "")
            no_folder_path = os.path.join(conanfile.package_folder, "no_folder")
            conanfile.cpp_info.libdirs = ["no_folder", "lib"]  # 'no_folder' does NOT exist
            output.clear()
            result = tools.collect_libs(conanfile)
            self.assertEqual(["mylib"], result)
            self.assertIn("WARN: Lib folder doesn't exist, can't collect libraries: %s"
                          % no_folder_path, output.getvalue())

    def test_self_collect_libs(self):
        output = RedirectedTestOutput()
        with redirect_output(output):
            conanfile = ConanFileMock()
            # Without package_folder
            conanfile.package_folder = None
            result = tools.collect_libs(conanfile)
            self.assertEqual([], result)

            # Default behavior
            conanfile.package_folder = temp_folder()
            mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
            save(mylib_path, "")
            conanfile.cpp = Infos()
            result = tools.collect_libs(conanfile)
            self.assertEqual(["mylib"], result)

            # Custom folder
            customlib_path = os.path.join(conanfile.package_folder, "custom_folder", "customlib.lib")
            save(customlib_path, "")
            result = tools.collect_libs(conanfile, folder="custom_folder")
            self.assertEqual(["customlib"], result)

            # Custom folder doesn't exist
            output.clear()
            result = tools.collect_libs(conanfile, folder="fake_folder")
            self.assertEqual([], result)
            self.assertIn("Lib folder doesn't exist, can't collect libraries:", output.getvalue())

            # Use cpp_info.libdirs
            conanfile.cpp_info.libdirs = ["lib", "custom_folder"]
            result = tools.collect_libs(conanfile)
            self.assertEqual(["customlib", "mylib"], result)

            # Custom folder with multiple libdirs should only collect from custom folder
            self.assertEqual(["lib", "custom_folder"], conanfile.cpp_info.libdirs)
            result = tools.collect_libs(conanfile, folder="custom_folder")
            self.assertEqual(["customlib"], result)

            # Warn same lib different folders
            conanfile = ConanFileMock()
            conanfile.package_folder = temp_folder()
            conanfile.cpp = Infos()
            custom_mylib_path = os.path.join(conanfile.package_folder, "custom_folder", "mylib.lib")
            lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
            save(custom_mylib_path, "")
            save(lib_mylib_path, "")
            conanfile.cpp_info.libdirs = ["lib", "custom_folder"]
            output.clear()
            result = tools.collect_libs(conanfile)
            self.assertEqual(["mylib"], result)
            self.assertIn("Library 'mylib' was either already found in a previous "
                          "'conanfile.cpp_info.libdirs' folder or appears several times with a "
                          "different file extension", output.getvalue())

            # Warn lib folder does not exist with correct result
            conanfile = ConanFileMock()
            conanfile.package_folder = temp_folder()
            conanfile.cpp = Infos()
            lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
            save(lib_mylib_path, "")
            no_folder_path = os.path.join(conanfile.package_folder, "no_folder")
            conanfile.cpp_info.libdirs = ["no_folder", "lib"]  # 'no_folder' does NOT exist
            output.clear()
            result = tools.collect_libs(conanfile)
            self.assertEqual(["mylib"], result)
            self.assertIn("WARN: Lib folder doesn't exist, can't collect libraries: %s"
                          % no_folder_path, output.getvalue())
