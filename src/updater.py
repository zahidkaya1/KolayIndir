"""GitHub Releases tabanlı basit güncelleme kontrolü."""

from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, Signal, Slot

from src.config import (
    APP_VERSION,
    GITHUB_OWNER,
    GITHUB_REPO,
    HTTP_USER_AGENT,
)


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(value) for value in re.findall(r"\d+", version)[:3])


class UpdateWorker(QObject):
    update_available = Signal(str, str, str)
    up_to_date = Signal()
    no_release_found = Signal()
    error = Signal(str)
    finished = Signal()

    @Slot()
    def run(self) -> None:
        endpoint = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
        request = Request(
            endpoint,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": HTTP_USER_AGENT,
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urlopen(request, timeout=10) as response:
                payload = json.load(response)
            tag = str(payload.get("tag_name", "")).strip()
            page_url = str(payload.get("html_url", "")).strip()
            notes = str(payload.get("body", "")).strip()
            if not tag:
                raise ValueError("GitHub yanıtında sürüm etiketi bulunamadı.")
            if _version_tuple(tag) > _version_tuple(APP_VERSION):
                self.update_available.emit(tag, page_url, notes)
            else:
                self.up_to_date.emit()
        except HTTPError as exc:
            if exc.code == 404:
                self.no_release_found.emit()
            else:
                self.error.emit(f"Güncelleme sorgusu başarısız: HTTP {exc.code}")
        except (URLError, TimeoutError):
            self.error.emit("Güncelleme kontrolü için internete bağlanılamadı.")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.error.emit(f"Güncelleme bilgisi okunamadı: {exc}")
        finally:
            self.finished.emit()

