from authlib.integrations.flask_client import OAuth
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate

oauth = OAuth()
migrate = Migrate()

# 速率限制器（依用戶端 IP 限流）。
# 預設使用記憶體儲存，適合單一程序；正式環境多 worker 建議改用 Redis：
#   Limiter(key_func=get_remote_address, storage_uri="redis://localhost:6379")
limiter = Limiter(key_func=get_remote_address)
