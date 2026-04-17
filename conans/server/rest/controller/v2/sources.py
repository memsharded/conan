from bottle import request, response

from conans.server.service.v2.sources_service import SourcesService


class SourcesController:

    @staticmethod
    def attach_to(app):
        app.sources_service = SourcesService(app.sources_backup_folder)

        @app.route("/sources/backup/<sha256>", method=["POST"])
        def get_source_backup(sha256):
            data = request.json or {}
            urls = data.get("urls", [])
            # Access via app.sources_service so that tests can replace _download_fn
            # on the service instance after server setup.
            result = app.sources_service.get_source(sha256, urls)
            response.content_type = "application/octet-stream"
            return result
