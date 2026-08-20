# -*- coding: utf-8 -*-
"""
extract_parking_tag.py — 從使用者評論萃取「好停車」標籤

背景：
  推薦系統的硬條件裡有「好停車」，但資料庫沒有任何停車欄位，
  tags 表也沒有相關標籤，所以這個條件一直無法套用（見 services/cafe_facts.py）。
  但 reviews 表有 24,770 則評論全文，其中 263 則提到停車，涵蓋 42 家店
  —— 資料一直都在，只是沒被抽出來。

作法：
  1. 取出每則評論中「停車／車位」前後的片段
  2. 逐片段判斷正面／負面（不是整則評論，因為一則評論可能同時誇餐點、抱怨停車）
  3. 以店家為單位彙總，正面票數達門檻且多於負面才給標籤

為什麼要逐片段判斷而不是整則：
  「餐點好吃，不過要先預約，不好停車」——整則是好評（5 星），停車卻是負面。
  用評分或整則語氣判斷會完全判錯。

為什麼要彙總而不是單則決定：
  單一片段一定會有判錯的，但同一家店有多則評論；
  要求「至少 N 則正面且正面多於負面」可以把個別誤判洗掉。

用法：
    python scripts/extract_parking_tag.py            # 只看結果，不寫入
    python scripts/extract_parking_tag.py --apply    # 寫入資料庫
"""

import argparse
import io
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

TAG_NAME = '好停車'

# 片段取前後各 16 個字。太短會漏掉「有附設」這種修飾，
# 太長會把隔壁句子的語氣混進來。
WINDOW = 16

# 命中即為負面。放在最前面判斷，因為「不好停車」同時含有「停車」，
# 只看正面詞會誤判成正面。
NEGATIVE = (
    '不好停', '不太好停', '不方便停', '不易停', '難停', '很難停', '不能停',
    '沒有停車', '沒停車', '無停車', '不好找停車', '停車位難找', '車位難找',
    '停車不便', '停車不易', '停車困難', '停車麻煩', '要碰運氣',
    '沒有專屬停車', '沒有附設停車',
)

# 命中即為正面
POSITIVE = (
    '有停車場', '有附停車', '附停車', '有專屬停車', '附設停車', '有提供停車',
    '提供停車', '有停車位', '有車位', '有規劃停車', '設有停車',
    '好停車', '很好停', '停車方便', '停車很方便', '停車也方便', '停車也很方便',
    '停車容易', '好停', '方便停車', '可以停車', '免費停車', '停車免費',
    '停車位多', '停車場很大', '大停車場', '停車無虞', '不用擔心停車',
    '不擔心停車', '免煩惱', '不怕沒地方停',
)

# 「否定的否定」——這些片語把負面詞救回來，必須比 NEGATIVE 更優先。
# 例：「完全不擔心停車位難找」含「車位難找」，但整句是正面；
#     「店門前不難停車」含「難停」，意思卻是好停。
NEGATED_NEGATIVE = (
    '不擔心', '不用擔心', '免擔心', '不怕', '免煩惱', '不必煩惱', '不用煩惱',
    '不會難找', '不難找', '不難停', '不會難停', '不至於難停', '沒有不好停',
    '不算難停', '不太難停', '沒有很難停',
)

TRIGGER = re.compile(r'停車|車位')


def snippets(text):
    """
    取出「停車／車位」前後的片段；相鄰的出現位置合併成同一段。

    合併是必要的，否則否定詞會被視窗邊界切掉：
      「店家附近不好停車，看網路上說可以停在七星潭停車場」
    第二個「停車」往前數 16 個字剛好從「好停車」開始，
    「不」落在視窗外，整段就被讀成正面。合併之後兩個觸發點在同一段裡，
    「不好停車」還在，才判得對。
    """
    flat = re.sub(r'\s+', '', text or '')
    spans = []
    for m in TRIGGER.finditer(flat):
        s, e = max(0, m.start() - WINDOW), min(len(flat), m.end() + WINDOW)
        if spans and s <= spans[-1][1]:
            spans[-1][1] = max(spans[-1][1], e)
        else:
            spans.append([s, e])
    return [flat[s:e] for s, e in spans]


def classify(snip):
    """
    回傳 'pos' | 'neg' | None。

    負面優先於正面：一段話同時說「路邊不好停，但對面有停車場」時判為負面。
    這是刻意保守——「好停車」是推薦時的硬條件，
    把難停的店標成好停會直接害到使用者，漏掉一家好停的店只是少一個選項。
    """
    # 否定的否定最優先：先確認這個片段有沒有被救回來
    if any(k in snip for k in NEGATED_NEGATIVE):
        return 'pos' if any(k in snip for k in POSITIVE) or TRIGGER.search(snip) else None
    if any(k in snip for k in NEGATIVE):
        return 'neg'
    if any(k in snip for k in POSITIVE):
        return 'pos'
    return None


def collect(min_positive, ratio):
    """掃過所有評論，回傳 {cafe_id: {'pos':n, 'neg':n, 'samples':[...]}}。"""
    from app import app
    from database import db
    import sqlalchemy as sa

    stats = defaultdict(lambda: {'pos': 0, 'neg': 0, 'pos_s': [], 'neg_s': []})
    with app.app_context():
        rows = db.session.execute(
            sa.text('SELECT cafe_id, txt FROM reviews WHERE txt LIKE :a OR txt LIKE :b'),
            {'a': '%停車%', 'b': '%車位%'}
        ).mappings().all()
        names = dict(db.session.execute(sa.text('SELECT id, name FROM cafes')).all())

    for r in rows:
        # 一則評論最多投一張正票、一張負票。
        # 證據單位是「寫評論的人」而不是「出現幾次停車兩個字」——
        # 同一句話裡「停車」出現兩次會產生兩個重疊片段，逐片段計票會灌水。
        # 同時提到好與不好的評論（「路邊不好停，但對面有停車場」）兩票都投，
        # 在後面的比較中互相抵銷，這正是它該有的效果。
        verdicts = {classify(s): s for s in snippets(r['txt'])}
        if 'pos' in verdicts:
            stats[r['cafe_id']]['pos'] += 1
            stats[r['cafe_id']]['pos_s'].append(verdicts['pos'])
        if 'neg' in verdicts:
            stats[r['cafe_id']]['neg'] += 1
            stats[r['cafe_id']]['neg_s'].append(verdicts['neg'])

    qualified = {
        cid for cid, s in stats.items()
        if s['pos'] >= min_positive and s['pos'] >= s['neg'] * ratio
    }
    return stats, qualified, names


def apply_tag(cafe_ids):
    """把 TAG_NAME 掛到指定店家上（已存在的關聯不重複新增）。"""
    from app import app
    from database import db
    from models.cafe import Cafes, Tags

    with app.app_context():
        tag = Tags.query.filter_by(tag_name=TAG_NAME).first()
        created = False
        if not tag:
            tag = Tags(tag_name=TAG_NAME)
            db.session.add(tag)
            db.session.flush()
            created = True

        added = 0
        for cafe in Cafes.query.filter(Cafes.id.in_(list(cafe_ids))).all():
            if tag not in cafe.tags:
                cafe.tags.append(tag)
                added += 1
        db.session.commit()
        return created, added, tag.tag_id


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='實際寫入資料庫')
    ap.add_argument('--min-positive', type=int, default=2,
                    help='至少要有幾則正面提及（預設 2）')
    ap.add_argument('--ratio', type=float, default=1.0,
                    help='正面須為負面的幾倍（預設 1.0，即正面不少於負面）')
    ap.add_argument('--show', type=int, default=0, help='列出前 N 家的原始片段')
    args = ap.parse_args()

    stats, qualified, names = collect(args.min_positive, args.ratio)

    print(f'提到停車／車位的店家：{len(stats)} 家')
    print(f'門檻：正面 >= {args.min_positive} 則，且正面 >= 負面 × {args.ratio}')
    print(f'符合「{TAG_NAME}」：{len(qualified)} 家\n')

    rows = sorted(stats.items(), key=lambda kv: (-kv[1]['pos'], kv[1]['neg']))
    print(f'{"":2s} {"店家":26s} {"正面":>4s} {"負面":>4s}')
    for cid, s in rows:
        mark = '✓' if cid in qualified else ' '
        name = (names.get(cid) or f'#{cid}')[:24]
        print(f'{mark}  {name:26s} {s["pos"]:>4d} {s["neg"]:>4d}')

    if args.show:
        print('\n--- 原始片段 ---')
        for cid, s in rows[:args.show]:
            print(f'\n{names.get(cid)}（正 {s["pos"]} / 負 {s["neg"]}）')
            for x in s['pos_s'][:4]:
                print(f'   ＋ {x}')
            for x in s['neg_s'][:4]:
                print(f'   － {x}')

    if args.apply:
        created, added, tag_id = apply_tag(qualified)
        print(f'\n已寫入：標籤「{TAG_NAME}」(tag_id={tag_id}, '
              f'{"新建" if created else "沿用既有"})，新增 {added} 家關聯')
    else:
        print('\n（未寫入。確認結果無誤後加上 --apply）')


if __name__ == '__main__':
    main()
