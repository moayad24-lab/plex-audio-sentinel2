# Plex Audio Sentinel

A dependency-free Python CLI that scans one local Plex library path, finds videos without an AAC audio stream, and safely converts audio while copying video. It refreshes the configured Plex section and optionally reports to Telegram.

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
PLEX_MEDIA_PATH=/srv/media python -m plex_audio_sentinel scan       # always dry inspection
PLEX_MEDIA_PATH=/srv/media python -m plex_audio_sentinel process --dry-run
PLEX_MEDIA_PATH=/srv/media python -m plex_audio_sentinel process
PLEX_MEDIA_PATH=/srv/media python -m plex_audio_sentinel --config
```
Scan discovers common video extensions recursively. ffprobe JSON is required. A file with any AAC audio stream is skipped. Processing writes a same-directory temporary file, waits for successful FFmpeg exit, makes `<file>.bak`, then atomically replaces the original. Failed conversions leave the original untouched. Ensure sufficient free disk and backup storage; reruns skip AAC outputs.

Exit status is nonzero when probing, conversion, Plex refresh, or Telegram reporting fails. Secrets are never included in logs or summary output. Limitations: one path/section per invocation, no Plex library listing, no scheduling, and conversion maps all streams and re-encodes all audio streams to AAC.
