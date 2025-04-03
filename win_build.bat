@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion

echo [*] PyInstaller 기반 TIDAL Downloader 빌드 시작...

REM ✅ PyInstaller 설치 확인
where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [!] PyInstaller가 설치되어 있지 않습니다. 설치 중...
    pip install pyinstaller
)

REM ✅ PyQt 번역 경로 확인
echo [*] PyQt 번역 파일 경로 찾는 중...
for /f "delims=" %%i in ('python -c "from PyQt5.QtCore import QLibraryInfo; print(QLibraryInfo.location(QLibraryInfo.TranslationsPath))"') do (
    set RAW_PATH=%%i
)

REM 경로 정리
set "RAW_PATH=!RAW_PATH:"=!"
set "TRANSLATION_PATH=!RAW_PATH:/=\!"

REM 파일 경로 정의
set "QTBASE_KO_QM=!TRANSLATION_PATH!\qtbase_ko.qm"
set "QTBASE_FAKE_QM=%TEMP%\qtbase.qm"

REM qtbase_ko.qm → qtbase.qm 로 복사 (TEMP에)
if exist "!QTBASE_KO_QM!" (
    copy /y "!QTBASE_KO_QM!" "!QTBASE_FAKE_QM!" >nul
    echo [✓] qtbase_ko.qm → 임시 qtbase.qm 복사 완료
) else (
    echo [!] qtbase_ko.qm 파일이 없습니다. PyQt 설치 상태를 확인해주세요.
    pause
    exit /b
)

REM ✅ 이전 빌드 삭제
echo [*] 이전 빌드 정리 중...
rd /s /q build 2>nul
rd /s /q dist 2>nul
del /q *.spec 2>nul

REM ✅ 빌드 실행
echo [*] PyInstaller 빌드 시작...
pyinstaller --noconfirm --windowed --onefile ^
  --name YT-TidalDownloader ^
  --add-data "!QTBASE_FAKE_QM!;PyQt5/Qt5/translations/qtbase.qm" ^
  tidal_downloader_gui.py

REM ✅ 빌드 결과 확인
if exist dist\YT-TidalDownloader.exe (
    echo [✓] 빌드 성공: dist\YT-TidalDownloader.exe
) else (
    echo [X] 빌드 실패! 오류 로그를 확인해주세요.
)

REM ✅ 임시 복사 파일 제거
del /q "!QTBASE_FAKE_QM!"

pause
