import json
import os
import tempfile
import unittest
from types import SimpleNamespace

from plex_audio_sentinel.config import Config
from plex_audio_sentinel.core import (
    COMPANION_SUFFIX,
    build_output_map,
    convert,
    destination_for,
    discover,
    eligible_audio,
    ffmpeg_command,
    is_english_or_unknown,
    is_multichannel,
    output_path,
    process,
    select_downmix_source,
    selected_audio,
)


def audio(index, codec="ac3", channels=2, language=None, bit_rate=None):
    stream = {"index": index, "codec_type": "audio", "codec_name": codec, "channels": channels}
    if language is not None:
        stream["tags"] = {"language": language}
    if bit_rate is not None:
        stream["bit_rate"] = str(bit_rate)
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

    def test_downmix_source_prefers_more_channels(self):
        streams = [
            audio(0, codec="dts", channels=6, language="eng"),
            audio(1, codec="ac3", channels=8, language="eng"),
            audio(2, codec="ac3", channels=2, language="eng"),
        ]
        self.assertEqual(select_downmix_source(streams)["index"], 1)

    def test_downmix_source_ties_break_on_bitrate_then_index(self):
        streams = [
            audio(0, codec="dts", channels=6, language="eng", bit_rate="768000"),
            audio(1, codec="ac3", channels=6, language="eng", bit_rate="640000"),
            audio(2, codec="ac3", channels=6, language="eng", bit_rate="1536000"),
        ]
        self.assertEqual(select_downmix_source(streams)["index"], 2)
        same = [audio(i, codec="ac3", channels=6, language="eng") for i in (3, 4)]
        self.assertEqual(select_downmix_source(same)["index"], 3)  # stable lowest index

    def test_downmix_source_never_selects_explicit_non_english(self):
        streams = [
            audio(0, codec="dts", channels=8, language="spa"),
            audio(1, codec="ac3", channels=6, language="eng"),
        ]
        self.assertEqual(select_downmix_source(streams)["index"], 1)
        only_non_english = [audio(0, codec="dts", channels=6, language="fra")]
        self.assertIsNone(select_downmix_source(only_non_english))

    def test_dts_eligibility_even_when_reported_channels_low(self):
        stream = audio(0, codec="dts", channels=2, language="eng")
        self.assertTrue(is_multichannel(stream))
        self.assertEqual(select_downmix_source([stream])["index"], 0)

    def test_process_skips_safely_when_only_non_english_multichannel(self):
        with tempfile.TemporaryDirectory() as directory:
            source = os.path.join(directory, "Movie.mkv")
            with open(source, "wb"):
                pass
            outdir = os.path.join(directory, "Converted")
            cfg = Config(directory, output_path=outdir)

            def runner(command, **kwargs):
                return SimpleNamespace(stdout=json.dumps({"streams": [
                    audio(0, codec="dts", channels=6, language="fra"),
                    audio(1, codec="aac", channels=2, language="eng"),
                ]}))

            self.assertEqual(process(source, cfg, runner=runner), "skipped")
            self.assertFalse(os.path.exists(os.path.join(outdir, "Movie.stereo-ac3.mkv")))

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
        # Video, then the selected stream first (encoded to stereo AC-3), then
        # the other English/unknown originals as copies; explicit non-English
        # (the French DTS track) is dropped.
        self.assertEqual(maps, ["0:0", "0:2", "0:2", "0:3", "0:4"])
        self.assertEqual(command[command.index("-c:a:0") + 1], "ac3")
        self.assertEqual(command[command.index("-ac:a:0") + 1], "2")
        self.assertEqual(command[command.index("-c:a") + 1], "copy")
        self.assertEqual(command[-1], "Movie.stereo-ac3.mkv")

    def test_selected_stream_is_mapped_first_and_only_it_is_encoded(self):
        streams = [
            audio(0, codec="dts", channels=6, language="eng"),
            audio(1, codec="dts", channels=6, language="eng", bit_rate="999999"),
        ]
        command = ffmpeg_command("in.mkv", "out.mkv", streams)
        maps = [command[i + 1] for i, value in enumerate(command) if value == "-map"]
        # 0:1 has the higher bit rate so it is selected, mapped first, and is
        # the only stream encoded; both originals are kept as copies.
        self.assertEqual(maps, ["0:1", "0:0", "0:1"])
        self.assertEqual(command[command.index("-c:a:0") + 1], "ac3")
        self.assertEqual(command[command.index("-ac:a:0") + 1], "2")

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

    def test_build_output_map_plain_names_and_collision_hashes(self):
        sources = ["/media/A/Movie.mkv", "/media/B/Movie.mkv", "/media/C/Other.mkv"]
        mapping = build_output_map(sources, "/out", "/media")
        self.assertEqual(
            mapping[os.path.abspath("/media/C/Other.mkv")],
            os.path.join("/out", "Other.stereo-ac3.mkv"),
        )
        first = mapping[os.path.abspath("/media/A/Movie.mkv")]
        second = mapping[os.path.abspath("/media/B/Movie.mkv")]
        self.assertNotEqual(first, second)
        for dst in (first, second):
            name = os.path.basename(dst)
            self.assertTrue(name.startswith("Movie.stereo-ac3-"), name)
            self.assertTrue(name.endswith(".mkv"), name)
        self.assertEqual(len(set(mapping.values())), len(mapping))
        # Deterministic across calls: same source, same destination.
        self.assertEqual(build_output_map(sources, "/out", "/media"), mapping)

    def test_destination_for_prefers_runner_map_then_falls_back(self):
        cfg = Config("/media", output_path="/out")
        cfg.output_names = {
            os.path.abspath("/media/A/Movie.mkv"): os.path.join("/out", "hashed.stereo-ac3.mkv")
        }
        self.assertEqual(
            destination_for("/media/A/Movie.mkv", cfg),
            os.path.join("/out", "hashed.stereo-ac3.mkv"),
        )
        self.assertEqual(
            destination_for("/media/A/Other.mkv", cfg),
            os.path.join("/out", "Other.stereo-ac3.mkv"),
        )

    def test_destination_for_requires_output_path(self):
        cfg = Config("/media")
        with self.assertRaises(ValueError):
            destination_for("/media/a.mkv", cfg)

    def test_existing_companion_is_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            outdir = os.path.join(directory, "Converted")
            os.makedirs(outdir)
            source = os.path.join(directory, "Movie.mkv")
            companion = os.path.join(outdir, "Movie.stereo-ac3.mkv")
            with open(source, "wb") as handle:
                handle.write(b"original")
            with open(companion, "wb") as handle:
                handle.write(b"existing")
            calls = []

            def runner(command, **kwargs):
                calls.append(command)
                return SimpleNamespace(stdout=json.dumps({"streams": [audio(0, channels=6, language="eng")]}))

            cfg = Config(directory, output_path=outdir)
            result = process(source, cfg, runner=runner)
            self.assertEqual(result, "skipped")
            self.assertEqual(len(calls), 1)  # probe only; never overwrite the companion
            with open(companion, "rb") as handle:
                self.assertEqual(handle.read(), b"existing")

    def test_conversion_preserves_original_and_writes_only_to_output_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            outdir = os.path.join(directory, "Converted")
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

            dst = os.path.join(outdir, "Movie.stereo-ac3.mkv")
            self.assertTrue(convert(source, streams, runner=runner, dst=dst))
            with open(source, "rb") as handle:
                self.assertEqual(handle.read(), b"original bytes")
            with open(dst, "rb") as handle:
                self.assertEqual(handle.read(), b"converted companion")
            self.assertEqual(len(calls), 1)
            self.assertFalse(os.path.exists(os.path.join(directory, "Movie.stereo-ac3.mkv")))
            self.assertEqual(sorted(os.listdir(directory)), ["Converted", "Movie.mkv"])
            self.assertFalse(any(name.startswith(".plex-audio-") for name in os.listdir(outdir)))

    def test_discover_excludes_companions(self):
        with tempfile.TemporaryDirectory() as directory:
            open(os.path.join(directory, "x.MKV"), "w").close()
            open(os.path.join(directory, "x" + COMPANION_SUFFIX + ".mkv"), "w").close()
            open(os.path.join(directory, "x.txt"), "w").close()
            self.assertEqual(len(list(discover(directory))), 1)

    def test_discover_excludes_output_folder_nested_under_media_root(self):
        with tempfile.TemporaryDirectory() as directory:
            outdir = os.path.join(directory, "Converted", "Nested")
            os.makedirs(outdir)
            open(os.path.join(directory, "a.mkv"), "w").close()
            open(os.path.join(directory, "b.mp4"), "w").close()
            open(os.path.join(outdir, "gen.stereo-ac3.mkv"), "w").close()
            open(os.path.join(outdir, "junk.mkv"), "w").close()
            found = sorted(os.path.basename(p) for p in discover(directory, exclude_dir=outdir))
            self.assertEqual(found, ["a.mkv", "b.mp4"])


if __name__ == "__main__":
    unittest.main()
