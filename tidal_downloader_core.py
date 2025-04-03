import os
import re
import json
import time
import base64
import subprocess
import requests
import Levenshtein
from ytmusicapi import YTMusic

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

def update_tidal_dl_config(tidal_dl, track_dir, logger):
    logger("[+] tidal-dl-ng 설정 파일 경로 확인 중...")
    try:
        result = subprocess.run([tidal_dl, "cfg"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0, text=True)
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
    except Exception as e:
        logger(f"❌ 설정 업데이트 중 예외 발생: {e}")

def get_tracks_from_directory(track_dir):
    files = os.listdir(track_dir+"/Tracks")
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
    return track_set

def get_tracks_from_ytmusic(playlist_url, logger):
    match = re.search(r'list=([a-zA-Z0-9_-]+)', playlist_url)
    if not match:
        logger("❌ 유효하지 않은 유튜브 링크입니다.")
        return []

    playlist_id = match.group(1)
    ytmusic = YTMusic()
    playlist = ytmusic.get_playlist(playlist_id, limit=None)

    tracks = []
    for item in playlist['tracks']:
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

def search_tidal_track(title, artist, headers, logger):
    query = normalize(f"{title} {artist}")
    print(query)
    url = f"https://openapi.tidal.com/v2/searchresults/{query}?countryCode=US&include=tracks"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            tracks = data.get("data", {}).get("relationships", {}).get("tracks", {}).get("data", [])
            if tracks:
                track = tracks[0]
                logger(f"[+] TIDAL 검색 성공: {track['id']}")
                return f"https://tidal.com/browse/track/{track['id']}"
        else:
            logger(f"❌ 검색 실패: {response.status_code} - {response.text}")
    except Exception as e:
        logger(f"⚠️ 검색 중 예외 발생: {e}")
    return None

def download_with_tidal_dl(tidal_dl, track_url, logger):
    logger(f"⬇️ 다운로드 시도 중: {track_url}")
    try:
        result = subprocess.run([tidal_dl, "dl", track_url], text=True, timeout=60, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        logger(result.stdout)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        logger("⏱ 타임아웃 발생")
    except Exception as e:
        logger(f"⚠️ 다운로드 중 예외 발생: {e}")
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