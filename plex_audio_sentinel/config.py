"""Environment configuration."""
import os
from dataclasses import dataclass

from .core import normalize_path
from .state import default_state_path

@dataclass
class Config:
    media_path: str
    plex_url: str = ""
    plex_token: str = ""
    plex_section: str = ""
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    telegram_token: str = ""
    telegram_chat_id: str = ""
    extensions: tuple = (".mkv", ".mp4", ".m4v", ".avi", ".mov", ".webm")
    state_file: str = ""
    output_path: str = ""
    # Collision-safe source -> companion map, computed and set by runner.run;
    # not an environment setting.
    output_names: dict = None

    @classmethod
    def from_env(cls, environ=None):
        e = environ or os.environ
        path = e.get("PLEX_MEDIA_PATH", "").strip()
        if not path:
            raise ValueError("PLEX_MEDIA_PATH is required")
        state_file = e.get("PLEX_STATE_FILE", "").strip()
        if not state_file:
            state_file = default_state_path(path)
        return cls(
            media_path=path,
            plex_url=e.get("PLEX_URL", "").rstrip("/"),
            plex_token=e.get("PLEX_TOKEN", ""),
            plex_section=e.get("PLEX_SECTION", ""),
            ffmpeg=e.get("FFMPEG", "ffmpeg"),
            ffprobe=e.get("FFPROBE", "ffprobe"),
            telegram_token=e.get("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=e.get("TELEGRAM_CHAT_ID", ""),
            state_file=state_file,
            output_path=e.get("PLEX_OUTPUT_PATH", "").strip(),
        )

    def validate(self):
        if not self.media_path.strip(): raise ValueError("media path is empty")
        if not self.state_file.strip(): raise ValueError("state file path is empty")
        output_path = self.output_path.strip()
        if not output_path:
            raise ValueError(
                "PLEX_OUTPUT_PATH is required: all generated companions are "
                "written into this single folder (example: "
                "PLEX_OUTPUT_PATH=E:\\Plex Media Server\\Converted)"
            )
        media = normalize_path(self.media_path)
        output = normalize_path(output_path)
        if output == media or media.startswith(output + os.sep):
            raise ValueError(
                "PLEX_OUTPUT_PATH must not be the media root or one of its "
                "parent directories (the output folder is excluded from source "
                "discovery, so that would hide the whole library)"
            )
        if not self.plex_url and self.plex_section: raise ValueError("PLEX_URL required when PLEX_SECTION is set")
        if bool(self.telegram_token) != bool(self.telegram_chat_id):
            raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set together")
        return self
