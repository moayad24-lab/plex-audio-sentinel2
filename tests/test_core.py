import json
import os
import tempfile
import unittest
from types import SimpleNamespace

from plex_audio_sentinel.config import Config
from plex_audio_sentinel.core import (
    COMPANION_SUFFIX,
    convert,
    discover,
    eligible_audio,
    ffmpeg_command,
    is_english_or_unknown,
    is_multichannel,
    output_path,
    process,
    selected_audio,
)


def audio(index, codec="ac3", channels=2, language=None):
    stream = {"index": index, "codec_type": "audio", "codec_name": codec, "channels": channels}
    if language is not None:
        stream["tags"] = {"language": language}
    return stream


class CoreTests(unittest.TestCase):
    def test_multichannel_and_dts_eligibility(self):
        self.assertTrue(is_multichannel(audio(0, channels=6)))
        self.assertTrue(is_multichannel(audio(1, codec="dts", channels=2)))
        self.assertFalse(is_multichannel(audio(2, codec="ac3", channels=2)))
        streams = [audio(0, channels=6), audio(1, codec="dts", channels=2), audio(2)]
        self.assertEqual([s["index"] for s in eligible_audio(streams)], [0, 1])

    def test_language_retention_and_explicit_non_english_filtering(self):
        languages = ["eng", "en", "English", None, "und", "undetermined", "unknown", "fra"]
        streams = [audio(i, language=language) for i, language in enumerate(languages)]
        self.assertEqual(
            [s["index"] for s in selected_audio(streams)], list(range(7))
        )
        self.assertFalse(is_english_or_unknown(audio(10, language="spa")))
        self.assertFalse(is_english_or_unknown(audio(11, language="de")))
        self.assertTrue(is_english_or_unknown(audio(12)))

    def test_companion_naming_and_map_order(self):
        self.assertEqual(output_path("Movie.mkv"), "Movie.stereo-ac3.mkv")
        streams = [
            {"index": 0, "codec_type": "video"},
            audio(1, codec="dts", channels=2, language="fra"),
            audio(2, codec="ac3", channels=6, language="eng"),
            audio(3, codec="aac", channels=2),
            {"index": 4, "codec_type": "subtitle", "codec_name": "subrip"},
        ]
        command = ffmpeg_command("Movie.mkv", "Movie.stereo-ac3.mkv", streams)
        maps = [command[i + 1] for i, value in enumerate(command) if value == "-map"]
        self.assertEqual(maps, ["0:0", "0:1", "0:2", "0:3", "0:4"])
        # The first audio output is the generated stereo AC-3; retained originals follow.
        self.assertEqual(command[command.index("-c:a:0") + 1], "ac3")
        self.assertEqual(command[command.index("-ac:a:0") + 1], "2")
        self.assertEqual(command[-1], "Movie.stereo-ac3.mkv")

    def test_video_and_subtitle_mapping_is_stream_copy(self):
        streams = [
            {"index": 0, "codec_type": "subtitle"},
            {"index": 1, "codec_type": "video"},
            audio(2, channels=6, language="eng"),
            {"index": 3, "codec_type": "subtitle"},
        ]
        command = ffmpeg_command("in.mkv", "out.mkv", streams)
        self.assertEqual(
            [command[i + 1] for i, value in enumerate(command) if value == "-map"],
            ["0:1", "0:2", "0:2", "0:0", "0:3"],
        )
        self.assertEqual(command[command.index("-c:v") + 1], "copy")
        self.assertEqual(command[command.index("-c:s") + 1], "copy")

    def test_existing_companion_is_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            source = os.path.join(directory, "Movie.mkv")
            companion = output_path(source)
            with open(source, "wb") as handle:
                handle.write(b"original")
            with open(companion, "wb") as handle:
                handle.write(b"existing")
            calls = []

            def runner(command, **kwargs):
                calls.append(command)
                return SimpleNamespace(stdout=json.dumps({"streams": [{"codec_type": "audio", "codec_name": "ac3", "channels": 6, "index": 0, "tags": {"language": "eng"}}]}))

            result = process(source, Config(directory), runner=runner)
            self.assertEqual(result, "skipped")
            self.assertEqual(len(calls), 1)  # probe only; never overwrite the companion
            with open(companion, "rb") as handle:
                self.assertEqual(handle.read(), b"existing")

    def test_conversion_preserves_original_and_uses_atomic_temp_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = os.path.join(directory, "Movie.mkv")
            with open(source, "wb") as handle:
                handle.write(b"original bytes")
            streams = [audio(0, channels=6, language="eng")]
            calls = []

            def runner(command, **kwargs):
                calls.append(command)
                with open(command[-1], "wb") as handle:
                    handle.write(b"converted companion")
                return SimpleNamespace(stdout="")

            self.assertTrue(convert(source, streams, runner=runner))
            with open(source, "rb") as handle:
                self.assertEqual(handle.read(), b"original bytes")
            with open(output_path(source), "rb") as handle:
                self.assertEqual(handle.read(), b"converted companion")
            self.assertEqual(len(calls), 1)
            self.assertFalse(any(name.startswith(".plex-audio-") for name in os.listdir(directory)))

    def test_discover_excludes_companions(self):
        with tempfile.TemporaryDirectory() as directory:
            open(os.path.join(directory, "x.MKV"), "w").close()
            open(os.path.join(directory, "x" + COMPANION_SUFFIX + ".mkv"), "w").close()
            open(os.path.join(directory, "x.txt"), "w").close()
            self.assertEqual(len(list(discover(directory))), 1)


if __name__ == "__main__":
    unittest.main()
