from conan.api.conan_api import ConanAPI
from conan.cli.command import conan_command, conan_subcommand
from conan.internal.conan_app import ConanApp
from conan.tools.scm import Git
from conans.model.recipe_ref import RecipeReference


@conan_subcommand()
def workspace_open(conan_api: ConanAPI, parser, subparser, *args):
    """
    Add packages to current workspace
    """
    subparser.add_argument("--requires", action="append",
                           help="Add package recipes by reference. ")
    group = subparser.add_mutually_exclusive_group()
    group.add_argument("-r", "--remote", action="append", default=None,
                       help='Look in the specified remote or remotes server')
    group.add_argument("-nr", "--no-remote", action="store_true",
                       help='Do not use remote, resolve exclusively in the cache')
    args = parser.parse_args(*args)
    requires = [RecipeReference.loads(r) for r in args.requires]
    app = ConanApp(conan_api)
    remotes = conan_api.remotes.list(args.remote) if not args.no_remote else []
    for r in requires:
        recipe = app.proxy.get_recipe(r, remotes, update=False, check_update=False)
        layout, recipe_status, remote = recipe
        path = layout.conanfile()
        conanfile, module = app.loader.load_basic_module(path, remotes=remotes)
        scm = conanfile.conan_data.get("scm")
        if scm is None:
            conanfile.output.error("conandata doesn't contain 'scm' information")
            continue
        git = Git(conanfile)
        git.clone(url=scm["url"], target=".")
        git.checkout(commit=scm["commit"])


@conan_command(group="Consumer")
def workspace(conan_api, parser, *args):
    """
    Manage the remote list and the users authenticated on them.
    """
