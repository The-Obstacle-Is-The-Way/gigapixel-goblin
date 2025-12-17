"""Unit tests for WSI exceptions."""

from __future__ import annotations

from pathlib import Path

from giant.wsi.exceptions import WSIError, WSIOpenError, WSIReadError


class TestWSIError:
    """Tests for base WSIError class."""

    def test_error_message_only(self) -> None:
        """Test error with message only."""
        error = WSIError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.path is None

    def test_error_with_path_string(self) -> None:
        """Test error with path as string."""
        error = WSIError("Error occurred", path="/path/to/file.svs")
        assert "Error occurred" in str(error)
        assert "/path/to/file.svs" in str(error)
        assert error.path == Path("/path/to/file.svs")

    def test_error_with_path_object(self) -> None:
        """Test error with path as Path object."""
        path = Path("/path/to/file.svs")
        error = WSIError("Error occurred", path=path)
        assert error.path == path


class TestWSIOpenError:
    """Tests for WSIOpenError class."""

    def test_inheritance(self) -> None:
        """Test WSIOpenError inherits from WSIError."""
        error = WSIOpenError("Cannot open file")
        assert isinstance(error, WSIError)
        assert isinstance(error, Exception)

    def test_file_not_found_message(self) -> None:
        """Test typical file not found error."""
        error = WSIOpenError("File not found", path="/missing/slide.svs")
        assert "File not found" in str(error)
        assert "/missing/slide.svs" in str(error)


class TestWSIReadError:
    """Tests for WSIReadError class."""

    def test_inheritance(self) -> None:
        """Test WSIReadError inherits from WSIError."""
        error = WSIReadError("Read failed")
        assert isinstance(error, WSIError)
        assert isinstance(error, Exception)

    def test_error_with_all_context(self) -> None:
        """Test error with full operation context."""
        error = WSIReadError(
            "Failed to read region",
            path="/path/to/slide.svs",
            level=2,
            location=(1000, 2000),
            size=(512, 512),
        )

        error_str = str(error)
        assert "Failed to read region" in error_str
        assert "path=" in error_str
        assert "level=2" in error_str
        assert "location=(1000, 2000)" in error_str
        assert "size=(512, 512)" in error_str

    def test_error_with_partial_context(self) -> None:
        """Test error with partial operation context."""
        error = WSIReadError(
            "Invalid level",
            path="/path/to/slide.svs",
            level=5,
        )

        error_str = str(error)
        assert "Invalid level" in error_str
        assert "level=5" in error_str
        assert "location=" not in error_str
        assert "size=" not in error_str

    def test_error_message_only(self) -> None:
        """Test error with message only."""
        error = WSIReadError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.level is None
        assert error.location is None
        assert error.size is None

    def test_context_attributes(self) -> None:
        """Test context attributes are accessible."""
        error = WSIReadError(
            "Test",
            level=1,
            location=(100, 200),
            size=(256, 256),
        )

        assert error.level == 1
        assert error.location == (100, 200)
        assert error.size == (256, 256)
