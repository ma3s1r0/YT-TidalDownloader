#!/bin/bash

echo "[*] PyInstaller로 macOS 앱 빌드 중..."

# 현재 위치 기준 경로
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# PyQt5 번역 파일 경로 자동 추출
TRANSLATION_PATH=$(python3 -c "from PyQt5.QtCore import QLibraryInfo; print(QLibraryInfo.location(QLibraryInfo.TranslationsPath))")

if [ ! -f "$TRANSLATION_PATH/qtbase_ko.qm" ]; then
  echo "[!] qtbase_ko.qm 번역 파일을 찾을 수 없습니다."
  echo "[!] PyQt5가 올바르게 설치되어 있는지 확인해주세요."
  exit 1
fi

echo "[✓] 번역 경로 확인됨: $TRANSLATION_PATH"

# 기존 빌드 정리
echo "[*] 이전 빌드 정리 중..."
rm -rf build dist *.spec

# 빌드 수행
pyinstaller --noconfirm --windowed --onefile \
  --name "TidalDownloader" \
  --add-data ".env:." \
  --add-data "$TRANSLATION_PATH:PyQt5/Qt5/translations" \
  tidal_downloader_gui.py

if [ -f "dist/TidalDownloader" ]; then
  echo "[✓] 빌드 성공: dist/TidalDownloader"
else
  echo "[X] 빌드 실패! 오류를 확인해주세요."
fi
