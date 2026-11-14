# 測試沙盒（只用來試新功能，不要合併進 main）

在正式機上開一份獨立副本：程式碼在另一個資料夾、資料庫是正式庫的複本（`<庫名>_sandbox`），
後端 5001／前端 5174。正式站（5000／5173、正式資料庫）完全不受影響。

```
cd /d C:\Users\IMBigData\Desktop\CafeMatch
git fetch origin sandbox/passport-blindbox
git worktree add ..\CafeMatch-test FETCH_HEAD
..\CafeMatch-test\scripts\sandbox\start_sandbox.bat
```

- 瀏覽器會自動以「沙盒測試帳號」登入並進到護照頁（沒做過測驗 → 盲盒隨機）。
- 用自己的帳號（有測驗結果 → 盲盒走 GNN）：`http://127.0.0.1:5001/sandbox-login?email=你的Gmail`
- 想回到正式站當下的資料重測：再跑一次 `start_sandbox.bat`（會重新複製）。

測完清理：

```
cd /d C:\Users\IMBigData\Desktop\CafeMatch
venv\Scripts\python.exe ..\CafeMatch-test\scripts\sandbox\copy_db.py --drop
git worktree remove --force ..\CafeMatch-test
```
