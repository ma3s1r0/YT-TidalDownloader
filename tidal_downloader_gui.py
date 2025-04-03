import sys
import os
from pathlib import Path
from dotenv import load_dotenv, set_key
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QLineEdit, QLabel, QFileDialog
)
from PyQt5.QtCore import Qt, pyqtSignal, QTranslator, QLibraryInfo
import builtins

# gettext 함수를 재정의하여 번역 문제 해결
original_gettext = builtins.__dict__.get('_', lambda x: x)
builtins.__dict__['_'] = lambda x: x

# 설정 파일 경로를 홈 디렉토리로 변경
ENV_FILE = os.path.join(os.path.expanduser("~"), ".tidal_downloader.env")

# 기존 .env가 있으면 새 위치로 복사
if os.path.exists(".env") and not os.path.exists(ENV_FILE):
    try:
        with open(".env", "r", encoding="utf-8") as src:
            with open(ENV_FILE, "w", encoding="utf-8") as dst:
                dst.write(src.read())
    except Exception:
        pass

load_dotenv(ENV_FILE)

class DownloaderApp(QWidget):
    log_signal = pyqtSignal(str)  # UI thread-safe logging

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.setWindowTitle("TIDAL Auto Downloader")
        self.setMinimumSize(800, 600)
        self.is_processing = False
        self.log_signal.connect(self.append_log)
        self.auto_save_enabled = True  # 자동 저장 활성화 플래그
        
        # 시작 시 로딩 메시지 표시
        self.log("프로그램이 시작되었습니다. 다운로드를 시작하려면 'Start Download'를 클릭하세요.")

    def init_ui(self):
        layout = QVBoxLayout()

        # 상단 입력 폼
        form_layout = QVBoxLayout()
        self.track_dir_input = self.create_input(form_layout, "Tracks Directory", os.getenv("TRACKS_DIR", ""))
        self.tidal_dl_input = self.create_input(form_layout, "TIDAL DL Command", os.getenv("TIDAL_DL", "tidal-dl-ng"))
        self.playlist_url_input = self.create_input(form_layout, "YouTube Playlist URL", os.getenv("YT_PLAYLIST_URL", ""))
        self.client_id_input = self.create_input(form_layout, "Client ID", os.getenv("CLIENT_ID", ""))
        self.client_secret_input = self.create_input(form_layout, "Client Secret", os.getenv("CLIENT_SECRET", ""))

        # 모든 입력 필드에 textChanged 이벤트 연결
        self.track_dir_input.textChanged.connect(lambda: self.save_setting("TRACKS_DIR", self.track_dir_input.text()))
        self.tidal_dl_input.textChanged.connect(lambda: self.save_setting("TIDAL_DL", self.tidal_dl_input.text()))
        self.playlist_url_input.textChanged.connect(lambda: self.save_setting("YT_PLAYLIST_URL", self.playlist_url_input.text()))
        self.client_id_input.textChanged.connect(lambda: self.save_setting("CLIENT_ID", self.client_id_input.text()))
        self.client_secret_input.textChanged.connect(lambda: self.save_setting("CLIENT_SECRET", self.client_secret_input.text()))

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
        
        # UI 잠금 시 자동 저장 비활성화, 해제 시 다시 활성화
        self.auto_save_enabled = not lock

    def save_setting(self, key, value):
        """설정 값을 저장하는 함수"""
        if not self.auto_save_enabled:
            return
            
        try:
            set_key(ENV_FILE, key, value)
        except Exception as e:
            # 자동 저장 중 에러는 콘솔에만 출력 (UI에는 표시하지 않음)
            print(f"설정 저장 중 오류: {e}")

    def on_start(self):
        if self.is_processing:
            return
        
        # 기본 유효성 검사
        if not self.track_dir_input.text():
            self.log("❌ Tracks Directory를 입력하세요.")
            return
        if not self.client_id_input.text() or not self.client_secret_input.text():
            self.log("❌ TIDAL Client ID와 Secret을 입력하세요.")
            return
        if not self.playlist_url_input.text() or "list=" not in self.playlist_url_input.text():
            self.log("❌ 유효한 YouTube 플레이리스트 URL을 입력하세요.")
            return

        self.log("[+] 설정 저장 중...")
        try:
            # 시작 전에 모든 설정 저장
            self.save_setting("TRACKS_DIR", self.track_dir_input.text())
            self.save_setting("TIDAL_DL", self.tidal_dl_input.text())
            self.save_setting("YT_PLAYLIST_URL", self.playlist_url_input.text())
            self.save_setting("CLIENT_ID", self.client_id_input.text())
            self.save_setting("CLIENT_SECRET", self.client_secret_input.text())
        except Exception as e:
            self.log(f"⚠️ 설정 저장 중 오류: {e}")

        self.lock_ui(True)
        self.is_processing = True
        
        # 모듈 로딩 시작 알림
        self.log("[+] 필요한 모듈 로딩 중... (이 작업은 처음 실행 시 시간이 걸릴 수 있습니다)")
        
        # 별도 스레드에서 실행
        import threading
        threading.Thread(target=self.run_process, daemon=True).start()

    def run_process(self):
        try:
            # gettext 관련 예외 처리
            import sys
            import builtins
            
            # 임시로 gettext 관련 함수를 모두 패치하여 오류 방지
            builtins.__dict__['_'] = lambda x: x
            
            if 'gettext' in sys.modules:
                import gettext
                original_translation = gettext.translation
                gettext.translation = lambda *args, **kwargs: type('DummyTranslation', (), {'gettext': lambda self, x: x, 'ngettext': lambda self, s1, s2, n: s1 if n == 1 else s2})()
            
            # 무거운 모듈들은 여기서 지연 로딩
            self.log("[+] ytmusicapi 및 필요 라이브러리 로딩 중...")
            import re
            import json
            import time
            import base64
            import subprocess
            import requests
            import Levenshtein
            import shutil
            import platform
            from ytmusicapi import YTMusic
            
            from tidal_downloader_core import run_downloader, find_executable_path
            
            # Tracks 폴더 존재 확인 및 생성
            tracks_path = os.path.join(self.track_dir_input.text(), "Tracks")
            if not os.path.exists(tracks_path):
                self.log(f"[+] Tracks 폴더 생성: {tracks_path}")
                os.makedirs(tracks_path, exist_ok=True)
            
            # tidal-dl-ng 실행 파일 확인
            tidal_dl_cmd = self.tidal_dl_input.text().strip()
            self.log(f"[+] tidal-dl-ng 명령어 검색 중: '{tidal_dl_cmd}'")
            
            # 명령어가 비어있으면 기본값으로 설정
            if not tidal_dl_cmd:
                tidal_dl_cmd = "tidal-dl-ng"
                self.tidal_dl_input.setText(tidal_dl_cmd)
                self.log("[!] 명령어가 비어있어 기본값 'tidal-dl-ng'으로 설정합니다.")
            
            # 1. 입력된 경로가 직접 실행 가능한지 확인
            tidal_dl_path = tidal_dl_cmd
            is_executable = False
            
            if os.path.exists(tidal_dl_path):
                if os.path.isfile(tidal_dl_path) and os.access(tidal_dl_path, os.X_OK):
                    is_executable = True
                    self.log(f"[✓] 실행 파일을 찾았습니다: {tidal_dl_path}")
                else:
                    self.log(f"[!] 파일이 존재하지만 실행 권한이 없습니다: {tidal_dl_path}")
            
            # 2. 입력된 명령어가 시스템 PATH에 있는지 확인
            if not is_executable:
                self.log("[+] 시스템 PATH에서 검색 중...")
                path_cmd = "where" if platform.system() == "Windows" else "which"
                try:
                    result = subprocess.run([path_cmd, tidal_dl_cmd], capture_output=True, text=True)
                    if result.returncode == 0 and result.stdout.strip():
                        tidal_dl_path = result.stdout.strip().split('\n')[0]  # 첫 번째 결과만 사용
                        is_executable = True
                        self.log(f"[✓] 시스템 PATH에서 찾았습니다: {tidal_dl_path}")
                        # 입력란 업데이트
                        self.tidal_dl_input.setText(tidal_dl_path)
                        self.save_setting("TIDAL_DL", tidal_dl_path)
                except Exception:
                    pass
                
                # 그래도 못 찾으면 경고
                if not os.path.exists(tidal_dl_path):
                    self.log(f"⚠️ 경고: '{tidal_dl_cmd}' 명령을 찾을 수 없습니다.")
                    self.log("시스템 PATH에 추가되어 있거나 전체 경로를 입력했는지 확인하세요.")
                    
                    # 현재 디렉토리에서 찾기 시도
                    local_path = os.path.join(os.getcwd(), tidal_dl_cmd)
                    if os.path.exists(local_path):
                        self.log(f"[+] 현재 폴더에서 찾음: {local_path}")
                        tidal_dl_path = local_path
                        self.tidal_dl_input.setText(tidal_dl_path)
                        self.save_setting("TIDAL_DL", tidal_dl_path)
            
            self.log(f"[+] 사용할 tidal-dl-ng 경로: {tidal_dl_path}")
            
            run_downloader(
                track_dir=self.track_dir_input.text(),
                tidal_dl=tidal_dl_path,  # 전체 경로 전달
                playlist_url=self.playlist_url_input.text(),
                client_id=self.client_id_input.text(),
                client_secret=self.client_secret_input.text(),
                logger=self.log
            )
        except ModuleNotFoundError as e:
            self.log(f"❌ 필요한 모듈을 찾을 수 없습니다: {e}")
            self.log("pip install -r requirements.txt 명령으로 필요한 패키지를 설치하세요.")
        except Exception as e:
            import traceback
            self.log(f"❌ 예외 발생: {e}")
            self.log(traceback.format_exc())
        finally:
            self.is_processing = False
            self.lock_ui(False)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # 한국어 번역 설정
    translator = QTranslator()
    path = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
    if translator.load("qtbase_ko", path):
        app.installTranslator(translator)
        
    main_window = DownloaderApp()
    main_window.show()
    sys.exit(app.exec_())
