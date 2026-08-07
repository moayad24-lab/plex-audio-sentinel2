# Plex Audio Sentinel

A dependency-free Python CLI that scans one local Plex library path and writes safe companion files for videos containing multichannel audio. Each companion adds a stereo AC-3 track first, retains the original English/unknown-language audio tracks, removes explicitly non-English audio, and copies video/subtitles where feasible. Originals are never modified and **all generated companions are written into one configurable output folder** (`PLEX_OUTPUT_PATH`), never beside the originals.

The tool is **baseline-safe**: the first real run records every discovered source file into a durable state file and converts *nothing*. Later runs only process media files that were **added after the baseline**; pre-existing library files are never touched.

## Requirements

Python 3.9+, FFmpeg and ffprobe in PATH (or configure commands), write permission in the **output folder** (`PLEX_OUTPUT_PATH`), and — by default — write permission in the media root for the state file. Plex token is the value from Plex Web's authenticated API requests (do not commit it). Create a Telegram bot with BotFather, start a chat with it, and use the bot token and numeric chat ID.

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
| `PLEX_OUTPUT_PATH` | yes | **Single folder where all generated companion files are written.** Companions are never written beside the originals. The folder is excluded from source discovery even when nested under `PLEX_MEDIA_PATH`. Example used by the current Windows test client: `PLEX_OUTPUT_PATH=E:\Plex Media Server\Converted`. Must not be the media root or one of its parent directories. |
| `PLEX_URL`, `PLEX_SECTION` | for refresh | Plex server URL and library section key; needed only when conversions happen |
| `PLEX_TOKEN` | optional | Plex API token |
| `FFMPEG`, `FFPROBE` | no | Binaries to use (default `ffmpeg` / `ffprobe`) |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | together | Telegram completion report (both or neither) |
| `PLEX_STATE_FILE` | no | Baseline state file path. **Default: `<PLEX_MEDIA_PATH>/.plex-audio-sentinel-state.json`** — a hidden JSON file inside the media root. Set it explicitly when the media root is read-only or state must live elsewhere (e.g. `PLEX_STATE_FILE=/var/lib/plex-audio-sentinel.json`). |

## Usage

```sh
PLEX_MEDIA_PATH=/srv/media PLEX_OUTPUT_PATH=/srv/converted python3 -m plex_audio_sentinel scan       # dry inspection
PLEX_MEDIA_PATH=/srv/media PLEX_OUTPUT_PATH=/srv/converted python3 -m plex_audio_sentinel process --dry-run
PLEX_MEDIA_PATH=/srv/media PLEX_OUTPUT_PATH=/srv/converted python3 -m plex_audio_sentinel process
PLEX_MEDIA_PATH=/srv/media PLEX_OUTPUT_PATH=/srv/converted python3 -m plex_audio_sentinel --config
```

On the Windows test client this becomes, for example:

```bat
set PLEX_MEDIA_PATH=E:\Plex Media Server\Movies
set PLEX_OUTPUT_PATH=E:\Plex Media Server\Converted
python -m plex_audio_sentinel process
```

- `scan` (and `process --dry-run`) never writes state or media. Before a baseline exists it reports that the next real run will record a baseline; afterwards it probes only new files and reports what would be converted.
- The first real `process` run records **all** discovered source paths into the state file and performs zero conversions (this is the safe baseline).
- Later `process` runs convert only paths not present in the state. Summary output reports `scanned`, `new`, `ignored` (already seen), `converted`, `skipped`, and `errors` counts.

## Output folder and companion naming

- **One folder.** Every companion is written into `PLEX_OUTPUT_PATH` (created on demand); nothing is ever written next to an original, and originals remain byte-for-byte unchanged.
- **Basename preserved.** For `Movie.mkv` the companion is named `Movie.stereo-ac3.mkv` inside the output folder.
- **Collision-safe.** If two or more sources share a basename (e.g. `A/Movie.mkv` and `B/Movie.mkv`), each gets a deterministic 8-character hash suffix derived from its path relative to the media root, e.g. `Movie.stereo-ac3-1a2b3c4d.mkv`. The same source always maps to the same name across runs, and two different sources never map to the same output.
- **No overwrites.** If the computed companion name already exists in the output folder, the source is skipped (by design, there is no overwrite option). To regenerate a companion, delete the existing file and remove the source's entry from the state file (or rebuild the baseline).
- **Excluded from discovery.** The output folder is never scanned as a source — including when it is nested under the media root — so generated companions are never re-processed, and only real source media paths are ever recorded in the baseline state.

## Audio selection

For each source with eligible audio, the tool picks the **best English/unknown multichannel track** for the stereo AC-3 downmix:

1. **Most channels** wins (5.1/7.1/8.1 and so on).
2. Ties break on **higher numeric bit rate**.
3. Remaining ties break on the **lowest stream index** (stable, deterministic).

Eligibility and language rules:

- A track is eligible when it has **more than two channels** or its codec is **DTS** — DTS stays eligible even when the container reports 2 channels.
- Only **English or unknown-language** tracks are candidates: `eng`, `en`, `English`, missing/undetermined (`und`), etc. **Explicit non-English tracks are never selected**, even when they are the only multichannel tracks — if no English/unknown eligible multichannel track exists, the file is skipped safely.
- The ffmpeg command maps the **selected stream first** (the new AC-3 stereo track is the first audio stream) and encodes **only it** to 2-channel AC-3. All original English/unknown audio tracks are kept afterwards as copies; explicit non-English audio is dropped; video and subtitle streams are copied.

## Baseline state file

The state file is JSON: `{"version": 1, "seen": ["/abs/path/1.mkv", ...]}`.

- **Only source media paths are tracked.** Generated companions in the output folder are never considered new sources and never appear in the state.
- **Never processed again**: a path once recorded (baseline, converted, or skipped as ineligible) is ignored on all later runs.
- **Retry-safe**: a path that fails conversion is *not* recorded, so it is retried on the next run.
- **Atomic writes**: state is written to a temporary file in the same directory and moved into place with `os.replace`, so a crash can never leave a half-written state file. No temporary files are left behind.
- **Malformed state aborts the run** with a clear error instead of silently treating existing media as new. Fix the file, or delete it and re-run to rebuild the baseline.
- Dry runs never create or modify the state file.

### Reset / rebuild the baseline

Deleting (or moving) the state file resets the baseline. **This is always safe**: the first run after deletion only re-records every currently discovered file and converts nothing, exactly like the original first run. Only files added *after* that rebuild run are ever processed.

```sh
rm /srv/media/.plex-audio-sentinel-state.json   # or your PLEX_STATE_FILE
PLEX_MEDIA_PATH=/srv/media PLEX_OUTPUT_PATH=/srv/converted python3 -m plex_audio_sentinel process   # rebuilds baseline, 0 conversions
```

If you want a *replacement* companion for an already-seen file, delete that file's `Movie.stereo-ac3.mkv` in the output folder **and** remove its entry from the state file, or rebuild the whole baseline as above; the tool has no overwrite option by design.

## Plex library visibility

Plex discovers media by folder, not by tracking files individually. For the generated companions to appear in Plex:

1. **Add the output folder to a Plex library.** Either add `PLEX_OUTPUT_PATH` as an extra folder in an existing Movies/TV library, or create a dedicated library pointing at it. Until the folder belongs to a library, Plex will not list the companion files.
2. **Refresh the library that contains the output folder.** The tool triggers a refresh of the configured `PLEX_SECTION` after runs that converted files — make sure that section key refers to the library that actually contains the companions (if the output folder is its own library, point `PLEX_SECTION` at that library; if the companion files appear as duplicates of existing entries, Plex handles them as separate versions/items once scanned).
3. Because each companion carries its own complete video+audio track set, a player that prefers AC-3 or has no DTS decoder can direct-play the companion instead of the original.

## Operational safety notes

- **Originals are never modified.** For `Movie.mkv`, processing writes `Movie.stereo-ac3.mkv` in `PLEX_OUTPUT_PATH`; `Movie.mkv` stays byte-for-byte unchanged.
- **Atomic conversion.** FFmpeg writes to a temporary file (`.plex-audio-*`) inside the output folder which is renamed into place only on success; failed conversions remove the temporary file.
- **Eligibility.** A file is eligible when an audio stream has more than two channels (including 5.1/7.1/8.1) or its codec is DTS. Audio selection keeps language tags `eng`, `en`, `English`, and missing/unknown/undetermined (`und`) and excludes explicitly non-English tracks. Subtitle and video streams are not language-filtered.
- **Existing companions are skipped** (no overwrite option); conversion errors surface in the summary and the file stays unseen so it is retried next run.
- **Plex refresh** is triggered after runs that converted files; if `PLEX_URL`/`PLEX_SECTION` are not configured, the run reports a refresh error (and exits nonzero). Telegram reports are sent whenever configured.
- **Exit status** is nonzero when probing, conversion, state handling, Plex refresh, or Telegram reporting fails. Secrets are never included in logs or summary output.

Limitations: one path/section per invocation, no Plex library listing, no scheduling, and FFmpeg/container compatibility depends on the input format.
