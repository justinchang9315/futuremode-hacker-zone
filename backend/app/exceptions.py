class DomainError(Exception):
    """Base error for expected domain failures."""

    status_code = 400
    code = "DOMAIN_ERROR"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(DomainError):
    status_code = 409
    code = "CONFLICT"


class ForbiddenError(DomainError):
    status_code = 403
    code = "FORBIDDEN"


class UnauthorizedError(DomainError):
    status_code = 401
    code = "UNAUTHORIZED"


class ProviderConfigurationError(DomainError):
    status_code = 503
    code = "PROVIDER_NOT_CONFIGURED"


class UpstreamServiceError(DomainError):
    status_code = 502
    code = "UPSTREAM_SERVICE_ERROR"
