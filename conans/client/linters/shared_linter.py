import os


def _search_libs(folder, extensions):
    files = os.listdir(folder)
    for f in files:
        _, ext = os.path.splitext(f)
        if ext in extensions:
            return True
    return False


def linter(conanfile, output):
    try:
        shared = conanfile.options.shared
    except:
        return

    lib_paths = conanfile.cpp_info.lib_paths
    bin_paths = conanfile.cpp_info.bin_paths
    os = conanfile.settings.os
    if shared:
        if os == "Windows":
            ext, paths = (".dll", bin_paths)
        elif os == "Macos":
            ext, paths = (".dylib", lib_paths)
        elif os == "Linux" or os == "FreeBSD" or os == "SunOS":
            ext, paths = (".so", lib_paths)
        else:
            return

        libs = any(_search_libs(folder, [ext]) for folder in paths)
        if not libs:
            output.werror("SharedLinter: shared package does not contain any %s file" % ext)

        # Check for linking libs
        if os == "Windows":
            ext = ".lib" if conanfile.settings.compiler == "Visual Studio" else ".a"
            libs = any(_search_libs(folder, [ext]) for folder in lib_paths)
            if not libs:
                output.werror("SharedLinter: shared package does not contain any %s link library"
                              % ext)
    else:
        if os == "Windows" and conanfile.settings.compiler == "Visual Studio":
            ext = ".lib"
        else:
            ext = ".a"
        libs = any(_search_libs(folder, [ext]) for folder in lib_paths)
        if not libs:
            output.werror("SharedLinter: static package does not contain any %s file" % ext)
