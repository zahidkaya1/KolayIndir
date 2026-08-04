import os
import subprocess

from src.utils import hidden_subprocess_kwargs, patch_subprocess_for_hidden_console


def test_hidden_subprocess_kwargs_windows():
    """Windows helper CREATE_NO_WINDOW döndürür, STARTF_USESHOWWINDOW aktif, vb."""
    original_os_name = os.name
    try:
        os.name = "nt"

        # Test 1: Basic
        kwargs = hidden_subprocess_kwargs(stdout=subprocess.PIPE)
        assert "startupinfo" in kwargs
        assert "creationflags" in kwargs

        si = kwargs["startupinfo"]
        cf = kwargs["creationflags"]

        # Windows-specific flags
        # CREATE_NO_WINDOW = 0x08000000
        assert cf & subprocess.CREATE_NO_WINDOW == subprocess.CREATE_NO_WINDOW
        assert si.dwFlags & subprocess.STARTF_USESHOWWINDOW == subprocess.STARTF_USESHOWWINDOW
        assert si.wShowWindow == subprocess.SW_HIDE
        assert kwargs["stdout"] == subprocess.PIPE

        # Test 2: Existing flags are merged
        kwargs2 = hidden_subprocess_kwargs(creationflags=0x10)
        assert kwargs2["creationflags"] == 0x10 | subprocess.CREATE_NO_WINDOW

    finally:
        os.name = original_os_name

def test_hidden_subprocess_kwargs_non_windows():
    """Linux/macOS için Windows flagleri eklenmez."""
    original_os_name = os.name
    try:
        os.name = "posix"
        kwargs = hidden_subprocess_kwargs(stdout=subprocess.PIPE)
        assert "startupinfo" not in kwargs
        assert "creationflags" not in kwargs
        assert kwargs["stdout"] == subprocess.PIPE
    finally:
        os.name = original_os_name

def test_patch_subprocess_context_manager():
    """patch_subprocess_for_hidden_console ile Popen sınıfları güvenle sarmalanır."""
    original_os_name = os.name
    try:
        os.name = "nt"

        import yt_dlp.utils
        orig_sub_popen = subprocess.Popen
        orig_yt_popen = yt_dlp.utils.Popen

        with patch_subprocess_for_hidden_console():
            assert subprocess.Popen is not orig_sub_popen
            assert yt_dlp.utils.Popen is not orig_yt_popen

        # Context manager bitince orijinal sınıflara dönülür
        assert subprocess.Popen is orig_sub_popen
        assert yt_dlp.utils.Popen is orig_yt_popen
    finally:
        os.name = original_os_name


def test_patch_subprocess_context_manager_nested():
    """İç içe kullanımda orijinal Popen sınıfları yalnız son çıkışta geri döner."""
    original_os_name = os.name
    try:
        os.name = "nt"
        orig_sub_popen = subprocess.Popen

        with patch_subprocess_for_hidden_console():
            patched_1 = subprocess.Popen
            assert patched_1 is not orig_sub_popen

            with patch_subprocess_for_hidden_console():
                patched_2 = subprocess.Popen
                assert patched_2 is patched_1  # Aynı patch sınıfı kullanılmaya devam etmeli

            # İçteki context bittiğinde hala patchli kalmalı
            assert subprocess.Popen is patched_1

        # Dıştaki context bittiğinde orijinal haline dönmeli
        assert subprocess.Popen is orig_sub_popen
    finally:
        os.name = original_os_name

def test_patch_subprocess_context_manager_threading():
    """Thread'ler arası eşzamanlı kullanımda patch durumu korunur."""
    import threading
    import time

    original_os_name = os.name
    try:
        os.name = "nt"
        orig_sub_popen = subprocess.Popen

        # We need a shared state to verify
        results = []

        def worker_1():
            with patch_subprocess_for_hidden_console():
                results.append(('w1_enter', subprocess.Popen is not orig_sub_popen))
                time.sleep(0.5)
                results.append(('w1_exit', subprocess.Popen is not orig_sub_popen))

        def worker_2():
            time.sleep(0.1)  # worker_1'in patch yapmasını bekle
            with patch_subprocess_for_hidden_console():
                results.append(('w2_enter', subprocess.Popen is not orig_sub_popen))
                time.sleep(0.1)
                results.append(('w2_exit', subprocess.Popen is not orig_sub_popen))

        t1 = threading.Thread(target=worker_1)
        t2 = threading.Thread(target=worker_2)

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        # Bütün adımlarda patchli olmalıydı
        assert all(is_patched for _, is_patched in results)

        # Threadler bittikten sonra orijinaline dönmeli
        assert subprocess.Popen is orig_sub_popen
    finally:
        os.name = original_os_name
