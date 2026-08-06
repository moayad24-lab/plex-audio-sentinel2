import json
import os
import tempfile
import unittest

from plex_audio_sentinel.config import Config
from plex_audio_sentinel.runner import run
from plex_audio_sentinel.state import STATE_FILENAME, State, StateError


def make_proc(results):
    """Fake processor recording calls; returns per-path result or "skipped"."""
    calls = []

    def proc(path, cfg):
        calls.append(path)
        return results.get(path, "skipped")

    return proc, calls


class RunnerTests(unittest.TestCase):
    def test_first_run_records_baseline_and_converts_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("a.mkv", "b.mp4"):
                with open(os.path.join(directory, name), "wb"):
                    pass
            # Generated companions must never be tracked as source media.
            with open(os.path.join(directory, "x.stereo-ac3.mkv"), "wb"):
                pass
            cfg = Config(directory, state_file=os.path.join(directory, STATE_FILENAME))
            proc, calls = make_proc({})
            summary = run(cfg, proc=proc)
            self.assertTrue(summary.baseline_created)
            self.assertEqual(summary.scanned, 2)
            self.assertEqual(summary.new, 0)
            self.assertEqual(summary.ignored, 2)
            self.assertEqual(summary.converted, 0)
            self.assertEqual(calls, [])  # baseline run processes nothing
            state = State.load(cfg.state_file)
            self.assertTrue(state.contains(os.path.join(directory, "a.mkv")))
            self.assertTrue(state.contains(os.path.join(directory, "b.mp4")))
            self.assertFalse(state.contains(os.path.join(directory, "x.stereo-ac3.mkv")))
            with open(cfg.state_file, encoding="utf-8") as handle:
                self.assertEqual(len(json.load(handle)["seen"]), 2)

    def test_second_run_processes_only_new_files(self):
        with tempfile.TemporaryDirectory() as directory:
            with open(os.path.join(directory, "old.mkv"), "wb"):
                pass
            cfg = Config(directory, state_file=os.path.join(directory, STATE_FILENAME))
            run(cfg, proc=make_proc({})[0])  # baseline
            new_path = os.path.join(directory, "new.mkv")
            with open(new_path, "wb"):
                pass
            proc, calls = make_proc({new_path: "converted"})
            summary = run(cfg, proc=proc)
            self.assertEqual(summary.scanned, 2)
            self.assertEqual(summary.new, 1)
            self.assertEqual(summary.ignored, 1)
            self.assertEqual(summary.converted, 1)
            self.assertEqual(calls, [new_path])  # only the new file was processed
            self.assertTrue(State.load(cfg.state_file).contains(new_path))
            # Third run: nothing left to do.
            proc3, calls3 = make_proc({})
            summary3 = run(cfg, proc=proc3)
            self.assertEqual(summary3.new, 0)
            self.assertEqual(summary3.ignored, 2)
            self.assertEqual(calls3, [])

    def test_failed_conversion_is_not_recorded_and_is_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg = Config(directory, state_file=os.path.join(directory, STATE_FILENAME))
            run(cfg, proc=make_proc({})[0])  # baseline on an empty library
            path = os.path.join(directory, "a.mkv")
            with open(path, "wb"):
                pass
            summary = run(cfg, proc=make_proc({path: "error"})[0])
            self.assertEqual(summary.errors, 1)
            self.assertFalse(State.load(cfg.state_file).contains(path))
            # Next run retries the same file; success marks it as seen.
            proc, calls = make_proc({path: "converted"})
            summary2 = run(cfg, proc=proc)
            self.assertEqual(summary2.converted, 1)
            self.assertEqual(summary2.errors, 0)
            self.assertEqual(calls, [path])
            self.assertTrue(State.load(cfg.state_file).contains(path))

    def test_skipped_ineligible_file_is_recorded_as_seen(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg = Config(directory, state_file=os.path.join(directory, STATE_FILENAME))
            run(cfg, proc=make_proc({})[0])
            path = os.path.join(directory, "a.mkv")
            with open(path, "wb"):
                pass
            summary = run(cfg, proc=make_proc({path: "skipped"})[0])
            self.assertEqual(summary.skipped, 1)
            self.assertTrue(State.load(cfg.state_file).contains(path))
            summary3 = run(cfg, proc=make_proc({})[0])
            self.assertEqual(summary3.new, 0)

    def test_malformed_state_aborts_without_processing_anything(self):
        with tempfile.TemporaryDirectory() as directory:
            with open(os.path.join(directory, "a.mkv"), "wb"):
                pass
            cfg = Config(directory, state_file=os.path.join(directory, STATE_FILENAME))
            with open(cfg.state_file, "w", encoding="utf-8") as handle:
                handle.write("garbage {")
            proc, calls = make_proc({})
            with self.assertRaises(StateError):
                run(cfg, proc=proc)
            self.assertEqual(calls, [])  # existing media never treated as new

    def test_dry_run_before_baseline_reports_baseline_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "a.mkv")
            with open(path, "wb"):
                pass
            cfg = Config(directory, state_file=os.path.join(directory, STATE_FILENAME))
            proc, calls = make_proc({path: "would-convert"})
            summary = run(cfg, dry_run=True, proc=proc)
            # No baseline yet: nothing is probed and nothing is written; the
            # first real run will only record files and convert nothing.
            self.assertEqual(summary.new, 1)
            self.assertEqual(summary.converted, 0)
            self.assertEqual(calls, [])
            self.assertFalse(os.path.exists(cfg.state_file))

    def test_dry_run_after_baseline_reports_would_convert_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg = Config(directory, state_file=os.path.join(directory, STATE_FILENAME))
            run(cfg, proc=make_proc({})[0])  # baseline
            path = os.path.join(directory, "a.mkv")
            with open(path, "wb"):
                pass
            proc, calls = make_proc({path: "would-convert"})
            summary = run(cfg, dry_run=True, proc=proc)
            self.assertEqual(summary.new, 1)
            self.assertEqual(summary.converted, 1)
            self.assertEqual(calls, [path])
            # Dry run never records the file or rewrites the state.
            self.assertFalse(State.load(cfg.state_file).contains(path))

    def test_configured_state_file_outside_media_root(self):
        with tempfile.TemporaryDirectory() as media, tempfile.TemporaryDirectory() as state_dir:
            with open(os.path.join(media, "a.mkv"), "wb"):
                pass
            state_path = os.path.join(state_dir, "state.json")
            cfg = Config(media, state_file=state_path)
            summary = run(cfg, proc=make_proc({})[0])
            self.assertTrue(summary.baseline_created)
            self.assertTrue(os.path.exists(state_path))
            self.assertTrue(State.load(state_path).contains(os.path.join(media, "a.mkv")))


if __name__ == "__main__":
    unittest.main()
