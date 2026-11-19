from pathlib import Path

import pytest

from backend.engine import decode_project


@pytest.fixture
def six_lane_project():
    """Use the saved six-lane project for generate and routing regressions."""
    path = Path(__file__).resolve().parents[1] / "artifacts" / "verilinx_top.sv"
    project = decode_project(path.read_text(encoding="utf-8"))
    positions = {"bus": (1070, 480), "clocks": (-5, -150), "clock_const": (-325, -150),
                 "resets": (-5, 620), "reset_const": (-325, 620)}
    for node in project["nodes"]:
        if node["id"] in positions:
            x, y = positions[node["id"]]
            node["position"] = {"x": x, "y": y}
    return project
