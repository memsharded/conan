from parameterized import parameterized

from conans.client.graph.graph_error import GraphError
from conans.test.integration.graph.core.graph_manager_base import GraphManagerTest
from conans.test.utils.tools import GenConanfile


def _check_transitive(node, transitive_deps):
    values = list(node.transitive_deps.values())

    assert len(values) == len(transitive_deps), \
        "Number of deps don't match \n{}!=\n{}".format(values, transitive_deps)

    for v1, v2 in zip(values, transitive_deps):
        assert v1.node is v2[0]
        assert v1.require.headers is v2[1]
        assert v1.require.libs is v2[2]
        assert v1.require.build is v2[3]
        assert v1.require.run is v2[4]


class TestLinear(GraphManagerTest):
    def test_basic(self):
        deps_graph = self.build_graph(GenConanfile("app", "0.1"))
        self.assertEqual(1, len(deps_graph.nodes))
        node = deps_graph.root
        self._check_node(node, "app/0.1")

    def test_dependency(self):
        # app -> libb0.1
        self.recipe_cache("libb/0.1")
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[], dependents=[app])

    def test_dependency_missing(self):
        # app -> libb0.1 (non existing)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])
        deps_graph = self.build_consumer(consumer, install=False)

        # TODO: Better error handling
        assert deps_graph.error.kind == GraphError.MISSING_RECIPE

        self.assertEqual(1, len(deps_graph.nodes))
        app = deps_graph.root
        self._check_node(app, "app/0.1", deps=[])

    def test_transitive(self):
        # app -> libb0.1 -> liba0.1
        # By default if packages do not specify anything link=True is propagated run=None (unknown)
        self.recipe_cache("liba/0.1")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, None),
                                (liba, True, True, False, None)])
        _check_transitive(libb, [(liba, True, True, False, None)])

    def test_transitive_propagate_link(self):
        # app -> libb0.1 -> liba0.1
        # transitive_link=False will avoid propagating linkage requirement
        self.recipe_cache("liba/0.1")
        self.recipe_conanfile("libb/0.1", GenConanfile().with_requirement("liba/0.1",
                                                                          transitive_libs=False))
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, None),
                                (liba, True, False, False, None)])
        _check_transitive(libb, [(liba, True, True, False, None)])

    def test_transitive_all_static(self):
        # app -> libb0.1 (static) -> liba0.1 (static)
        self.recipe_cache("liba/0.1", option_shared=False)
        self.recipe_cache("libb/0.1", ["liba/0.1"], option_shared=False)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, False),
                                (liba, False, True, False, False)])
        _check_transitive(libb, [(liba, True, True, False, False)])

    def test_transitive_all_static_transitive_headers(self):
        # app -> libb0.1 (static) -> liba0.1 (static)
        self.recipe_cache("liba/0.1", option_shared=False)
        libb = GenConanfile().with_requirement("liba/0.1", transitive_headers=True)
        libb.with_shared_option()
        self.recipe_conanfile("libb/0.1", libb)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, False),
                                (liba, True, True, False, False)])
        _check_transitive(libb, [(liba, True, True, False, False)])

    def test_transitive_all_shared(self):
        # app -> libb0.1 (shared)  -> liba0.1 (shared)
        self.recipe_cache("liba/0.1", option_shared=True)
        self.recipe_cache("libb/0.1", ["liba/0.1"], option_shared=True)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, include, link, build, run
        # Default for app->liba is that it doesn't link, libb shared will isolate symbols by default
        _check_transitive(app, [(libb, True, True, False, True),
                                (liba, False, False, False, True)])
        _check_transitive(libb, [(liba, True, True, False, True)])

    def test_transitive_all_shared_transitive_headers_libs(self):
        # app -> libb0.1 (shared) -> liba0.1 (shared)
        self.recipe_cache("liba/0.1", option_shared=True)
        libb = GenConanfile().with_requirement("liba/0.1", transitive_headers=True,
                                               transitive_libs=True)
        libb.with_shared_option(True)
        self.recipe_conanfile("libb/0.1", libb)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, include, link, build, run
        # Default for app->liba is that it doesn't link, libb shared will isolate symbols by default
        _check_transitive(app, [(libb, True, True, False, True),
                                (liba, True, True, False, True)])
        _check_transitive(libb, [(liba, True, True, False, True)])

    def test_middle_shared_up_static(self):
        # app -> libb0.1 (shared) -> liba0.1 (static)
        self.recipe_cache("liba/0.1", option_shared=False)
        self.recipe_cache("libb/0.1", ["liba/0.1"], option_shared=True)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, True),
                                (liba, False, False, False, False)])
        _check_transitive(libb, [(liba, True, True, False, False)])

    def test_middle_shared_up_static_transitive_headers(self):
        # app -> libb0.1 (shared) -> liba0.1 (static)
        self.recipe_cache("liba/0.1", option_shared=False)
        libb = GenConanfile().with_requirement("liba/0.1", transitive_headers=True)
        libb.with_shared_option(True)
        self.recipe_conanfile("libb/0.1", libb)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, True),
                                (liba, True, False, False, False)])
        _check_transitive(libb, [(liba, True, True, False, False)])

    def test_middle_static_up_shared(self):
        # app -> libb0.1 (static) -> liba0.1 (shared)
        self.recipe_cache("liba/0.1", option_shared=True)
        self.recipe_cache("libb/0.1", ["liba/0.1"], option_shared=False)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, False),
                                (liba, False, True, False, True)])
        _check_transitive(libb, [(liba, True, True, False, True)])

    def test_middle_static_up_shared_transitive_headers(self):
        # app -> libb0.1 (static) -> liba0.1 (shared)
        self.recipe_cache("liba/0.1", option_shared=True)
        libb = GenConanfile().with_requirement("liba/0.1", transitive_headers=True)
        libb.with_shared_option(False)
        self.recipe_conanfile("libb/0.1", libb)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, False),
                                (liba, True, True, False, True)])
        _check_transitive(libb, [(liba, True, True, False, True)])

    def test_private(self):
        # app -> libb0.1 -(private) -> liba0.1
        self.recipe_cache("liba/0.1")
        libb = GenConanfile().with_requirement("liba/0.1", visible=False)
        self.recipe_conanfile("libb/0.1", libb)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, None)])
        _check_transitive(libb, [(liba, True, True, False, None)])

    def test_header_only(self):
        # app -> libb0.1 -> liba0.1 (header_only)
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("header-library"))
        libb = GenConanfile().with_requirement("liba/0.1")
        self.recipe_conanfile("libb/0.1", libb)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, None),
                                (liba, False, False, False, False)])
        _check_transitive(libb, [(liba, True, False, False, False)])


class TestDiamond(GraphManagerTest):

    def test_diamond(self):
        # app -> libb0.1 -> liba0.1
        #    \-> libc0.1 ->/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["liba/0.1"])
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba = libb.dependencies[0].dst

        # TODO: No Revision??? Because of consumer?
        self._check_node(app, "app/0.1", deps=[libb, libc])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc])

        _check_transitive(app, [(libb, True, True, False, None),
                                (libc, True, True, False, None),
                                (liba, True, True, False, None)])

    @parameterized.expand([(True, ), (False, )])
    def test_diamond_additive(self, order):
        # app -> libb0.1 ---------> liba0.1
        #    \-> libc0.1 (run=True)->/
        self.recipe_cache("liba/0.1")
        if order:
            self.recipe_cache("libb/0.1", ["liba/0.1"])
            self.recipe_conanfile("libc/0.1", GenConanfile().with_requirement("liba/0.1", run=True))
        else:
            self.recipe_conanfile("libb/0.1", GenConanfile().with_requirement("liba/0.1", run=True))
            self.recipe_cache("libc/0.1", ["liba/0.1"])

        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba = libb.dependencies[0].dst

        # TODO: No Revision??? Because of consumer?
        self._check_node(app, "app/0.1", deps=[libb, libc])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc])

        _check_transitive(app, [(libb, True, True, False, None),
                                (libc, True, True, False, None),
                                (liba, True, True, False, True)])

    def test_half_diamond(self):
        # app -----------> liba0.1
        #    \-> libc0.1 ->/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("libc/0.1", ["liba/0.1"])
        consumer = self.recipe_consumer("app/0.1", ["liba/0.1", "libc/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        liba = app.dependencies[0].dst
        libc = app.dependencies[1].dst

        # TODO: No Revision??? Because of consumer?
        self._check_node(app, "app/0.1", deps=[liba, libc])
        self._check_node(libc, "libc/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[app, libc])

        # Order seems to be link order
        _check_transitive(app, [(libc, True, True, False, None),
                                (liba, True, True, False, None)])

    def test_shared_static(self):
        # app -> libb0.1 (shared) -> liba0.1 (static)
        #    \-> libc0.1 (shared) ->/
        self.recipe_cache("liba/0.1", option_shared=False)
        self.recipe_cache("libb/0.1", ["liba/0.1"], option_shared=True)
        self.recipe_cache("libc/0.1", ["liba/0.1"], option_shared=True)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba = libb.dependencies[0].dst
        liba1 = libc.dependencies[0].dst

        assert liba is liba1

        self._check_node(app, "app/0.1", deps=[libb, libc])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc])

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, True),
                                (libc, True, True, False, True),
                                (liba, False, False, False, False)])
        _check_transitive(libb, [(liba, True, True, False, False)])
        _check_transitive(libc, [(liba, True, True, False, False)])

    def test_private(self):
        # app -> libd0.1 -(private)-> libb0.1 -> liba0.1
        #            \ ---(private)-> libc0.1 --->/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["liba/0.1"])
        libd = GenConanfile().with_requirement("libb/0.1", visible=False)
        libd.with_requirement("libc/0.1", visible=False)
        self.recipe_conanfile("libd/0.1", libd)
        consumer = self.recipe_consumer("app/0.1", ["libd/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libd = app.dependencies[0].dst
        libb = libd.dependencies[0].dst
        libc = libd.dependencies[1].dst
        liba = libb.dependencies[0].dst
        liba2 = libc.dependencies[0].dst

        assert liba is liba2

        self._check_node(app, "app/0.1", deps=[libd])
        self._check_node(libd, "libd/0.1#123", deps=[libb, libc], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libd])
        self._check_node(libc, "libc/0.1#123", deps=[liba], dependents=[libd])
        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc])

        # node, include, link, build, run
        _check_transitive(app, [(libd, True, True, False, None)])
        _check_transitive(libd, [(libb, True, True, False, None),
                                 (libc, True, True, False, None),
                                 (liba, True, True, False, None)])

    def test_shared_static_private(self):
        # app -> libb0.1 (shared) -(private)-> liba0.1 (static)
        #    \-> libc0.1 (shared) -> liba0.2 (static)
        # This private allows to avoid the liba conflict
        self.recipe_cache("liba/0.1", option_shared=False)
        self.recipe_cache("liba/0.2", option_shared=False)
        libb = GenConanfile().with_requirement("liba/0.1", visible=False)
        libb.with_shared_option(True)
        self.recipe_conanfile("libb/0.1", libb)
        self.recipe_cache("libc/0.1", ["liba/0.2"], option_shared=True)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba1 = libb.dependencies[0].dst
        liba2 = libc.dependencies[0].dst

        assert liba1 is not liba2

        self._check_node(app, "app/0.1", deps=[libb, libc])
        self._check_node(libb, "libb/0.1#123", deps=[liba1], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[liba2], dependents=[app])
        self._check_node(liba1, "liba/0.1#123", dependents=[libb])
        self._check_node(liba2, "liba/0.2#123", dependents=[libc])

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, True),
                                (libc, True, True, False, True),
                                (liba2, False, False, False, False)])
        _check_transitive(libb, [(liba1, True, True, False, False)])
        _check_transitive(libc, [(liba2, True, True, False, False)])

    def test_diamond_conflict(self):
        # app -> libb0.1 -> liba0.1
        #    \-> libc0.1 -> liba0.2
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["liba/0.2"])

        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1"])
        deps_graph = self.build_consumer(consumer, install=False)

        assert deps_graph.error.kind == GraphError.VERSION_CONFLICT

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba1 = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb, libc])
        self._check_node(libb, "libb/0.1#123", deps=[liba1], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[], dependents=[app])
        self._check_node(liba1, "liba/0.1#123", dependents=[libb])

    def test_shared_conflict_shared(self):
        # app -> libb0.1 (shared) -> liba0.1 (shared)
        #    \-> libc0.1 (shared) -> liba0.2 (shared)
        self.recipe_cache("liba/0.1", option_shared=True)
        self.recipe_cache("liba/0.2", option_shared=True)
        self.recipe_cache("libb/0.1", ["liba/0.1"], option_shared=True)
        self.recipe_cache("libc/0.1", ["liba/0.2"], option_shared=True)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1"])

        deps_graph = self.build_consumer(consumer, install=False)

        assert deps_graph.error.kind == GraphError.VERSION_CONFLICT

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba1 = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb, libc])
        self._check_node(libb, "libb/0.1#123", deps=[liba1], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[], dependents=[app])
        self._check_node(liba1, "liba/0.1#123", dependents=[libb])

    def test_private_conflict(self):
        # app -> libd0.1 -(private)-> libb0.1 -> liba0.1
        #            \ ---(private)-> libc0.1 -> liba0.2
        #
        # private requires do not avoid conflicts at the node level, only downstream
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["liba/0.2"])
        libd = GenConanfile().with_requirement("libb/0.1", visible=False)
        libd.with_requirement("libc/0.1", visible=False)
        self.recipe_conanfile("libd/0.1", libd)
        consumer = self.recipe_consumer("app/0.1", ["libd/0.1"])

        deps_graph = self.build_consumer(consumer, install=False)

        assert deps_graph.error.kind == GraphError.VERSION_CONFLICT

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libd = app.dependencies[0].dst
        libb = libd.dependencies[0].dst
        libc = libd.dependencies[1].dst
        liba1 = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libd])
        self._check_node(libd, "libd/0.1#123", deps=[libb, libc], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[liba1], dependents=[libd])
        self._check_node(libc, "libc/0.1#123", deps=[], dependents=[libd])
        self._check_node(liba1, "liba/0.1#123", dependents=[libb])


class TestDiamondMultiple(GraphManagerTest):

    def test_consecutive_diamonds(self):
        # app -> libe0.1 -> libd0.1 -> libb0.1 -> liba0.1
        #    \-> libf0.1 ->/    \-> libc0.1 ->/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["liba/0.1"])
        self.recipe_cache("libd/0.1", ["libb/0.1", "libc/0.1"])
        self.recipe_cache("libe/0.1", ["libd/0.1"])
        self.recipe_cache("libf/0.1", ["libd/0.1"])
        consumer = self.recipe_consumer("app/0.1", ["libe/0.1", "libf/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(7, len(deps_graph.nodes))
        app = deps_graph.root
        libe = app.dependencies[0].dst
        libf = app.dependencies[1].dst
        libd = libe.dependencies[0].dst
        libb = libd.dependencies[0].dst
        libc = libd.dependencies[1].dst
        liba = libc.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libe, libf])
        self._check_node(libe, "libe/0.1#123", deps=[libd], dependents=[app])
        self._check_node(libf, "libf/0.1#123", deps=[libd], dependents=[app])
        self._check_node(libd, "libd/0.1#123", deps=[libb, libc], dependents=[libe, libf])
        self._check_node(libc, "libc/0.1#123", deps=[liba], dependents=[libd])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libd])
        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc])

        _check_transitive(app, [(libe, True, True, False, None),
                                (libf, True, True, False, None),
                                (libd, True, True, False, None),
                                (libb, True, True, False, None),
                                (libc, True, True, False, None),
                                (liba, True, True, False, None)])

    def test_consecutive_diamonds_private(self):
        # app -> libe0.1 ---------> libd0.1 ---> libb0.1 ---> liba0.1
        #    \-> (private)->libf0.1 ->/    \-private-> libc0.1 ->/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["liba/0.1"])
        self._cache_recipe("libd/0.1", GenConanfile().with_require("libb/0.1")
                           .with_requirement("libc/0.1", visible=False))
        self.recipe_cache("libe/0.1", ["libd/0.1"])
        self.recipe_cache("libf/0.1", ["libd/0.1"])
        consumer = self.consumer_conanfile(GenConanfile("app", "0.1").with_require("libe/0.1")
                                           .with_requirement("libf/0.1", visible=False))

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(7, len(deps_graph.nodes))
        app = deps_graph.root
        libe = app.dependencies[0].dst
        libf = app.dependencies[1].dst
        libd = libe.dependencies[0].dst
        libb = libd.dependencies[0].dst
        libc = libd.dependencies[1].dst
        liba = libc.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libe, libf])
        self._check_node(libe, "libe/0.1#123", deps=[libd], dependents=[app])
        self._check_node(libf, "libf/0.1#123", deps=[libd], dependents=[app])
        self._check_node(libd, "libd/0.1#123", deps=[libb, libc], dependents=[libe, libf])
        self._check_node(libc, "libc/0.1#123", deps=[liba], dependents=[libd])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libd])
        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc])

        # FIXME: In this case the order seems a bit broken
        _check_transitive(app, [(libe, True, True, False, None),
                                (libf, True, True, False, None),
                                (libd, True, True, False, None),
                                (libb, True, True, False, None),
                                (liba, True, True, False, None),
                                ])

    def test_parallel_diamond(self):
        # app -> libb0.1 -> liba0.1
        #    \-> libc0.1 ->/
        #    \-> libd0.1 ->/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["liba/0.1"])
        self.recipe_cache("libd/0.1", ["liba/0.1"])

        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1", "libd/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        libd = app.dependencies[2].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb, libc, libd])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[liba], dependents=[app])
        self._check_node(libd, "libd/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc, libd])

    def test_nested_diamond(self):
        # app --------> libb0.1 -> liba0.1
        #    \--------> libc0.1 ->/
        #     \-> libd0.1 ->/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["liba/0.1"])
        self.recipe_cache("libd/0.1", ["libc/0.1"])

        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1", "libd/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        libd = app.dependencies[2].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb, libc, libd])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[liba], dependents=[app, libd])
        self._check_node(libd, "libd/0.1#123", deps=[libc], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc])

    def test_multiple_transitive(self):
        # https://github.com/conanio/conan/issues/4720
        # app -> libb0.1  -> libc0.1 -> libd0.1
        #    \--------------->/          /
        #     \------------------------>/
        self.recipe_cache("libd/0.1")
        self.recipe_cache("libc/0.1", ["libd/0.1"])
        self.recipe_cache("libb/0.1", ["libc/0.1"])
        consumer = self.recipe_consumer("app/0.1", ["libd/0.1", "libc/0.1", "libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libd = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        libb = app.dependencies[2].dst

        self._check_node(app, "app/0.1", deps=[libd, libc, libb])
        self._check_node(libd, "libd/0.1#123", dependents=[app, libc])
        self._check_node(libb, "libb/0.1#123", deps=[libc], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[libd], dependents=[app, libb])

    def test_loop(self):
        # app -> libc0.1 -> libb0.1 -> liba0.1 ->|
        #             \<-------------------------|
        self.recipe_cache("liba/0.1", ["libc/0.1"])
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["libb/0.1"])

        consumer = self.recipe_consumer("app/0.1", ["libc/0.1"])

        deps_graph = self.build_consumer(consumer, install=False)
        # TODO: Better error modeling
        assert deps_graph.error.kind == GraphError.LOOP

        self.assertEqual(4, len(deps_graph.nodes))

        app = deps_graph.root
        libc = app.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libc])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", deps=[], dependents=[libb])


class TransitiveOverridesGraphTest(GraphManagerTest):

    def test_diamond(self):
        # app -> libb0.1 -> liba0.2 (overriden to lib0.2)
        #    \-> --------- ->/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        consumer = self.consumer_conanfile(GenConanfile("app", "0.1").with_require("libb/0.1")
                                           .with_requirement("liba/0.2", force=True))
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = app.dependencies[1].dst
        liba2 = libb.dependencies[0].dst

        assert liba is liba2

        # TODO: No Revision??? Because of consumer?
        self._check_node(app, "app/0.1", deps=[libb, liba])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.2#123", dependents=[libb, app])

    def test_diamond_conflict(self):
        # app -> libb0.1 -> liba0.2 (overriden to lib0.2)
        #    \-> --------- ->/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "liba/0.2"])

        deps_graph = self.build_consumer(consumer, install=False)

        assert deps_graph.error.kind == GraphError.VERSION_CONFLICT

        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst

        # TODO: No Revision??? Because of consumer?
        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[], dependents=[app])

    def test_diamond_reverse_order(self):
        # foo ---------------------------------> dep1/2.0
        #   \ -> dep2/1.0--(dep1/1.0 overriden)-->/
        self.recipe_cache("dep1/1.0")
        self.recipe_cache("dep1/2.0")
        self.recipe_cache("dep2/1.0", ["dep1/1.0"])
        consumer = self.consumer_conanfile(GenConanfile("app", "0.1")
                                           .with_requirement("dep1/2.0", force=True)
                                           .with_requirement("dep2/1.0"))
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        dep1 = app.dependencies[0].dst
        dep2 = app.dependencies[1].dst

        self._check_node(app, "app/0.1", deps=[dep1, dep2])
        self._check_node(dep1, "dep1/2.0#123", deps=[], dependents=[app, dep2])
        self._check_node(dep2, "dep2/1.0#123", deps=[dep1], dependents=[app])

    def test_diamond_reverse_order_conflict(self):
        # foo ---------------------------------> dep1/2.0
        #   \ -> dep2/1.0--(dep1/1.0 overriden)-->/
        self.recipe_cache("dep1/1.0")
        self.recipe_cache("dep1/2.0")
        self.recipe_cache("dep2/1.0", ["dep1/1.0"])
        consumer = self.recipe_consumer("app/0.1", ["dep1/2.0", "dep2/1.0"])
        deps_graph = self.build_consumer(consumer, install=False)

        assert deps_graph.error.kind == GraphError.VERSION_CONFLICT

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        dep1 = app.dependencies[0].dst
        dep2 = app.dependencies[1].dst


class PureOverrideTest(GraphManagerTest):

    def test_diamond(self):
        # app -> libb0.1 -> liba0.2 (overriden to lib0.2)
        #    \-> ---(override)------ ->/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        consumer = self.consumer_conanfile(GenConanfile("app", "0.1").with_require("libb/0.1")
                                           .with_requirement("liba/0.2", override=True))
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        # TODO: No Revision??? Because of consumer?
        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.2#123", dependents=[libb])

    def test_discarded_override(self):
        # app ->---(override)------> liba0.2
        consumer = self.consumer_conanfile(GenConanfile("app", "0.1")
                                           .with_requirement("liba/0.2", override=True))
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(1, len(deps_graph.nodes))
        app = deps_graph.root
        # TODO: No Revision??? Because of consumer?
        self._check_node(app, "app/0.1", deps=[])


class TestProjectApp(GraphManagerTest):
    """
    Emulating a project that can gather multiple applications and other resources and build a
    consistent graph, in which dependencies are same versions
    """
    def test_project_require_transitive(self):
        # project -> app1 -> lib
        #    \---- > app2 --/

        self._cache_recipe("lib/0.1", GenConanfile())
        self._cache_recipe("app1/0.1", GenConanfile().with_requirement("lib/0.1"))
        self._cache_recipe("app2/0.1", GenConanfile().with_requirement("lib/0.1"))

        deps_graph = self.build_graph(GenConanfile("project", "0.1")
                                      .with_requirement("app1/0.1", headers=False, libs=False,
                                                        build=False, run=True)
                                      .with_requirement("app2/0.1", headers=False, libs=False,
                                                        build=False, run=True)
                                      )

        self.assertEqual(4, len(deps_graph.nodes))
        project = deps_graph.root
        app1 = project.dependencies[0].dst
        app2 = project.dependencies[1].dst
        lib = app1.dependencies[0].dst
        lib2 = app2.dependencies[0].dst

        assert lib is lib2

        self._check_node(project, "project/0.1@", deps=[app1, app2], dependents=[])
        self._check_node(app1, "app1/0.1#123", deps=[lib], dependents=[project])
        self._check_node(app2, "app2/0.1#123", deps=[lib], dependents=[project])
        self._check_node(lib, "lib/0.1#123", deps=[], dependents=[app1, app2])

        # node, include, link, build, run
        _check_transitive(project, [(app1, False, False, False, True),
                                    (app2, False, False, False, True),
                                    (lib, False, False, False, None)])

    def test_project_require_transitive_conflict(self):
        # project -> app1 -> lib/0.1
        #    \---- > app2 -> lib/0.2

        self._cache_recipe("lib/0.1", GenConanfile())
        self._cache_recipe("lib/0.2", GenConanfile())
        self._cache_recipe("app1/0.1", GenConanfile().with_requirement("lib/0.1"))
        self._cache_recipe("app2/0.1", GenConanfile().with_requirement("lib/0.2"))

        deps_graph = self.build_graph(GenConanfile("project", "0.1")
                                      .with_requirement("app1/0.1", headers=False, libs=False,
                                                        build=False, run=True)
                                      .with_requirement("app2/0.1", headers=False, libs=False,
                                                        build=False, run=True),
                                      install=False)

        assert deps_graph.error.kind == GraphError.VERSION_CONFLICT

    def test_project_require_apps_transitive(self):
        # project -> app1 (app type) -> lib
        #    \---- > app2 (app type) --/

        self._cache_recipe("lib/0.1", GenConanfile())
        self._cache_recipe("app1/0.1", GenConanfile().with_package_type("application").
                           with_requirement("lib/0.1"))
        self._cache_recipe("app2/0.1", GenConanfile().with_package_type("application").
                           with_requirement("lib/0.1"))

        deps_graph = self.build_graph(GenConanfile("project", "0.1").with_requires("app1/0.1",
                                                                                   "app2/0.1"))

        self.assertEqual(4, len(deps_graph.nodes))
        project = deps_graph.root
        app1 = project.dependencies[0].dst
        app2 = project.dependencies[1].dst
        lib = app1.dependencies[0].dst
        lib2 = app2.dependencies[0].dst

        assert lib is lib2

        self._check_node(project, "project/0.1@", deps=[app1, app2], dependents=[])
        self._check_node(app1, "app1/0.1#123", deps=[lib], dependents=[project])
        self._check_node(app2, "app2/0.1#123", deps=[lib], dependents=[project])
        self._check_node(lib, "lib/0.1#123", deps=[], dependents=[app1, app2])

        # node, include, link, build, run
        _check_transitive(project, [(app1, False, False, False, True),
                                    (app2, False, False, False, True),
                                    (lib, False, False, False, None)])

    def test_project_require_apps_transitive_conflict(self):
        # project -> app1 (app type) -> lib/0.1
        #    \---- > app2 (app type) -> lib/0.2

        self._cache_recipe("lib/0.1", GenConanfile())
        self._cache_recipe("lib/0.2", GenConanfile())
        self._cache_recipe("app1/0.1", GenConanfile().with_package_type("application").
                           with_requirement("lib/0.1"))
        self._cache_recipe("app2/0.1", GenConanfile().with_package_type("application").
                           with_requirement("lib/0.2"))

        deps_graph = self.build_graph(GenConanfile("project", "0.1").with_requires("app1/0.1",
                                                                                   "app2/0.1"),
                                      install=False)

        assert deps_graph.error.kind == GraphError.VERSION_CONFLICT

    def test_project_require_private(self):
        # project -(private)-> app1 -> lib1
        #    \----(private)- > app2 -> lib2
        # This doesn't conflict on project, as lib1, lib2 do not include, link or public

        self._cache_recipe("lib/0.1", GenConanfile())
        self._cache_recipe("lib/0.2", GenConanfile())
        self._cache_recipe("app1/0.1", GenConanfile().with_requirement("lib/0.1"))
        self._cache_recipe("app2/0.1", GenConanfile().with_requirement("lib/0.2"))

        deps_graph = self.build_graph(GenConanfile("project", "0.1")
                                      .with_requirement("app1/0.1", headers=False, libs=False,
                                                        build=False, run=True, visible=False)
                                      .with_requirement("app2/0.1", headers=False, libs=False,
                                                        build=False, run=True, visible=False)
                                      )

        self.assertEqual(5, len(deps_graph.nodes))
        project = deps_graph.root
        app1 = project.dependencies[0].dst
        app2 = project.dependencies[1].dst
        lib1 = app1.dependencies[0].dst
        lib2 = app2.dependencies[0].dst

        assert lib1 is not lib2

        self._check_node(project, "project/0.1@", deps=[app1, app2], dependents=[])
        self._check_node(app1, "app1/0.1#123", deps=[lib1], dependents=[project])
        self._check_node(app2, "app2/0.1#123", deps=[lib2], dependents=[project])
        self._check_node(lib1, "lib/0.1#123", deps=[], dependents=[app1])
        self._check_node(lib2, "lib/0.2#123", deps=[], dependents=[app2])

        # node, include, link, build, run
        _check_transitive(project, [(app1, False, False, False, True),
                                    (lib1, False, False, False, None),
                                    (app2, False, False, False, True),
                                    (lib2, False, False, False, None)])
