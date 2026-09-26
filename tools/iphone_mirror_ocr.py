"""Find text targets in a live JPEG frame without persisting phone content."""

from __future__ import annotations

from collections import defaultdict
import csv
from io import BytesIO, StringIO
import subprocess

from PIL import Image


_MAX_JPEG_BYTES = 16 * 1024 * 1024
_MAX_TARGETS = 200


def detect_targets(jpeg: bytes) -> list[dict]:
    """Return visible text lines with normalized bounding boxes and OCR confidence.

    Each target has ``text``, ``x``, ``y``, ``w``, ``h``, and ``confidence``.
    Coordinates and sizes are floats in [0, 1]; confidence is in [0, 1].
    OCR input and output exist only in memory. The subprocess has a 3 s limit.
    """
    if not isinstance(jpeg, bytes) or not jpeg or len(jpeg) > _MAX_JPEG_BYTES:
        raise ValueError("Expected a nonempty JPEG frame of at most 16 MiB")
    try:
        with Image.open(BytesIO(jpeg)) as image:
            if image.format != "JPEG":
                raise ValueError("Expected a JPEG frame")
            width, height = image.size
    except OSError as exc:
        raise ValueError("Invalid JPEG frame") from exc
    if width < 1 or height < 1:
        raise ValueError("Invalid JPEG dimensions")

    try:
        result = subprocess.run(
            ["tesseract", "stdin", "stdout", "-l", "eng", "--psm", "11",
             "--loglevel", "OFF", "tsv"],
            input=jpeg,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=True,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError("Phone frame OCR exceeded 3 seconds") from exc
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("Phone frame OCR unavailable") from exc

    lines: dict[tuple[str, str, str, str], list[tuple[int, int, int, int, str, float]]] = defaultdict(list)
    rows = csv.DictReader(StringIO(result.stdout.decode("utf-8", errors="replace")), delimiter="\t")
    for row in rows:
        if row.get("level") != "5":
            continue
        word = (row.get("text") or "").strip()
        if not word:
            continue
        try:
            confidence = float(row["conf"])
            left, top = int(row["left"]), int(row["top"])
            box_w, box_h = int(row["width"]), int(row["height"])
        except (ValueError, TypeError, KeyError):
            continue
        if confidence < 30 or box_w <= 0 or box_h <= 0:
            continue
        key = (row["page_num"], row["block_num"], row["par_num"], row["line_num"])
        lines[key].append((left, top, box_w, box_h, word, confidence))

    targets = []
    for words in lines.values():
        words.sort(key=lambda word: word[0])
        left = max(0, min(word[0] for word in words))
        top = max(0, min(word[1] for word in words))
        right = min(width, max(word[0] + word[2] for word in words))
        bottom = min(height, max(word[1] + word[3] for word in words))
        if right <= left or bottom <= top:
            continue
        weight = sum(word[2] for word in words)
        targets.append({
            "text": " ".join(word[4] for word in words),
            "x": left / width,
            "y": top / height,
            "w": (right - left) / width,
            "h": (bottom - top) / height,
            "confidence": round(sum(word[5] * word[2] for word in words) / weight / 100, 3),
        })
    targets.sort(key=lambda target: (target["y"], target["x"]))
    return targets[:_MAX_TARGETS]
