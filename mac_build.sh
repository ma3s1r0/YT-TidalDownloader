#!/bin/bash

echo "[*] PyInstaller 기반 TIDAL Downloader 빌드 시작..."

# 현재 위치 기준 경로
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# PyInstaller 설치 확인
if ! command -v pyinstaller &> /dev/null; then
  echo "[!] PyInstaller가 설치되어 있지 않습니다. 설치 중..."
  pip3 install pyinstaller
fi

# .env 파일 존재 확인
if [ ! -f ".env" ]; then
  echo "[!] .env 파일이 없습니다. 빈 .env 파일을 생성합니다."
  touch .env
fi

# PyQt5 번역 파일 경로 자동 추출
echo "[*] PyQt 번역 파일 경로 찾는 중..."
TRANSLATION_PATH=$(python3 -c "from PyQt5.QtCore import QLibraryInfo; print(QLibraryInfo.location(QLibraryInfo.TranslationsPath))")

# 번역 파일 확인 및 임시 복사
QTBASE_KO_QM="$TRANSLATION_PATH/qtbase_ko.qm"
QTBASE_FAKE_QM="/tmp/qtbase.qm"

if [ -f "$QTBASE_KO_QM" ]; then
  cp "$QTBASE_KO_QM" "$QTBASE_FAKE_QM"
  echo "[✓] qtbase_ko.qm → 임시 qtbase.qm 복사 완료"
else
  echo "[!] qtbase_ko.qm 번역 파일을 찾을 수 없습니다. 더미 파일을 생성합니다."
  touch "$QTBASE_FAKE_QM"
fi

echo "[✓] 번역 경로 확인됨: $TRANSLATION_PATH"

# 기존 빌드 정리
echo "[*] 이전 빌드 정리 중..."
rm -rf build dist *.spec

# 빌드 수행
echo "[*] PyInstaller 빌드 시작..."
pyinstaller --noconfirm --windowed --onefile \
  --name "YT-TidalDownloader" \
  --add-data "$QTBASE_FAKE_QM:PyQt5/Qt5/translations/qtbase.qm" \
  tidal_downloader_gui.py

# 빌드 결과 확인
if [ -f "dist/YT-TidalDownloader" ]; then
  echo "[✓] 빌드 성공: dist/YT-TidalDownloader"
  chmod +x dist/YT-TidalDownloader
  echo "[✓] 실행 권한 부여 완료"
else
  echo "[X] 빌드 실패! 오류를 확인해주세요."
fi

# 임시 파일 제거
rm -f "$QTBASE_FAKE_QM"