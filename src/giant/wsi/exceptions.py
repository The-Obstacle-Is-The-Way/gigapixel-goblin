"""Custom exceptions for WSI operations.

These exceptions provide context-rich error handling for WSI file
operations, wrapping low-level OpenSlide errors with meaningful messages.
"""

from pathlib import Path


class WSIError(Exception):
    """Base exception for all WSI-related errors."""

    def __init__(self, message: str, path: Path | str | None = None) -> None:
        """Initialize WSI error with optional path context.

        Args:
            message: Human-readable error description.
            path: Path to the WSI file that caused the error.
        """
        self.path = Path(path) if path else None
        self.message = message
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format error message with path context if available."""
        if self.path:
            return f"{self.message} (path: {self.path})"
        return self.message


class WSIOpenError(WSIError):
    """Raised when a WSI file cannot be opened.

    This error is raised when:
    - The file does not exist
    - The file format is not supported
    - The file is corrupted or unreadable
    - OpenSlide fails to initialize the slide
    """

    pass


class WSIReadError(WSIError):
    """Raised when a read operation on an open WSI fails.

    This error is raised when:
    - read_region fails due to invalid coordinates
    - read_region fails due to invalid level
    - get_thumbnail fails
    - Any other read operation encounters an error
    """

    def __init__(
        self,
        message: str,
        path: Path | str | None = None,
        *,
        level: int | None = None,
        location: tuple[int, int] | None = None,
        size: tuple[int, int] | None = None,
    ) -> None:
        """Initialize read error with operation context.

        Args:
            message: Human-readable error description.
            path: Path to the WSI file.
            level: Pyramid level being accessed.
            location: (x, y) coordinates of the read operation.
            size: (width, height) of the requested region.
        """
        self.level = level
        self.location = location
        self.size = size
        super().__init__(message, path)

    def _format_message(self) -> str:
        """Format error message with full operation context."""
        parts = [self.message]
        if self.path:
            parts.append(f"path={self.path}")
        if self.level is not None:
            parts.append(f"level={self.level}")
        if self.location is not None:
            parts.append(f"location={self.location}")
        if self.size is not None:
            parts.append(f"size={self.size}")

        if len(parts) == 1:
            return parts[0]
        return f"{parts[0]} ({', '.join(parts[1:])})"
