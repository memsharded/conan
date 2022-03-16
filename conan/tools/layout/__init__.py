import os
# FIXME: Temporary fixes to avoid breaking 1.45, to be removed 2.0
from conan.tools.cmake import cmake_layout, clion_layout
from conan.tools.microsoft import vs_layout


def basic_layout(conanfile, src_folder="."):
    conanfile.folders.build = "build"
    if conanfile.settings.get_safe("build_type"):
        conanfile.folders.build += "-{}".format(str(conanfile.settings.build_type).lower())
    conanfile.folders.generators = os.path.join(conanfile.folders.build, "conan")
    conanfile.cpp.build.bindirs = ["."]
    conanfile.cpp.build.libdirs = ["."]
    conanfile.folders.source = src_folder
