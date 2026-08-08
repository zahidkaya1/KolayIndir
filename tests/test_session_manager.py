import os
import tempfile
import unittest
from unittest.mock import patch

from src.session_manager import SessionManager


class TestSessionManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patcher = patch.dict(os.environ, {"LOCALAPPDATA": self.temp_dir.name})
        self.patcher.start()
        self.mgr = SessionManager()
            
    def tearDown(self):
        self.patcher.stop()
        self.temp_dir.cleanup()

    def test_session_status(self):
        self.assertEqual(self.mgr.get_session_status(), "Oturum yok")
        self.mgr.store.save_session("fake_cookie_data")
        self.assertEqual(self.mgr.get_session_status(), "Bağlı")
        
    def test_test_session_validity(self):
        self.mgr.store.save_session("somecookie\tvalue")
        self.assertEqual(self.mgr.test_session(), "Geçersiz")
        
        self.mgr.store.save_session("sessionid\t12345")
        self.assertEqual(self.mgr.test_session(), "Geçerli")
        
    def test_startup_stale_temp_cleanup(self):
        # Create a fake stale file
        self.mgr.temp_dir.mkdir(parents=True, exist_ok=True)
        fake_stale = self.mgr.temp_dir / "session-stale123.txt"
        with open(fake_stale, "w") as f:
            f.write("old_data")
            
        self.assertTrue(fake_stale.exists())
        self.mgr.cleanup_stale_temp_files()
        self.assertFalse(fake_stale.exists())
