import unittest
from unittest.mock import MagicMock, patch

from src.session_manager import SessionManager
from src.threads_share_resolver import (
    _RESOLVED_CACHE,
    normalize_threads_url,
    resolve_threads_share_url,
)


class TestThreadsShareResolver(unittest.TestCase):
    def setUp(self):
        _RESOLVED_CACHE.clear()

    def test_normalize_canonical(self):
        url = "https://www.threads.com/@askineren1907/post/Dbqt3MZDPmT"
        self.assertEqual(normalize_threads_url(url), url)

    def test_normalize_strips_params(self):
        url = "https://www.threads.com/@askineren1907/post/Dbqt3MZDPmT?xmt=AQG&slof=1&igshid=xyz"
        expected = "https://www.threads.com/@askineren1907/post/Dbqt3MZDPmT"
        self.assertEqual(normalize_threads_url(url), expected)

    def test_normalize_threads_net(self):
        url = "https://threads.net/@user/post/123"
        expected = "https://www.threads.com/@user/post/123"
        self.assertEqual(normalize_threads_url(url), expected)

    @patch('src.threads_share_resolver.cffi_requests.get')
    def test_share_redirect_location(self, mock_get):
        mock_response = MagicMock()
        mock_response.url = "https://www.threads.com/@askineren1907/post/Dbqt3MZDPmT?xmt=1"
        mock_response.text = ""
        mock_get.return_value = mock_response

        result = resolve_threads_share_url("https://www.threads.net/share/Dbqt3MZDPmT")
        self.assertEqual(result, "https://www.threads.com/@askineren1907/post/Dbqt3MZDPmT")
        mock_get.assert_called_once()

    @patch('src.threads_share_resolver.cffi_requests.get')
    def test_html_canonical_link(self, mock_get):
        mock_response = MagicMock()
        mock_response.url = "https://www.threads.net/share/Dbqt3MZDPmT"
        mock_response.text = '<link rel="canonical" href="https://www.threads.com/@user/post/Dbqt3MZDPmT">'
        mock_get.return_value = mock_response

        result = resolve_threads_share_url("https://www.threads.net/share/Dbqt3MZDPmT")
        self.assertEqual(result, "https://www.threads.com/@user/post/Dbqt3MZDPmT")

    @patch('src.threads_share_resolver.cffi_requests.get')
    def test_html_og_url(self, mock_get):
        mock_response = MagicMock()
        mock_response.url = "https://www.threads.net/share/Dbqt3MZDPmT"
        mock_response.text = '<meta property="og:url" content="https://www.threads.com/@user/post/Dbqt3MZDPmT">'
        mock_get.return_value = mock_response

        result = resolve_threads_share_url("https://www.threads.net/share/Dbqt3MZDPmT")
        self.assertEqual(result, "https://www.threads.com/@user/post/Dbqt3MZDPmT")

    @patch('src.threads_share_resolver.cffi_requests.get')
    def test_html_embedded_permalink(self, mock_get):
        mock_response = MagicMock()
        mock_response.url = "https://www.threads.net/share/Dbqt3MZDPmT"
        mock_response.text = 'data-text-post-permalink="/@user/post/Dbqt3MZDPmT"'
        mock_get.return_value = mock_response

        result = resolve_threads_share_url("https://www.threads.net/share/Dbqt3MZDPmT")
        self.assertEqual(result, "https://www.threads.com/@user/post/Dbqt3MZDPmT")

    @patch('src.threads_share_resolver.cffi_requests.get')
    def test_cache_usage(self, mock_get):
        mock_response = MagicMock()
        mock_response.url = "https://www.threads.com/@user/post/Dbqt3MZDPmT"
        mock_response.text = ""
        mock_get.return_value = mock_response

        resolve_threads_share_url("https://www.threads.net/share/Dbqt3MZDPmT")
        self.assertEqual(mock_get.call_count, 1)

        # Second time should hit cache
        result = resolve_threads_share_url("https://www.threads.net/share/Dbqt3MZDPmT")
        self.assertEqual(result, "https://www.threads.com/@user/post/Dbqt3MZDPmT")
        self.assertEqual(mock_get.call_count, 1) # Still 1

    @patch('src.threads_share_resolver.cffi_requests.get')
    @patch('src.session_manager.SessionManager.get_session_status')
    @patch('src.session_store.SessionStore.load_session')
    def test_anonymous_fail_session_retry(self, mock_load_session, mock_status, mock_get):
        # First call anonymous fails
        mock_resp_fail = MagicMock()
        mock_resp_fail.url = "https://www.threads.net/share/Dbqt3MZDPmT"
        mock_resp_fail.text = "Login page"

        mock_resp_success = MagicMock()
        mock_resp_success.url = "https://www.threads.com/@user/post/Dbqt3MZDPmT"
        mock_resp_success.text = ""

        mock_get.side_effect = [mock_resp_fail, mock_resp_success]

        mock_status.return_value = "Geçerli"
        mock_load_session.return_value = ".threads.com\tTRUE\t/\tFALSE\t1234567\tsessionid\t123"

        mgr = SessionManager()
        # mock temp dir setup to avoid polluting real dir
        with patch.dict('os.environ', {"LOCALAPPDATA": "test_temp"}):
            mgr = SessionManager()
        result = resolve_threads_share_url("https://www.threads.net/share/Dbqt3MZDPmT", session_mgr=mgr)
        self.assertEqual(result, "https://www.threads.com/@user/post/Dbqt3MZDPmT")
        self.assertEqual(mock_get.call_count, 2)

    @patch('src.threads_share_resolver.cffi_requests.get')
    @patch('src.session_manager.SessionManager.get_session_status')
    def test_anonymous_success_no_session_retry(self, mock_status, mock_get):
        mock_resp = MagicMock()
        mock_resp.url = "https://www.threads.com/@user/post/123"
        mock_get.return_value = mock_resp

        mgr = SessionManager()
        result = resolve_threads_share_url("https://www.threads.net/share/123", session_mgr=mgr)
        self.assertEqual(result, "https://www.threads.com/@user/post/123")
        self.assertEqual(mock_get.call_count, 1)
        mock_status.assert_not_called()
