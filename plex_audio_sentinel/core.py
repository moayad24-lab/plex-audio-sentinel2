"""Media inspection and safe replacement."""
import json, logging, os, shutil, subprocess, tempfile
from dataclasses import dataclass

VIDEO_EXTENSIONS = (".mkv", ".mp4", ".m4v", ".avi", ".mov", ".webm")
@dataclass
class Summary:
    scanned:int=0; converted:int=0; skipped:int=0; errors:int=0
    def text(self): return f"Plex Audio Sentinel: scanned {self.scanned}, converted {self.converted}, skipped {self.skipped}, errors {self.errors}."

def has_aac(streams):
    return any((s.get("codec_type") == "audio" and str(s.get("codec_name", "")).lower() == "aac") for s in streams)

def probe(path, ffprobe="ffprobe", runner=subprocess.run):
    p=runner([ffprobe, "-v", "error", "-show_streams", "-of", "json", path], capture_output=True, text=True, check=True)
    return json.loads(p.stdout).get("streams", [])

def ffmpeg_command(src, dst, ffmpeg="ffmpeg"):
    # map all video and audio streams; encode every audio stream to AAC while copying video/subtitles.
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-map", "0", "-c:v", "copy", "-c:a", "aac", "-c:s", "copy", dst]

def convert(path, ffmpeg="ffmpeg", runner=subprocess.run, backup=True):
    directory=os.path.dirname(path) or "."
    fd,tmp=tempfile.mkstemp(prefix=".plex-audio-", suffix=os.path.splitext(path)[1], dir=directory); os.close(fd)
    try:
        runner(ffmpeg_command(path,tmp,ffmpeg), check=True)
        if backup:
            backup_path=path + ".bak"
            shutil.copy2(path, backup_path)
        os.replace(tmp,path)
    except Exception:
        try: os.unlink(tmp)
        except OSError: pass
        raise

def discover(path, extensions=VIDEO_EXTENSIONS):
    for root, _, files in os.walk(path):
        for name in sorted(files):
            if name.lower().endswith(tuple(extensions)): yield os.path.join(root,name)

def process(path, cfg, dry_run=False, runner=subprocess.run, logger=None):
    log=logger or logging.getLogger(__name__)
    try:
        streams=probe(path,cfg.ffprobe,runner); 
        if has_aac(streams): return "skipped"
        if dry_run: return "would-convert"
        convert(path,cfg.ffmpeg,runner); return "converted"
    except Exception as exc:
        log.error("%s: %s", path, exc); return "error"
