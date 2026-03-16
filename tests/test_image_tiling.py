import pathlib
import sys

import numpy as np


ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "backEnd" / "src"
sys.path.insert(0, str(SRC_DIR))

from promptrefine.services.image_tiling import (  # noqa: E402
    TilingConfig,
    fuse_detections,
    fuse_probability_tiles,
    generate_tiles,
)


def test_generate_tiles_covers_image():
    config = TilingConfig(tile_width=4, tile_height=4, overlap_x=2, overlap_y=2)
    tiles = generate_tiles(10, 8, config)
    assert len(tiles) > 0

    covered = np.zeros((8, 10), dtype=np.uint8)
    for tile in tiles:
        covered[tile["y"] : tile["y2"], tile["x"] : tile["x2"]] = 1

    assert covered.min() == 1


def test_fuse_detections_merges_overlap():
    tile_predictions = [
        {
            "tileId": "t0",
            "x": 0,
            "y": 0,
            "detections": [{"bbox": [10, 10, 40, 40], "score": 0.9, "label": "obj"}],
        },
        {
            "tileId": "t1",
            "x": 20,
            "y": 0,
            "detections": [{"bbox": [-10, 11, 20, 41], "score": 0.8, "label": "obj"}],
        },
    ]
    merged = fuse_detections(tile_predictions, iou_threshold=0.5)
    assert len(merged) == 1
    assert merged[0]["label"] == "obj"
    assert set(merged[0]["sources"]) == {"t0", "t1"}


def test_fuse_probability_tiles_averages_overlap():
    maps = [
        {"x": 0, "y": 0, "probability": [[1.0, 1.0], [1.0, 1.0]]},
        {"x": 1, "y": 0, "probability": [[0.0, 0.0], [0.0, 0.0]]},
    ]
    out = fuse_probability_tiles(maps, image_width=3, image_height=2, threshold=0.6)
    prob = np.asarray(out["probability"], dtype=float)
    mask = np.asarray(out["mask"], dtype=np.uint8)

    assert prob.shape == (2, 3)
    assert prob[0, 0] == 1.0
    assert prob[0, 1] == 0.5
    assert mask[0, 0] == 1
    assert mask[0, 1] == 0
