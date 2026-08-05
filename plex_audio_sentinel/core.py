"""Media inspection and companion-file conversion."""
import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass

VIDEO_EXTENSIONS = (".mkv", ".mp4", ".m4v", ".avi", ".mov", ".webm")
COMPANION_SUFFIX = ".stereo-ac3"

@dataclass
class Summary:
    scanned: int = 0
    converted: int = 0
    skipped: int = 0
    errors: int = 0
    def text(self):
        return f"Plex Audio Sentinel: scanned {self.scanned}, converted {self.converted}, skipped {self.skipped}, errors {self.errors}."

def _language(stream):
    tags = stream.get("tags") or {}
    return str(tags.get("language", stream.get("language", ""))).strip().lower()

def is_english_or_unknown(stream):
    """Keep English and absent/unknown language tags; reject explicit other languages."""
    lang = _language(stream)
    if not lang or lang in {"und", "unknown", "unk", "none", "null"}:
        return True
    return lang in {"en", "eng", "english"} or lang.startswith("en-") or lang.startswith("en_")

def has_aac(streams):
    """Backward-compatible inspection helper; AAC is not an eligibility criterion."""
    return any(s.get("codec_type") == "audio" and str(s.get("codec_name", "")).lower() == "aac" for s in streams)

def is_multichannel(stream):
    codec = str(stream.get("codec_name", "")).lower()
    try:
        channels = int(stream.get("channels", 0) or 0)
    except (TypeError, ValueError):
        channels = 0
    return channels > 2 or codec.startswith("dts")

def eligible_audio(streams):
    return [s for s in streams if s.get("codec_type") == "audio" and is_multichannel(s)]

def selected_audio(streams):
    return [s for s in streams if s.get("codec_type") == "audio" and is_english_or_unknown(s)]

def output_path(path):
    root, ext = os.path.splitext(path)
    return root + COMPANION_SUFFIX + ext

def probe(path, ffprobe="ffprobe", runner=subprocess.run):
    p = runner([ffprobe, "-v", "error", "-show_streams", "-of", "json", path], capture_output=True, text=True, check=True)
    return json.loads(p.stdout).get("streams", [])

def ffmpeg_command(src, dst, streams=None, ffmpeg="ffmpeg"):
    """Build a map preserving video/subtitles and English/unknown audio.

    The first audio map is a copy of an eligible source but encoded as stereo AC-3;
    remaining selected audio maps are copied unchanged. Stream indexes are global
    ffprobe indexes, so this works when non-audio streams are interspersed.
    """
    if streams is None:
        # Compatibility/default shape for callers that only need to inspect command options.
        return [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-map", "0", "-c:v", "copy", "-c:a", "ac3", "-ac", "2", dst]
    eligible = eligible_audio(streams)
    keep = selected_audio(streams)
    if not eligible or not keep:
        raise ValueError("no eligible multichannel audio or no English/unknown audio")
    source = eligible[0]
    args = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", src]
    for s in [x for x in streams if x.get("codec_type") == "video"]:
        args += ["-map", f"0:{s['index']}"]
    args += ["-map", f"0:{source['index']}"]
    # Keep every selected original track too, including the source used for the downmix.
    for s in keep:
        args += ["-map", f"0:{s['index']}"]
    for s in [x for x in streams if x.get("codec_type") == "subtitle"]:
        args += ["-map", f"0:{s['index']}"]
    args += ["-map_metadata", "0", "-map_chapters", "0", "-c:v", "copy", "-c:s", "copy", "-c:a", "copy", "-c:a:0", "ac3", "-ac:a:0", "2", "-metadata:s:a:0", "language=eng", dst]
    return args

def convert(path, streams, ffmpeg="ffmpeg", runner=subprocess.run):
    dst = output_path(path)
    if os.path.exists(dst):
        return False
    directory = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".plex-audio-", suffix=os.path.splitext(path)[1], dir=directory)
    os.close(fd)
    try:
        runner(ffmpeg_command(path, tmp, streams, ffmpeg), check=True)
        os.replace(tmp, dst)
        return True
    except Exception:
        try: os.unlink(tmp)
        except OSError: pass
        raise

def discover(path, extensions=VIDEO_EXTENSIONS):
    for root, _, files in os.walk(path):
        for name in sorted(files):
            if name.lower().endswith(tuple(extensions)) and COMPANION_SUFFIX not in os.path.splitext(name)[0]:
                yield os.path.join(root, name)

def process(path, cfg, dry_run=False, runner=subprocess.run, logger=None):
    log = logger or logging.getLogger(__name__)
    try:
        streams = probe(path, cfg.ffprobe, runner)
        if not eligible_audio(streams) or not selected_audio(streams):
            return "skipped"
        if os.path.exists(output_path(path)):
            return "skipped"
        if dry_run:
            return "would-convert"
        convert(path, streams, cfg.ffmpeg, runner)
        return "converted"
    except Exception as exc:
        log.error("%s: %s", path, exc)
        return "error"
