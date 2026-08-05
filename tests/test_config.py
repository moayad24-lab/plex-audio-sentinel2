import unittest
from plex_audio_sentinel.config import Config
class ConfigTests(unittest.TestCase):
 def test_path_required(self):
  with self.assertRaises(ValueError): Config.from_env({})
 def test_telegram_pair(self):
  with self.assertRaises(ValueError): Config.from_env({'PLEX_MEDIA_PATH':'/x','TELEGRAM_BOT_TOKEN':'x'}).validate()
if __name__=='__main__': unittest.main()
