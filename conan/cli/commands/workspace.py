import json
import os

from conan.api.conan_api import ConanAPI
from conan.api.output import ConanOutput, cli_out_write
from conan.cli import make_abs_path
from conan.cli.args import add_reference_args
from conan.cli.command import conan_command, conan_subcommand
from conan.internal.conan_app import ConanApp
from conan.tools.scm import Git
from conans.errors import ConanException
from conans.model.recipe_ref import RecipeReference


@conan_subcommand(formatters={"text": cli_out_write})
def workspace_root(conan_api: ConanAPI, parser, subparser, *args):
    """
    Return the folder containing the conanws.py workspace file
    """
    ws = conan_api.workspace
    if not ws.folder:
        raise ConanException("No workspace defined, conanws.py file not found")
    return ws.folder


@conan_subcommand()
def workspace_open(conan_api: ConanAPI, parser, subparser, *args):
    """
    Open (clone and checkout) the source repo of a recipe from its reference.
    The recipe in the server should have stored in it conandata.yml "scm" field
    the url and commit of the sources (in the "export()" method)
    It doesn't add it to the current workspace
    """
    subparser.add_argument("--requires", action="append",
                           help="Open this package source repository")
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
        git.checkout(commit=scm["commit"], branch=scm["branch"])


@conan_subcommand()
def workspace_add(conan_api: ConanAPI, parser, subparser, *args):
    """
    Add packages to current workspace
    """
    subparser.add_argument('path', help='Path to the package folder in the user workspace')
    add_reference_args(subparser)
    subparser.add_argument("-of", "--output-folder",
                           help='The root output folder for generated and build files')
    group = subparser.add_mutually_exclusive_group()
    group.add_argument("-r", "--remote", action="append", default=None,
                       help='Look in the specified remote or remotes server')
    group.add_argument("-nr", "--no-remote", action="store_true",
                       help='Do not use remote, resolve exclusively in the cache')
    args = parser.parse_args(*args)
    remotes = conan_api.remotes.list(args.remote) if not args.no_remote else []
    cwd = os.getcwd()
    ref = conan_api.local.workspace_add(args.path,
                                        args.name, args.version, args.user, args.channel,
                                        cwd, args.output_folder, remotes=remotes)
    ConanOutput().success("Reference '{}' added to workspace".format(ref))


@conan_subcommand()
def workspace_remove(conan_api: ConanAPI, parser, subparser, *args):
    """
    Remove packages to current workspace
    """
    subparser.add_argument('path', help='Path to the package folder in the user workspace')
    args = parser.parse_args(*args)
    conan_api.local.workspace_remove(make_abs_path(args.path))


def print_json(data):
    results = data["info"]
    myjson = json.dumps(results, indent=4)
    cli_out_write(myjson)


@conan_subcommand(formatters={"text": cli_out_write, "json": print_json})
def workspace_info(conan_api: ConanAPI, parser, subparser, *args):
    """
    Display info for current workspace
    """
    parser.parse_args(*args)
    return {"info": conan_api.local.workspace_info()}


@conan_command(group="Consumer")
def workspace(conan_api, parser, *args):
    """
    Manage the remote list and the users authenticated on them.
    """
