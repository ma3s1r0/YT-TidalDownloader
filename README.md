## 🎧 TIDAL Auto Downloader (YouTube Music Playlist 기반)

- TIDAL Auto Downloader는 YouTube Music의 재생목록을 기반으로
- TIDAL에서 해당 곡을 자동으로 검색하고 다운로드해주는 GUI 기반 유틸리티입니다.  
- 로컬에 이미 존재하는 곡을 자동으로 감지하고, 누락된 곡만 다운로드하도록 구현되어있습니다.

## ✨ 주요 기능

- ✅ 유튜브 뮤직 플레이리스트 URL로 곡 정보 자동 수집
- ✅ 로컬 트랙 디렉토리 비교로 누락된 곡만 필터링
- ✅ `tidal-dl-ng` CLI를 사용한 자동 다운로드
- ✅ 다운로드 실패 시 diff 재시도
- ✅ 최종 실패 목록 `missing_tracks.json` 저장
- ✅ GUI 기반 편리한 조작 (PyQt5)
- ✅ `.env` 기반 설정 자동 로딩 및 저장
- ✅ 콘솔 창 없이 조용한 백그라운드 다운로드

---

## 📦 설치 방법

### 1. 의존성 설치

```bash
pip install tidal-dl-ng
```
- python 3.12 권장


### 2. 실행
```bash
python tidal_downloader_gui.py
```

- macOS/Windows용 단독 실행파일은 /dist 폴더에서 확인 가능합니다.

### GUI 입력 항목
|항목|	설명|
|----|----|
|Tracks Directory|	다운로드된 파일이 저장된 폴더 (Tracks 폴더 포함)|
|TIDAL DL Command	|tidal-dl-ng 실행 명령어 또는 경로 (tidal-dl-ng)|
|YouTube Playlist URL	|대상이 되는 유튜브 뮤직 플레이리스트 URL|
|Client ID / Secret	TIDAL| 개발자 콘솔에서 발급받은 값|

### ⚙️ 빌드 (선택 사항)
✅ Windows 빌드
```bash
build.bat
```
- 빌드 결과: dist/TidalDownloader.exe

✅ macOS 빌드
```bash
chmod +x build-mac.sh
./build-mac.sh
```
- 빌드 결과: dist/TidalDownloader

### .env 파일 예시
```sh
TRACKS_DIR=D:/DATA/Tracks
TIDAL_DL=tidal-dl-ng
YT_PLAYLIST_URL=https://music.youtube.com/playlist?list=PLxxxx
CLIENT_ID=your_client_id
CLIENT_SECRET=your_client_secret
```

### 파일 구조
```bash
YT-TidalDownloader
├── tidal_downloader_gui.py         # PyQt5 기반 GUI 앱
├── tidal_downloader_core.py        # 다운로드 로직 코어
├── .env                            # 사용자 설정 저장
├── win_build.bat / mac_build.sh    # 빌드 스크립트
├── dist/                           # 빌드 아웃풋
├── missing_tracks.json             # 실패한 곡 목록
└── requirements.txt
```

### 참고 사항

- tidal-dl-ng CLI가 설치되어 있어야 하며, 인증도 완료되어야 합니다.
- FFmpeg가 설치되어 있지 않으면 FLAC 추출이 제한될 수 있습니다.
- 일부 곡은 지역 제한/검색 실패로 인해 다운로드가 되지 않을 수 있습니다.

### 개발자 참고
```
Python 3.10+
PyQt5
PyInstaller
ytmusicapi
Levenshtein (fast string distance)
dotenv
```
