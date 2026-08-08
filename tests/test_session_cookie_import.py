import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.session_manager import SessionManager


class TestSessionCookieImport(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patcher = patch.dict(os.environ, {"LOCALAPPDATA": self.temp_dir.name})
        self.patcher.start()
        self.mgr = SessionManager()
            
        self.test_file = Path("test_cookies_temp.txt")
            
    def tearDown(self):
        self.patcher.stop()
        self.temp_dir.cleanup()
        if self.test_file.exists():
            self.test_file.unlink()

    def test_import_only_allowed_domains(self):
        with open(self.test_file, "w") as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write(".instagram.com\tTRUE\t/\tFALSE\t1234567890\tsessionid\t12345\n")
            f.write(".threads.net\tTRUE\t/\tFALSE\t1234567890\tcsrftoken\tabcde\n")
            f.write(".youtube.com\tTRUE\t/\tFALSE\t1234567890\tLOGIN_INFO\txxxxxx\n")
            f.write(".facebook.com\tTRUE\t/\tFALSE\t1234567890\tc_user\t9999\n")
            
        success, _msg = self.mgr.import_from_cookie_file(self.test_file)
        self.assertTrue(success)
        
        saved_data = self.mgr.store.load_session()
        self.assertIn("instagram.com", saved_data)
        self.assertIn("threads.net", saved_data)
        self.assertNotIn("youtube.com", saved_data)
        self.assertNotIn("facebook.com", saved_data)

    def test_reject_corrupted_or_empty_cookie_file(self):
        # Empty
        with open(self.test_file, "w") as f:
            f.write("")
        success, _msg = self.mgr.import_from_cookie_file(self.test_file)
        self.assertFalse(success)
        
        # Only comments
        with open(self.test_file, "w") as f:
            f.write("# This is a comment\n# Another one\n")
        success, msg = self.mgr.import_from_cookie_file(self.test_file)
        self.assertFalse(success)
        
        # No allowed domains
        with open(self.test_file, "w") as f:
            f.write(".youtube.com\tTRUE\t/\tFALSE\t1234567890\tLOGIN_INFO\txxxxxx\n")
        success, msg = self.mgr.import_from_cookie_file(self.test_file)
        self.assertFalse(success)
        self.assertIn("uygun Threads veya Instagram oturumu bulunamadı", msg)
