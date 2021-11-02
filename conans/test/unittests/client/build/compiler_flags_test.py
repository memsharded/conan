import unittest
from parameterized.parameterized import parameterized

from conans.client.build.compiler_flags import architecture_flag, \
    build_type_flags, libcxx_define, libcxx_flag, pic_flag
from conans.test.utils.mocks import MockSettings


class CompilerFlagsTest(unittest.TestCase):

    @parameterized.expand([("gcc", "x86", None, "-m32"),
                           ("clang", "x86", None, "-m32"),
                           ("sun-cc", "x86", None, "-m32"),
                           ("gcc", "x86_64", None, "-m64"),
                           ("clang", "x86_64", None, "-m64"),
                           ("sun-cc", "x86_64", None, "-m64"),
                           ("sun-cc", "sparc", None, "-m32"),
                           ("sun-cc", "sparcv9", None, "-m64"),
                           ("gcc", "armv7", None, ""),
                           ("clang", "armv7", None, ""),
                           ("sun-cc", "armv7", None, ""),
                           ("gcc", "s390", None, "-m31"),
                           ("clang", "s390", None, "-m31"),
                           ("sun-cc", "s390", None, "-m31"),
                           ("gcc", "s390x", None, "-m64"),
                           ("clang", "s390x", None, "-m64"),
                           ("sun-cc", "s390x", None, "-m64"),
                           ("Visual Studio", "x86", None, ""),
                           ("Visual Studio", "x86_64", None, ""),
                           ("gcc", "ppc32", "AIX", "-maix32"),
                           ("gcc", "ppc64", "AIX", "-maix64"),
                           ])
    def test_arch_flag(self, compiler, arch, the_os, flag):
        settings = MockSettings({"compiler": compiler,
                                 "arch": arch,
                                 "os": the_os})
        self.assertEqual(architecture_flag(settings), flag)

    def test_catalyst(self):
        settings = MockSettings({"compiler": "apple-clang",
                                 "arch": "x86_64",
                                 "os": "Macos",
                                 "os.subsystem": "catalyst"})
        self.assertEqual(architecture_flag(settings), "--target=x86_64-apple-ios-macabi")

        settings = MockSettings({"compiler": "apple-clang",
                                 "arch": "armv8",
                                 "os": "Macos",
                                 "os.subsystem": "catalyst"})
        self.assertEqual(architecture_flag(settings), "--target=arm64-apple-ios-macabi")

    @parameterized.expand([("gcc", "x86", "-m32"),
                           ("gcc", "x86_64", "-m64"),
                           ("Visual Studio", "x86", "/Qm32"),
                           ("Visual Studio", "x86_64", "/Qm64"),
                           ])
    def test_arch_flag_intel(self, base, arch, flag):
        settings = MockSettings({"compiler": "intel",
                                 "compiler.base": base,
                                 "arch": arch})
        self.assertEqual(architecture_flag(settings), flag)

    @parameterized.expand([("e2k-v2", "-march=elbrus-v2"),
                           ("e2k-v3", "-march=elbrus-v3"),
                           ("e2k-v4", "-march=elbrus-v4"),
                           ("e2k-v5", "-march=elbrus-v5"),
                           ("e2k-v6", "-march=elbrus-v6"),
                           ("e2k-v7", "-march=elbrus-v7"),
                           ])
    def test_arch_flag_mcst_lcc(self, arch, flag):
        settings = MockSettings({"compiler": "mcst-lcc",
                                 "compiler.base": "gcc",
                                 "arch": arch})
        self.assertEqual(architecture_flag(settings), flag)

    @parameterized.expand([("gcc", "libstdc++", "_GLIBCXX_USE_CXX11_ABI=0"),
                           ("gcc", "libstdc++11", "_GLIBCXX_USE_CXX11_ABI=1"),
                           ("clang", "libstdc++", "_GLIBCXX_USE_CXX11_ABI=0"),
                           ("clang", "libstdc++11", "_GLIBCXX_USE_CXX11_ABI=1"),
                           ("clang", "libc++", ""),
                           ("Visual Studio", None, ""),
                           ])
    def test_libcxx_define(self, compiler, libcxx, define):
        settings = MockSettings({"compiler": compiler,
                                 "compiler.libcxx": libcxx})
        self.assertEqual(libcxx_define(settings), define)

    @parameterized.expand([("gcc", "libstdc++", ""),
                           ("gcc", "libstdc++11", ""),
                           ("clang", "libstdc++", "-stdlib=libstdc++"),
                           ("clang", "libstdc++11", "-stdlib=libstdc++"),
                           ("clang", "libc++", "-stdlib=libc++"),
                           ("apple-clang", "libstdc++", "-stdlib=libstdc++"),
                           ("apple-clang", "libstdc++11", "-stdlib=libstdc++"),
                           ("apple-clang", "libc++", "-stdlib=libc++"),
                           ("Visual Studio", None, ""),
                           ("sun-cc", "libCstd", "-library=Cstd"),
                           ("sun-cc", "libstdcxx", "-library=stdcxx4"),
                           ("sun-cc", "libstlport", "-library=stlport4"),
                           ("sun-cc", "libstdc++", "-library=stdcpp")
                           ])
    def test_libcxx_flags(self, compiler, libcxx, flag):
        settings = MockSettings({"compiler": compiler,
                                 "compiler.libcxx": libcxx})
        self.assertEqual(libcxx_flag(settings), flag)

    @parameterized.expand([("cxx",),
                           ("gpp",),
                           ("cpp",),
                           ("cpp-ne",),
                           ("acpp",),
                           ("acpp-ne",),
                           ("ecpp",),
                           ("ecpp-ne",)])
    def test_libcxx_flags_qnx(self, libcxx):
        settings = MockSettings({"compiler": "qcc",
                                 "compiler.libcxx": libcxx})
        arch_flags = libcxx_flag(settings)
        self.assertEqual(arch_flags, '-Y _%s' % libcxx)

    def test_pic_flags(self):
        flag = pic_flag(MockSettings({}))
        self.assertEqual(flag, '')

        flags = pic_flag(MockSettings({"compiler": 'gcc'}))
        self.assertEqual(flags, '-fPIC')

        flags = pic_flag(MockSettings({"compiler": 'Visual Studio'}))
        self.assertEqual(flags, "")

        flags = pic_flag(MockSettings({"compiler": 'intel', "compiler.base": "gcc"}))
        self.assertEqual(flags, '-fPIC')

        flags = pic_flag(MockSettings({"compiler": 'intel', "compiler.base": "Visual Studio"}))
        self.assertEqual(flags, '')

    @parameterized.expand([("Visual Studio", "Debug", None, "-Zi -Ob0 -Od"),
                           ("Visual Studio", "Release", None, "-O2 -Ob2"),
                           ("Visual Studio", "RelWithDebInfo", None, "-Zi -O2 -Ob1"),
                           ("Visual Studio", "MinSizeRel", None, "-O1 -Ob1"),
                           ("Visual Studio", "Debug", "v140_clang_c2", "-gline-tables-only -fno-inline -O0"),
                           ("Visual Studio", "Release", "v140_clang_c2", "-O2"),
                           ("Visual Studio", "RelWithDebInfo", "v140_clang_c2", "-gline-tables-only -O2 -fno-inline"),
                           ("Visual Studio", "MinSizeRel", "v140_clang_c2", ""),
                           ("gcc", "Debug", None, "-g"),
                           ("gcc", "Release", None, "-O3 -s"),
                           ("gcc", "RelWithDebInfo", None, "-O2 -g"),
                           ("gcc", "MinSizeRel", None, "-Os"),
                           ("clang", "Debug", None, "-g"),
                           ("clang", "Release", None, "-O3"),
                           ("clang", "RelWithDebInfo", None, "-O2 -g"),
                           ("clang", "MinSizeRel", None, "-Os"),
                           ("apple-clang", "Debug", None, "-g"),
                           ("apple-clang", "Release", None, "-O3"),
                           ("apple-clang", "RelWithDebInfo", None, "-O2 -g"),
                           ("apple-clang", "MinSizeRel", None, "-Os"),
                           ("sun-cc", "Debug", None, "-g"),
                           ("sun-cc", "Release", None, "-xO3"),
                           ("sun-cc", "RelWithDebInfo", None, "-xO2 -g"),
                           ("sun-cc", "MinSizeRel", None, "-xO2 -xspace"),
                           ])
    def test_build_type_flags(self, compiler, build_type, vs_toolset, flags):
        settings = MockSettings({"compiler": compiler,
                                 "build_type": build_type,
                                 "compiler.toolset": vs_toolset})
        self.assertEqual(' '.join(build_type_flags(settings)),
                         flags)
