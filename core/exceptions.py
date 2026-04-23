class WorkspaceError(Exception):
    """Base error for workspace operations."""


class InvalidMoveError(WorkspaceError):
    """Raised when a move request is invalid."""


class InvalidRotationError(WorkspaceError):
    """Raised when rotation angle is invalid."""


class PdfBackendUnavailableError(WorkspaceError):
    """Raised when the PDF backend is unavailable in the environment."""
