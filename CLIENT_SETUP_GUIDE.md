# Plex Audio Sentinel — Windows Client Setup Guide

This guide installs and runs Plex Audio Sentinel against the client media source **`G:\`** and writes generated companions to **`C:\Users\Salah\Downloads\1. fixed audio`**. It is intentionally copy/paste friendly. Run PowerShell commands in a normal PowerShell window unless noted.

> **Important:** Plex Audio Sentinel runs on the computer that can read the media files. Having access to a shared Plex server or Plex account does **not** grant this computer filesystem access to `G:\` or to the output folder. Confirm that Windows Explorer can open `G:\` and that your Windows account can create a test file in the output folder.

## 1. Install prerequisites

### Windows PowerShell basics

- Open **Start**, type **PowerShell**, and open Windows PowerShell (or PowerShell 7).
- Paste one command at a time and press Enter. A path containing spaces must be quoted, for example:

```powershell
Set-Location "C:\Users\Salah\Downloads\1. fixed audio"
Get-ChildItem "G:\" | Select-Object -First 5
```

- `Get-Location` shows the current folder; `Set-Location "C:\path with spaces"` changes it; `cd` is an alias for `Set-Location`.
- To set a value for the current PowerShell window, use `$env:NAME = "value"`. Do not put secrets in a script committed to GitHub.

### Git for Windows

Install Git from the official download: <https://git-scm.com/download/win>. Accept the option to add Git to the command-line PATH (the installer commonly calls this **Git from the command line and also from 3rd-party software**). Close and reopen PowerShell, then verify:

```powershell
git --version
```

### Python 3

Install Python 3 for Windows from <https://www.python.org/downloads/windows/>. During setup, check **Add python.exe to PATH**. Close and reopen PowerShell, then verify either launcher form:

```powershell
py --version
python --version
```

Python 3.9 or newer is required. If `python` opens the Microsoft Store or is not found, use `py` in the commands below, or disable the Windows **App execution aliases** for Python and reinstall with PATH enabled.

### FFmpeg and ffprobe

Install FFmpeg using one of these reliable options:

1. Download a current Windows **essentials** build from the links provided by <https://ffmpeg.org/download.html> (Windows builds are linked there), extract it, and add its `bin` folder—containing `ffmpeg.exe` and `ffprobe.exe`—to the system or user PATH.
2. If `winget` is available, install a reputable FFmpeg package, then reopen PowerShell:

```powershell
winget search FFmpeg
winget install --id Gyan.FFmpeg.Shared
```

If that package ID is unavailable, use the official FFmpeg download page and add its `bin` directory to PATH manually. Verify both programs before continuing:

```powershell
ffmpeg -version
ffprobe -version
Get-Command ffmpeg
Get-Command ffprobe
```

Seeing a version and a path for both commands confirms PATH is correct. If FFmpeg is installed in a nonstandard folder, set `FFMPEG` and `FFPROBE` to the full quoted executable paths instead of changing PATH (see Configuration).

## 2. Clone the project

Choose a working folder, then clone the published repository:

```powershell
Set-Location "$HOME\Downloads"
git clone https://github.com/moayad24-lab/plex-audio-sentinel2.git
Set-Location "$HOME\Downloads\plex-audio-sentinel2"
git status
```

The project directory is now the folder shown by `Get-Location`. Keep PowerShell in this directory for the remaining commands. The repository's `README.md` is the technical reference and support information.

## 3. Run the 45 tests

No third-party Python package is required. From the project directory:

```powershell
py -m unittest discover -s tests -v
```

If `py` is unavailable, use:

```powershell
python -m unittest discover -s tests -v
```

The test run should finish successfully with **45 tests** and `OK`. Do not continue with a failed test run until the reported error is understood.

## 4. Configure the exact client paths

Set the required values in the current PowerShell window:

```powershell
$env:PLEX_MEDIA_PATH = "G:\"
$env:PLEX_OUTPUT_PATH = "C:\Users\Salah\Downloads\1. fixed audio"
```

The quotes are important: they protect the spaces in `1. fixed audio`. The quotes are PowerShell syntax and are not part of the path value. The output folder may be created by the application, but the Windows account running it must have write permission there. Confirm configuration without scanning or writing media:

```powershell
py -m plex_audio_sentinel --config
```

By default the state file is `G:\.plex-audio-sentinel-state.json`. If the root is read-only, choose a writable location explicitly (for example):

```powershell
$env:PLEX_STATE_FILE = "$HOME\Downloads\plex-audio-sentinel-state.json"
```

Optional FFmpeg overrides (only needed when the executables are not in PATH):

```powershell
$env:FFMPEG = "C:\path\to\ffmpeg.exe"
$env:FFPROBE = "C:\path\to\ffprobe.exe"
```

These environment values last only for the current PowerShell window. Re-run them after opening a new window. For repeatable local setup, use a private, untracked PowerShell script; never commit tokens or passwords.

## 5. Optional Plex refresh configuration

Conversions can complete without Plex refresh settings, but a Plex refresh is required for the new files to become visible automatically. Set these only when you have the correct local Plex server details:

```powershell
$env:PLEX_URL = "http://your-plex-server:32400"
$env:PLEX_TOKEN = "PASTE_YOUR_TOKEN_ONLY_IN_THIS_LOCAL_WINDOW"
$env:PLEX_SECTION = "1"
```

`PLEX_SECTION` is the numeric library section ID, not the library name. Find it safely using an authenticated request from a machine that can reach Plex:

1. In Plex Web, open the library and note its name.
2. Open `http://your-plex-server:32400/library/sections` in a browser only if Plex Web has already authenticated that browser, or use a local authenticated API tool. The XML lists each library's `key` (the section ID) and `title`.
3. Match the desired title and use its `key`, such as `1`.

Find the token safely from Plex Web's own authenticated network requests (browser developer tools → Network, inspect a Plex API request and its `X-Plex-Token`/`X-Plex-Token` query value), or from your existing Plex configuration documentation. Do not post the token in GitHub, screenshots, chat, logs, or this guide. If the Plex server is on another computer, use its reachable LAN URL; `localhost` refers to the computer running this command, not necessarily the Plex host.

## 6. Optional Telegram completion report

To receive a concise completion report, create a bot through Telegram's verified **BotFather**, send the bot a message from the intended chat, and obtain the numeric chat ID through your private bot/API workflow. Then set both values locally:

```powershell
$env:TELEGRAM_BOT_TOKEN = "PASTE_BOT_TOKEN_LOCALLY"
$env:TELEGRAM_CHAT_ID = "PASTE_NUMERIC_CHAT_ID_LOCALLY"
```

Both values must be set together, or both left empty. Never commit them or include them in support screenshots. Telegram is optional; it does not replace checking the command summary.

## 7. Inspect safely before processing

A read-only scan never writes media or state:

```powershell
py -m plex_audio_sentinel scan
```

A process dry run is also read-only:

```powershell
py -m plex_audio_sentinel process --dry-run
```

Dry-run output reports discovered files and what would be eligible. Before a baseline exists it says that the next real run will establish a baseline; it does not preview conversions for those existing files because they are intentionally protected by baseline semantics. Probe/conversion errors are reported and do not mark a file as processed.

## 8. First real run: establish the safe baseline

Run this only after reviewing the configuration and dry-run results:

```powershell
py -m plex_audio_sentinel process
```

The **first real run converts zero files**. It records every currently discovered source under `G:\` in the state file, protecting existing `G:\` files from modification and from later automatic processing. This is expected, not a failure. Originals remain byte-for-byte unchanged.

To test the workflow, add one or more new episode/video files under `G:\` after the baseline run. Then inspect them:

```powershell
py -m plex_audio_sentinel scan
py -m plex_audio_sentinel process --dry-run
```

Only files added after the baseline are candidates. If the dry run looks correct, perform real processing:

```powershell
py -m plex_audio_sentinel process
```

The generated result is a **converted video container**, not an audio-only file. It is written only to `C:\Users\Salah\Downloads\1. fixed audio`, never beside the source. FFmpeg uses a temporary file and atomic rename, and existing output files are not overwritten.

### What gets converted and what is retained

- Eligible source audio is English or unknown-language audio with more than two channels, or DTS (DTS remains eligible even if reported as two channels).
- The best eligible track is selected by most channels, then highest numeric bitrate, then lowest stream index for a stable tie-break.
- The new stereo AC-3 track is placed first. Original English and unknown-language audio tracks are retained as copies.
- Explicitly non-English audio tracks are removed from the generated companion. If no eligible English/unknown track exists, the source is skipped safely.
- Video and subtitle streams are copied where supported. The source file is never overwritten or deleted.
- If source basenames collide, the output name receives a deterministic 8-character path-hash suffix so different sources cannot overwrite one another.

### Make output visible in Plex

Plex must scan the output folder. Add `C:\Users\Salah\Downloads\1. fixed audio` as an additional folder in the relevant Plex library, or create a dedicated library for it. Set `PLEX_SECTION` to the section that contains that folder. After a successful conversion, the tool requests a refresh of that section. If the folder is not part of that library, Plex cannot list the generated containers.

## 9. State file and reset/rebuild

The default state file is `G:\.plex-audio-sentinel-state.json` (or the path in `PLEX_STATE_FILE`). It records source paths already seen. Dry runs and scans do not create or change it. A failed conversion is not marked and will be retried; malformed state aborts safely rather than treating all media as new.

To reset, first close any run, then move or delete the state file. For the default exact client location:

```powershell
Remove-Item -LiteralPath "G:\.plex-audio-sentinel-state.json"
py -m plex_audio_sentinel process
```

That command rebuilds the baseline and again converts **zero** files. Resetting is therefore safe, but it does not process old files. To replace one already-seen companion, delete its output and remove that source entry from state (or rebuild the entire baseline); there is deliberately no overwrite mode. Back up the state file before manual edits. If state is malformed, restore a valid backup or remove it and run the rebuild command.

## 10. Routine updates

Before an update, finish or stop any processing run. From the project directory:

```powershell
git pull --ff-only origin master
py -m unittest discover -s tests -v
py -m plex_audio_sentinel --config
```

Re-enter the environment variables if this is a new PowerShell window. Do not run `git clean` in a media folder, and do not store secrets in the repository.

## 11. Troubleshooting

- **`py` or `python` is not recognized:** reinstall Python 3 with **Add python.exe to PATH**, reopen PowerShell, and verify `py --version` or `python --version`. Use whichever launcher works.
- **`ffmpeg`/`ffprobe` is not recognized:** verify the extracted `bin` directory is on PATH, reopen PowerShell, and run `Get-Command ffmpeg` and `Get-Command ffprobe`. Or set `FFMPEG`/`FFPROBE` to quoted full `.exe` paths.
- **Cannot access `G:\`:** verify the drive is mounted and readable in Explorer under the same Windows account. A mapped drive may not be available to another account or scheduled process; use the exact accessible drive/path.
- **Output path validation fails:** ensure `PLEX_OUTPUT_PATH` is exactly `C:\Users\Salah\Downloads\1. fixed audio`, is not the source root or a parent of `G:\`, and is not the same location as the source. Create it and grant the running account write permission if necessary.
- **Plex refresh failed:** verify `PLEX_URL` is reachable from this computer, `PLEX_TOKEN` is valid and private, and `PLEX_SECTION` is the numeric ID of the library containing the output folder. The media conversion itself and source safety are separate from refresh; retry after correcting settings.
- **Malformed state error:** do not edit blindly. Restore a backup, or remove `G:\.plex-audio-sentinel-state.json` (or the configured state path) and run one real process command to rebuild the safe baseline.
- **Windows access denied / permission errors:** run PowerShell as the account that owns the media access, check folder Security permissions, ensure the output folder is writable, and check that antivirus or another process is not locking a temporary/output file. Avoid running as Administrator unless your organization's policy requires it.
- **No files appear in Plex:** confirm the output folder is included in the correct Plex library and refresh that library. Check the command summary and output directory in Explorer.

## Client safety checklist

- [ ] `G:\` opens in Explorer and is the intended source.
- [ ] `C:\Users\Salah\Downloads\1. fixed audio` is the intended output and is writable.
- [ ] Git, Python 3, FFmpeg, and ffprobe version checks succeed.
- [ ] All 45 tests finish with `OK`.
- [ ] `scan` and `process --dry-run` were reviewed before processing.
- [ ] The first real run completed with zero conversions (baseline established).
- [ ] Plex output folder membership and section ID were verified.
- [ ] Plex and Telegram tokens, if used, remain local and were not committed or shared.
- [ ] Important originals and the state file are backed up according to the household/admin backup policy.

## Support and technical reference

For command details, configuration names, limitations, and implementation behavior, see the repository README: <https://github.com/moayad24-lab/plex-audio-sentinel2/blob/master/README.md>. When requesting help, include the non-secret command summary and error text, but redact Plex and Telegram tokens and any private network details.
