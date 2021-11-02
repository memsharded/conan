import mock
import pytest
from mock import Mock
import re

from conan.tools.google import BazelDeps
from conans import ConanFile
from conans.model.conanfile_interface import ConanFileInterface
from conans.model.dependencies import Requirement, ConanFileDependencies
from conans.model.build_info import CppInfo
from conans.model.ref import ConanFileReference


def test_bazeldeps_dependency_buildfiles():
    conanfile = ConanFile(None)

    cpp_info = CppInfo(set_defaults=True)
    cpp_info.defines = ["DUMMY_DEFINE=\"string/value\""]
    cpp_info.system_libs = ["system_lib1"]
    cpp_info.libs = ["lib1"]

    conanfile_dep = ConanFile(None)
    conanfile_dep.cpp_info = cpp_info
    conanfile_dep._conan_node = Mock()
    conanfile_dep._conan_node.ref = ConanFileReference.loads("OriginalDepName/1.0")
    conanfile_dep.package_folder = "/path/to/folder_dep"

    with mock.patch('conans.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
        req = Requirement(ConanFileReference.loads("OriginalDepName/1.0"))
        mock_deps.return_value = ConanFileDependencies({req: ConanFileInterface(conanfile_dep)})

        bazeldeps = BazelDeps(conanfile)

        for dependency in bazeldeps._conanfile.dependencies.host.values():
            dependency_content = bazeldeps._get_dependency_buildfile_content(dependency)
            assert 'cc_library(\n    name = "OriginalDepName",' in dependency_content
            assert 'defines = ["DUMMY_DEFINE=\'string/value\'"],' in dependency_content
            assert 'linkopts = ["-lsystem_lib1"],' in dependency_content
            assert 'deps = [\n    \n    ":lib1_precompiled",' in dependency_content

def test_bazeldeps_interface_buildfiles():
    conanfile = ConanFile(None)

    cpp_info = CppInfo(set_defaults=True)

    conanfile_dep = ConanFile(None)
    conanfile_dep.cpp_info = cpp_info
    conanfile_dep._conan_node = Mock()
    conanfile_dep._conan_node.ref = ConanFileReference.loads("OriginalDepName/2.0")

    with mock.patch('conans.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
        req = Requirement(ConanFileReference.loads("OriginalDepName/1.0"))
        mock_deps.return_value = ConanFileDependencies({req: ConanFileInterface(conanfile_dep)})

        bazeldeps = BazelDeps(conanfile)

        dependency = next(iter(bazeldeps._conanfile.dependencies.host.values()))
        dependency_content = re.sub(r"\s", "", bazeldeps._get_dependency_buildfile_content(dependency))
        assert(dependency_content == 'load("@rules_cc//cc:defs.bzl","cc_import","cc_library")cc_library(name="OriginalDepName",hdrs=glob(["include/**"]),includes=["include"],visibility=["//visibility:public"],)')

def test_bazeldeps_main_buildfile():
    expected_content = [
        'def load_conan_dependencies():',
        'native.new_local_repository(',
        'name="OriginalDepName",',
        'path="/path/to/folder_dep",',
        'build_file="conandeps/OriginalDepName/BUILD",'
    ]

    conanfile = ConanFile(None)

    cpp_info = CppInfo(set_defaults=True)

    conanfile_dep = ConanFile(None)
    conanfile_dep.cpp_info = cpp_info
    conanfile_dep._conan_node = Mock()
    conanfile_dep._conan_node.ref = ConanFileReference.loads("OriginalDepName/1.0")
    conanfile_dep.package_folder = "/path/to/folder_dep"

    with mock.patch('conans.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
        req = Requirement(ConanFileReference.loads("OriginalDepName/1.0"))
        mock_deps.return_value = ConanFileDependencies({req: ConanFileInterface(conanfile_dep)})

        bazeldeps = BazelDeps(conanfile)

        local_repositories = []
        for dependency in bazeldeps._conanfile.dependencies.host.values():
            content = bazeldeps._create_new_local_repository(dependency,
                                                             "conandeps/OriginalDepName/BUILD")
            local_repositories.append(content)

        content = bazeldeps._get_main_buildfile_content(local_repositories)

        for line in expected_content:
            assert line in content
