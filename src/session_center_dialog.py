"""Oturum Merkezi kullanici arayuzu dialogu."""

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from src.dialogs import AppMessageDialog
from src.session_manager import SessionManager


class SessionCenterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Oturum Merkezi")
        self.setFixedSize(400, 250)

        self.manager = SessionManager()

        self._build_ui()
        self._refresh_status()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("Loadvia Oturum Merkezi")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")

        desc = QLabel(
            "Threads ve Instagram gibi oturum gerektiren platformlarda\n"
            "her indirmede sorun yaşamamak için bir kez oturum bağlayın."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #64748b; font-size: 12px;")

        status_layout = QHBoxLayout()
        status_label_title = QLabel("Durum:")
        status_label_title.setStyleSheet("font-weight: bold;")
        self.status_value = QLabel("Hesaplanıyor...")
        self.status_value.setStyleSheet("color: #2563eb; font-weight: bold;")
        status_layout.addWidget(status_label_title)
        status_layout.addWidget(self.status_value)
        status_layout.addStretch()

        layout.addWidget(title)
        layout.addWidget(desc)
        layout.addLayout(status_layout)
        layout.addStretch()

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_firefox = QPushButton("Firefox'tan Al")
        self.btn_firefox.clicked.connect(self._import_firefox)

        self.btn_file = QPushButton("Çerez Dosyası Seç (Netscape)")
        self.btn_file.clicked.connect(self._import_file)

        row1 = QHBoxLayout()
        row1.addWidget(self.btn_firefox)
        row1.addWidget(self.btn_file)
        btn_layout.addLayout(row1)

        self.btn_test = QPushButton("Oturumu Test Et")
        self.btn_test.clicked.connect(self._test_session)

        self.btn_remove = QPushButton("Oturumu Kaldır")
        self.btn_remove.setStyleSheet("color: #ef4444;")
        self.btn_remove.clicked.connect(self._remove_session)

        row2 = QHBoxLayout()
        row2.addWidget(self.btn_test)
        row2.addWidget(self.btn_remove)
        btn_layout.addLayout(row2)

        layout.addLayout(btn_layout)

    def _refresh_status(self):
        status = self.manager.get_session_status()
        self.status_value.setText(status)

        has_session = status != "Oturum yok"
        self.btn_test.setEnabled(has_session)
        self.btn_remove.setEnabled(has_session)

        if has_session:
            self.status_value.setStyleSheet("color: #16a34a; font-weight: bold;")
        else:
            self.status_value.setStyleSheet("color: #ef4444; font-weight: bold;")

    def _import_firefox(self):
        success, msg = self.manager.import_from_firefox()
        if success:
            AppMessageDialog("Başarılı", msg, "success", self).exec()
        else:
            AppMessageDialog("Hata", msg, "error", self).exec()
        self._refresh_status()

    def _import_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Çerez Dosyası Seç", "", "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            success, msg = self.manager.import_from_cookie_file(file_path)
            if success:
                AppMessageDialog("Başarılı", msg, "success", self).exec()
            else:
                AppMessageDialog("Hata", msg, "error", self).exec()
            self._refresh_status()

    def _test_session(self):
        status = self.manager.test_session()
        if status == "Geçerli":
            AppMessageDialog("Test Sonucu", "Oturum geçerli.", "success", self).exec()
            self.status_value.setText("Bağlı (Geçerli)")
            self.status_value.setStyleSheet("color: #16a34a; font-weight: bold;")
        elif status == "Geçersiz":
            AppMessageDialog(
                "Test Sonucu", "Oturum geçersiz. Yenilenmesi gerekiyor.", "error", self
            ).exec()
            self.status_value.setText("Oturum yenilenmeli")
            self.status_value.setStyleSheet("color: #eab308; font-weight: bold;")
        else:
            AppMessageDialog("Test Sonucu", f"Durum: {status}", "info", self).exec()

    def _remove_session(self):
        self.manager.remove_session()
        AppMessageDialog("Başarılı", "Oturum kaldırıldı.", "success", self).exec()
        self._refresh_status()
