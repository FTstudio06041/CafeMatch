# -*- coding: utf-8 -*-
"""
回填咖啡廳座標（cafes.lat / cafes.lng），首頁地圖靠它標點。

座標以 google_place_id 為鍵存在 data/cafe_coords.json 並進版控：
place_id 在不同資料庫之間是穩定的，所以只要有一台機器向 Google 查過一次，
其他環境（例如正式機）直接從檔案套用即可，不必再呼叫 API。

用法：
    python scripts/backfill_cafe_coords.py                     # 從 JSON 套用到資料庫（不連外）
    python scripts/backfill_cafe_coords.py --from-short-links  # JSON 沒有的，解析 Google 地圖短網址
    python scripts/backfill_cafe_coords.py --fetch             # JSON 沒有的，向 Google Places 查詢
    python scripts/backfill_cafe_coords.py --dry-run           # 只列出會做什麼

--from-short-links 不需要 API key：cafes.url 存的是 Google 地圖分享短碼
（maps.app.goo.gl/<短碼>），請求一次就會轉址到帶有店家圖釘座標的網址
（…!3d<緯度>!4d<經度>…）。只讀轉址標頭裡的座標，不抓地圖頁內容。

--fetch 使用 .env 的 GOOGLE_MAPS_API_KEY，每家店一次 Place Details（只取 location 欄位）。
"""

import argparse
import json
import os
import re
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

COORDS_FILE = os.path.join(ROOT, 'data', 'cafe_coords.json')
PLACE_DETAILS_URL = 'https://places.googleapis.com/v1/places/{place_id}'
SHORT_LINK_URL = 'https://maps.app.goo.gl/{code}'
# 店家圖釘的座標（!3d緯度!4d經度）；@緯度,經度 是畫面中心，只在沒有圖釘時退而求其次
PIN_RE = re.compile(r'!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)')
CENTER_RE = re.compile(r'@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)')

# 資料庫的店全在花蓮；超出這個範圍多半是 place_id 對錯店，只警告不擋
HUALIEN_BOUNDS = {'lat': (23.0, 24.6), 'lng': (120.9, 121.9)}


def load_coords():
    if not os.path.exists(COORDS_FILE):
        return {}
    with open(COORDS_FILE, encoding='utf-8') as f:
        return json.load(f)


def save_coords(coords):
    with open(COORDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(dict(sorted(coords.items(), key=lambda kv: kv[1].get('name', ''))),
                  f, ensure_ascii=False, indent=2)
        f.write('\n')


def fetch_location(place_id, api_key):
    resp = requests.get(
        PLACE_DETAILS_URL.format(place_id=place_id),
        headers={'X-Goog-Api-Key': api_key, 'X-Goog-FieldMask': 'location,displayName'},
        params={'languageCode': 'zh-TW'},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    loc = data.get('location') or {}
    if 'latitude' not in loc or 'longitude' not in loc:
        return None
    return {
        'lat': round(float(loc['latitude']), 7),
        'lng': round(float(loc['longitude']), 7),
        'google_name': (data.get('displayName') or {}).get('text', ''),
    }


def coords_from_short_link(code, max_hops=3):
    """
    解析 Google 地圖分享短網址的轉址，回傳 {'lat', 'lng', 'precision'} 或 None。
    每一跳只看 Location 標頭，讀到座標就停，不會去請求地圖頁本身。
    """
    url = SHORT_LINK_URL.format(code=code)
    center = None
    for _ in range(max_hops):
        resp = requests.get(url, allow_redirects=False, stream=True, timeout=10,
                            headers={'User-Agent': 'CafeMatch-coord-backfill/1.0'})
        location = resp.headers.get('Location', '')
        resp.close()
        pin = PIN_RE.search(location)
        if pin:
            return {'lat': round(float(pin.group(1)), 7), 'lng': round(float(pin.group(2)), 7),
                    'precision': 'pin'}
        found = CENTER_RE.search(location)
        if found:
            center = {'lat': round(float(found.group(1)), 7), 'lng': round(float(found.group(2)), 7),
                      'precision': 'center'}
        if resp.status_code not in (301, 302, 303, 307, 308) or not location:
            break
        if 'google.com/maps' in location:
            break  # 再往下就是地圖頁本身了，不抓
        url = location
    return center


def in_hualien(lat, lng):
    return (HUALIEN_BOUNDS['lat'][0] <= lat <= HUALIEN_BOUNDS['lat'][1]
            and HUALIEN_BOUNDS['lng'][0] <= lng <= HUALIEN_BOUNDS['lng'][1])


def main():
    parser = argparse.ArgumentParser(description='回填咖啡廳座標')
    parser.add_argument('--fetch', action='store_true', help='JSON 沒有的座標向 Google Places 查詢')
    parser.add_argument('--from-short-links', action='store_true',
                        help='JSON 沒有的座標從 Google 地圖短網址（cafes.url）解析，不需 API key')
    parser.add_argument('--dry-run', action='store_true', help='只列出會做什麼，不寫入')
    args = parser.parse_args()

    from app import app
    from database import db
    from models import Cafes

    coords = load_coords()
    fetched = 0
    with app.app_context():
        api_key = app.config.get('GOOGLE_MAPS_API_KEY')
        if args.fetch and not api_key:
            sys.exit('沒有 GOOGLE_MAPS_API_KEY，無法 --fetch')

        cafes = Cafes.query.order_by(Cafes.id).all()
        updated, missing = [], []
        for cafe in cafes:
            pid = cafe.google_place_id
            if not pid:
                missing.append(f'#{cafe.id} {cafe.name}（沒有 place_id）')
                continue
            entry = coords.get(pid)
            if entry is None and args.from_short_links and cafe.url:
                if args.dry_run:
                    print(f'[DRY] 會解析短網址 #{cafe.id} {cafe.name}')
                    continue
                try:
                    loc = coords_from_short_link(cafe.url)
                except requests.RequestException as e:
                    loc = None
                    print(f'[WARN] #{cafe.id} {cafe.name} 短網址解析失敗：{e}')
                time.sleep(0.5)  # 一次性的少量請求，仍然放慢一點
                if loc:
                    if loc['precision'] != 'pin':
                        print(f'[WARN] #{cafe.id} {cafe.name} 只拿到畫面中心座標，位置可能不精準')
                    entry = {'name': cafe.name, 'source': 'short_link', **loc}
                    coords[pid] = entry
                    fetched += 1
            if entry is None and args.fetch:
                if args.dry_run:
                    print(f'[DRY] 會向 Google 查詢 #{cafe.id} {cafe.name}')
                    continue
                try:
                    loc = fetch_location(pid, api_key)
                except requests.RequestException as e:
                    missing.append(f'#{cafe.id} {cafe.name}（查詢失敗：{e}）')
                    continue
                if not loc:
                    missing.append(f'#{cafe.id} {cafe.name}（Google 沒有回傳座標）')
                    continue
                entry = {'name': cafe.name, 'source': 'places_api', **loc}
                coords[pid] = entry
                fetched += 1
            if entry is None:
                missing.append(f'#{cafe.id} {cafe.name}（JSON 沒有，需 --from-short-links 或 --fetch）')
                continue

            lat, lng = entry['lat'], entry['lng']
            if not in_hualien(lat, lng):
                print(f'[WARN] #{cafe.id} {cafe.name} 座標 ({lat}, {lng}) 不在花蓮範圍，請確認 place_id')
            if cafe.lat == lat and cafe.lng == lng:
                continue
            updated.append(f'#{cafe.id} {cafe.name} → ({lat}, {lng})')
            if not args.dry_run:
                cafe.lat, cafe.lng = lat, lng

        if not args.dry_run:
            db.session.commit()
            if fetched:
                save_coords(coords)

    prefix = '[DRY] 會更新' if args.dry_run else '已更新'
    for line in updated:
        print(f'{prefix} {line}')
    print(f'\n共 {len(cafes)} 家：{prefix} {len(updated)} 家，新查到 {fetched} 家，缺 {len(missing)} 家')
    for line in missing:
        print(f'  缺：{line}')
    if fetched and not args.dry_run:
        print(f'座標已存入 {os.path.relpath(COORDS_FILE, ROOT)}，記得一起 commit')


if __name__ == '__main__':
    main()
