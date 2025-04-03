import sys
import os
import re
import json
import time
import base64
import subprocess
import threading
from pathlib import Path
from dotenv import load_dotenv, set_key
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QLineEdit, QLabel, QFileDialog
)
from PyQt5.QtCore import Qt, pyqtSignal
from ytmusicapi import YTMusic
import requests
import Levenshtein
from PyQt5.QtCore import QTranslator, QLibraryInfo, QLocale
from PyQt5.QtWidgets import QApplication
import gettext

class DummyTranslations:
    def gettext(self, msg): return msg
    def ngettext(self, msg1, msg2, n): return msg1 if n == 1 else msg2

gettext.translation = lambda domain, *args, **kwargs: DummyTranslations()


load_dotenv()

class DownloaderApp(QWidget):
    log_signal = pyqtSignal(str)  # UI thread-safe logging

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.setWindowTitle("TIDAL Auto Downloader")
        self.setMinimumSize(800, 600)
        self.is_processing = False
        self.log_signal.connect(self.append_log)

    def init_ui(self):
        layout = QVBoxLayout()

        # 상단 입력 폼
        form_layout = QVBoxLayout()
        self.track_dir_input = self.create_input(form_layout, "Tracks Directory", os.getenv("TRACKS_DIR", ""))
        self.tidal_dl_input = self.create_input(form_layout, "TIDAL DL Command", os.getenv("TIDAL_DL", "tidal-dl-ng"))
        self.playlist_url_input = self.create_input(form_layout, "YouTube Playlist URL", os.getenv("YT_PLAYLIST_URL", ""))
        self.client_id_input = self.create_input(form_layout, "Client ID", os.getenv("CLIENT_ID", ""))
        self.client_secret_input = self.create_input(form_layout, "Client Secret", os.getenv("CLIENT_SECRET", ""))

        layout.addLayout(form_layout)

        # 버튼
        button_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start Download")
        self.clear_btn = QPushButton("Clear Log")
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.clear_btn)
        layout.addLayout(button_layout)

        # 로그 출력 텍스트 영역
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area)

        self.setLayout(layout)

        # 이벤트 연결
        self.start_btn.clicked.connect(self.on_start)
        self.clear_btn.clicked.connect(lambda: self.log_area.clear())

    def create_input(self, layout, label, default=""):
        h = QHBoxLayout()
        h.addWidget(QLabel(label))
        edit = QLineEdit()
        edit.setText(default)
        h.addWidget(edit)
        layout.addLayout(h)
        return edit

    def append_log(self, msg):
        self.log_area.append(msg)
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())

    def log(self, msg):
        self.log_signal.emit(msg)

    def lock_ui(self, lock: bool):
        for widget in [
            self.track_dir_input,
            self.tidal_dl_input,
            self.playlist_url_input,
            self.client_id_input,
            self.client_secret_input,
            self.start_btn,
        ]:
            widget.setDisabled(lock)

    def on_start(self):
        if self.is_processing:
            return

        self.log("[+] 설정 저장 중...")
        set_key(".env", "TRACKS_DIR", self.track_dir_input.text())
        set_key(".env", "TIDAL_DL", self.tidal_dl_input.text())
        set_key(".env", "YT_PLAYLIST_URL", self.playlist_url_input.text())
        set_key(".env", "CLIENT_ID", self.client_id_input.text())
        set_key(".env", "CLIENT_SECRET", self.client_secret_input.text())

        self.lock_ui(True)
        self.is_processing = True

        threading.Thread(target=self.run_process, daemon=True).start()

    def run_process(self):
        try:
            from tidal_downloader_core import run_downloader
            run_downloader(
                track_dir=self.track_dir_input.text(),
                tidal_dl=self.tidal_dl_input.text(),
                playlist_url=self.playlist_url_input.text(),
                client_id=self.client_id_input.text(),
                client_secret=self.client_secret_input.text(),
                logger=self.log
            )
        except Exception as e:
            self.log(f"[!] 예외 발생: {e}")
        finally:
            self.lock_ui(False)
            self.is_processing = False


if __name__ == '__main__':
    app = QApplication(sys.argv)
    translator = QTranslator()
    path = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
    if translator.load("qtbase_ko", path):
        app.installTranslator(translator)
    main_window = DownloaderApp()
    main_window.show()
    sys.exit(app.exec_())
