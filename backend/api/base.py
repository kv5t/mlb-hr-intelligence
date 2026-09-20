"""One captured publication revision and one public error envelope per request."""

from django.db import transaction
from rest_framework.exceptions import MethodNotAllowed, NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from ingestion.models import DatasetRevision

from .errors import ApiProblem


class ReadOnlyView(APIView):
    http_method_names = ["get", "head", "options"]
    authentication_classes = []
    permission_classes = []
    throttle_classes = []

    def dispatch(self, request, *args, **kwargs):
        # The revision is the first read in this transaction. SQLite/WAL holds
        # that read snapshot for the complete response construction.
        with transaction.atomic():
            return super().dispatch(request, *args, **kwargs)

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.revision = DatasetRevision.objects.order_by("-id").first()
        if self.revision is None:
            raise ApiProblem(
                "REVISION_UNAVAILABLE", "Current publication is unavailable", status=503
            )

    def _meta(self):
        revision = getattr(self, "revision", None)
        return {
            "dataset_revision": str(revision.id) if revision else None,
            "data_as_of": revision.committed_at_utc.isoformat().replace("+00:00", "Z")
            if revision
            else None,
        }

    def handle_exception(self, exc):
        if isinstance(exc, ApiProblem):
            return Response(
                {
                    "error": {
                        "code": exc.public_code,
                        "message": exc.public_message,
                        "details": exc.details,
                    }
                },
                status=exc.status_code,
            )
        if isinstance(exc, MethodNotAllowed):
            return Response(
                {
                    "error": {
                        "code": "METHOD_NOT_ALLOWED",
                        "message": "Only GET is supported",
                        "details": {},
                    }
                },
                status=405,
            )
        if isinstance(exc, NotFound):
            return Response(
                {
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Canonical resource not found",
                        "details": {},
                    }
                },
                status=404,
            )
        return super().handle_exception(exc)

    def finalize_response(self, request, response, *args, **kwargs):
        if isinstance(response, Response) and isinstance(response.data, dict):
            response.data["meta"] = self._meta()
        return super().finalize_response(request, response, *args, **kwargs)
