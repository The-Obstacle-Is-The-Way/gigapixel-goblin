"""Tests for CLI visualizer (Spec-12)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from giant.cli.visualizer import _escape_html, create_trajectory_html


class TestEscapeHtml:
    """Tests for HTML escaping utility."""

    def test_escapes_ampersand(self) -> None:
        assert _escape_html("a & b") == "a &amp; b"

    def test_escapes_less_than(self) -> None:
        assert _escape_html("a < b") == "a &lt; b"

    def test_escapes_greater_than(self) -> None:
        assert _escape_html("a > b") == "a &gt; b"

    def test_escapes_double_quote(self) -> None:
        assert _escape_html('say "hello"') == "say &quot;hello&quot;"

    def test_escapes_single_quote(self) -> None:
        assert _escape_html("it's") == "it&#39;s"

    def test_handles_multiple_special_chars(self) -> None:
        result = _escape_html('<script>alert("xss")</script>')
        assert "<" not in result
        assert ">" not in result
        assert '"' not in result


class TestCreateTrajectoryHtml:
    """Tests for trajectory HTML generation."""

    @pytest.fixture
    def sample_trajectory(self, tmp_path: Path) -> Path:
        """Create a sample trajectory JSON file."""
        trajectory = {
            "wsi_path": "/path/to/slide.svs",
            "answer": "This is a cancer diagnosis",
            "success": True,
            "total_cost": 1.50,
            "turns": [
                {
                    "step": 1,
                    "action": "zoom_in",
                    "reasoning": "Looking at suspicious area",
                    "region": {"x": 100, "y": 200, "width": 500, "height": 500},
                },
                {
                    "step": 2,
                    "action": "pan",
                    "reasoning": "Moving to adjacent tissue",
                    "region": {"x": 600, "y": 200, "width": 500, "height": 500},
                },
                {
                    "step": 3,
                    "action": "answer",
                    "reasoning": "Confident in diagnosis",
                },
            ],
        }
        traj_path = tmp_path / "trajectory.json"
        traj_path.write_text(json.dumps(trajectory))
        return traj_path

    def test_generates_html_file(self, sample_trajectory: Path, tmp_path: Path) -> None:
        output_path = tmp_path / "output.html"

        with patch("giant.cli.visualizer.webbrowser.open"):
            result = create_trajectory_html(
                trajectory_path=sample_trajectory,
                output_path=output_path,
                open_browser=False,
            )

        assert result == output_path
        assert output_path.exists()
        content = output_path.read_text()
        assert "<!DOCTYPE html>" in content
        assert "GIANT" in content

    def test_includes_answer(self, sample_trajectory: Path, tmp_path: Path) -> None:
        output_path = tmp_path / "output.html"

        with patch("giant.cli.visualizer.webbrowser.open"):
            create_trajectory_html(
                trajectory_path=sample_trajectory,
                output_path=output_path,
                open_browser=False,
            )

        content = output_path.read_text()
        assert "This is a cancer diagnosis" in content

    def test_includes_steps(self, sample_trajectory: Path, tmp_path: Path) -> None:
        output_path = tmp_path / "output.html"

        with patch("giant.cli.visualizer.webbrowser.open"):
            create_trajectory_html(
                trajectory_path=sample_trajectory,
                output_path=output_path,
                open_browser=False,
            )

        content = output_path.read_text()
        assert "Step 1" in content
        assert "Step 2" in content
        assert "Step 3" in content
        assert "zoom_in" in content
        assert "Looking at suspicious area" in content

    def test_includes_region_info(
        self, sample_trajectory: Path, tmp_path: Path
    ) -> None:
        output_path = tmp_path / "output.html"

        with patch("giant.cli.visualizer.webbrowser.open"):
            create_trajectory_html(
                trajectory_path=sample_trajectory,
                output_path=output_path,
                open_browser=False,
            )

        content = output_path.read_text()
        assert "100" in content  # x coordinate
        assert "200" in content  # y coordinate
        assert "500" in content  # width/height

    def test_includes_cost(self, sample_trajectory: Path, tmp_path: Path) -> None:
        output_path = tmp_path / "output.html"

        with patch("giant.cli.visualizer.webbrowser.open"):
            create_trajectory_html(
                trajectory_path=sample_trajectory,
                output_path=output_path,
                open_browser=False,
            )

        content = output_path.read_text()
        assert "1.50" in content or "$1.5" in content

    def test_default_output_path(self, sample_trajectory: Path) -> None:
        with patch("giant.cli.visualizer.webbrowser.open"):
            result = create_trajectory_html(
                trajectory_path=sample_trajectory,
                output_path=None,  # Should default to .html extension
                open_browser=False,
            )

        assert result == sample_trajectory.with_suffix(".html")
        assert result.exists()

    def test_opens_browser_when_requested(
        self, sample_trajectory: Path, tmp_path: Path
    ) -> None:
        output_path = tmp_path / "output.html"

        with patch("giant.cli.visualizer.webbrowser.open") as mock_open:
            create_trajectory_html(
                trajectory_path=sample_trajectory,
                output_path=output_path,
                open_browser=True,
            )

            mock_open.assert_called_once()
            call_arg = mock_open.call_args[0][0]
            assert "file://" in call_arg
            assert str(output_path) in call_arg

    def test_does_not_open_browser_when_disabled(
        self, sample_trajectory: Path, tmp_path: Path
    ) -> None:
        output_path = tmp_path / "output.html"

        with patch("giant.cli.visualizer.webbrowser.open") as mock_open:
            create_trajectory_html(
                trajectory_path=sample_trajectory,
                output_path=output_path,
                open_browser=False,
            )

            mock_open.assert_not_called()

    def test_handles_empty_turns(self, tmp_path: Path) -> None:
        trajectory = {
            "wsi_path": "/path/to/slide.svs",
            "answer": "No answer",
            "success": False,
            "total_cost": 0.0,
            "turns": [],
        }
        traj_path = tmp_path / "empty.json"
        traj_path.write_text(json.dumps(trajectory))
        output_path = tmp_path / "output.html"

        with patch("giant.cli.visualizer.webbrowser.open"):
            create_trajectory_html(
                trajectory_path=traj_path,
                output_path=output_path,
                open_browser=False,
            )

        content = output_path.read_text()
        assert "No navigation steps recorded" in content

    def test_escapes_html_in_answer(self, tmp_path: Path) -> None:
        trajectory = {
            "answer": "<script>alert('xss')</script>",
            "turns": [],
        }
        traj_path = tmp_path / "xss.json"
        traj_path.write_text(json.dumps(trajectory))
        output_path = tmp_path / "output.html"

        with patch("giant.cli.visualizer.webbrowser.open"):
            create_trajectory_html(
                trajectory_path=traj_path,
                output_path=output_path,
                open_browser=False,
            )

        content = output_path.read_text()
        # The answer should be escaped (HTML has legit script tags for JS)
        assert "&lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;" in content

    def test_handles_missing_fields(self, tmp_path: Path) -> None:
        # Minimal trajectory with missing optional fields
        trajectory = {"turns": [{"action": "zoom"}]}
        traj_path = tmp_path / "minimal.json"
        traj_path.write_text(json.dumps(trajectory))
        output_path = tmp_path / "output.html"

        with patch("giant.cli.visualizer.webbrowser.open"):
            # Should not raise
            create_trajectory_html(
                trajectory_path=traj_path,
                output_path=output_path,
                open_browser=False,
            )

        assert output_path.exists()
