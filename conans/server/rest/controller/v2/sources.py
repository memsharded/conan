from bottle import request, response

from conans.server.service.v2.sources_service import SourcesService


class SourcesController:

    @staticmethod
    def attach_to(app):
        sources_service = SourcesService(app.sources_backup_folder)

        @app.route("/sources/backup/<sha256>", method=["POST"])
        def get_source_backup(sha256):
            data = request.json or {}
            urls = data.get("urls", [])
            result = sources_service.get_source(sha256, urls)
            # For the streaming (generator) case set the content-type explicitly;
            # static_file already sets it for the cached case.
            response.content_type = "application/octet-stream"
            return result
