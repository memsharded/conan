import fnmatch
import os
from collections import OrderedDict

from conans.client.generators.text import TXTGenerator
from conans.client.graph.build_mode import BuildMode
from conans.client.graph.graph import BINARY_BUILD, BINARY_WORKSPACE, Node,\
    RECIPE_CONSUMER, RECIPE_VIRTUAL
from conans.client.graph.graph_binaries import GraphBinariesAnalyzer
from conans.client.graph.graph_builder import DepsGraphBuilder
from conans.client.graph.graph_lock_builder import DepsGraphLockBuilder, GraphLockNode
from conans.client.loader import ProcessedProfile
from conans.errors import ConanException, conanfile_exception_formatter
from conans.model.conan_file import get_env_context_manager
from conans.model.graph_info import GraphInfo
from conans.model.ref import ConanFileReference
from conans.paths import BUILD_INFO
from conans.util.files import load


class _RecipeBuildRequires(OrderedDict):
    def __init__(self, conanfile):
        super(_RecipeBuildRequires, self).__init__()
        build_requires = getattr(conanfile, "build_requires", [])
        if not isinstance(build_requires, (list, tuple)):
            build_requires = [build_requires]
        for build_require in build_requires:
            self.add(build_require)

    def add(self, build_require):
        if not isinstance(build_require, ConanFileReference):
            build_require = ConanFileReference.loads(build_require)
        self[build_require.name] = build_require

    def __call__(self, build_require):
        self.add(build_require)

    def update(self, build_requires):
        for build_require in build_requires:
            self.add(build_require)

    def __str__(self):
        return ", ".join(str(r) for r in self.values())


class GraphManager(object):
    def __init__(self, output, client_cache, remote_manager, loader, proxy, resolver):
        self._proxy = proxy
        self._output = output
        self._resolver = resolver
        self._client_cache = client_cache
        self._remote_manager = remote_manager
        self._loader = loader

    def load_consumer_conanfile(self, conanfile_path, info_folder,
                                deps_info_required=False, test=None):
        """loads a conanfile for local flow: source, imports, package, build
        """
        try:
            graph_info = GraphInfo.load(info_folder)
        except IOError:  # Only if file is missing
            # This is very dirty, should be removed for Conan 2.0 (source() method only)
            profile = self._client_cache.default_profile
            profile.process_settings(self._client_cache)
        else:
            profile = graph_info.profile
            profile.process_settings(self._client_cache, preprocess=False)
            # This is the hack of recovering the options from the graph_info
            profile.options.update(graph_info.options)
        processed_profile = ProcessedProfile(profile, None)
        if conanfile_path.endswith(".py"):
            conanfile = self._loader.load_consumer(conanfile_path,
                                                   processed_profile=processed_profile, test=test)
            with get_env_context_manager(conanfile, without_python=True):
                with conanfile_exception_formatter(str(conanfile), "config_options"):
                    conanfile.config_options()
                with conanfile_exception_formatter(str(conanfile), "configure"):
                    conanfile.configure()

                conanfile.settings.validate()  # All has to be ok!
                conanfile.options.validate()
        else:
            conanfile = self._loader.load_conanfile_txt(conanfile_path, processed_profile)

        load_deps_info(info_folder, conanfile, required=deps_info_required)

        return conanfile

    def load_simple_graph(self, reference, profile, recorder):
        # Loads a graph without computing the binaries. It is necessary for
        # export-pkg command, not hitting the server
        # # https://github.com/conan-io/conan/issues/3432
        builder = DepsGraphBuilder(self._proxy, self._output, self._loader, self._resolver,
                                   workspace=None, recorder=recorder)
        processed_profile = ProcessedProfile(profile, create_reference=None)
        conanfile = self._loader.load_virtual([reference], processed_profile)
        root_node = Node(None, conanfile, recipe=RECIPE_VIRTUAL)
        graph = builder.load_graph(root_node, check_updates=False, update=False, remote_name=None,
                                   processed_profile=processed_profile)
        return graph

    def load_graph(self, reference, create_reference, graph_info, build_mode, check_updates, update,
                   remote_name, recorder, workspace):

        def _inject_require(conanfile, reference):
            """ test_package functionality requires injecting the tested package as requirement
            before running the install
            """
            require = conanfile.requires.get(reference.name)
            if require:
                require.conan_reference = require.range_reference = reference
            else:
                conanfile.requires(str(reference))
            conanfile._conan_user = reference.user
            conanfile._conan_channel = reference.channel

        # Computing the full dependency graph
        graph_lock_root_node = None

        profile = graph_info.profile
        graph_lock = graph_info.graph_lock
        cache_settings = profile.processed_settings
        processed_profile = ProcessedProfile(profile, create_reference)
        conan_ref = None
        if isinstance(reference, list):  # Install workspace with multiple root nodes
            conanfile = self._loader.load_virtual(reference, processed_profile)
            root_node = Node(conan_ref, conanfile, recipe=RECIPE_VIRTUAL)
        elif isinstance(reference, ConanFileReference):
            if graph_lock:
                graph_lock_node_id = graph_lock.get_node_from_ref(reference)
                # If we are creating, the root, virtual node is None, and the create_reference
                # Might not be there
                if graph_lock_node_id is None and reference:
                    graph_lock_node_id = graph_lock.get_node_from_ref(None)
                    node = graph_lock._nodes[graph_lock_node_id]
                    graph_lock._nodes[graph_lock_node_id] = GraphLockNode(reference,
                                                                          node.binary_id,
                                                                          node.options_values,
                                                                          node.dependencies,
                                                                          [])
                graph_lock_root_node = graph_lock.insert_virtual([graph_lock_node_id])
            conanfile = self._loader.load_virtual([reference], processed_profile)
            root_node = Node(conan_ref, conanfile, recipe=RECIPE_VIRTUAL)
            root_node.id = graph_lock_root_node
        else:
            if graph_lock:
                graph_lock_ root_node = graph_lock.get_node_from_ref(None)

            if reference.endswith(".py"):
                test = str(create_reference) if create_reference else None
                conanfile = self._loader.load_consumer(reference, processed_profile, test=test)
                if create_reference:  # create with test_package
                    _inject_require(conanfile, create_reference)
                conan_ref = ConanFileReference(conanfile.name, conanfile.version, None, None,
                                               validate=False)
            else:
                conanfile = self._loader.load_conanfile_txt(reference, processed_profile)
            root_node = Node(conan_ref, conanfile, recipe=RECIPE_CONSUMER)
            root_node.id = graph_lock_root_node

        build_mode = BuildMode(build_mode, self._output)
        deps_graph = self._load_graph(root_node, check_updates, update,
                                      build_mode=build_mode, remote_name=remote_name,
                                      profile_build_requires=profile.build_requires,
                                      recorder=recorder, workspace=workspace,
                                      processed_profile=processed_profile,
                                      graph_lock=graph_lock)

        # THIS IS NECESSARY to store dependencies options in profile, for consumer
        # FIXME: This is a hack. Might dissapear if the graph for local commands is always recomputed
        graph_info.options = root_node.conanfile.options.values

        version_ranges_output = self._resolver.output
        if version_ranges_output:
            self._output.success("Version ranges solved")
            for msg in version_ranges_output:
                self._output.info("    %s" % msg)
            self._output.writeln("")

        build_mode.report_matches()
        return deps_graph, conanfile, cache_settings

    @staticmethod
    def _get_recipe_build_requires(conanfile):
        conanfile.build_requires = _RecipeBuildRequires(conanfile)
        if hasattr(conanfile, "build_requirements"):
            with get_env_context_manager(conanfile):
                with conanfile_exception_formatter(str(conanfile), "build_requirements"):
                    conanfile.build_requirements()

        return conanfile.build_requires

    def _recurse_build_requires(self, graph, check_updates, update, build_mode, remote_name,
                                profile_build_requires, recorder, workspace, processed_profile):
        for node in list(graph.nodes):
            # Virtual conanfiles doesn't have output, but conanfile.py and conanfile.txt do
            # FIXME: To be improved and build a explicit model for this
            if node.recipe == RECIPE_VIRTUAL:
                continue
            if (node.binary not in (BINARY_BUILD, BINARY_WORKSPACE) and
                    node.recipe != RECIPE_CONSUMER):
                continue
            package_build_requires = self._get_recipe_build_requires(node.conanfile)
            str_ref = str(node.conan_ref)
            new_profile_build_requires = OrderedDict()
            profile_build_requires = profile_build_requires or {}
            for pattern, build_requires in profile_build_requires.items():
                if ((node.recipe == RECIPE_CONSUMER and pattern == "&") or
                        (node.recipe != RECIPE_CONSUMER and pattern == "&!") or
                        fnmatch.fnmatch(str_ref, pattern)):
                            for build_require in build_requires:
                                if build_require.name in package_build_requires:  # Override existing
                                    package_build_requires[build_require.name] = build_require
                                else:  # Profile one
                                    new_profile_build_requires[build_require.name] = build_require

            if package_build_requires:
                node.conanfile.build_requires_options.clear_unscoped_options()
                build_requires_options = node.conanfile.build_requires_options
                virtual = self._loader.load_virtual(package_build_requires.values(),
                                                    scope_options=False,
                                                    build_requires_options=build_requires_options,
                                                    processed_profile=processed_profile)
                virtual_node = Node(None, virtual, recipe=RECIPE_VIRTUAL)
                build_requires_package_graph = self._load_graph(virtual_node, check_updates, update,
                                                                build_mode, remote_name,
                                                                profile_build_requires,
                                                                recorder, workspace,
                                                                processed_profile)
                graph.add_graph(node, build_requires_package_graph, build_require=True)

            if new_profile_build_requires:
                node.conanfile.build_requires_options.clear_unscoped_options()
                build_requires_options = node.conanfile.build_requires_options
                virtual = self._loader.load_virtual(new_profile_build_requires.values(),
                                                    scope_options=False,
                                                    build_requires_options=build_requires_options,
                                                    processed_profile=processed_profile)
                virtual_node = Node(None, virtual, recipe=RECIPE_VIRTUAL)
                build_requires_profile_graph = self._load_graph(virtual_node, check_updates, update,
                                                                build_mode, remote_name,
                                                                new_profile_build_requires,
                                                                recorder, workspace,
                                                                processed_profile)
                graph.add_graph(node, build_requires_profile_graph, build_require=True)

    def _recurse_build_requires_lock(self, graph, graph_lock, processed_profile,
                                     check_updates, update, build_mode, remote_name, recorder,
                                     workspace):
        for node in list(graph.nodes):
            if node.conanfile.output is None:
                continue
            if node.binary not in (BINARY_BUILD, BINARY_WORKSPACE) and node.conan_ref:
                continue
            graph_lock_node_id = node.id
            build_requires = OrderedDict()
            build_requires_lock_ids = []
            for dependency in graph_lock.dependencies(graph_lock_node_id):
                if dependency.build_require:
                    dep_id = dependency.node_id
                    build_requires_lock_ids.append(dep_id)
                    dep_ref = graph_lock.conan_ref(dep_id)
                    build_requires[dep_ref.name] = dep_ref
            if build_requires:
                graph_lock_root_node = graph_lock.insert_virtual(build_requires_lock_ids)
                virtual_conanfile = self._loader.load_virtual(build_requires.values(),
                                                              processed_profile,
                                                              scope_options=False)
                virtual_node = Node(None, virtual_conanfile)
                virtual_node.id = graph_lock_root_node
                build_requires_graph = self._load_graph(virtual_node, check_updates, update,
                                                        build_mode, remote_name,
                                                        build_requires,
                                                        recorder, workspace,
                                                        processed_profile,
                                                        graph_lock)
                graph.add_graph(node, build_requires_graph, build_require=True)

    def _load_graph(self, root_node, check_updates, update, build_mode, remote_name,
                    profile_build_requires, recorder, workspace, processed_profile,
                    graph_lock=None):
        if graph_lock:
            builder = DepsGraphLockBuilder(self._proxy, self._output, self._loader, recorder)
            graph = builder.load_graph(root_node, remote_name, processed_profile, graph_lock)
        else:
            builder = DepsGraphBuilder(self._proxy, self._output, self._loader, self._resolver,
                                       workspace, recorder)
            graph = builder.load_graph(root_node, check_updates, update, remote_name,
                                       processed_profile)

        if build_mode is None:
            return graph
        binaries_analyzer = GraphBinariesAnalyzer(self._client_cache, self._output,
                                                  self._remote_manager, workspace)
        binaries_analyzer.evaluate_graph(graph, build_mode, update, remote_name)

        if graph_lock:
            self._recurse_build_requires_lock(graph, graph_lock, processed_profile, check_updates,
                                              update, build_mode, remote_name, recorder, workspace)
        else:
            self._recurse_build_requires(graph, check_updates, update, build_mode, remote_name,
                                         profile_build_requires, recorder, workspace,
                                         processed_profile)
        return graph


def load_deps_info(current_path, conanfile, required):

    def get_forbidden_access_object(field_name):
        class InfoObjectNotDefined(object):
            def __getitem__(self, item):
                raise ConanException("self.%s not defined. If you need it for a "
                                     "local command run 'conan install'" % field_name)
            __getattr__ = __getitem__

        return InfoObjectNotDefined()

    if not current_path:
        return
    info_file_path = os.path.join(current_path, BUILD_INFO)
    try:
        deps_cpp_info, deps_user_info, deps_env_info = TXTGenerator.loads(load(info_file_path))
        conanfile.deps_cpp_info = deps_cpp_info
        conanfile.deps_user_info = deps_user_info
        conanfile.deps_env_info = deps_env_info
    except IOError:
        if required:
            raise ConanException("%s file not found in %s\nIt is required for this command\n"
                                 "You can generate it using 'conan install'"
                                 % (BUILD_INFO, current_path))
        conanfile.deps_cpp_info = get_forbidden_access_object("deps_cpp_info")
        conanfile.deps_user_info = get_forbidden_access_object("deps_user_info")
    except ConanException:
        raise ConanException("Parse error in '%s' file in %s" % (BUILD_INFO, current_path))
