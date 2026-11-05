import os
import unittest
from unittest.mock import patch, MagicMock
import sys
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from deploy_guardian import probe_http_health

class TestHealthChecker(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_probe_success_200(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = probe_http_health("http://example.com/healthz", expected_status=200, retries=1)
        self.assertTrue(result)

    @patch("urllib.request.urlopen")
    def test_probe_expected_status_match(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 302
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = probe_http_health("http://example.com/login", expected_status=302, retries=1)
        self.assertTrue(result)

    @patch("urllib.request.urlopen")
    def test_probe_failure_500(self, mock_urlopen):
        err = urllib.error.HTTPError(
            url="http://example.com/healthz",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None
        )
        mock_urlopen.side_effect = err

        result = probe_http_health("http://example.com/healthz", expected_status=200, retries=2, backoff=0.01)
        self.assertFalse(result)

if __name__ == "__main__":
    unittest.main()

