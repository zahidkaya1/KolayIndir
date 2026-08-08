import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from src.session_center_dialog import SessionCenterDialog

app = QApplication.instance() or QApplication([])

class TestSessionCenterDialog(unittest.TestCase):
    @patch("src.session_center_dialog.SessionManager")
    def test_dialog_init(self, mock_sm_class):
        mock_sm = mock_sm_class.return_value
        mock_sm.get_session_status.return_value = "Oturum yok"
        
        dialog = SessionCenterDialog()
        self.assertEqual(dialog.status_value.text(), "Oturum yok")
        
    @patch("src.session_center_dialog.SessionManager")
    @patch("src.session_center_dialog.AppMessageDialog")
    def test_remove_session(self, mock_msg_dlg, mock_sm_class):
        mock_sm = mock_sm_class.return_value
        mock_sm.get_session_status.return_value = "Bağlı"
        
        dialog = SessionCenterDialog()
        dialog._remove_session()
        
        mock_sm.remove_session.assert_called_once()
        mock_msg_dlg.return_value.exec.assert_called_once()
