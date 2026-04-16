import os

import requests
from bottle import static_file

from conan.errors import ConanException
from conan.internal.rest.download_cache import DownloadCache
from conan.internal.util.files import mkdir, set_dirty_context_manager, remove_if_dirty
from conan.internal.util.files import check_with_algorithm_sum


class SourcesService:

    def __init__(self, backup_folder):
        self._cache = DownloadCache(backup_folder)

    def get_source(self, sha256, urls):
        cached_path = self._cache.source_path(sha256)
        with self._cache.lock(sha256):
            remove_if_dirty(cached_path)
            if os.path.exists(cached_path):
                # Already cached — serve from disk immediately
                return static_file(sha256,
                                   root=os.path.dirname(cached_path),
                                   mimetype="application/octet-stream")
        # Not cached — stream from origin URL while writing to cache.
        # The lock is released here so other requests are not blocked during the
        # (potentially long) origin download.
        return self._stream_and_cache(sha256, cached_path, urls)

    @staticmethod
    def _stream_and_cache(sha256, cached_path, urls):
        """Return a generator that fetches from the first working origin URL,
        streams each chunk to the caller, and simultaneously writes to the
        server-side cache.  The dirty marker keeps the cache consistent if the
        download or sha256 check fails mid-stream.
        """
        def generator():
            mkdir(os.path.dirname(cached_path))
            with set_dirty_context_manager(cached_path):
                response = None
                last_error = None
                for url in urls:
                    try:
                        r = requests.get(url, stream=True)
                        r.raise_for_status()
                        response = r
                        break
                    except Exception as e:
                        last_error = e
                if response is None:
                    raise ConanException(f"Could not download sources from any of {urls}: "
                                         f"{last_error}")
                with open(cached_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024 * 100):
                        f.write(chunk)
                        yield chunk
                # Verify integrity after the full file has been written and streamed.
                # A mismatch raises here; set_dirty_context_manager leaves the dirty
                # marker so the bad file is cleaned on the next access.
                check_with_algorithm_sum("sha256", cached_path, sha256)

        return generator()
