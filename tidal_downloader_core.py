import os
import re
import json
import time
import base64
import subprocess
import requests
import Levenshtein
from ytmusicapi import YTMusic
from mutagen import File as MutagenFile
from pathlib import Path

# gettext 관련 에러 방지
try:
    import builtins
    builtins.__dict__['_'] = lambda x: x
    
    import sys
    if 'gettext' in sys.modules:
        import gettext
        gettext.translation = lambda *args, **kwargs: type('DummyTranslation', (), {
            'gettext': lambda self, x: x, 
            'ngettext': lambda self, s1, s2, n: s1 if n == 1 else s2
        })()
except Exception:
    pass  # 실패해도 계속 진행

DEBUG = False  # 디버그 로그 출력 여부

def normalize(text):
    text = text.lower()
    text = text.replace('&', ' ')
    text = text.replace('/', ' ')
    text = text.replace('(', ' ').replace(')', ' ')
    text = text.replace('ukf drum and bass', '')
    text = re.sub(r'[^a-z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def similar(a, b):
    if not a or not b:
        return 0.0
    distance = Levenshtein.distance(a, b)
    max_len = max(len(a), len(b))
    return 1 - distance / max_len

def get_tidal_access_token(client_id, client_secret, logger):
    auth_str = f"{client_id}:{client_secret}"
    b64_auth_str = base64.b64encode(auth_str.encode()).decode()

    url = "https://auth.tidal.com/v1/oauth2/token"
    headers = {
        "Authorization": f"Basic {b64_auth_str}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "client_credentials"
    }

    response = requests.post(url, headers=headers, data=data)

    if response.status_code == 200:
        token_info = response.json()
        logger(f"✅ 액세스 토큰 발급 완료 (유효 시간: {token_info.get('expires_in')}초)")
        return token_info.get("access_token")
    else:
        logger(f"❌ 액세스 토큰 요청 실패: {response.status_code} {response.text}")
        return None

def get_tracks_from_directory(track_dir):
    # Tracks 폴더가 없는 경우를 대비한 경로 처리
    tracks_path = os.path.join(track_dir, "Tracks")
    if not os.path.exists(tracks_path):
        os.makedirs(tracks_path, exist_ok=True)
        return set()
    
    # 결과 캐싱 파일 경로
    cache_file = os.path.join(tracks_path, ".track_cache.json")
    
    # 캐시 파일이 존재하고 최근에 생성된 경우 사용
    if os.path.exists(cache_file):
        try:
            cache_mtime = os.path.getmtime(cache_file)
            dir_mtime = os.path.getmtime(tracks_path)
            
            # 폴더 수정 시간이 캐시보다 오래된 경우 캐시 사용 (24시간 내)
            if dir_mtime < cache_mtime and (time.time() - cache_mtime) < 86400:  # 24시간
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_tracks = json.load(f)
                    if cached_tracks and isinstance(cached_tracks, list):
                        return set(cached_tracks)
        except Exception:
            pass  # 캐시 파일 문제 시 무시하고 계속 진행
        
    files = os.listdir(tracks_path)
    track_set = set()

    for filename in files:
        if filename.lower().endswith(('.mp3', '.flac', '.wav', '.m4a')):
            name = os.path.splitext(filename)[0]
            norm1 = normalize(name)
            if ' - ' in name:
                parts = name.split(' - ')
                norm2 = normalize(f"{parts[0]} {parts[1]}")  # 곡명 아티스트 순서로 변경
            else:
                norm2 = norm1
            if DEBUG:
                print(f"[LOCAL] {filename} → norm1: {norm1} / norm2: {norm2}")
            track_set.add(norm1)
            track_set.add(norm2)
    
    # 캐시 저장
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(list(track_set), f)
    except Exception:
        pass  # 캐시 저장 실패는 무시
            
    return track_set

def get_tracks_from_ytmusic(playlist_url, logger):
    match = re.search(r'list=([a-zA-Z0-9_-]+)', playlist_url)
    if not match:
        logger("❌ 유효하지 않은 유튜브 링크입니다.")
        return []

    playlist_id = match.group(1)
    logger(f"[+] YTMusic에서 플레이리스트 '{playlist_id}' 로드 중...")
    
    # 연결 타임아웃 설정
    ytmusic = YTMusic()
    
    try:
        playlist = ytmusic.get_playlist(playlist_id, limit=None)
        
        if not playlist or 'tracks' not in playlist:
            logger("❌ 플레이리스트를 불러올 수 없습니다. 공개 플레이리스트인지 확인하세요.")
            return []
        
        track_count = len(playlist['tracks'])
        logger(f"[+] 총 {track_count}개 트랙 발견")
        
        tracks = []
        for idx, item in enumerate(playlist['tracks'], 1):
            if idx % 20 == 0:  # 진행 상황 업데이트
                logger(f"[+] 트랙 {idx}/{track_count} 처리 중...")
                
            title = item['title']
            artist = ", ".join([a['name'] for a in item['artists']])
            combined1 = f"{title} - {artist}"
            combined2 = f"{artist} - {title}"
            norm1 = normalize(combined1)
            norm2 = normalize(combined2)
            if DEBUG:
                logger(f"[YT   ] {title} - {artist} → norm1: {norm1}, norm2: {norm2}")
            tracks.append({
                "title": title,
                "artist": artist,
                "patterns": [norm1, norm2]
            })
        return tracks
    except Exception as e:
        logger(f"❌ YouTube Music API 오류: {e}")
        return []

def search_tidal_track(title, artist, headers, logger):
    query = f"{title} {artist}"
    norm_query = normalize(query)
    
    # 요청 재시도 로직 추가
    max_retries = 3
    retry_delay = 2  # 초
    
    for attempt in range(max_retries):
        try:
            url = f"https://openapi.tidal.com/v2/searchresults/{norm_query}?countryCode=US&include=tracks"
            if attempt == 0:
                logger(f"[+] 검색 쿼리: {norm_query}")
            else:
                logger(f"[+] 재시도 {attempt+1}/{max_retries}: {norm_query}")
            
            response = requests.get(url, headers=headers, timeout=10)  # 10초 타임아웃
            
            if response.status_code == 200:
                data = response.json()
                tracks = data.get("data", {}).get("relationships", {}).get("tracks", {}).get("data", [])
                if tracks:
                    track = tracks[0]
                    logger(f"[+] TIDAL 검색 성공: {track['id']}")
                    return f"https://tidal.com/browse/track/{track['id']}"
                else:
                    logger(f"⚠️ 검색 결과 없음: {norm_query}")
                    return None
            elif response.status_code == 429:  # Too Many Requests
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1)
                    logger(f"⚠️ 요청 제한 발생. {wait_time}초 후 재시도...")
                    time.sleep(wait_time)
                    continue
            else:
                logger(f"❌ 검색 실패: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            logger("⚠️ 검색 타임아웃")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
        except Exception as e:
            logger(f"⚠️ 검색 중 예외 발생: {e}")
            return None
            
    return None

def find_executable_path(command):
    """명령어의 전체 경로 찾기"""
    # 이미 절대 경로이고 존재하는 경우
    if os.path.isabs(command) and os.path.exists(command):
        return command
    
    # 상대 경로이며 존재하는 경우 (현재 디렉토리 기준)
    if os.path.exists(command):
        return os.path.abspath(command)
    
    # 시스템 PATH에서 찾기
    try:
        path_env = os.environ.get("PATH", "").split(os.pathsep)
        for path in path_env:
            if not path:  # 빈 경로 무시
                continue
                
            try:
                exe_path = os.path.join(path, command)
                if os.path.isfile(exe_path) and os.access(exe_path, os.X_OK):
                    return exe_path
            except Exception:
                # 잘못된 경로는 무시하고 계속 검색
                continue
    except Exception:
        pass  # PATH 검색 실패는 무시
    
    # 확장자가 없는 명령어에 .exe 추가 (Windows)
    if os.name == 'nt' and not command.lower().endswith('.exe'):
        return find_executable_path(command + '.exe')
    
    # 홈 디렉토리와 일반적인 bin 디렉토리 확인
    additional_paths = [
        os.path.expanduser("~"),  # 홈 디렉토리
        os.path.join(os.path.expanduser("~"), "bin"),  # ~/bin
        os.path.join(os.path.expanduser("~"), ".local", "bin"),  # ~/.local/bin
        "/usr/local/bin",  # 일반적인 설치 위치 (macOS, Linux)
        "/opt/homebrew/bin",  # Homebrew (Apple Silicon)
        "/usr/bin",  # 시스템 바이너리 (Linux)
    ]
    
    for path in additional_paths:
        try:
            if not os.path.exists(path):
                continue
                
            exe_path = os.path.join(path, command)
            if os.path.isfile(exe_path) and os.access(exe_path, os.X_OK):
                return exe_path
        except Exception:
            continue
            
    # 찾지 못했을 경우 원래 명령어 반환
    return command

def update_tidal_dl_config(tidal_dl, track_dir, logger):
    logger("[+] tidal-dl-ng 설정 파일 경로 확인 중...")
    
    # 실행 파일 경로 찾기
    tidal_dl_path = find_executable_path(tidal_dl)
    logger(f"[+] tidal-dl-ng 경로: {tidal_dl_path}")
    
    try:
        # Windows에서만 CREATE_NO_WINDOW 사용
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        extra_kwargs = {"creationflags": creation_flags} if os.name == "nt" else {}
        
        # 환경 변수 설정 - PATH 포함
        env = os.environ.copy()
        
        result = subprocess.run([tidal_dl_path, "cfg"], 
                               capture_output=True, 
                               text=True, 
                               env=env,
                               **extra_kwargs)
                               
        match = re.search(r'Config:\s+(.*settings\.json)', result.stdout)
        if match:
            config_path = match.group(1)
            logger(f"[+] 설정 파일 경로: {config_path}")

            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            config["download_base_path"] = track_dir
            config["quality_audio"] = "LOSSLESS"

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

            logger("[+] tidal-dl-ng 설정 업데이트 완료")
        else:
            logger("❌ settings.json 경로를 찾을 수 없습니다.")
            logger(f"출력: {result.stdout}")
            if result.stderr:
                logger(f"오류: {result.stderr}")
    except Exception as e:
        logger(f"❌ 설정 업데이트 중 예외 발생: {e}")

def download_with_tidal_dl(tidal_dl, track_url, logger):
    logger(f"⬇️ 다운로드 시도 중: {track_url}")
    
    # 실행 파일 경로 찾기
    tidal_dl_path = find_executable_path(tidal_dl)
    
    # 파일 존재 확인 및 오류 표시
    if not os.path.exists(tidal_dl_path):
        logger(f"❌ 오류: tidal-dl-ng 실행 파일이 존재하지 않습니다: {tidal_dl_path}")
        return False
        
    if not os.access(tidal_dl_path, os.X_OK):
        logger(f"❌ 오류: tidal-dl-ng 실행 파일에 실행 권한이 없습니다: {tidal_dl_path}")
        try:
            os.chmod(tidal_dl_path, 0o755)  # 실행 권한 추가 시도
            logger(f"✓ 실행 권한을 추가했습니다.")
        except Exception as e:
            logger(f"⚠️ 실행 권한 추가 실패: {e}")
            return False
    
    try:
        # Windows에서만 CREATE_NO_WINDOW 사용
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        extra_kwargs = {"creationflags": creation_flags} if os.name == "nt" else {}
        
        # 환경 변수 설정 - PATH 포함
        env = os.environ.copy()
        
        logger(f"[+] 실행 명령: {tidal_dl_path} dl {track_url}")
        
        result = subprocess.run([tidal_dl_path, "dl", track_url], 
                               text=True, 
                               timeout=60, 
                               capture_output=True, 
                               env=env,
                               **extra_kwargs)
                               
        logger(result.stdout)
        if result.stderr:
            logger(f"오류: {result.stderr}")
            
        if result.returncode != 0:
            logger(f"⚠️ 프로세스 종료 코드: {result.returncode}")
            
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        logger("⏱ 타임아웃 발생")
    except FileNotFoundError:
        logger(f"❌ 오류: 파일을 찾을 수 없습니다: {tidal_dl_path}")
        logger("tidal-dl-ng가 올바르게 설치되었는지 확인하세요.")
    except PermissionError:
        logger(f"❌ 오류: 권한이 거부되었습니다: {tidal_dl_path}")
        logger("파일에 실행 권한이 있는지 확인하세요.")
    except Exception as e:
        logger(f"⚠️ 다운로드 중 예외 발생: {e}")
        import traceback
        logger(traceback.format_exc())
    return False

def try_download(tracks, tidal_dl, headers, track_dir, logger):
    failed = []
    for idx, t in enumerate(tracks, start=1):
        logger(f"[{idx:02d}] 🎵 {t['title']} - {t['artist']}")
        track_url = search_tidal_track(t['title'], t['artist'], headers, logger)
        if track_url:
            if not download_with_tidal_dl(tidal_dl, track_url, logger):
                failed.append(t)
        else:
            failed.append(t)
        time.sleep(1)
    return failed

def verify_audio_file(file_path, logger):
    """
    음악 파일의 무결성을 검사합니다.
    
    Args:
        file_path (str): 검사할 파일 경로
        logger (callable): 로깅 함수
        
    Returns:
        bool: 파일이 유효하면 True, 그렇지 않으면 False
    """
    try:
        audio = MutagenFile(file_path)
        if audio is None:
            logger(f"⚠️ 손상된 파일 감지: {os.path.basename(file_path)}")
            return False
            
        # 파일 크기가 0인 경우
        if os.path.getsize(file_path) == 0:
            logger(f"⚠️ 빈 파일 감지: {os.path.basename(file_path)}")
            return False
            
        # 재생 시간이 없거나 너무 짧은 경우 (1초 미만)
        if hasattr(audio.info, 'length') and audio.info.length < 1:
            logger(f"⚠️ 비정상적으로 짧은 파일 감지: {os.path.basename(file_path)}")
            return False
            
        return True
    except Exception as e:
        logger(f"⚠️ 파일 검증 중 오류 발생: {os.path.basename(file_path)} - {str(e)}")
        return False

def verify_downloaded_files(track_dir, logger):
    """
    다운로드된 모든 음악 파일의 무결성을 검사합니다.
    
    Args:
        track_dir (str): 트랙 디렉토리 경로
        logger (callable): 로깅 함수
        
    Returns:
        list: 손상된 파일들의 경로 목록
    """
    tracks_path = os.path.join(track_dir, "Tracks")
    corrupted_files = []
    
    if not os.path.exists(tracks_path):
        logger("❌ Tracks 디렉토리를 찾을 수 없습니다.")
        return corrupted_files
        
    logger("\n[+] 다운로드된 파일 검증 시작...")
    total_files = len([f for f in os.listdir(tracks_path) 
                      if f.lower().endswith(('.mp3', '.flac', '.wav', '.m4a'))])
    
    for idx, filename in enumerate(os.listdir(tracks_path), 1):
        if filename.lower().endswith(('.mp3', '.flac', '.wav', '.m4a')):
            file_path = os.path.join(tracks_path, filename)
            logger(f"[{idx}/{total_files}] 검증 중: {filename}")
            
            if not verify_audio_file(file_path, logger):
                corrupted_files.append(file_path)
                
    return corrupted_files

def retry_corrupted_downloads(corrupted_files, tidal_dl, headers, track_dir, logger):
    """
    손상된 파일들을 삭제하고 재다운로드를 시도합니다.
    
    Args:
        corrupted_files (list): 손상된 파일들의 경로 목록
        tidal_dl (str): tidal-dl 실행 파일 경로
        headers (dict): API 요청 헤더
        track_dir (str): 트랙 디렉토리 경로
        logger (callable): 로깅 함수
    """
    if not corrupted_files:
        logger("✅ 모든 파일이 정상입니다!")
        return
        
    logger(f"\n[+] {len(corrupted_files)}개의 손상된 파일 재다운로드 시작")
    
    for file_path in corrupted_files:
        filename = os.path.basename(file_path)
        name = os.path.splitext(filename)[0]
        
        # 파일명에서 아티스트와 제목 추출
        if ' - ' in name:
            artist, title = name.split(' - ', 1)
        else:
            # 구분자가 없는 경우 전체를 제목으로 취급
            artist, title = "", name
            
        logger(f"\n[+] 재다운로드 시도: {filename}")
        
        # 기존 파일 삭제
        try:
            os.remove(file_path)
            logger(f"[+] 손상된 파일 삭제: {filename}")
        except Exception as e:
            logger(f"⚠️ 파일 삭제 실패: {filename} - {e}")
            continue
            
        # Tidal에서 검색 및 다운로드
        track_url = search_tidal_track(title, artist, headers, logger)
        if track_url:
            if download_with_tidal_dl(tidal_dl, track_url, logger):
                logger(f"✅ 재다운로드 성공: {filename}")
            else:
                logger(f"❌ 재다운로드 실패: {filename}")
        else:
            logger(f"❌ Tidal에서 트랙을 찾을 수 없습니다: {filename}")
        
        time.sleep(1)  # API 요청 간격 조절

def run_downloader(track_dir, tidal_dl, playlist_url, client_id, client_secret, logger):
    logger("[+] 액세스 토큰 요청 중...")
    access_token = get_tidal_access_token(client_id, client_secret, logger)
    if not access_token:
        return

    headers = {"Authorization": f"Bearer {access_token}"}
    update_tidal_dl_config(tidal_dl, track_dir, logger)

    logger("[+] 로컬 트랙 목록 불러오는 중...")
    local_tracks = get_tracks_from_directory(track_dir)
    logger("[+] 유튜브 뮤직에서 트랙 가져오는 중...")
    yt_tracks = get_tracks_from_ytmusic(playlist_url, logger)

    missing = []
    for t in yt_tracks:
        matched = False
        logger(f"[CHECK] {t['title']} - {t['artist']}")
        for p in t['patterns']:
            for l in local_tracks:
                sim = similar(p, l)
                if DEBUG: logger(f"[DEBUG] comparing '{p}' vs '{l}' → {sim:.2f}")
                if sim > 0.5:
                    if DEBUG: logger(f"[SIMILAR] {p} ≈ {l} → {sim:.2f}")
                    matched = True
                    break
            if matched:
                break
        if not matched:
            logger(f"[MISS] ❌ {t['title']} - {t['artist']}")
            missing.append(t)
        else:
            logger(f"[SKIP] ✅ {t['title']} - {t['artist']}")

    logger(f"\n[+] 총 {len(missing)}곡 다운로드 시도 중...")
    failed = try_download(missing, tidal_dl, headers, track_dir, logger)

    if failed:
        logger("\n[+] 다운로드 실패 곡 diff 기반 재시도 중...")
        local_tracks_retry = get_tracks_from_directory(track_dir)
        recheck = []
        for t in failed:
            matched = False
            for pattern in t['patterns']:
                for l in local_tracks_retry:
                    sim = similar(pattern, l)
                    if DEBUG:
                        logger(f"[DEBUG] retry comparing '{pattern}' vs '{l}' → {sim:.2f}")
                    if sim > 0.2:
                        matched = True
                        logger(f"[RETRY SKIP] ✅ {t['title']} - {t['artist']} ≈ {l} → {sim:.2f}")
                        break
                if matched:
                    break
            if not matched:
                recheck.append(t)

        if recheck:
            logger(f"\n[+] 재시도할 {len(recheck)}곡 다운로드 중...")
            still_failed = try_download(recheck, tidal_dl, headers, track_dir, logger)

            if still_failed:
                with open("missing_tracks.json", "w", encoding="utf-8") as f:
                    json.dump(still_failed, f, ensure_ascii=False, indent=2)
                logger(f"❌ 최종 실패 트랙 {len(still_failed)}개 → missing_tracks.json 저장 완료")
        else:
            logger("✅ 모든 실패 곡이 재시도에서 성공했습니다.")
    else:
        logger("✅ 모든 곡 다운로드 완료!")
        
    # 다운로드 완료 후 파일 무결성 검사
    logger("\n[+] 다운로드된 파일 무결성 검사 시작...")
    corrupted_files = verify_downloaded_files(track_dir, logger)
    
    if corrupted_files:
        logger(f"\n⚠️ {len(corrupted_files)}개의 손상된 파일이 발견되었습니다.")
        retry_corrupted_downloads(corrupted_files, tidal_dl, headers, track_dir, logger)
    else:
        logger("\n✅ 모든 파일이 정상적으로 다운로드되었습니다!")