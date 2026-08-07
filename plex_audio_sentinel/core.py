"""Media inspection, collision-safe output naming, and companion-file conversion."""
import hashlib
import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass

VIDEO_EXTENSIONS = (".mkv", ".mp4", ".m4v", ".avi", ".mov", ".webm")
COMPANION_SUFFIX = ".stereo-ac3"
_ENGLISH = {"en", "eng", "english"}
_UNKNOWN = {"und", "undetermined", "unknown", "unk", "none", "null"}


@dataclass
class Summary:
    scanned: int = 0
    new: int = 0
    ignored: int = 0
    converted: int = 0
    skipped: int = 0
    errors: int = 0
    baseline_created: bool = False
    def text(self):
        return (f"Plex Audio Sentinel: scanned {self.scanned}, new {self.new}, "
                f"ignored {self.ignored}, converted {self.converted}, "
                f"skipped {self.skipped}, errors {self.errors}.")


def normalize_path(path):
    """Absolute, normalized path; case-folded on Windows for reliable comparison."""
    normalized = os.path.abspath(os.path.normpath(path))
    return normalized.lower() if os.name == "nt" else normalized


def _language(stream):
    tags = stream.get("tags") or {}
    return str(tags.get("language", stream.get("language", ""))).strip().lower()


def is_english_or_unknown(stream):
    """Keep English and absent/unknown language tags; reject explicit other languages."""
    lang = _language(stream)
    if not lang or lang in _UNKNOWN:
        return True
    return lang in _ENGLISH or lang.startswith("en-") or lang.startswith("en_")


def has_aac(streams):
    """Backward-compatible inspection helper; AAC is not an eligibility criterion."""
    return any(s.get("codec_type") == "audio" and str(s.get("codec_name", "")).lower() == "aac" for s in streams)


def _channels(stream):
    try:
        return int(stream.get("channels", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _bit_rate(stream):
    try:
        return int(stream.get("bit_rate", 0) or 0)
    except (TypeError, ValueError):
        return 0


def is_multichannel(stream):
    codec = str(stream.get("codec_name", "")).lower()
    return _channels(stream) > 2 or codec.startswith("dts")


def eligible_audio(streams):
    return [s for s in streams if s.get("codec_type") == "audio" and is_multichannel(s)]


def selected_audio(streams):
    return [s for s in streams if s.get("codec_type") == "audio" and is_english_or_unknown(s)]


def select_downmix_source(streams):
    """Best English/unknown multichannel/DTS audio stream for the stereo AC-3 downmix.

    Candidates must be both English/unknown-language and multichannel/DTS-
    eligible (DTS stays eligible even when the container reports 2 channels).
    The winner has the most channels; ties break on the higher numeric bit
    rate, then the lowest stream index (stable, deterministic). Explicit
    non-English tracks are never candidates, even when they are the only
    multichannel tracks — such files are skipped.
    """
    candidates = [
        s for s in streams
        if s.get("codec_type") == "audio"
        and is_english_or_unknown(s)
        and is_multichannel(s)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda s: (_channels(s), _bit_rate(s), -int(s.get("index", 0))))


def output_path(path, output_dir=""):
    """Companion name for one source inside the shared output folder.

    Preserves the source basename. Collision-avoiding hash suffixes for
    sources that share a basename are added by build_output_map().
    """
    stem, ext = os.path.splitext(os.path.basename(path))
    name = stem + COMPANION_SUFFIX + ext
    return os.path.join(output_dir, name) if output_dir else name


def _path_key(source, media_root):
    key = source
    if media_root:
        try:
            key = os.path.relpath(source, media_root)
        except ValueError:  # different drive on Windows
            pass
    return key


def build_output_map(sources, output_dir, media_root=None):
    """Deterministic source -> companion map, collision-safe by basename.

    A source whose basename is unique keeps its plain basename (e.g.
    ``Movie.stereo-ac3.mkv``). When two or more sources share a basename, each
    gets a deterministic short hash suffix derived from its path (relative to
    media_root when available), so distinct sources can never map to the same
    output and no existing output is ever overwritten. The mapping is stable
    across runs for the same library layout.
    """
    by_basename = {}
    for source in sources:
        by_basename.setdefault(os.path.basename(source), []).append(source)
    mapping = {}
    for group in by_basename.values():
        if len(group) == 1:
            mapping[normalize_path(group[0])] = output_path(group[0], output_dir)
        else:
            for source in sorted(group):
                digest = hashlib.sha256(
                    _path_key(source, media_root).encode("utf-8", "surrogateescape")
                ).hexdigest()[:8]
                stem, ext = os.path.splitext(os.path.basename(source))
                name = f"{stem}{COMPANION_SUFFIX}-{digest}{ext}"
                mapping[normalize_path(source)] = os.path.join(output_dir, name) if output_dir else name
    return mapping


def destination_for(path, cfg):
    """Companion path for a source, honoring the runner's collision-safe map."""
    mapping = getattr(cfg, "output_names", None)
    if mapping:
        normalized = normalize_path(path)
        if normalized in mapping:
            return mapping[normalized]
    if not (cfg.output_path or "").strip():
        raise ValueError("PLEX_OUTPUT_PATH is required to compute the companion output path")
    return output_path(path, cfg.output_path)


def probe(path, ffprobe="ffprobe", runner=subprocess.run):
    p = runner([ffprobe, "-v", "error", "-show_streams", "-of", "json", path], capture_output=True, text=True, check=True)
    return json.loads(p.stdout).get("streams", [])


def ffmpeg_command(src, dst, streams=None, ffmpeg="ffmpeg"):
    """Build a map preserving video/subtitles and English/unknown audio.

    The selected stream (highest channels, then bit rate, then index) is
    mapped as the first audio output and is the only stream encoded — to
    stereo AC-3. Every English/unknown original audio track is then kept as
    a copy (including the selected one), explicit non-English audio is
    dropped, and video/subtitles are copied. Stream indexes are global
    ffprobe indexes, so this works when non-audio streams are interspersed.
    """
    if streams is None:
        # Compatibility/default shape for callers that only need to inspect command options.
        return [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-map", "0", "-c:v", "copy", "-c:a", "ac3", "-ac", "2", dst]
    source = select_downmix_source(streams)
    if source is None:
        raise ValueError("no English/unknown multichannel audio to downmix")
    keep = [s for s in streams if s.get("codec_type") == "audio" and is_english_or_unknown(s)]
    args = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", src]
    for s in [x for x in streams if x.get("codec_type") == "video"]:
        args += ["-map", f"0:{s['index']}"]
    # Selected stream mapped first among audio, encoded to stereo AC-3.
    args += ["-map", f"0:{source['index']}"]
    for s in keep:
        args += ["-map", f"0:{s['index']}"]
    for s in [x for x in streams if x.get("codec_type") == "subtitle"]:
        args += ["-map", f"0:{s['index']}"]
    args += ["-map_metadata", "0", "-map_chapters", "0", "-c:v", "copy", "-c:s", "copy", "-c:a", "copy", "-c:a:0", "ac3", "-ac:a:0", "2", "-metadata:s:a:0", "language=eng", dst]
    return args


def convert(path, streams, ffmpeg="ffmpeg", runner=subprocess.run, dst=None):
    """Write the companion into the output folder, never beside the original.

    dst defaults to the original same-directory name only for direct API
    compatibility; production calls (core.process) always pass a dst inside
    PLEX_OUTPUT_PATH. The output directory is created if needed, conversion
    writes to a same-directory temporary file renamed into place on success,
    and existing outputs are never overwritten.
    """
    if dst is None:
        dst = output_path(path)
    if os.path.exists(dst):
        return False
    directory = os.path.dirname(dst) or "."
    os.makedirs(directory, exist_ok=True)
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


def discover(path, extensions=VIDEO_EXTENSIONS, exclude_dir=None):
    """Yield source media files under path, never files from the output folder.

    The configured output folder (PLEX_OUTPUT_PATH) is excluded from discovery
    even when it is nested inside the media root, so generated companions are
    never seen as new sources. Companion-named files are excluded as well.
    """
    excluded = normalize_path(exclude_dir) if exclude_dir else None
    for root, dirs, files in os.walk(path):
        abs_root = normalize_path(root)
        if excluded and (abs_root == excluded or abs_root.startswith(excluded + os.sep)):
            dirs[:] = []
            continue
        if excluded:
            def _under_excluded(directory):
                candidate = normalize_path(os.path.join(root, directory))
                return candidate == excluded or candidate.startswith(excluded + os.sep)
            dirs[:] = [d for d in dirs if not _under_excluded(d)]
        for name in sorted(files):
            if name.lower().endswith(tuple(extensions)) and COMPANION_SUFFIX not in os.path.splitext(name)[0]:
                yield os.path.join(root, name)


def process(path, cfg, dry_run=False, runner=subprocess.run, logger=None):
    log = logger or logging.getLogger(__name__)
    try:
        streams = probe(path, cfg.ffprobe, runner)
        if select_downmix_source(streams) is None:
            # No English/unknown multichannel/DTS track: skip safely even if a
            # non-English multichannel track exists.
            return "skipped"
        dst = destination_for(path, cfg)
        if os.path.exists(dst):
            return "skipped"
        if dry_run:
            return "would-convert"
        convert(path, streams, cfg.ffmpeg, runner, dst=dst)
        return "converted"
    except Exception as exc:
        log.error("%s: %s", path, exc)
        return "error"
