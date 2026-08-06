"""Durable baseline state tracking which source media paths are already seen.

The state file records every source media path that must never be processed
again (the baseline). Only paths that appear after the baseline was recorded
are eligible for processing. State writes are atomic: the JSON payload is
written to a temporary file in the target directory and moved into place with
``os.replace``, so a crash can never leave a half-written state file. If the
state file exists but is malformed, loading raises :class:`StateError` and the
caller must abort rather than silently treating existing media as new.
"""
import json
import os
import tempfile

STATE_FILENAME = ".plex-audio-sentinel-state.json"
STATE_VERSION = 1


class StateError(Exception):
    """The state file exists but cannot be trusted; processing must not proceed."""


def default_state_path(media_path):
    """Default state location: a hidden JSON file inside the media root.

    The file is never picked up by discovery because discovery only matches
    video extensions, but the location is documented and can be overridden
    with PLEX_STATE_FILE (useful when the media root is read-only).
    """
    return os.path.join(media_path, STATE_FILENAME)


def _normalize(path):
    """Absolute, normalized form used for all state comparisons."""
    return os.path.abspath(os.path.normpath(path))


class State:
    """A set of source media paths that have already been safely considered."""

    def __init__(self, path, seen=()):
        self.path = path
        self.seen = {_normalize(p) for p in seen}

    @classmethod
    def load(cls, path):
        """Load state from disk.

        Raises:
            FileNotFoundError: no state file exists yet (first run / no baseline).
            StateError: the file exists but is malformed or unreadable; the
                library must not be treated as brand new in that case.
        """
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise StateError(
                f"state file {path} could not be read: {exc}. Refusing to treat "
                "existing media as new."
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StateError(
                f"state file {path} is malformed ({exc}). Refusing to treat "
                "existing media as new. Fix the file, or delete it and re-run to "
                "rebuild the baseline (the rebuild run records files and converts nothing)."
            ) from exc
        if not isinstance(data, dict) or data.get("version") != STATE_VERSION:
            raise StateError(
                f"state file {path} is not a valid v{STATE_VERSION} state file "
                f'(expected an object with "version": {STATE_VERSION} and a "seen" '
                "list of paths). Refusing to treat existing media as new. Fix the "
                "file, or delete it and re-run to rebuild the baseline."
            )
        seen = data.get("seen")
        if not isinstance(seen, list) or not all(isinstance(p, str) for p in seen):
            raise StateError(
                f'state file {path} has an invalid "seen" field (expected a list '
                "of path strings). Refusing to treat existing media as new. Fix the "
                "file, or delete it and re-run to rebuild the baseline."
            )
        return cls(path, seen=seen)

    def contains(self, path):
        return _normalize(path) in self.seen

    def mark(self, path):
        """Record a source path as seen (converted or safely skipped)."""
        self.seen.add(_normalize(path))

    def mark_many(self, paths):
        for path in paths:
            self.mark(path)

    def save(self):
        """Atomically persist state: temp file in the target dir + os.replace."""
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        payload = json.dumps(
            {"version": STATE_VERSION, "seen": sorted(self.seen)}, indent=2
        ) + "\n"
        fd, tmp_path = tempfile.mkstemp(prefix=".plex-state-", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, self.path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
