# -*- coding: utf-8 -*-
"""
run_backend_service.py — 給服務／排程器託管用的後端啟動器

跟 `python app.py` 的差別：

  1. 不開 debug、不開 reloader
     app.py 的 app.run(debug=True) 會多生一個 reloader 子行程，
     實測行程鏈變成四層（cmd → python → python → python → python）。
     被服務託管時這會讓服務管理員抓不準該監看哪一個行程，
     停止服務時也容易留下孤兒。

  2. 日誌寫進檔案
     服務沒有主控台視窗，print 出去的東西會消失。
     這裡把 stdout/stderr 與 logging 都導到 logs/backend.log（輪替保留 5 份）。

  3. 用 waitress 而不是 Flask 內建伺服器
     內建的開發伺服器單執行緒、沒有連線佇列，長時間掛著跑並不合適。
     waitress 是純 Python 的 WSGI 伺服器，Windows 上可用。
     沒安裝時會退回 werkzeug 的 make_server（仍然關閉 debug），不會直接失敗。

用法：
    venv\\Scripts\\python.exe scripts\\run_backend_service.py
環境變數：
    BACKEND_PORT     監聽埠，預設 5000
    BACKEND_THREADS  waitress 的工作執行緒數，預設 8
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

LOG_DIR = os.path.join(ROOT, 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'backend.log')

PORT = int(os.getenv('BACKEND_PORT', '5000'))
THREADS = int(os.getenv('BACKEND_THREADS', '8'))


class _StreamToLog:
    """把 print 與 traceback 導進 logging，服務模式下才不會整段消失。"""

    def __init__(self, level):
        self._level = level
        self._buf = ''

    def write(self, text):
        self._buf += text
        while '\n' in self._buf:
            line, self._buf = self._buf.split('\n', 1)
            if line.strip():
                logging.log(self._level, line.rstrip())

    def flush(self):
        if self._buf.strip():
            logging.log(self._level, self._buf.rstrip())
        self._buf = ''

    def isatty(self):
        return False


def _setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8'
    )
    handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    ))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers[:] = [handler]

    # 服務沒有主控台，這兩條要接住，否則例外訊息會憑空消失
    sys.stdout = _StreamToLog(logging.INFO)
    sys.stderr = _StreamToLog(logging.ERROR)


def main():
    _setup_logging()
    logging.info('=' * 60)
    logging.info('後端啟動（服務模式）port=%s threads=%s', PORT, THREADS)

    from app import app

    try:
        from waitress import serve
    except ImportError:
        logging.warning('未安裝 waitress，退回 werkzeug 內建伺服器'
                        '（可用，但不適合長時間掛著跑；pip install waitress 即可改善）')
        from werkzeug.serving import make_server
        make_server('0.0.0.0', PORT, app, threaded=True).serve_forever()
        return

    serve(app, host='0.0.0.0', port=PORT, threads=THREADS,
          channel_timeout=300,          # 對話是串流回應，別太早切斷
          ident='CafeMatch')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        logging.exception('後端異常結束')
        raise
