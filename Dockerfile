# 1. 使用輕量級的 Python 映像
FROM python:3.10-slim

# 2. 設定工作目錄
WORKDIR /app

# 3. 安裝系統依賴（這是連線 MySQL 必備的編譯套件）
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 4. 複製依賴清單並安裝 Python 套件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 複製所有後端程式碼
COPY . .

# 6. 宣告程式執行的 Port (Flask 預設是 5000)
EXPOSE 5000

# 7. 啟動指令 (使用 Gunicorn 作為生產環境的伺服器，比 Flask 自帶的更穩定)
# 如果你還沒安裝 gunicorn，記得把它加進 requirements.txt
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]