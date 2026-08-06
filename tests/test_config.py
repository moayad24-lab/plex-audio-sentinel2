import os
import unittest
from plex_audio_sentinel.config import Config
class ConfigTests(unittest.TestCase):
 def test_path_required(self):
  with self.assertRaises(ValueError): Config.from_env({})
 def test_telegram_pair(self):
  with self.assertRaises(ValueError): Config.from_env({'PLEX_MEDIA_PATH':'/x','TELEGRAM_BOT_TOKEN':'x'}).validate()
 def test_state_file_default_under_media_root(self):
  cfg = Config.from_env({'PLEX_MEDIA_PATH':'/srv/media'})
  self.assertEqual(cfg.state_file, os.path.join('/srv/media', '.plex-audio-sentinel-state.json'))
 def test_state_file_override(self):
  cfg = Config.from_env({'PLEX_MEDIA_PATH':'/srv/media','PLEX_STATE_FILE':'/var/lib/plex-state.json'})
  self.assertEqual(cfg.state_file, '/var/lib/plex-state.json')
if __name__=='__main__': unittest.main()
