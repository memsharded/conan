from conans.client.graph.graph_error import GraphError
from conans.model.ref import ConanFileReference


def check_graph_provides(dep_graph):
    if dep_graph.error:
        return
    for node in dep_graph.nodes:
        provides = {}
        current_provides = node.conanfile.provides
        for dep in node.transitive_deps.values():
            dep_node = dep.node
            dep_require = dep.require

            if not dep_node.conanfile.provides:
                continue
            for provide in dep_node.conanfile.provides:
                # First check if collides with current node
                if current_provides is not None and provide in current_provides:
                    raise GraphError.provides(node, dep_node)

                # Then, check if collides with other requirements
                new_req = dep_require.copy()
                new_req.ref = ConanFileReference(provide, new_req.ref.version, new_req.ref.user,
                                                 new_req.ref.channel, validate=False)
                existing = node.transitive_deps.get(new_req)
                if existing is not None:
                    raise GraphError.provides(existing.node, dep_node)
                else:
                    existing_provide = provides.get(new_req)
                    if existing_provide is not None:
                        raise GraphError.provides(existing_provide, dep_node)
                    else:
                        provides[new_req] = dep_node