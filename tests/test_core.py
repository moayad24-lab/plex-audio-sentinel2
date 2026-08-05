import json, os, tempfile, unittest
from types import SimpleNamespace
from plex_audio_sentinel.core import has_aac, ffmpeg_command, discover
class CoreTests(unittest.TestCase):
 def test_detection(self):
  self.assertTrue(has_aac([{'codec_type':'audio','codec_name':'aac'}])); self.assertFalse(has_aac([{'codec_type':'audio','codec_name':'ac3'}]))
 def test_command(self): self.assertIn('-c:v',ffmpeg_command('a','b')); self.assertEqual(ffmpeg_command('a','b')[-1],'b')
 def test_discover(self):
  with tempfile.TemporaryDirectory() as d:
   open(os.path.join(d,'x.MKV'),'w').close(); open(os.path.join(d,'x.txt'),'w').close(); self.assertEqual(len(list(discover(d))),1)
if __name__=='__main__': unittest.main()
