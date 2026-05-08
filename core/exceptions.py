class WorkspaceError(Exception):
    """Base error for workspace operations."""


class InvalidMoveError(WorkspaceError):
    """Raised when a move request is invalid."""


class InvalidRotationError(WorkspaceError):
    """Raised when rotation angle is invalid."""


class InvalidPageIndexError(WorkspaceError):
    """Raised when one or more page indices are out of range."""


class EmptyWorkspaceError(WorkspaceError):
    """Raised when an operation requires pages but the workspace is empty."""


class ExportError(WorkspaceError):
    """Raised when export cannot be completed."""


class PdfBackendUnavailableError(WorkspaceError):
    """Raised when the PDF backend is unavailable in the environment."""