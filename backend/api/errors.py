"""Small stable public error contract; operational details stay private."""

from rest_framework.exceptions import APIException


class ApiProblem(APIException):
    def __init__(self, code, message, *, status=400, details=None):
        self.status_code = status
        self.public_code = code
        self.public_message = message
        self.details = details or {}
        super().__init__(message)
