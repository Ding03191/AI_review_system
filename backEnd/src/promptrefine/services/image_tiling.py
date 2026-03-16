from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class TilingConfig:
    tile_width: int = 1024
    tile_height: int = 1024
    overlap_x: int = 128
    overlap_y: int = 128


def _validate_config(config: TilingConfig) -> None:
    if config.tile_width <= 0 or config.tile_height <= 0:
        raise ValueError("tile_width and tile_height must be > 0")
    if config.overlap_x < 0 or config.overlap_y < 0:
        raise ValueError("overlap_x and overlap_y must be >= 0")
    if config.overlap_x >= config.tile_width:
        raise ValueError("overlap_x must be smaller than tile_width")
    if config.overlap_y >= config.tile_height:
        raise ValueError("overlap_y must be smaller than tile_height")


def _axis_starts(total: int, tile_size: int, overlap: int) -> list[int]:
    if total <= tile_size:
        return [0]

    starts: list[int] = []
    stride = tile_size - overlap
    cursor = 0
    while True:
        starts.append(cursor)
        if cursor + tile_size >= total:
            break
        cursor += stride
        if cursor + tile_size > total:
            cursor = total - tile_size
    return starts


def generate_tiles(
    image_width: int,
    image_height: int,
    config: TilingConfig,
) -> list[dict[str, Any]]:
    """
    Return tile metadata for overlap-tiled inference.

    Tile format:
    {
      "tileId": "t0",
      "x": 0, "y": 0,
      "width": 1024, "height": 1024,
      "x2": 1024, "y2": 1024
    }
    """
    if image_width <= 0 or image_height <= 0:
        raise ValueError("image_width and image_height must be > 0")
    _validate_config(config)

    xs = _axis_starts(image_width, config.tile_width, config.overlap_x)
    ys = _axis_starts(image_height, config.tile_height, config.overlap_y)

    tiles: list[dict[str, Any]] = []
    index = 0
    for y in ys:
        for x in xs:
            width = min(config.tile_width, image_width - x)
            height = min(config.tile_height, image_height - y)
            tiles.append(
                {
                    "tileId": f"t{index}",
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                    "x2": x + width,
                    "y2": y + height,
                }
            )
            index += 1
    return tiles


def _iou(box_a: tuple[float, float, float, float], box_b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter = inter_w * inter_h
    if inter == 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    if denom <= 0:
        return 0.0
    return inter / denom


def fuse_detections(
    tile_predictions: Iterable[dict[str, Any]],
    *,
    iou_threshold: float = 0.5,
    score_threshold: float = 0.0,
) -> list[dict[str, Any]]:
    """
    Merge tiled local detections into image-global detections.

    Expected input format per tile:
    {
      "tileId": "t0",
      "x": 0,
      "y": 0,
      "detections": [
        { "bbox": [x1, y1, x2, y2], "score": 0.91, "label": "defect" }
      ]
    }

    Output:
    [
      { "bbox": [gx1, gy1, gx2, gy2], "score": 0.91, "label": "defect", "sources": ["t0"] }
    ]
    """
    if not 0.0 <= iou_threshold <= 1.0:
        raise ValueError("iou_threshold must be in [0, 1]")

    flattened: list[dict[str, Any]] = []
    for tile in tile_predictions:
        ox = float(tile.get("x", 0))
        oy = float(tile.get("y", 0))
        tile_id = str(tile.get("tileId", ""))
        for det in tile.get("detections") or []:
            bbox = det.get("bbox")
            if not bbox or len(bbox) != 4:
                continue
            score = float(det.get("score", 0.0))
            if score < score_threshold:
                continue
            label = str(det.get("label", "object"))
            gx1 = float(bbox[0]) + ox
            gy1 = float(bbox[1]) + oy
            gx2 = float(bbox[2]) + ox
            gy2 = float(bbox[3]) + oy
            if gx2 <= gx1 or gy2 <= gy1:
                continue
            flattened.append(
                {
                    "bbox": [gx1, gy1, gx2, gy2],
                    "score": score,
                    "label": label,
                    "tileId": tile_id,
                }
            )

    if not flattened:
        return []

    flattened.sort(key=lambda x: x["score"], reverse=True)
    used = [False] * len(flattened)
    merged: list[dict[str, Any]] = []

    for i, leader in enumerate(flattened):
        if used[i]:
            continue
        used[i] = True
        leader_box = tuple(leader["bbox"])
        same_cluster = [leader]
        for j in range(i + 1, len(flattened)):
            if used[j]:
                continue
            cand = flattened[j]
            if cand["label"] != leader["label"]:
                continue
            cand_box = tuple(cand["bbox"])
            if _iou(leader_box, cand_box) >= iou_threshold:
                same_cluster.append(cand)
                used[j] = True

        score_sum = sum(max(item["score"], 1e-6) for item in same_cluster)
        box_np = np.array([item["bbox"] for item in same_cluster], dtype=float)
        weights = np.array([max(item["score"], 1e-6) for item in same_cluster], dtype=float).reshape(-1, 1)
        fused_box = (box_np * weights).sum(axis=0) / score_sum
        sources = sorted({item["tileId"] for item in same_cluster if item["tileId"]})
        merged.append(
            {
                "bbox": [float(v) for v in fused_box.tolist()],
                "score": max(item["score"] for item in same_cluster),
                "label": leader["label"],
                "sources": sources,
            }
        )

    merged.sort(key=lambda x: x["score"], reverse=True)
    return merged


def fuse_probability_tiles(
    tile_probability_maps: Iterable[dict[str, Any]],
    *,
    image_width: int,
    image_height: int,
    threshold: float = 0.5,
) -> dict[str, Any]:
    """
    Merge per-tile probability map into one full-resolution map with overlap averaging.

    Expected tile format:
    {
      "x": 0,
      "y": 0,
      "probability": [[0.1, 0.9, ...], [...]]
    }
    """
    if image_width <= 0 or image_height <= 0:
        raise ValueError("image_width and image_height must be > 0")

    accumulator = np.zeros((image_height, image_width), dtype=np.float32)
    counter = np.zeros((image_height, image_width), dtype=np.float32)

    for tile in tile_probability_maps:
        ox = int(tile.get("x", 0))
        oy = int(tile.get("y", 0))
        prob = np.asarray(tile.get("probability"), dtype=np.float32)
        if prob.ndim != 2:
            continue
        h, w = prob.shape
        x2 = min(image_width, ox + w)
        y2 = min(image_height, oy + h)
        if x2 <= ox or y2 <= oy:
            continue
        sub = prob[: y2 - oy, : x2 - ox]
        accumulator[oy:y2, ox:x2] += sub
        counter[oy:y2, ox:x2] += 1.0

    counter[counter == 0] = 1.0
    merged = accumulator / counter
    binary = (merged >= threshold).astype(np.uint8)

    return {
        "probability": merged.tolist(),
        "mask": binary.tolist(),
    }


def run_tiled_detection_inference(
    image: Image.Image,
    predictor: Callable[[Image.Image, dict[str, Any]], list[dict[str, Any]]],
    *,
    config: TilingConfig | None = None,
    iou_threshold: float = 0.5,
    score_threshold: float = 0.0,
) -> dict[str, Any]:
    """
    Run tiled detection end-to-end.

    `predictor` input:
      - tile image (PIL.Image)
      - tile metadata dict from generate_tiles

    `predictor` output:
      - local detection list:
        [{"bbox": [x1,y1,x2,y2], "score": 0.9, "label": "obj"}]
    """
    if config is None:
        config = TilingConfig()

    width, height = image.size
    tiles = generate_tiles(width, height, config)

    tile_predictions: list[dict[str, Any]] = []
    for tile in tiles:
        crop = image.crop((tile["x"], tile["y"], tile["x2"], tile["y2"]))
        detections = predictor(crop, tile) or []
        tile_predictions.append(
            {
                "tileId": tile["tileId"],
                "x": tile["x"],
                "y": tile["y"],
                "detections": detections,
            }
        )

    fused = fuse_detections(
        tile_predictions,
        iou_threshold=iou_threshold,
        score_threshold=score_threshold,
    )
    return {
        "tiles": tiles,
        "tilePredictions": tile_predictions,
        "detections": fused,
    }
