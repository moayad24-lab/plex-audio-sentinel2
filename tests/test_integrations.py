import unittest
from unittest.mock import patch
from plex_audio_sentinel.integrations import send_telegram
class ReportingTests(unittest.TestCase):
 @patch('plex_audio_sentinel.integrations.urllib.request.urlopen')
 def test_telegram_payload(self, opener):
  response=opener.return_value.__enter__.return_value
  response.read.return_value=b'{"ok": true}'
  self.assertTrue(send_telegram('TOKEN','123','hello'))
  req=opener.call_args.args[0]
  self.assertIn('botTOKEN/sendMessage', req.full_url)
  self.assertIn(b'chat_id=123', req.data)
if __name__=='__main__': unittest.main()
