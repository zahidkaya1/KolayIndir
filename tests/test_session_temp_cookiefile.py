import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.session_manager import SessionManager


class TestSessionTempCookiefile(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patcher = patch.dict(os.environ, {"LOCALAPPDATA": self.temp_dir.name})
        self.patcher.start()
        self.mgr = SessionManager()
            
        self.mgr.store.save_session("fake_cookie_data")
            
    def tearDown(self):
        self.patcher.stop()
        self.temp_dir.cleanup()

    def test_temp_file_creation_and_cleanup(self):
        temp_path_str = None
        with self.mgr.create_temp_cookiefile() as cookie_path:
            self.assertIsNotNone(cookie_path)
            self.assertTrue(Path(cookie_path).exists())
            self.assertTrue(Path(cookie_path).name.startswith("session-"))
            self.assertTrue(Path(cookie_path).name.endswith(".txt"))
            temp_path_str = cookie_path
            
            with open(cookie_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "fake_cookie_data")
                
        # After context manager exit, it should be deleted
        self.assertFalse(Path(temp_path_str).exists())

    def test_temp_file_cleanup_on_exception(self):
        temp_path_str = None
        try:
            with self.mgr.create_temp_cookiefile() as cookie_path:
                temp_path_str = cookie_path
                self.assertTrue(Path(cookie_path).exists())
                raise RuntimeError("Test exception")
        except RuntimeError:
            pass
            
        # Even after exception, it should be deleted
        if temp_path_str:
            self.assertFalse(Path(temp_path_str).exists())
            
    def test_parallel_unique_filenames(self):
        with self.mgr.create_temp_cookiefile() as p1, self.mgr.create_temp_cookiefile() as p2:
                self.assertNotEqual(p1, p2)
                self.assertTrue(Path(p1).exists())
                self.assertTrue(Path(p2).exists())
