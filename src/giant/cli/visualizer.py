"""Trajectory visualization for GIANT CLI (Spec-12).

Generates interactive HTML visualizations of agent navigation trajectories.
"""

from __future__ import annotations

import json
import webbrowser
from pathlib import Path

from giant.utils.logging import get_logger

# HTML template for trajectory visualization
_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GIANT Trajectory Visualization</title>
    <style>
        :root {{
            --bg-primary: #1a1a2e;
            --bg-secondary: #16213e;
            --text-primary: #eee;
            --text-secondary: #aaa;
            --accent: #0f3460;
            --highlight: #e94560;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }}
        header {{
            text-align: center;
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--accent);
        }}
        h1 {{
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }}
        .subtitle {{
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .summary-card {{
            background: var(--bg-secondary);
            padding: 1.5rem;
            border-radius: 8px;
            text-align: center;
        }}
        .summary-card .value {{
            font-size: 2rem;
            font-weight: bold;
            color: var(--highlight);
        }}
        .summary-card .label {{
            color: var(--text-secondary);
            font-size: 0.85rem;
        }}
        .answer-box {{
            background: var(--bg-secondary);
            padding: 1.5rem;
            border-radius: 8px;
            margin-bottom: 2rem;
            border-left: 4px solid var(--highlight);
        }}
        .answer-box h3 {{
            margin-bottom: 0.5rem;
            color: var(--highlight);
        }}
        .timeline {{
            position: relative;
        }}
        .step {{
            background: var(--bg-secondary);
            border-radius: 8px;
            margin-bottom: 1rem;
            overflow: hidden;
        }}
        .step-header {{
            background: var(--accent);
            padding: 1rem 1.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
        }}
        .step-header:hover {{
            background: #1a4a70;
        }}
        .step-number {{
            background: var(--highlight);
            color: white;
            padding: 0.25rem 0.75rem;
            border-radius: 4px;
            font-weight: bold;
        }}
        .step-action {{
            font-weight: 500;
        }}
        .step-content {{
            padding: 1.5rem;
            display: none;
        }}
        .step.active .step-content {{
            display: block;
        }}
        .step-section {{
            margin-bottom: 1rem;
        }}
        .step-section h4 {{
            color: var(--text-secondary);
            font-size: 0.85rem;
            text-transform: uppercase;
            margin-bottom: 0.5rem;
        }}
        .reasoning {{
            background: var(--bg-primary);
            padding: 1rem;
            border-radius: 4px;
            white-space: pre-wrap;
            font-family: monospace;
            font-size: 0.9rem;
        }}
        .region-info {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1rem;
        }}
        .region-info .item {{
            text-align: center;
        }}
        .region-info .value {{
            font-size: 1.25rem;
            font-weight: bold;
        }}
        .region-info .label {{
            font-size: 0.8rem;
            color: var(--text-secondary);
        }}
        .thumbnail-container {{
            position: relative;
            display: inline-block;
            margin-bottom: 2rem;
            max-width: 100%;
        }}
        .thumbnail-img {{
            max-width: 100%;
            border-radius: 8px;
            display: block;
        }}
        .crop-overlay {{
            position: absolute;
            border: 2px solid var(--highlight);
            background: rgba(233, 69, 96, 0.2);
            pointer-events: none;
        }}
        .step-image {{
            margin-top: 1rem;
            max-width: 100%;
            border-radius: 4px;
            border: 1px solid var(--accent);
        }}
        footer {{
            text-align: center;
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid var(--accent);
            color: var(--text-secondary);
            font-size: 0.85rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>GIANT Navigation Trajectory</h1>
            <p class="subtitle">{wsi_name}</p>
        </header>

        <div class="summary">
            <div class="summary-card">
                <div class="value">{n_steps}</div>
                <div class="label">Navigation Steps</div>
            </div>
            <div class="summary-card">
                <div class="value">${cost:.4f}</div>
                <div class="label">Total Cost</div>
            </div>
            <div class="summary-card">
                <div class="value">{success}</div>
                <div class="label">Status</div>
            </div>
        </div>

        {thumbnail_html}

        <div class="answer-box">
            <h3>Final Answer</h3>
            <p>{answer}</p>
        </div>

        <div class="timeline">
            <h2 style="margin-bottom: 1rem;">Navigation Steps</h2>
            {steps_html}
        </div>

        <footer>
            <p>Generated by GIANT v{version}</p>
        </footer>
    </div>

    <script>
        document.querySelectorAll('.step-header').forEach(header => {{
            header.addEventListener('click', () => {{
                const step = header.parentElement;
                step.classList.toggle('active');
            }});
        }});
        // Open first step by default
        const firstStep = document.querySelector('.step');
        if (firstStep) firstStep.classList.add('active');
    </script>
</body>
</html>
"""

_STEP_TEMPLATE = """
<div class="step">
    <div class="step-header">
        <span class="step-number">Step {step_num}</span>
        <span class="step-action">{action}</span>
    </div>
    <div class="step-content">
        <div class="step-section">
            <h4>Reasoning</h4>
            <div class="reasoning">{reasoning}</div>
        </div>
        {region_html}
        {image_html}
    </div>
</div>
"""

_REGION_TEMPLATE = """
<div class="step-section">
    <h4>Region</h4>
    <div class="region-info">
        <div class="item">
            <div class="value">{x}</div>
            <div class="label">X</div>
        </div>
        <div class="item">
            <div class="value">{y}</div>
            <div class="label">Y</div>
        </div>
        <div class="item">
            <div class="value">{width}</div>
            <div class="label">Width</div>
        </div>
        <div class="item">
            <div class="value">{height}</div>
            <div class="label">Height</div>
        </div>
    </div>
</div>
"""


def create_trajectory_html(
    *,
    trajectory_path: Path,
    output_path: Path | None,
    open_browser: bool,
) -> Path:
    """Generate HTML visualization for a trajectory.

    Args:
        trajectory_path: Path to trajectory JSON file.
        output_path: Optional output HTML path. If None, uses trajectory name.
        open_browser: Whether to open the result in a browser.

    Returns:
        Path to the generated HTML file.
    """
    from giant import __version__  # noqa: PLC0415

    logger = get_logger(__name__)

    # Load trajectory with error handling
    try:
        with trajectory_path.open() as f:
            trajectory = json.load(f)
    except json.JSONDecodeError as e:
        logger.error("Invalid trajectory JSON", path=str(trajectory_path), error=str(e))
        raise ValueError(f"Invalid trajectory JSON in {trajectory_path}: {e}") from e

    # Extract data
    turns = trajectory.get("turns", [])
    answer = _get_answer(trajectory)
    wsi_path = trajectory.get("wsi_path", "Unknown")
    wsi_name = Path(wsi_path).name if wsi_path else "Unknown"
    total_cost = _get_total_cost(trajectory)
    success = _get_success_label(trajectory)

    slide_width = _safe_int(trajectory.get("slide_width"))
    slide_height = _safe_int(trajectory.get("slide_height"))
    thumbnail_base64 = trajectory.get("thumbnail_base64")

    # Generate thumbnail HTML with overlays
    thumbnail_html = ""
    if thumbnail_base64:
        overlays = []
        for turn in turns:
            _, _, region = _extract_turn(turn)
            if region and slide_width > 0 and slide_height > 0:
                left = (region["x"] / slide_width) * 100
                top = (region["y"] / slide_height) * 100
                width = (region["width"] / slide_width) * 100
                height = (region["height"] / slide_height) * 100
                overlays.append(
                    f'<div class="crop-overlay" style="left: {left:.2f}%; '
                    f'top: {top:.2f}%; width: {width:.2f}%; height: {height:.2f}%;">'
                    "</div>"
                )

        thumbnail_html = (
            f'<div class="thumbnail-container">\n'
            f'    <img src="data:image/jpeg;base64,{thumbnail_base64}" '
            f'class="thumbnail-img" alt="WSI Thumbnail">\n'
            f"    {''.join(overlays)}\n"
            f"</div>"
        )

    # Generate steps HTML
    steps_html_parts = []
    for i, turn in enumerate(turns, 1):
        action, reasoning, region = _extract_turn(turn)
        region_html = _format_region_html(region)

        # Step image
        image_html = ""
        image_base64 = turn.get("image_base64")
        if image_base64:
            image_html = (
                f'<img src="data:image/jpeg;base64,{image_base64}" '
                f'class="step-image" alt="Step View">'
            )

        step_html = _STEP_TEMPLATE.format(
            step_num=i,
            action=action,
            reasoning=_escape_html(reasoning),
            region_html=region_html,
            image_html=image_html,
        )
        steps_html_parts.append(step_html)

    steps_html = "\n".join(steps_html_parts) or "<p>No navigation steps recorded.</p>"

    # Generate full HTML
    html = _HTML_TEMPLATE.format(
        wsi_name=_escape_html(wsi_name),
        n_steps=len(turns),
        cost=total_cost,
        success=success,
        answer=_escape_html(answer),
        steps_html=steps_html,
        thumbnail_html=thumbnail_html,
        version=__version__,
    )

    # Determine output path
    if output_path is None:
        output_path = trajectory_path.with_suffix(".html")

    # Write HTML
    output_path.write_text(html, encoding="utf-8")
    logger.info("Visualization generated", path=str(output_path))

    # Open in browser if requested
    if open_browser:
        webbrowser.open(f"file://{output_path.absolute()}")

    return output_path


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _get_answer(trajectory: dict[str, object]) -> str:
    answer = trajectory.get("answer")
    if isinstance(answer, str) and answer:
        return answer
    final_answer = trajectory.get("final_answer")
    if isinstance(final_answer, str) and final_answer:
        return final_answer
    return "No answer recorded"


def _get_total_cost(trajectory: dict[str, object]) -> float:
    total_cost = trajectory.get("total_cost", trajectory.get("total_cost_usd", 0.0))
    if isinstance(total_cost, (int, float)):
        return float(total_cost)
    return 0.0


def _get_success_label(trajectory: dict[str, object]) -> str:
    success_value = trajectory.get("success")
    if isinstance(success_value, bool):
        return "Success" if success_value else "Failed"
    return "Unknown"


def _extract_turn(turn: object) -> tuple[str, str, dict[str, int] | None]:
    if not isinstance(turn, dict):
        return "unknown", "No reasoning recorded", None

    response = turn.get("response")
    response_dict = response if isinstance(response, dict) else {}

    reasoning = (
        turn.get("reasoning")
        or response_dict.get("reasoning")
        or turn.get("thought")
        or "No reasoning recorded"
    )
    reasoning_text = str(reasoning)

    action = "unknown"
    raw_action = turn.get("action")
    if isinstance(raw_action, dict):
        action = str(raw_action.get("action_type", "unknown"))
    elif isinstance(raw_action, str):
        action = raw_action
    else:
        resp_action = response_dict.get("action")
        if isinstance(resp_action, dict):
            action = str(resp_action.get("action_type", "unknown"))

    region = turn.get("region") or turn.get("crop") or None
    if isinstance(region, dict) and region:
        return (
            action,
            reasoning_text,
            {
                "x": _safe_int(region.get("x", 0)),
                "y": _safe_int(region.get("y", 0)),
                "width": _safe_int(region.get("width", 0)),
                "height": _safe_int(region.get("height", 0)),
            },
        )

    return action, reasoning_text, None


def _safe_int(val: object) -> int:
    """Safely convert a value to int, returning 0 on failure."""
    try:
        return int(val)  # type: ignore[call-overload, no-any-return]
    except (TypeError, ValueError):
        return 0


def _format_region_html(region: dict[str, int] | None) -> str:
    if not region:
        return ""
    return _REGION_TEMPLATE.format(
        x=region["x"],
        y=region["y"],
        width=region["width"],
        height=region["height"],
    )
