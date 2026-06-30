from datetime import datetime, timezone

DATE_FORMAT_STANDARD = '%Y-%m-%d %H:%M:%S'

def get_utc_now():
    return datetime.now(timezone.utc)

import os

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

ANALYSIS_KEYWORDS = [
    '安靜', '讀書', '工作', '約會', '聚會', '早午餐', '下午茶',
    '便宜', '平價', '文青', '氛圍', '環境', '貓', '寵物', '座位',
    'wifi', '插座', '不限時', '深夜', '拿鐵', '手沖', '甜點',
    '蛋糕', '司康', '可頌', '鬆餅', '花蓮', '台北', '信義',
    '中山', '大安', '松山', '中正', '萬華', '內湖'
]

# 店家無地址時，Google Places 查詢的預設地區字串
DEFAULT_PLACE_QUERY_REGION = '花蓮 咖啡廳'
