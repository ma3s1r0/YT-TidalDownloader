import sys
import os
from pathlib import Path
from dotenv import load_dotenv, set_key
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QLineEdit, QLabel, QFileDialog, QRadioButton, QButtonGroup
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
        
        # 플레이리스트 선택 라디오 버튼
        playlist_type_layout = QHBoxLayout()
        playlist_type_layout.addWidget(QLabel("플레이리스트 유형:"))
        self.playlist_group = QButtonGroup(self)
        
        self.youtube_radio = QRadioButton("YouTube Music")
        self.tidal_radio = QRadioButton("TIDAL")
        self.youtube_radio.setChecked(True)  # 기본값은 YouTube
        
        self.playlist_group.addButton(self.youtube_radio)
        self.playlist_group.addButton(self.tidal_radio)
        
        playlist_type_layout.addWidget(self.youtube_radio)
        playlist_type_layout.addWidget(self.tidal_radio)
        playlist_type_layout.addStretch()
        form_layout.addLayout(playlist_type_layout)
        
        # YouTube 플레이리스트 입력
        self.youtube_playlist_layout = QHBoxLayout()
        self.youtube_playlist_layout.addWidget(QLabel("YouTube Playlist URL"))
        self.playlist_url_input = QLineEdit()
        self.playlist_url_input.setText(os.getenv("YT_PLAYLIST_URL", ""))
        self.youtube_playlist_layout.addWidget(self.playlist_url_input)
        form_layout.addLayout(self.youtube_playlist_layout)
        
        # Tidal 플레이리스트 입력
        self.tidal_playlist_layout = QHBoxLayout()
        self.tidal_playlist_layout.addWidget(QLabel("TIDAL Playlist URL"))
        self.tidal_playlist_input = QLineEdit()
        self.tidal_playlist_input.setText(os.getenv("TIDAL_PLAYLIST_URL", ""))
        self.tidal_playlist_layout.addWidget(self.tidal_playlist_input)
        form_layout.addLayout(self.tidal_playlist_layout)
        
        self.client_id_input = self.create_input(form_layout, "Client ID", os.getenv("CLIENT_ID", ""))
        self.client_secret_input = self.create_input(form_layout, "Client Secret", os.getenv("CLIENT_SECRET", ""))

        # 라디오 버튼 상태에 따라 입력 필드 활성화/비활성화
        self.youtube_radio.toggled.connect(self.update_playlist_inputs)
        self.tidal_radio.toggled.connect(self.update_playlist_inputs)
        self.update_playlist_inputs()

        # 모든 입력 필드에 textChanged 이벤트 연결
        self.track_dir_input.textChanged.connect(lambda: self.save_setting("TRACKS_DIR", self.track_dir_input.text()))
        self.tidal_dl_input.textChanged.connect(lambda: self.save_setting("TIDAL_DL", self.tidal_dl_input.text()))
        self.playlist_url_input.textChanged.connect(lambda: self.save_setting("YT_PLAYLIST_URL", self.playlist_url_input.text()))
        self.tidal_playlist_input.textChanged.connect(lambda: self.save_setting("TIDAL_PLAYLIST_URL", self.tidal_playlist_input.text()))
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
            self.tidal_playlist_input,
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

    def update_playlist_inputs(self):
        """라디오 버튼 상태에 따라 입력 필드 활성화/비활성화"""
        is_youtube = self.youtube_radio.isChecked()
        self.playlist_url_input.setEnabled(is_youtube)
        self.tidal_playlist_input.setEnabled(not is_youtube)

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
            
        # 플레이리스트 URL 검사
        if self.youtube_radio.isChecked():
            if not self.playlist_url_input.text() or "list=" not in self.playlist_url_input.text():
                self.log("❌ 유효한 YouTube 플레이리스트 URL을 입력하세요.")
                return
        else:
            if not self.tidal_playlist_input.text() or "playlist/" not in self.tidal_playlist_input.text():
                self.log("❌ 유효한 TIDAL 플레이리스트 URL을 입력하세요.")
                return

        self.log("[+] 설정 저장 중...")
        try:
            # 시작 전에 모든 설정 저장
            self.save_setting("TRACKS_DIR", self.track_dir_input.text())
            self.save_setting("TIDAL_DL", self.tidal_dl_input.text())
            if self.youtube_radio.isChecked():
                self.save_setting("YT_PLAYLIST_URL", self.playlist_url_input.text())
            else:
                self.save_setting("TIDAL_PLAYLIST_URL", self.tidal_playlist_input.text())
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
            from tidal_downloader_core import run_downloader
            
            # 플레이리스트 URL 선택
            playlist_url = self.playlist_url_input.text() if self.youtube_radio.isChecked() else self.tidal_playlist_input.text()
            is_tidal_playlist = not self.youtube_radio.isChecked()
            
            run_downloader(
                track_dir=self.track_dir_input.text(),
                tidal_dl=self.tidal_dl_input.text(),
                playlist_url=playlist_url,
                client_id=self.client_id_input.text(),
                client_secret=self.client_secret_input.text(),
                logger=self.log,
                is_tidal_playlist=is_tidal_playlist
            )
        except Exception as e:
            self.log(f"❌ 처리 중 오류 발생: {e}")
            import traceback
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
