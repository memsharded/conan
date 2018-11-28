from conans.model.ref import ConanFileReference
from conans.errors import ConanException
from conans.search.search import search_recipes


def _parse_versionexpr(versionexpr, output):
    expression = versionexpr.split(",")

    include_prerelease = False
    loose = True
    version_range = []

    import re
    pattern = re.compile(r"^\s*(include_prerelease|loose)\s*=\s*(True|False)\s*$")

    for keyword in expression:
        match = pattern.search(keyword)
        if match:
            if match.group(1) == "include_prerelease":
                if match.group(2) == "True":
                    include_prerelease = True
            if match.group(1) == "loose":
                if match.group(2) == "False":
                    loose = False
        else:
            version_range.append(keyword.strip())

    if version_range and len(version_range) > 1:
        output.warn("Commas as separator in version '%s' range will are deprecated and will be removed in Conan 2.0" %
                    str(versionexpr))
    version_range = " ".join(map(str, version_range))
    return version_range, loose, include_prerelease


def satisfying(list_versions, versionexpr, output):
    """ returns the maximum version that satisfies the expression
    if some version cannot be converted to loose SemVer, it is discarded with a msg
    This provides some workaround for failing comparisons like "2.1" not matching "<=2.1"
    """
    from semver import SemVer, max_satisfying

    version_range, loose, include_prerelease = _parse_versionexpr(versionexpr, output)

    candidates = {}
    for v in list_versions:
        try:
            ver = SemVer(v, loose=loose)
            candidates[ver] = v
        except (ValueError, AttributeError):
            output.warn("Version '%s' is not semver, cannot be compared with a range" % str(v))
    result = max_satisfying(candidates, version_range, loose=loose, include_prerelease=include_prerelease)
    return candidates.get(result)


class RangeResolver(object):

    def __init__(self, output, client_cache, remote_search):
        self._output = output
        self._client_cache = client_cache
        self._remote_search = remote_search
        self._cached_remote_found = {}

    def resolve(self, require, base_conanref, update, remote_name):
        version_range = require.version_range
        if version_range is None:
            return

        if require.is_resolved:
            ref = require.conan_reference
            resolved = self._resolve_version(version_range, [ref])
            if not resolved:
                raise ConanException("Version range '%s' required by '%s' not valid for "
                                     "downstream requirement '%s'"
                                     % (version_range, base_conanref, str(ref)))
            else:
                self._output.success("Version range '%s' required by '%s' valid for "
                                     "downstream requirement '%s'"
                                     % (version_range, base_conanref, str(ref)))
            return

        ref = require.conan_reference
        # The search pattern must be a string
        search_ref = str(ConanFileReference(ref.name, "*", ref.user, ref.channel))

        if update:
            resolved = (self._resolve_remote(search_ref, version_range, remote_name) or
                        self._resolve_local(search_ref, version_range))
        else:
            resolved = (self._resolve_local(search_ref, version_range) or
                        self._resolve_remote(search_ref, version_range, remote_name))

        if resolved:
            self._output.success("Version range '%s' required by '%s' resolved to '%s'"
                                 % (version_range, base_conanref, str(resolved)))
            require.conan_reference = resolved
        else:
            base_conanref = base_conanref or "PROJECT"
            raise ConanException("Version range '%s' from requirement '%s' required by '%s' "
                                 "could not be resolved" % (version_range, require, base_conanref))

    def _resolve_local(self, search_ref, version_range):
        local_found = search_recipes(self._client_cache, search_ref)
        if local_found:
            return self._resolve_version(version_range, local_found)

    def _resolve_remote(self, search_ref, version_range, remote_name):
        remote_cache = self._cached_remote_found.setdefault(remote_name, {})
        # We should use ignorecase=False, we want the exact case!
        remote_found = remote_cache.get(search_ref)
        if remote_found is None:
            remote_found = self._remote_search.search_remotes(search_ref, remote_name)
            # Empty list, just in case it returns None
            remote_cache[search_ref] = remote_found or []
        if remote_found:
            return self._resolve_version(version_range, remote_found)

    def _resolve_version(self, version_range, refs_found):
        versions = {ref.version: ref for ref in refs_found}
        result = satisfying(versions, version_range, self._output)
        return versions.get(result)
