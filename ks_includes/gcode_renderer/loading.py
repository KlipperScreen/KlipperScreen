from __future__ import annotations

import os
from dataclasses import dataclass

RESET_PRINT_STATES = {"cancelled", "complete", "error", "standby"}
VIRTUAL_SDCARD_FILENAME_KEYS = ("file_path", "filename", "path")


@dataclass(slots=True)
class LoadTracker:
    load_in_progress: bool = False
    loading_filename: str = ""
    load_generation: int = 0
    load_cancelled: bool = False
    panel_active: bool = False

    def activate(self, filename: str = "") -> None:
        self.panel_active = True
        if self.load_in_progress and filename and filename == self.loading_filename:
            self.load_cancelled = False

    def deactivate(self) -> None:
        self.panel_active = False
        if self.load_in_progress:
            self.load_cancelled = False

    def begin(self, filename: str, force_reload: bool = False) -> int | None:
        if not filename:
            return None
        if self.load_in_progress and self.loading_filename == filename and not force_reload:
            return None
        self.load_generation += 1
        self.load_in_progress = True
        self.loading_filename = filename
        self.load_cancelled = False
        return self.load_generation

    def invalidate(self) -> int:
        self.load_generation += 1
        self.load_in_progress = False
        self.loading_filename = ""
        self.load_cancelled = False
        return self.load_generation

    def finish(self, generation: int, filename: str) -> str:
        if generation != self.load_generation or filename != self.loading_filename:
            return "stale"
        self.load_in_progress = False
        if self.load_cancelled:
            self.load_cancelled = False
            return "cancelled"
        if not self.panel_active:
            return "inactive"
        return "accepted"


def first_non_empty_filename(*values: str | None) -> str:
    for value in values:
        if not isinstance(value, str):
            continue
        candidate = value.strip()
        if candidate:
            return candidate
    return ""


def virtual_sdcard_filename(status: dict | None) -> str:
    if not isinstance(status, dict):
        return ""
    return first_non_empty_filename(*(status.get(key) for key in VIRTUAL_SDCARD_FILENAME_KEYS))


def resolve_active_filename(
    printer_filename: str | None = None,
    explicit_filename: str | None = None,
    current_filename: str | None = None,
    virtual_sdcard_status: dict | None = None,
) -> str:
    return first_non_empty_filename(
        printer_filename,
        explicit_filename,
        current_filename,
        virtual_sdcard_filename(virtual_sdcard_status),
    )


def should_clear_active_filename(
    current_filename: str | None,
    resolved_filename: str | None,
    print_state: str | None,
) -> bool:
    if not current_filename or resolved_filename:
        return False
    state = (print_state or "").strip().lower()
    return state in RESET_PRINT_STATES


def resolve_local_gcode_path(root: str | None, filename: str | None) -> str | None:
    if not root or not filename:
        return None
    root_path = os.path.realpath(os.path.abspath(os.path.expanduser(root)))
    if not os.path.isdir(root_path):
        return None

    candidate = os.path.realpath(
        os.path.abspath(os.path.join(root_path, filename.replace("/", os.sep)))
    )
    try:
        if os.path.commonpath([root_path, candidate]) != root_path:
            return None
    except ValueError:
        return None

    if not os.path.isfile(candidate) or not os.access(candidate, os.R_OK):
        return None
    return candidate


def load_local_gcode(root: str | None, filename: str | None) -> tuple[str, bytes] | None:
    resolved = resolve_local_gcode_path(root, filename)
    if resolved is None:
        return None
    with open(resolved, "rb") as handle:
        return (resolved, handle.read())
