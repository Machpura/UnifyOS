class AppResolverError(Exception):
    """Base class for user-facing App Resolver errors."""


class InvalidAppIdError(AppResolverError):
    """Raised when an app ID cannot be safely used by the resolver."""


class ManifestError(AppResolverError):
    """Raised when a manifest is invalid or cannot be parsed."""


class RegistryError(AppResolverError):
    """Raised when registry storage cannot be read or written."""


class AppNotFoundError(RegistryError):
    """Raised when an app manifest is not present in the registry."""


class BackendError(AppResolverError):
    """Raised when a backend cannot complete an operation."""


class CommandExecutionError(BackendError):
    """Raised when an external command exits unsuccessfully."""

