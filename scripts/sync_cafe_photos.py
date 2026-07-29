# -*- coding: utf-8 -*-
"""
咖啡廳照片同步腳本。

把上傳到 img/coffee store/ 的照片（檔名 = 咖啡廳 id，例如 2.jpg 對應 id=2）
複製到前端靜態目錄，並把 cafes.image 更新成可直接顯示的路徑。

用法：
    venv\\Scripts\\python.exe scripts\\sync_cafe_photos.py            # 同步
    venv\\Scripts\\python.exe scripts\\sync_cafe_photos.py --dry-run  # 只看會做什麼

之後在 GitHub 上傳新照片到 img/coffee store/ 後，重跑一次即可。
"""

import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SOURCE_DIR = os.path.join(ROOT, 'img', 'coffee store')
TARGET_DIR = os.path.join(ROOT, 'frontend', 'public', 'cafes')
# 前端以這個路徑存取（Vite dev 直接服務 public/，build 時複製到 dist/）
URL_PREFIX = '/cafes'
VALID_EXT = ('.jpg', '.jpeg', '.png', '.webp')


def collect_photos():
    """回傳 {cafe_id: 檔名}，只收檔名是純數字的圖片。"""
    photos = {}
    if not os.path.isdir(SOURCE_DIR):
        return photos
    for fname in os.listdir(SOURCE_DIR):
        stem, ext = os.path.splitext(fname)
        if ext.lower() not in VALID_EXT or not stem.isdigit():
            continue
        photos[int(stem)] = fname
    return photos


def sync(dry_run=False):
    from app import app
    from database import db
    from models import Cafes

    photos = collect_photos()
    if not photos:
        return False, f'在 {SOURCE_DIR} 找不到以 id 命名的照片'

    if not dry_run:
        os.makedirs(TARGET_DIR, exist_ok=True)

    copied, updated, orphans = 0, 0, []
    with app.app_context():
        existing_ids = {c.id for c in Cafes.query.with_entities(Cafes.id).all()}

        for cafe_id, fname in sorted(photos.items()):
            if cafe_id not in existing_ids:
                orphans.append(fname)
                continue

            src = os.path.join(SOURCE_DIR, fname)
            dst = os.path.join(TARGET_DIR, fname)
            url = f'{URL_PREFIX}/{fname}'

            if not dry_run:
                # 只有內容不同才複製，重跑時省 I/O
                if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(src):
                    shutil.copy2(src, dst)
                    copied += 1
                cafe = db.session.get(Cafes, cafe_id)
                if cafe and cafe.image != url:
                    cafe.image = url
                    updated += 1
            else:
                copied += 1
                updated += 1

        if not dry_run:
            db.session.commit()

    msg = f'照片 {len(photos)} 張：複製 {copied} 張、更新 {updated} 筆 cafes.image'
    if orphans:
        msg += f'；{len(orphans)} 張找不到對應咖啡廳（{", ".join(orphans[:5])}）'
    if dry_run:
        msg = '[試跑] ' + msg
    return True, msg


if __name__ == '__main__':
    ok, message = sync(dry_run='--dry-run' in sys.argv)
    print(message)
    sys.exit(0 if ok else 1)
