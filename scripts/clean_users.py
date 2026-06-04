import pymysql

# 資料庫設定
DB_HOST = 'localhost'
DB_USER = 'root'
DB_PASS = ''
DB_NAME = 'cafematch'

conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME)
cursor = conn.cursor()

print("🧹 開始清理舊的使用者資料...")
cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
cursor.execute("DROP TABLE IF EXISTS user_shop_state")
cursor.execute("DROP TABLE IF EXISTS quiz_history")
cursor.execute("DROP TABLE IF EXISTS users")
cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
print("✅ 清理完成！請繼續執行 app.py")
conn.close()