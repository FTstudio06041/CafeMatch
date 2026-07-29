# -*- coding: utf-8 -*-
"""
圖片同步腳本（咖啡廳照片 + 咖啡人格插畫）。

  img/coffee store/<id>.jpg      → frontend/public/cafes/<id>.jpg
                                   並更新 cafes.image
  img/quiz/<人格稱號>.jpg         → frontend/src/assets/personality/<type_key>.jpg
                                   （依 quiz_result_types.title 對應，改用英文 key 命名，
                                     並縮圖壓縮成 800px JPEG）

用法：
    venv\\Scripts\\python.exe scripts\\sync_cafe_photos.py            # 同步
    venv\\Scripts\\python.exe scripts\\sync_cafe_photos.py --dry-run  # 只看會做什麼

之後在 GitHub 上傳新圖到對應資料夾後，重跑一次即可。
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

# 咖啡人格插畫：來源用中文稱號命名，輸出改用 type_key。
# 放在 src/assets（而非 public）——與題目插畫一致，前端用 import.meta.glob 取用，
# 副檔名 .jpg/.png 混用也不必特別處理，還能享有打包壓縮與快取雜湊。
PERSONA_SOURCE_DIR = os.path.join(ROOT, 'img', 'quiz')
PERSONA_TARGET_DIR = os.path.join(ROOT, 'frontend', 'src', 'assets', 'personality')
# 結果頁顯示尺寸只有 280px，800px 已足夠涵蓋高解析螢幕
PERSONA_MAX_SIZE = 800


def optimize_image(src, dst, max_size, quality=85):
    """
    縮圖並輸出成 JPEG（原圖多為 2048px，網頁顯示只需幾百 px）。

    回傳 True 表示已優化；Pillow 不存在或圖片有透明度時回傳 False，
    由呼叫端改用原檔複製。
    """
    try:
        from PIL import Image
    except ImportError:
        return False

    try:
        with Image.open(src) as im:
            # 有實際透明度的圖不轉 JPEG（會變黑底），保留原格式
            if im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info):
                if im.convert('RGBA').getchannel('A').getextrema()[0] < 255:
                    return False
            im = im.convert('RGB')
            if max(im.size) > max_size:
                im.thumbnail((max_size, max_size), Image.LANCZOS)
            im.save(dst, 'JPEG', quality=quality, optimize=True, progressive=True)
        return True
    except Exception:
        return False


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


def sync_personality(dry_run=False):
    """
    咖啡人格插畫：img/quiz/<稱號>.<ext> → frontend/public/personality/<type_key>.<ext>

    以 quiz_result_types.title 對應，輸出檔名改用 type_key（英文），
    前端就能用 /personality/<type_key>.<ext> 直接取用。
    """
    from app import app
    from models import QuizResultType

    if not os.path.isdir(PERSONA_SOURCE_DIR):
        return True, f'略過人格插畫（找不到 {PERSONA_SOURCE_DIR}）'

    files = {}
    for fname in os.listdir(PERSONA_SOURCE_DIR):
        stem, ext = os.path.splitext(fname)
        if ext.lower() in VALID_EXT:
            files[stem] = fname

    if not dry_run:
        os.makedirs(PERSONA_TARGET_DIR, exist_ok=True)

    copied, missing, extra = 0, [], set(files)
    src_bytes, out_bytes = 0, 0
    with app.app_context():
        types = QuizResultType.query.all()
        for t in types:
            fname = files.get(t.title)
            if not fname:
                missing.append(t.title)
                continue
            extra.discard(t.title)
            src = os.path.join(PERSONA_SOURCE_DIR, fname)
            if dry_run:
                copied += 1
                continue

            # 先清掉同一個人格的舊檔（可能是別的副檔名），避免新舊並存
            for old_ext in VALID_EXT:
                old = os.path.join(PERSONA_TARGET_DIR, f'{t.type_key}{old_ext}')
                if os.path.exists(old):
                    os.remove(old)

            dst = os.path.join(PERSONA_TARGET_DIR, f'{t.type_key}.jpg')
            if not optimize_image(src, dst, PERSONA_MAX_SIZE):
                # Pillow 不可用或圖片有透明度 → 保留原格式直接複製
                dst = os.path.join(PERSONA_TARGET_DIR, f'{t.type_key}{os.path.splitext(fname)[1].lower()}')
                shutil.copy2(src, dst)

            src_bytes += os.path.getsize(src)
            out_bytes += os.path.getsize(dst)
            copied += 1

    msg = f'人格插畫 {copied}/{len(types)} 張'
    if copied and out_bytes:
        msg += f'（{src_bytes/1024/1024:.1f} MB → {out_bytes/1024/1024:.1f} MB）'
    if missing:
        msg += f'；缺圖：{", ".join(missing)}'
    if extra:
        msg += f'；找不到對應人格：{", ".join(sorted(extra))}'
    return True, msg


if __name__ == '__main__':
    dry = '--dry-run' in sys.argv
    ok, message = sync(dry_run=dry)
    print(('[試跑] ' if dry else '') + message.replace('[試跑] ', ''))
    ok2, message2 = sync_personality(dry_run=dry)
    print(('[試跑] ' if dry else '') + message2)
    sys.exit(0 if (ok and ok2) else 1)
