# Plex Audio Sentinel

A dependency-free Python CLI that scans one local Plex library path and writes safe companion files for videos containing multichannel audio. Each companion adds a stereo AC-3 track first, retains the original English/unknown-language audio tracks, removes explicitly non-English audio, and copies video/subtitles where feasible. Originals are never modified. Plex refresh/report refer to the generated companions via the conversion summary.

## Requirements
Python 3.9+, FFmpeg and ffprobe in PATH (or configure commands), and write permission in each media directory. Plex token is the value from Plex Web's authenticated API requests (do not commit it). Create a Telegram bot with BotFather, start a chat with it, and use the bot token and numeric chat ID.

## Setup
```sh
cd /home/team/shared/plex-audio-sentinel
cp .env.example .env                 # export values; CLI does not parse .env automatically
set -a; . ./.env; set +a
python -m unittest discover -s tests -v
python -m plex_audio_sentinel --help
```

`PLEX_MEDIA_PATH` is the authoritative local scan root; Plex is used for section refresh, not file discovery. `PLEX_URL` and `PLEX_SECTION` are needed for refresh after processing. Telegram variables are optional and must be supplied together.

## Usage
```sh
PLEX_MEDIA_PATH=/srv/media python -m plex_audio_sentinel scan       # dry inspection
PLEX_MEDIA_PATH=/srv/media python -m plex_audio_sentinel process --dry-run
PLEX_MEDIA_PATH=/srv/media python -m plex_audio_sentinel process
PLEX_MEDIA_PATH=/srv/media python -m plex_audio_sentinel --config
```

Scan discovers common video extensions recursively and uses ffprobe JSON. A file is eligible when an audio stream has more than two channels (including 5.1/7.1/8.1) or its codec is DTS. Audio selection keeps language tags `eng`, `en`, `English`, and missing/unknown/undetermined (`und`) and excludes explicitly non-English tracks. Subtitle and video streams are not language-filtered.

For `Movie.mkv`, processing writes `Movie.stereo-ac3.mkv` in the same directory. FFmpeg first maps a newly encoded 2-channel AC-3 downmix, then maps the retained original English/unknown audio tracks; video and subtitles are stream-copied. Conversion uses a same-directory temporary file and atomic rename, leaving `Movie.mkv` byte-for-byte unchanged. Failed conversions remove the temporary file. Existing companions are skipped safely (there is no overwrite option); remove the companion manually if re-generation is desired. Dry-run performs probing and reports what would be generated without writing anything.

Exit status is nonzero when probing, conversion, Plex refresh, or Telegram reporting fails. Secrets are never included in logs or summary output. Limitations: one path/section per invocation, no Plex library listing, no scheduling, and FFmpeg/container compatibility depends on the input format.
