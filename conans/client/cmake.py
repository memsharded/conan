from conans.errors import ConanException
from conans.model.settings import Settings


class CMake(object):

    def __init__(self, settings):
        assert isinstance(settings, Settings)
        self._settings = settings

    @staticmethod
    def options_cmd_line(options, option_upper=True, value_upper=True):
        result = []
        for option, value in options.values.as_list():
            if value is not None:
                option = option.upper() if option_upper else option
                value = value.upper() if value_upper else value
                result.append("-D%s=%s" % (option, value))
        return ' '.join(result)

    @property
    def generator(self):
        if (not self._settings.compiler or
            not self._settings.compiler.version or
            not self._settings.arch):
            raise ConanException("You must specify compiler, compiler.version and arch in "
                                 "your settings to use a CMake generator")

        operating_system = str(self._settings.os) if self._settings.os else None
        compiler = str(self._settings.compiler) if self._settings.compiler else None
        arch = str(self._settings.arch) if self._settings.arch else None

        if compiler == "Visual Studio":
            base = "Visual Studio %s" % self._settings.compiler.version
            if arch == "x86_64":
                return base + " Win64"
            elif arch == "arm":
                return base + " ARM"
            else:
                return base

        if operating_system == "Windows":
            if compiler == "gcc":
                return "MinGW Makefiles"
            if compiler in ["clang", "apple-clang"]:
                return "MinGW Makefiles"
        if operating_system == "Linux":
            if compiler in ["gcc", "clang", "apple-clang"]:
                return "Unix Makefiles"
        if operating_system == "Macos":
            if compiler in ["gcc", "clang", "apple-clang"]:
                return "Unix Makefiles"

        raise ConanException("Unknown cmake generator for these settings")

    @property
    def is_multi_configuration(self):
        """ some IDEs are multi-configuration, as Visual. Makefiles or Ninja are single-conf
        """
        if "Visual" in str(self._settings.compiler):
            return True
        # TODO: complete logic
        return False

    @property
    def command_line(self):
        return '-G "%s" %s %s %s -Wno-dev' % (self.generator, self.build_type,
                                              self.runtime, self.flags)

    @property
    def build_type(self):
        try:
            build_type = self._settings.build_type
        except ConanException:
            return ""
        if build_type and not self.is_multi_configuration:
            return "-DCMAKE_BUILD_TYPE=%s" % build_type
        return ""

    @property
    def build_config(self):
        """ cmake --build tool have a --config option for Multi-configuration IDEs
        """
        try:
            build_type = self._settings.build_type
        except ConanException:
            return ""
        if build_type and self.is_multi_configuration:
            return "--config %s" % build_type
        return ""

    @property
    def flags(self):
        op_system = str(self._settings.os) if self._settings.os else None
        arch = str(self._settings.arch) if self._settings.arch else None
        comp = str(self._settings.compiler) if self._settings.compiler else None
        comp_version = self._settings.compiler.version

        flags = []
        if op_system == "Windows":
            if comp == "clang":
                flags.append("-DCMAKE_C_COMPILER=clang")
                flags.append("-DCMAKE_CXX_COMPILER=clang++")
        if comp:
            flags.append('-DCONAN_COMPILER="%s"' % comp)
        if comp_version:
            flags.append('-DCONAN_COMPILER_VERSION="%s"' % comp_version)
        if arch == "x86":
            if op_system == "Linux":
                flags.extend(["-DCONAN_CXX_FLAGS=-m32",
                             "-DCONAN_SHARED_LINKER_FLAGS=-m32",
                             "-DCONAN_C_FLAGS=-m32"])
            elif op_system == "Macos":
                flags.append("-DCMAKE_OSX_ARCHITECTURES=i386")

        try:
            stdlib = self._settings.stdlib
            flags.append('-DCONAN_STDLIB="%s"' % stdlib)
        except:
            pass
        return " ".join(flags)

    @property
    def runtime(self):
        runtime = ""
        deprecation_warn = False
        # Check if exists the old compiler.runtime
        try:
            runtime = self._settings.compiler.runtime
            if runtime:
                deprecation_warn = True
        except ConanException:
            pass

        try:
            runtime = self._settings.msvcrt
        except ConanException:
            pass

        ret = ""
        if runtime:
            ret = "-DCONAN_LINK_RUNTIME=/%s" % runtime
            if deprecation_warn:
                ret += " -DRUNTIME_DEPRECATION_WARNING=ON"
        return ret
