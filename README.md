# Plex Audio Sentinel

A dependency-free Python CLI that scans one local Plex library path and writes safe companion files for videos containing multichannel audio. Each companion adds a stereo AC-3 track first, retains the original English/unknown-language audio tracks, removes explicitly non-English audio, and copies video/subtitles where feasible. Originals are never modified.

The tool is **baseline-safe**: the first real run records every discovered source file into a durable state file and converts *nothing*. Later runs only process media files that were **added after the baseline**; pre-existing library files are never touched.

## Requirements

Python 3.9+, FFmpeg and ffprobe in PATH (or configure commands), and write permission in each media directory (for companions and, by default, the state file). Plex token is the value from Plex Web's authenticated API requests (do not commit it). Create a Telegram bot with BotFather, start a chat with it, and use the bot token and numeric chat ID.

## Setup

```sh
cd /home/team/shared/plex-audio-sentinel
cp .env.example .env                 # export values; CLI does not parse .env automatically
set -a; . ./.env; set +a
python3 -m unittest discover -s tests -v
python3 -m plex_audio_sentinel --help
```

## Configuration

`PLEX_MEDIA_PATH` is the authoritative local scan root; Plex is used for section refresh, not file discovery. All variables are read from the environment:

| Variable | Required | Meaning |
| --- | --- | --- |
| `PLEX_MEDIA_PATH` | yes | Local media directory to scan recursively |
| `PLEX_URL`, `PLEX_SECTION` | for refresh | Plex server URL and library section key; needed only when conversions happen |
| `PLEX_TOKEN` | optional | Plex API token |
| `FFMPEG`, `FFPROBE` | no | Binaries to use (default `ffmpeg` / `ffprobe`) |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | together | Telegram completion report (both or neither) |
| `PLEX_STATE_FILE` | no | Baseline state file path. **Default: `<PLEX_MEDIA_PATH>/.plex-audio-sentinel-state.json`** — a hidden JSON file inside the media root. Set it explicitly when the media root is read-only or state must live elsewhere (e.g. `PLEX_STATE_FILE=/var/lib/plex-audio-sentinel.json`). |

## Usage

```sh
PLEX_MEDIA_PATH=/srv/media python3 -m plex_audio_sentinel scan       # dry inspection
PLEX_MEDIA_PATH=/srv/media python3 -m plex_audio_sentinel process --dry-run
PLEX_MEDIA_PATH=/srv/media python3 -m plex_audio_sentinel process
PLEX_MEDIA_PATH=/srv/media python3 -m plex_audio_sentinel --config
```

- `scan` (and `process --dry-run`) never writes state or media. Before a baseline exists it reports that the next real run will record a baseline; afterwards it probes only new files and reports what would be converted.
- The first real `process` run records **all** discovered source paths into the state file and performs zero conversions (this is the safe baseline).
- Later `process` runs convert only paths not present in the state. Summary output reports `scanned`, `new`, `ignored` (already seen), `converted`, `skipped`, and `errors` counts.

## Baseline state file

The state file is JSON: `{"version": 1, "seen": ["/abs/path/1.mkv", ...]}`.

- **Never processed again**: a path once recorded (baseline, converted, or skipped as ineligible) is ignored on all later runs.
- **Retry-safe**: a path that fails conversion is *not* recorded, so it is retried on the next run.
- **Atomic writes**: state is written to a temporary file in the same directory and moved into place with `os.replace`, so a crash can never leave a half-written state file. No temporary files are left behind.
- **Malformed state aborts the run** with a clear error instead of silently treating existing media as new. Fix the file, or delete it and re-run to rebuild the baseline.
- Generated `.stereo-ac3` companions are never tracked as source media, and the state file itself is never discovered (only video extensions are scanned).
- Dry runs never create or modify the state file.

### Reset / rebuild the baseline

Deleting (or moving) the state file resets the baseline. **This is always safe**: the first run after deletion only re-records every currently discovered file and converts nothing, exactly like the original first run. Only files added *after* that rebuild run are ever processed.

```sh
rm /srv/media/.plex-audio-sentinel-state.json   # or your PLEX_STATE_FILE
PLEX_MEDIA_PATH=/srv/media python3 -m plex_audio_sentinel process   # rebuilds baseline, 0 conversions
```

If you want a *replacement* companion for an already-seen file, delete that file's `Movie.stereo-ac3.mkv` **and** remove its entry from the state file, or rebuild the whole baseline as above; the tool has no overwrite option by design.

## Operational safety notes

- **Originals are never modified.** For `Movie.mkv`, processing writes `Movie.stereo-ac3.mkv` in the same directory; `Movie.mkv` stays byte-for-byte unchanged.
- **Atomic conversion.** FFmpeg writes to a same-directory temporary file (`.plex-audio-*`) which is renamed into place only on success; failed conversions remove the temporary file.
- **Eligibility.** A file is eligible when an audio stream has more than two channels (including 5.1/7.1/8.1) or its codec is DTS. Audio selection keeps language tags `eng`, `en`, `English`, and missing/unknown/undetermined (`und`) and excludes explicitly non-English tracks. Subtitle and video streams are not language-filtered.
- **Existing companions are skipped** (no overwrite option); conversion errors surface in the summary and the file stays unseen so it is retried next run.
- **Plex refresh** is triggered after runs that converted files; if `PLEX_URL`/`PLEX_SECTION` are not configured, the run reports a refresh error (and exits nonzero). Telegram reports are sent whenever configured.
- **Exit status** is nonzero when probing, conversion, state handling, Plex refresh, or Telegram reporting fails. Secrets are never included in logs or summary output.

Limitations: one path/section per invocation, no Plex library listing, no scheduling, and FFmpeg/container compatibility depends on the input format.
