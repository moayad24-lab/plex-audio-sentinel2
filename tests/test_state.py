import json
import os
import tempfile
import unittest

from plex_audio_sentinel.state import STATE_FILENAME, State, StateError, default_state_path


class StateTests(unittest.TestCase):
    def test_default_state_path_is_inside_media_root(self):
        self.assertEqual(
            default_state_path("/srv/media"),
            os.path.join("/srv/media", STATE_FILENAME),
        )

    def test_missing_state_file_means_no_baseline_yet(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                State.load(os.path.join(directory, "missing.json"))

    def test_atomic_save_and_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "state.json")
            state = State(path, seen=["/media/a.mkv", "/media/b.mp4"])
            state.save()
            self.assertTrue(os.path.exists(path))
            loaded = State.load(path)
            self.assertTrue(loaded.contains("/media/a.mkv"))
            self.assertTrue(loaded.contains("/media/b.mp4"))
            self.assertFalse(loaded.contains("/media/c.mkv"))
            # Atomic write: no temporary files left behind.
            self.assertEqual(os.listdir(directory), ["state.json"])
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
            self.assertEqual(payload["version"], 1)
            self.assertEqual(payload["seen"], ["/media/a.mkv", "/media/b.mp4"])

    def test_save_creates_configured_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "nested", "dir", "state.json")
            State(path, seen=["/x.mkv"]).save()
            self.assertTrue(os.path.exists(path))
            self.assertTrue(State.load(path).contains("/x.mkv"))

    def test_malformed_json_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "state.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("not json {")
            with self.assertRaises(StateError) as ctx:
                State.load(path)
            self.assertIn("malformed", str(ctx.exception))

    def test_wrong_shape_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "state.json")
            cases = [
                {"version": 2, "seen": []},
                {"version": 1, "seen": "nope"},
                {"version": 1, "seen": [1, 2]},
                {"seen": []},
            ]
            for payload in cases:
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle)
                with self.assertRaises(StateError):
                    State.load(path)


if __name__ == "__main__":
    unittest.main()
