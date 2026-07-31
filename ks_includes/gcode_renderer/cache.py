from __future__ import annotations

import hashlib
import logging
import os
import pickle
from dataclasses import dataclass

from .model import RenderMode


def build_cache_fingerprint(filename: str, file_size: int, modified: float) -> str:
    token = f"{filename}|{int(file_size)}|{float(modified):.6f}"
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CacheEntry:
    fingerprint: str
    filename: str
    file_size: int
    modified: float


class GcodeRenderCache:
    CACHE_VERSION = 2

    def __init__(self, cache_dir: str | None = None):
        self.cache_dir = cache_dir or self.default_cache_dir()
        os.makedirs(self.cache_dir, exist_ok=True)

    @staticmethod
    def default_cache_dir() -> str:
        home = os.path.expanduser("~")
        printer_data = os.path.join(home, "printer_data")
        if os.path.isdir(printer_data):
            return os.path.join(printer_data, ".cache", "KlipperScreen", "gcode_renderer")
        return os.path.join(home, ".cache", "KlipperScreen", "gcode_renderer")

    @classmethod
    def make_entry(cls, filename: str, file_size: int, modified: float) -> CacheEntry:
        return CacheEntry(
            fingerprint=build_cache_fingerprint(filename, file_size, modified),
            filename=filename,
            file_size=int(file_size),
            modified=float(modified or 0.0),
        )

    def load(self, entry: CacheEntry):
        path = self._cache_path(entry.fingerprint)
        if not os.path.exists(path):
            logging.info(f"G-code renderer cache miss: {entry.filename}")
            return None
        try:
            with open(path, "rb") as handle:
                payload = pickle.load(handle)
        except Exception as exc:
            logging.warning(f"Unable to read G-code renderer cache {path}: {exc}")
            return None
        if payload.get("version") != self.CACHE_VERSION:
            logging.info(f"G-code renderer cache invalid version: {entry.filename}")
            return None
        if payload.get("fingerprint") != entry.fingerprint:
            logging.info(f"G-code renderer cache invalidated by fingerprint: {entry.filename}")
            return None
        model = payload.get("model")
        is_valid, reason = validate_toolpath_model(model)
        if not is_valid:
            logging.warning(
                "G-code renderer cache incompatible for %s: %s",
                entry.filename,
                reason,
            )
            self._remove_cache_file(path)
            return None
        logging.info(f"G-code renderer cache hit: {entry.filename}")
        return model

    def save(self, entry: CacheEntry, model) -> None:
        path = self._cache_path(entry.fingerprint)
        temp_path = f"{path}.tmp"
        payload = {
            "version": self.CACHE_VERSION,
            "fingerprint": entry.fingerprint,
            "filename": entry.filename,
            "file_size": entry.file_size,
            "modified": entry.modified,
            "model": model,
        }
        with open(temp_path, "wb") as handle:
            pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(temp_path, path)
        logging.info(f"G-code renderer cache saved: {entry.filename}")

    def _cache_path(self, fingerprint: str) -> str:
        return os.path.join(self.cache_dir, f"{fingerprint}.cache")

    @staticmethod
    def _remove_cache_file(path: str) -> None:
        try:
            os.remove(path)
        except FileNotFoundError:
            return
        except OSError as exc:
            logging.warning("Unable to remove invalid G-code renderer cache %s: %s", path, exc)


def validate_toolpath_model(model) -> tuple[bool, str]:
    if model is None:
        return (False, "missing model")

    required_attrs = (
        "segments",
        "segment_count",
        "layer_ranges",
        "bounds",
        "visible_bounds",
        "visible_spatial_bounds",
    )
    for attr in required_attrs:
        if not hasattr(model, attr):
            return (False, f"missing attribute {attr}")

    segments = getattr(model, "segments", None)
    if not isinstance(segments, list):
        return (False, "segments must be a list")

    try:
        segment_count = int(model.segment_count)
    except Exception:
        return (False, "segment_count is not numeric")
    if segment_count != len(segments):
        return (False, "segment_count mismatch")

    layer_ranges = getattr(model, "layer_ranges", None)
    if not isinstance(layer_ranges, list):
        return (False, "layer_ranges must be a list")

    if segment_count == 0:
        return (True, "empty")

    if any(not isinstance(segment, tuple) or len(segment) < 9 for segment in segments):
        return (False, "segments use an incompatible shape")

    bounds, _ = model.visible_bounds(RenderMode.FULL_MODEL, 0, 0)
    if not getattr(bounds, "is_valid", False):
        return (False, "planar bounds are invalid")

    spatial_bounds, _ = model.visible_spatial_bounds(RenderMode.FULL_MODEL, 0, 0, show_travel=True)
    if not getattr(spatial_bounds, "is_valid", False):
        return (False, "spatial bounds are invalid")

    return (True, "valid")
