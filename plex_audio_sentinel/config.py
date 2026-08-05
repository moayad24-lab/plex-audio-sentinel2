"""Environment configuration."""
import os
from dataclasses import dataclass

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

    @classmethod
    def from_env(cls, environ=None):
        e = environ or os.environ
        path = e.get("PLEX_MEDIA_PATH", "").strip()
        if not path:
            raise ValueError("PLEX_MEDIA_PATH is required")
        return cls(path, e.get("PLEX_URL", "").rstrip("/"), e.get("PLEX_TOKEN", ""),
                   e.get("PLEX_SECTION", ""), e.get("FFMPEG", "ffmpeg"), e.get("FFPROBE", "ffprobe"),
                   e.get("TELEGRAM_BOT_TOKEN", ""), e.get("TELEGRAM_CHAT_ID", ""))

    def validate(self):
        if not self.media_path.strip(): raise ValueError("media path is empty")
        if not self.plex_url and self.plex_section: raise ValueError("PLEX_URL required when PLEX_SECTION is set")
        if bool(self.telegram_token) != bool(self.telegram_chat_id):
            raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set together")
        return self
