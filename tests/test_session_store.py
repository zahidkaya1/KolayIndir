import os
import tempfile
import unittest
from unittest.mock import patch

from src.session_store import SessionStore


class TestSessionStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patcher = patch.dict(os.environ, {"LOCALAPPDATA": self.temp_dir.name})
        self.patcher.start()
        self.store = SessionStore()

    def tearDown(self):
        self.patcher.stop()
        self.temp_dir.cleanup()

    def test_dpapi_encrypt_decrypt_roundtrip(self):
        secret_data = "my_secret_cookie_data_123"
        self.store.save_session(secret_data)
        
        # Check that file exists
        self.assertTrue(self.store.store_file.exists())
        
        # Check that file doesn't contain plaintext
        with open(self.store.store_file, "rb") as f:
            raw_data = f.read()
            self.assertNotIn(b"my_secret_cookie_data_123", raw_data)
            
        # Check decrypt
        decrypted = self.store.load_session()
        self.assertEqual(decrypted, secret_data)
        
    def test_corrupted_payload_safe_error(self):
        # Create a corrupted file
        self.store.store_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.store.store_file, "wb") as f:
            f.write(b"this_is_not_a_valid_dpapi_payload")
            
        # Loading should safely return None
        result = self.store.load_session()
        self.assertIsNone(result)
        
    def test_session_save_load_delete(self):
        self.store.save_session("test1")
        self.assertEqual(self.store.load_session(), "test1")
        
        self.store.delete_session()
        self.assertFalse(self.store.store_file.exists())
        self.assertIsNone(self.store.load_session())
