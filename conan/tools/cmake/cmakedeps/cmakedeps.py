import os

from conan.tools.cmake.cmakedeps.templates.config import ConfigTemplate
from conan.tools.cmake.cmakedeps.templates.config_version import ConfigVersionTemplate
from conan.tools.cmake.cmakedeps.templates.macros import MacrosTemplate
from conan.tools.cmake.cmakedeps.templates.target_configuration import TargetConfigurationTemplate
from conan.tools.cmake.cmakedeps.templates.target_data import ConfigDataTemplate
from conan.tools.cmake.cmakedeps.templates.targets import TargetsTemplate
from conans.util.files import save


class CMakeDeps(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.arch = self._conanfile.settings.get_safe("arch")
        self.configuration = str(self._conanfile.settings.build_type)
        self.configurations = [v for v in conanfile.settings.build_type.values_range if v != "None"]

    def generate(self):
        # Current directory is the generators_folder
        generator_files = self.content
        for generator_file, content in generator_files.items():
            save(generator_file, content)

    @property
    def content(self):
        macros = MacrosTemplate()
        ret = {macros.filename: macros.render()}

        for require, transitive in self._conanfile._conan_node.transitive_deps.items():
            if require.build:
                continue

            req = transitive.node.conanfile

            config_version = ConfigVersionTemplate(self, req)
            ret[config_version.filename] = config_version.render()

            self.require = require
            data_target = ConfigDataTemplate(self, req)
            ret[data_target.filename] = data_target.render()

            target_configuration = TargetConfigurationTemplate(self, req)
            ret[target_configuration.filename] = target_configuration.render()

            targets = TargetsTemplate(self, req)
            ret[targets.filename] = targets.render()

            config = ConfigTemplate(self, req)
            # Check if the XXConfig.cmake exists to keep the first generated configuration
            # to only include the build_modules from the first conan install. The rest of the
            # file is common for the different configurations.
            if not os.path.exists(config.filename):
                ret[config.filename] = config.render()
        return ret