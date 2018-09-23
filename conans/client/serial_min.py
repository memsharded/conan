
from conans.client.recorder.action_recorder import ActionRecorder
from conans.client.output import ScopedOutput
import time
from conans.client.loader import ProcessedProfile
from conans.model.values import Values
from conans.model.ref import ConanFileReference
from conans.model.conan_file import ConanFile


def serial_package_option_values(self):
    result = {k: str(v)
              for k, v in self._dict.items()}
    return result


def serial_values(self):
    return self.as_list()


def unserial_values(data):
    return Values.from_list(data)


def serial_conanfile(conanfile):
    result = {}
    result["settings"] = serial_values(conanfile.settings.values)
    result["options"] = serial_package_option_values(conanfile.options._package_options.values)
    return result


def unserial_conanfile(conanfile, data, env, settings):
    settings_values = unserial_values(data["settings"])
    settings = settings.copy()
    settings.values = settings_values
    # We are recovering state from captured profile from conaninfo, remove not defined
    settings.remove_undefined()
    conanfile.settings = settings
    # Same with options
    package_options_values = unserial_package_option_values(data["options"])


    conanfile._conan_env_values = env.copy()  # user specified -e
    
    # COMPUTE INFO
    
    # COMPUTE REQUIRES


def serial_ref(conan_reference):
    return repr(conan_reference)


def unserial_ref(data):
    if data is None:
        return None
    return ConanFileReference.loads(data)


def serial_edge(edge):
    result = {}
    result["src"] = str(id(edge.src))
    result["dst"] = str(id(edge.dst))
    result["private"] = edge.private
    return result


def serial_node(node):
    result = {}
    result["path"] = getattr(node, "path", None)
    result["conan_ref"] = serial_ref(node.conan_ref) if node.conan_ref else None
    result["conanfile"] = serial_conanfile(node.conanfile)
    result["build_require"] = node.build_require
    return result


def unserial_node(data, env, conanfile_path, output, proxy, loader, update=False,
                  scoped_output=None, remote_name=None):
    path = data["path"]
    conan_ref = unserial_ref(data["conan_ref"])
    t1 = time.time()
    if not path and not conan_ref:
        conanfile = ConanFile(None, loader._runner, Values())
    else:
        if path:
            conanfile_path = conanfile_path
            output = scoped_output
        else:
            result = proxy.get_recipe(conan_ref, check_updates=False, update=update,
                                      remote_name=remote_name, recorder=ActionRecorder())
            conanfile_path, recipe_status, remote, _ = result
            output = ScopedOutput(str(conan_ref or "Project"), output)
        if conanfile_path.endswith(".txt"):
            # FIXME: remove this ugly ProcessedProfile
            conanfile = loader.load_conanfile_txt(conanfile_path, output, ProcessedProfile())
        else:
            conanfile = loader.load_basic(conanfile_path, output, conan_ref)
    from conans.client.graph.graph import Node
    t1 = time.time()
    unserial_conanfile(conanfile, data["conanfile"], env)

    result = Node(conan_ref, conanfile)
    result.recipe = recipe_status
    result.remote = remote
    result.build_require = data["build_require"]
    return result


def serial_graph(graph):
    result = {}
    result["nodes"] = {str(id(n)): serial_node(n) for n in graph.nodes}
    result["edges"] = [serial_edge(e) for n in graph.nodes for e in n.dependencies]
    result["root"] = str(id(graph.root))
    build_order = graph.build_order_ids("ALL")
    result["build_order"] = build_order
    return result


def unserial_graph(data, env, conanfile_path, output, proxy, loader, scoped_output=None, id_=None):
    from conans.client.graph.graph import Node, DepsGraph
    result = DepsGraph()
    nodes_dict = {node_id: unserial_node(n, env, conanfile_path, output, proxy, loader,
                                         scoped_output=scoped_output)
                  for node_id, n in data["nodes"].items()}
    result.nodes = set(nodes_dict.values())
    result.root = nodes_dict[data["root"]]
    for edge in data["edges"]:
        result.add_edge(nodes_dict[edge["src"]], nodes_dict[edge["dst"]], edge["private"])
    if id_:
        node = nodes_dict[id_]
        result.prune_subgraph(node)
        virtual = Node(None, ConanFile(None, loader._runner, Values()))
        result.add_node(virtual)
        result.add_edge(virtual, node)
        result.root = virtual

    return result

