"""全局配置常量"""

# 基础 URL
BASE_URL = "https://www.ali213.net/zt/LOL/wiki/"
HERO_LIST_URL = f"{BASE_URL}lolyx/"
EQUIP_LIST_URL = f"{BASE_URL}lolzb/"
RUNE_LIST_URL = f"{BASE_URL}lolfw/"

# 详情页 URL 模板
HERO_DETAIL_TMPL = f"{BASE_URL}yx{{id}}.html"
EQUIP_DETAIL_TMPL = f"{BASE_URL}zb{{id}}.html"
RUNE_DETAIL_TMPL = f"{BASE_URL}fw{{id}}.html"

# 各板块数量
HERO_COUNT = 153
EQUIP_COUNT = 162
RUNE_COUNT = 378 - HERO_COUNT - EQUIP_COUNT  # 63

# HTTP 请求控制
REQUEST_DELAY = 0.2       # 请求间隔（秒）
MAX_RETRIES = 3           # 最大重试次数
RETRY_BACKOFF = [1, 3, 5] # 退避时间（秒）
CONCURRENCY = 5           # 默认并发数
REQUEST_TIMEOUT = 30      # 单请求超时（秒）

# 输出路径
OUTPUT_DIR = "data"
HERO_OUTPUT_DIR = f"{OUTPUT_DIR}/heroes"
EQUIP_OUTPUT_DIR = f"{OUTPUT_DIR}/equipment"
RUNE_OUTPUT_DIR = f"{OUTPUT_DIR}/runes"
FETCH_RECORD_FILE = f"{OUTPUT_DIR}/.fetch_record.json"
