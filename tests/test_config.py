import os
import unittest
from plex_audio_sentinel.config import Config
class ConfigTests(unittest.TestCase):
 def test_path_required(self):
  with self.assertRaises(ValueError): Config.from_env({})
 def test_output_path_required(self):
  with self.assertRaises(ValueError): Config.from_env({'PLEX_MEDIA_PATH':'/x'}).validate()
 def test_output_path_from_env(self):
  cfg = Config.from_env({'PLEX_MEDIA_PATH':'/x','PLEX_OUTPUT_PATH':r'E:\Plex Media Server\Converted'})
  self.assertEqual(cfg.output_path, r'E:\Plex Media Server\Converted')
 def test_output_path_must_not_be_media_root_or_ancestor(self):
  with self.assertRaises(ValueError): Config.from_env({'PLEX_MEDIA_PATH':'/srv/media','PLEX_OUTPUT_PATH':'/srv/media'}).validate()
  with self.assertRaises(ValueError): Config.from_env({'PLEX_MEDIA_PATH':'/srv/media','PLEX_OUTPUT_PATH':'/srv'}).validate()
 def test_output_path_nested_under_media_root_is_allowed(self):
  cfg = Config.from_env({'PLEX_MEDIA_PATH':'/srv/media','PLEX_OUTPUT_PATH':'/srv/media/Converted'})
  self.assertIs(cfg.validate(), cfg)
 def test_telegram_pair(self):
  with self.assertRaises(ValueError): Config.from_env({'PLEX_MEDIA_PATH':'/x','PLEX_OUTPUT_PATH':'/out','TELEGRAM_BOT_TOKEN':'x'}).validate()
 def test_state_file_default_under_media_root(self):
  cfg = Config.from_env({'PLEX_MEDIA_PATH':'/srv/media'})
  self.assertEqual(cfg.state_file, os.path.join('/srv/media', '.plex-audio-sentinel-state.json'))
 def test_state_file_override(self):
  cfg = Config.from_env({'PLEX_MEDIA_PATH':'/srv/media','PLEX_STATE_FILE':'/var/lib/plex-state.json'})
  self.assertEqual(cfg.state_file, '/var/lib/plex-state.json')
if __name__=='__main__': unittest.main()
