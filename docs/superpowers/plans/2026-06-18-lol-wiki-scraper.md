# LOL Wiki 资料抓取器 — 模块化实现文档

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从游侠网 LOL Wiki 抓取英雄/装备/符文资料，输出结构化 Markdown 文件用于 RAG 系统，支持断点续抓、并发控制、失败重试。

**Architecture:** 采用分层模块化设计，6 个核心模块各司其职。`Orchestrator` 作为顶层调度器组合各模块完成完整抓取流水线；`Fetcher` 封装 HTTP 并发与重试；`Parser` 采用策略模式按页面类型分发；`Repository` 管理抓取状态的持久化与查询；`Writer` 负责 Markdown 格式化与落盘；`CLI` 模块解析命令行参数并启动编排器。模块间通过明确的接口（函数签名/数据类）解耦。

**Tech Stack:** Python 3.10+, aiohttp, BeautifulSoup4, requests（仅用于初始首页探测）, dataclasses, argparse, logging

---

## 模块分解

```
src/
├── __init__.py
├── config.py              # 常量、URL 模板、默认设置
├── models.py              # 数据类定义（Hero, Equipment, Rune, FetchRecord）
├── fetcher.py             # HTTP 客户端：并发抓取、限速、重试
├── parser.py              # HTML 解析器：首页 → 详情页 URL 发现 + 内容提取
├── repository.py          # 抓取记录仓库：加载/保存/查询 fetch_record.json
├── writer.py              # Markdown 写入器：格式化数据类 → .md 文件
├── orchestrator.py        # 编排器：协调各模块完成完整流水线
└── cli.py                 # CLI 入口：argparse → 启动编排器
```

### 模块职责与接口

#### 1. `config.py` — 全局配置

**职责**：集中管理所有常量、URL 模板、默认参数，避免魔法数字散落各处。

| 常量 | 值 | 说明 |
|------|-----|------|
| `BASE_URL` | `https://www.ali213.net/zt/LOL/wiki/` | Wiki 首页 |
| `HERO_LIST_URL` | `.../lolyx/` | 英雄列表页 |
| `EQUIP_LIST_URL` | `.../lolzb/` | 装备列表页 |
| `RUNE_LIST_URL` | `.../lolfw/` | 符文列表页 |
| `HERO_DETAIL_TMPL` | `.../yx{id}.html` | 英雄详情 URL 模板 |
| `EQUIP_DETAIL_TMPL` | `.../zb{id}.html` | 装备详情 URL 模板 |
| `RUNE_DETAIL_TMPL` | `.../fw{id}.html` | 符文详情 URL 模板 |
| `HERO_COUNT` | 153 | 英雄总数 |
| `EQUIP_COUNT` | 162 | 装备总数 |
| `RUNE_COUNT` | 63 | 符文总数 |
| `REQUEST_DELAY` | 0.2 | 请求间隔（秒） |
| `MAX_RETRIES` | 3 | 最大重试次数 |
| `RETRY_BACKOFF` | [1, 3, 5] | 重试退避时间（秒） |
| `CONCURRENCY` | 5 | 并发请求数上限 |
| `OUTPUT_DIR` | `data/` | 输出根目录 |
| `FETCH_RECORD_FILE` | `data/.fetch_record.json` | 抓取记录文件路径 |

#### 2. `models.py` — 数据模型

**职责**：定义所有数据类，作为模块间传递的数据契约。

```python
@dataclass
class Hero:
    name_cn: str           # 中文名（如"祖安怒兽"）
    name_en: str           # 英文名（如"沃里克"）
    title: str             # 标题
    image_url: str         # 图片 URL
    role: str              # 定位（如"战士"）
    background: str        # 背景故事
    initial_attrs: dict    # 初始属性 {"攻击力": 65, "攻击速度": 0.67, ...}
    max_attrs: dict        # 满级属性
    passive_skill: Skill   # 被动技能
    skills: list[Skill]    # Q/W/E/R 技能
    source_url: str        # 来源 URL
    fetched_at: str        # 抓取时间 ISO 8601

@dataclass
class Skill:
    name: str
    icon_url: str
    description: str
    cost: str | None       # 技能消耗（仅 Q/W/E/R）
    cooldown: str | None   # 冷却时间（仅 Q/W/E/R）
    range: str | None      # 施法范围（仅 Q/W/E/R）

@dataclass
class Equipment:
    name: str
    icon_url: str
    tier: str              # 等级（如"传说"）
    price: str             # 售价
    base_attrs: list[str]  # 基础属性列表
    active_effect: str | None
    passive_effect: str | None
    mythic_bonus: str | None
    recipe: list[str]      # 合成路线
    recommended_heroes: list[str]  # 推荐英雄
    source_url: str
    fetched_at: str

@dataclass
class Rune:
    name: str
    icon_url: str
    category: str          # 所属类别（如"精密"）
    tier: str              # 符文等级（如"基石"）
    description: str       # 效果描述
    source_url: str
    fetched_at: str

@dataclass
class FetchRecord:
    url: str
    category: str          # "heroes" | "equipment" | "runes"
    name: str | None
    output_file: str | None
    fetched_at: str | None
    status: str            # "success" | "failed"
    error: str | None
    retries: int
    last_attempt: str | None
```

#### 3. `fetcher.py` — HTTP 抓取器

**职责**：
- 封装 aiohttp 异步 HTTP 请求
- 实现令牌桶 / 信号量控制的请求间延迟（≥0.2s）
- 单 URL 失败自动重试（退避 1s/3s/5s），最多 3 次
- 返回 `(url, html_text_or_None, error_or_None)` 三元组

**公开接口**：

```python
class Fetcher:
    def __init__(self, delay: float = REQUEST_DELAY,
                 max_retries: int = MAX_RETRIES,
                 backoff: list[float] | None = None,
                 concurrency: int = CONCURRENCY): ...
    async def fetch_one(self, session: aiohttp.ClientSession, url: str) -> FetchResult: ...
    async def fetch_all(self, urls: list[str]) -> list[FetchResult]: ...
```

`FetchResult = tuple[str, str | None, str | None]` — `(url, html, error)`

**核心逻辑**：

```
fetch_all(urls)
  ├── 创建 aiohttp.ClientSession（带超时 30s）
  ├── 使用 asyncio.Semaphore(concurrency) 控制并发
  ├── 对每个 URL 调用 fetch_one
  │     ├── 尝试 GET 请求
  │     ├── 成功 → 返回 (url, html, None)
  │     ├── 失败 → 按 backoff 退避重试
  │     │         ├── 成功 → 返回 (url, html, None)
  │     │         └── 耗尽重试 → 返回 (url, None, error_msg)
  │     └── 每次请求后 asyncio.sleep(delay)
  └── 返回 List[FetchResult]
```

#### 4. `parser.py` — HTML 解析器

**职责**：
- 从列表页解析详情页 URL（备用：若直接构造 URL 不可用）
- 从详情页 HTML 提取结构化数据（BeautifulSoup4）
- 每种页面类型一个解析函数，返回对应的 dataclass

**公开接口**：

```python
def parse_hero_page(html: str, url: str, fetched_at: str) -> Hero | None: ...
def parse_equip_page(html: str, url: str, fetched_at: str) -> Equipment | None: ...
def parse_rune_page(html: str, url: str, fetched_at: str) -> Rune | None: ...
def parse_list_page_urls(html: str, base_url: str) -> list[str]: ...
```

**解析策略**（因网站结构可能变化，采用 CSS 选择器 + 容错返回）：

```
parse_hero_page(html, url, fetched_at)
  ├── soup = BeautifulSoup(html, "html.parser")
  ├── 定位主体内容区（按页面实际选择器）
  ├── 提取各字段 → 构造 Hero 实例
  │     ├── name_cn, title, image_url → 头部信息区
  │     ├── name_en, role → 属性表
  │     ├── background → 背景故事段落
  │     ├── initial_attrs → "初始属性"表 → dict
  │     ├── max_attrs → "满级属性"表 → dict
  │     ├── passive_skill → 被动技能区块 → Skill
  │     └── skills → Q/W/E/R 区块列表 → list[Skill]
  └── 缺失字段填 None，不抛异常
```

#### 5. `repository.py` — 抓取记录仓库

**职责**：
- 加载/保存 `data/.fetch_record.json`
- 提供查询接口：判断 URL 是否需要抓取
- 更新单条记录的状态

**公开接口**：

```python
class FetchRepository:
    def __init__(self, record_path: str = FETCH_RECORD_FILE): ...
    def load(self) -> dict[str, dict]: ...            # 从文件加载
    def save(self) -> None: ...                       # 写回文件
    def should_fetch(self, url: str, force: bool = False) -> bool: ...
    def record_success(self, url: str, category: str, name: str, output_file: str) -> None: ...
    def record_failure(self, url: str, category: str, error: str) -> None: ...
    def get_pending_urls(self, urls: list[str], force: bool = False) -> list[str]: ...
```

**should_fetch 决策逻辑**：

```
should_fetch(url, force=False):
  if force: return True
  if url not in records: return True
  rec = records[url]
  if rec.status == "success":
      return not os.path.exists(rec.output_file)  # 文件缺失则重抓
  if rec.status == "failed":
      return rec.retries < MAX_RETRIES              # 未达重试上限
  return True
```

#### 6. `writer.py` — Markdown 写入器

**职责**：
- 将数据类实例格式化为 Markdown 字符串
- 写入对应目录的文件
- 末尾附加来源 URL 和抓取时间元数据

**公开接口**：

```python
def hero_to_markdown(hero: Hero) -> str: ...
def equip_to_markdown(equip: Equipment) -> str: ...
def rune_to_markdown(rune: Rune) -> str: ...
def write_markdown(content: str, filepath: str) -> None: ...
```

**Markdown 模板（英雄示例）**：

```markdown
# 祖安怒兽 — 沃里克

![祖安怒兽](https://...image_url)

**定位**: 战士

---

## 背景故事

沃里克是祖安城中一个...

---

## 属性

| 属性 | 初始值 | 满级值 |
|------|--------|--------|
| 攻击力 | 65 | 115 |
| 攻击速度 | 0.67 | 1.05 |
| ... | ... | ... |

---

## 技能

### 被动：血之饥渴

![被动](https://...icon_url)

沃里克的普通攻击造成额外魔法伤害...

### Q：野兽之口

- **消耗**: 50/60/70/80/90 法力
- **冷却**: 6秒
- **范围**: 350

沃里克向前猛扑...

---

> 来源: <https://www.ali213.net/zt/LOL/wiki/yx1.html>  
> 抓取时间: 2026-06-18T10:30:00+08:00
```

#### 7. `orchestrator.py` — 编排器

**职责**：
- 组合 Fetcher / Parser / Repository / Writer 完成端到端流水线
- 控制执行顺序：加载记录 → 判断待抓取 → 并发抓取 → 逐页解析 → 写入文件 → 更新记录
- 输出进度日志和最终统计

**公开接口**：

```python
class Orchestrator:
    def __init__(self, force: bool = False): ...
    async def run(self) -> dict: ...   # 返回统计 {"total": N, "success": N, "failed": N, "skipped": N}
```

**流水线流程**：

```
run()
  ├── 1. repo.load() 加载历史记录
  ├── 2. 生成全量 URL 列表（hero 1..153, equip 1..162, rune 1..63）
  ├── 3. repo.get_pending_urls() 过滤出待抓取 URL
  ├── 4. fetcher.fetch_all(pending_urls) 并发抓取 HTML
  ├── 5. 对每个成功结果：
  │     ├── 根据 URL 模式选择解析器（parse_hero/equip/rune）
  │     ├── 解析得数据类实例
  │     ├── 调用对应 to_markdown() 生成内容
  │     ├── writer.write_markdown() 落盘
  │     └── repo.record_success() 更新记录
  ├── 6. 对每个失败结果：
  │     └── repo.record_failure() 记录失败信息
  ├── 7. repo.save() 持久化记录
  └── 8. 返回统计摘要
```

#### 8. `cli.py` — 命令行入口

**职责**：argparse 解析参数，启动 Orchestrator。

```python
# 用法
python -m src.cli              # 普通模式，跳过已成功
python -m src.cli --force       # 强制重新抓取全部
python -m src.cli --category heroes  # 只抓取指定板块
python -m src.cli --concurrency 10   # 自定义并发数
```

---

## 输出目录结构

```
data/
├── heroes/
│   ├── 黑暗之女.md
│   ├── 狂战士.md
│   └── ...（153 个文件）
├── equipment/
│   ├── 冰霜之心.md
│   └── ...（162 个文件）
├── runes/
│   ├── 强攻.md
│   └── ...（63 个文件）
└── .fetch_record.json
```

---

## 任务分解

### Task 1: 项目骨架搭建

**Files:**
- Create: `src/__init__.py`
- Create: `src/config.py`
- Create: `src/models.py`
- Create: `requirements.txt`

- [ ] **Step 1: 创建 requirements.txt**

```
aiohttp>=3.9.0
beautifulsoup4>=4.12.0
```

- [ ] **Step 2: 创建 src/__init__.py**

```python
"""LOL Wiki Scraper — RAG 资料数据源构建工具"""
```

- [ ] **Step 3: 创建 src/config.py**

```python
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
RUNE_COUNT = 378 - HERO_COUNT - EQUIP_COUNT  # 63，保持与需求一致

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
```

- [ ] **Step 4: 创建 src/models.py**

```python
"""数据模型定义"""

from dataclasses import dataclass, field


@dataclass
class Skill:
    name: str
    icon_url: str
    description: str
    cost: str | None = None
    cooldown: str | None = None
    range: str | None = None


@dataclass
class Hero:
    name_cn: str
    name_en: str
    title: str
    image_url: str
    role: str
    background: str
    initial_attrs: dict[str, str]
    max_attrs: dict[str, str]
    passive_skill: Skill | None
    skills: list[Skill] = field(default_factory=list)
    source_url: str = ""
    fetched_at: str = ""


@dataclass
class Equipment:
    name: str
    icon_url: str
    tier: str
    price: str
    base_attrs: list[str] = field(default_factory=list)
    active_effect: str | None = None
    passive_effect: str | None = None
    mythic_bonus: str | None = None
    recipe: list[str] = field(default_factory=list)
    recommended_heroes: list[str] = field(default_factory=list)
    source_url: str = ""
    fetched_at: str = ""


@dataclass
class Rune:
    name: str
    icon_url: str
    category: str
    tier: str
    description: str
    source_url: str = ""
    fetched_at: str = ""


@dataclass
class FetchRecord:
    url: str
    category: str
    name: str | None = None
    output_file: str | None = None
    fetched_at: str | None = None
    status: str = "pending"
    error: str | None = None
    retries: int = 0
    last_attempt: str | None = None

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "name": self.name,
            "output_file": self.output_file,
            "fetched_at": self.fetched_at,
            "status": self.status,
            "error": self.error,
            "retries": self.retries,
            "last_attempt": self.last_attempt,
        }

    @classmethod
    def from_dict(cls, url: str, data: dict) -> "FetchRecord":
        return cls(url=url, **data)
```

- [ ] **Step 5: 安装依赖**

```bash
pip install -r requirements.txt
```

- [ ] **Step 6: Commit**

```bash
git add src/__init__.py src/config.py src/models.py requirements.txt
git commit -m "feat: add project skeleton — config, models, dependencies"
```

---

### Task 2: Fetcher 模块 — HTTP 并发抓取

**Files:**
- Create: `src/fetcher.py`
- Create: `tests/test_fetcher.py`

- [ ] **Step 1: 编写失败测试（mock aiohttp）**

```python
# tests/test_fetcher.py
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from src.fetcher import Fetcher
from src.config import MAX_RETRIES, RETRY_BACKOFF


class TestFetcher:
    @pytest.mark.asyncio
    async def test_fetch_one_success(self):
        fetcher = Fetcher(delay=0)
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.text = AsyncMock(return_value="<html>hero page</html>")

        mock_session = MagicMock()
        mock_session.get = MagicMock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

        url, html, error = await fetcher.fetch_one(mock_session, "http://test.com/yx1.html")
        assert url == "http://test.com/yx1.html"
        assert html == "<html>hero page</html>"
        assert error is None

    @pytest.mark.asyncio
    async def test_fetch_one_retry_then_success(self):
        fetcher = Fetcher(delay=0, max_retries=3, backoff=[0, 0, 0])
        fail_resp = MagicMock()
        fail_resp.status = 500
        ok_resp = MagicMock()
        ok_resp.status = 200
        ok_resp.text = AsyncMock(return_value="<html>ok</html>")

        mock_session = MagicMock()
        call_count = [0]

        async def mock_get(url):
            call_count[0] += 1
            resp = ok_resp if call_count[0] == 3 else fail_resp

            class _CtxMgr:
                async def __aenter__(self): return resp
                async def __aexit__(self, *a): pass
            return _CtxMgr()

        mock_session.get = mock_get

        url, html, error = await fetcher.fetch_one(mock_session, "http://test.com/yx1.html")
        assert html == "<html>ok</html>"
        assert error is None
        assert call_count[0] == 3

    @pytest.mark.asyncio
    async def test_fetch_one_all_retries_fail(self):
        fetcher = Fetcher(delay=0, max_retries=2, backoff=[0, 0])
        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Connection error")

        url, html, error = await fetcher.fetch_one(mock_session, "http://test.com/yx1.html")
        assert html is None
        assert "Connection error" in error

    @pytest.mark.asyncio
    async def test_fetch_all_concurrency(self):
        fetcher = Fetcher(delay=0, concurrency=3)
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.text = AsyncMock(return_value="<html>x</html>")

        urls = [f"http://test.com/yx{i}.html" for i in range(10)]

        async def fetch_one(session, url):
            return (url, f"html_{url}", None)

        fetcher.fetch_one = fetch_one
        results = await fetcher.fetch_all(urls)
        assert len(results) == 10
        assert all(r[1] is not None for r in results)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_fetcher.py -v
```
预期: FAIL — `src.fetcher` 模块不存在

- [ ] **Step 3: 实现 src/fetcher.py**

```python
"""HTTP 并发抓取模块：限速、重试、并发控制"""

import asyncio
import logging
import aiohttp
from src.config import REQUEST_DELAY, MAX_RETRIES, RETRY_BACKOFF, CONCURRENCY, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


class Fetcher:
    def __init__(
        self,
        delay: float = REQUEST_DELAY,
        max_retries: int = MAX_RETRIES,
        backoff: list[float] | None = None,
        concurrency: int = CONCURRENCY,
    ):
        self.delay = delay
        self.max_retries = max_retries
        self.backoff = backoff or RETRY_BACKOFF
        self.concurrency = concurrency
        self._semaphore = asyncio.Semaphore(concurrency)
        self._last_request_time = 0.0

    async def _rate_limit(self):
        """确保请求间隔 ≥ delay 秒"""
        now = asyncio.get_event_loop().time()
        wait = self._last_request_time + self.delay - now
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_request_time = asyncio.get_event_loop().time()

    async def fetch_one(
        self, session: aiohttp.ClientSession, url: str
    ) -> tuple[str, str | None, str | None]:
        """抓取单个 URL，失败自动重试。返回 (url, html | None, error | None)。"""
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                await self._rate_limit()
                async with self._semaphore:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as resp:
                        if resp.status == 200:
                            html = await resp.text()
                            logger.debug(f"✓ {url} ({attempt + 1} attempts)")
                            return (url, html, None)
                        else:
                            last_error = f"HTTP {resp.status}"
            except asyncio.TimeoutError:
                last_error = "Timeout"
            except aiohttp.ClientError as e:
                last_error = str(e)
            except Exception as e:
                last_error = f"Unexpected: {e}"

            if attempt < self.max_retries:
                wait = self.backoff[min(attempt, len(self.backoff) - 1)]
                logger.warning(f"✗ {url} (attempt {attempt + 1}/{self.max_retries + 1}): {last_error}, retrying in {wait}s")
                await asyncio.sleep(wait)

        logger.error(f"✗ {url}: FAILED after {self.max_retries + 1} attempts — {last_error}")
        return (url, None, last_error)

    async def fetch_all(self, urls: list[str]) -> list[tuple[str, str | None, str | None]]:
        """并发抓取所有 URL。"""
        logger.info(f"Starting fetch of {len(urls)} URLs (concurrency={self.concurrency})")
        connector = aiohttp.TCPConnector(limit=self.concurrency)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [self.fetch_one(session, url) for url in urls]
            results = await asyncio.gather(*tasks)
        return list(results)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_fetcher.py -v
```
预期: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/fetcher.py tests/test_fetcher.py
git commit -m "feat: add fetcher module with rate limiting and retry"
```

---

### Task 3: Repository 模块 — 抓取记录管理

**Files:**
- Create: `src/repository.py`
- Create: `tests/test_repository.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_repository.py
import json
import os
import tempfile
import pytest
from src.repository import FetchRepository


class TestFetchRepository:
    @pytest.fixture
    def repo(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, ".fetch_record.json")
        repo = FetchRepository(record_path=path)
        yield repo
        if os.path.exists(path):
            os.remove(path)
        os.rmdir(tmp)

    def test_should_fetch_new_url(self, repo):
        assert repo.should_fetch("http://test.com/yx1.html") is True

    def test_should_fetch_force(self, repo):
        repo.record_success("http://test.com/yx1.html", "heroes", "安妮", "/tmp/安妮.md")
        assert repo.should_fetch("http://test.com/yx1.html", force=True) is True

    def test_should_skip_success_with_existing_file(self, repo):
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            path = f.name
        try:
            repo.record_success("http://test.com/yx1.html", "heroes", "安妮", path)
            assert repo.should_fetch("http://test.com/yx1.html") is False
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_should_refetch_if_file_missing(self, repo):
        repo.record_success("http://test.com/yx1.html", "heroes", "安妮", "/nonexistent/安妮.md")
        assert repo.should_fetch("http://test.com/yx1.html") is True

    def test_should_retry_failed_under_limit(self, repo):
        repo.record_failure("http://test.com/yx1.html", "heroes", "Timeout")
        repo.records["http://test.com/yx1.html"].retries = 1
        assert repo.should_fetch("http://test.com/yx1.html") is True

    def test_should_skip_failed_at_limit(self, repo):
        repo.record_failure("http://test.com/yx1.html", "heroes", "Timeout")
        repo.records["http://test.com/yx1.html"].retries = 3
        assert repo.should_fetch("http://test.com/yx1.html") is False

    def test_get_pending_urls(self, repo):
        urls = ["http://test.com/yx1.html", "http://test.com/yx2.html"]
        repo.record_success("http://test.com/yx2.html", "heroes", "盖伦", "/tmp/盖伦.md")
        pending = repo.get_pending_urls(urls)
        assert pending == ["http://test.com/yx1.html"]

    def test_save_and_reload(self, repo):
        repo.record_success("http://test.com/yx1.html", "heroes", "安妮", "/tmp/安妮.md")
        repo.save()

        repo2 = FetchRepository(record_path=repo._record_path)
        repo2.load()
        assert repo2.should_fetch("http://test.com/yx1.html") is False  # file exists? will fail without actual file
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_repository.py -v
```
预期: FAIL

- [ ] **Step 3: 实现 src/repository.py**

```python
"""抓取记录仓库：持久化抓取状态到 JSON 文件"""

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from src.config import FETCH_RECORD_FILE, MAX_RETRIES
from src.models import FetchRecord

logger = logging.getLogger(__name__)

# 东八区
TZ = timezone(timedelta(hours=8))


def _now() -> str:
    return datetime.now(TZ).isoformat()


class FetchRepository:
    def __init__(self, record_path: str = FETCH_RECORD_FILE):
        self._record_path = record_path
        self.records: dict[str, FetchRecord] = {}

    def load(self) -> None:
        """从 JSON 文件加载抓取记录。"""
        if not os.path.exists(self._record_path):
            logger.info(f"No existing fetch record at {self._record_path}, starting fresh.")
            self.records = {}
            return
        with open(self._record_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        self.records = {url: FetchRecord.from_dict(url, data) for url, data in raw.items()}
        logger.info(f"Loaded {len(self.records)} fetch records from {self._record_path}")

    def save(self) -> None:
        """将抓取记录写回 JSON 文件。"""
        os.makedirs(os.path.dirname(self._record_path), exist_ok=True)
        data = {url: rec.to_dict() for url, rec in self.records.items()}
        with open(self._record_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(self.records)} fetch records to {self._record_path}")

    def should_fetch(self, url: str, force: bool = False) -> bool:
        """判断一个 URL 是否需要抓取。"""
        if force:
            return True
        if url not in self.records:
            return True

        rec = self.records[url]
        if rec.status == "success":
            if rec.output_file and os.path.exists(rec.output_file):
                return False
            return True
        if rec.status == "failed":
            return rec.retries < MAX_RETRIES
        return True

    def get_pending_urls(self, urls: list[str], force: bool = False) -> list[str]:
        """从 URL 列表中过滤出待抓取的 URL。"""
        pending = [u for u in urls if self.should_fetch(u, force)]
        logger.info(
            f"URL filtering: {len(urls)} total → {len(pending)} pending "
            f"({len(urls) - len(pending)} skipped)"
        )
        return pending

    def record_success(
        self, url: str, category: str, name: str, output_file: str
    ) -> None:
        """记录一次成功抓取。"""
        now = _now()
        if url in self.records:
            rec = self.records[url]
            rec.status = "success"
            rec.name = name
            rec.output_file = output_file
            rec.fetched_at = now
            rec.error = None
        else:
            self.records[url] = FetchRecord(
                url=url, category=category, name=name,
                output_file=output_file, fetched_at=now,
                status="success",
            )

    def record_failure(self, url: str, category: str, error: str) -> None:
        """记录一次失败抓取。"""
        now = _now()
        if url in self.records:
            rec = self.records[url]
            rec.status = "failed"
            rec.error = error
            rec.retries += 1
            rec.last_attempt = now
        else:
            self.records[url] = FetchRecord(
                url=url, category=category, status="failed",
                error=error, retries=1, last_attempt=now,
            )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_repository.py -v
```
预期: 8 passed（注意: `test_save_and_reload` 中 `should_fetch` 检查文件存在会返回 True 因为路径 `/tmp/安妮.md` 不存在，需要微调断言）

更新测试 `test_save_and_reload`:

```python
    def test_save_and_reload(self, repo):
        repo.record_success("http://test.com/yx1.html", "heroes", "安妮", "/tmp/安妮.md")
        repo.save()

        repo2 = FetchRepository(record_path=repo._record_path)
        repo2.load()
        assert "http://test.com/yx1.html" in repo2.records
        assert repo2.records["http://test.com/yx1.html"].status == "success"
        assert repo2.records["http://test.com/yx1.html"].name == "安妮"
```

- [ ] **Step 5: Commit**

```bash
git add src/repository.py tests/test_repository.py
git commit -m "feat: add fetch record repository with persistence"
```

---

### Task 4: Writer 模块 — Markdown 格式化与写入

**Files:**
- Create: `src/writer.py`
- Create: `tests/test_writer.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_writer.py
import os
import tempfile
import pytest
from src.writer import hero_to_markdown, equip_to_markdown, rune_to_markdown, write_markdown, sanitize_filename
from src.models import Hero, Equipment, Rune, Skill


class TestSanitizeFilename:
    def test_removes_slashes(self):
        assert sanitize_filename("a/b") == "ab"

    def test_keeps_chinese(self):
        assert sanitize_filename("黑暗之女") == "黑暗之女"

    def test_removes_other_special_chars(self):
        cleaned = sanitize_filename('test<>:"/\\|?*file')
        assert ">" not in cleaned
        assert "<" not in cleaned
        assert '"' not in cleaned


class TestHeroToMarkdown:
    def test_full_hero(self):
        hero = Hero(
            name_cn="祖安怒兽",
            name_en="沃里克",
            title="祖安怒兽 沃里克",
            image_url="https://example.com/warwick.png",
            role="战士",
            background="沃里克是祖安城中一个传奇人物。",
            initial_attrs={"攻击力": "65", "生命值": "620"},
            max_attrs={"攻击力": "115", "生命值": "2268"},
            passive_skill=Skill(name="血之饥渴", icon_url="https://x.com/p.png",
                                description="普攻造成额外魔法伤害"),
            skills=[Skill(name="野兽之口", icon_url="https://x.com/q.png",
                          description="向前猛扑", cost="50/60/70/80/90 法力",
                          cooldown="6秒", range="350")],
            source_url="https://www.ali213.net/zt/LOL/wiki/yx1.html",
            fetched_at="2026-06-18T10:30:00+08:00",
        )
        md = hero_to_markdown(hero)
        assert "# 祖安怒兽 — 沃里克" in md
        assert "![祖安怒兽](https://example.com/warwick.png)" in md
        assert "**定位**: 战士" in md
        assert "## 背景故事" in md
        assert "沃里克是祖安城中一个传奇人物。" in md
        assert "| 攻击力 | 65 | 115 |" in md
        assert "### 被动：血之饥渴" in md
        assert "### Q：野兽之口" in md
        assert "**冷却**: 6秒" in md
        assert "**范围**: 350" in md
        assert "来源: <https://www.ali213.net/zt/LOL/wiki/yx1.html>" in md
        assert "抓取时间: 2026-06-18T10:30:00+08:00" in md

    def test_hero_no_passive(self):
        hero = Hero(
            name_cn="测试", name_en="Test", title="测试英雄",
            image_url="", role="法师", background="",
            initial_attrs={}, max_attrs={},
            passive_skill=None, skills=[],
            source_url="http://x.com", fetched_at="2026-01-01T00:00:00+08:00",
        )
        md = hero_to_markdown(hero)
        assert "## 技能" not in md  # no skills section if empty
        assert "## 属性" not in md  # no attrs section if empty
        assert "测试英雄" in md


class TestEquipToMarkdown:
    def test_full_equip(self):
        equip = Equipment(
            name="冰霜之心",
            icon_url="https://x.com/ice.png",
            tier="传说",
            price="2700",
            base_attrs=["+400 法力值", "+20 技能急速", "+50 护甲"],
            active_effect=None,
            passive_effect="坚如磐石：使受到的伤害减少",
            mythic_bonus="+5 技能急速",
            recipe=["冰川圆盾", "守望者铠甲", "900 金币"],
            recommended_heroes=["盖伦", "德莱厄斯"],
            source_url="https://www.ali213.net/zt/LOL/wiki/zb1.html",
            fetched_at="2026-06-18T10:30:00+08:00",
        )
        md = equip_to_markdown(equip)
        assert "# 冰霜之心" in md
        assert "**等级**: 传说" in md
        assert "**售价**: 2700" in md
        assert "+400 法力值" in md
        assert "### 被动效果" in md
        assert "坚如磐石" in md
        assert "### 神话加成" in md
        assert "### 合成路线" in md
        assert "冰川圆盾" in md
        assert "### 推荐英雄" in md
        assert "盖伦" in md


class TestRuneToMarkdown:
    def test_full_rune(self):
        rune = Rune(
            name="强攻",
            icon_url="https://x.com/pta.png",
            category="精密",
            tier="基石",
            description="用3次连续的普攻命中一名敌方英雄",
            source_url="https://www.ali213.net/zt/LOL/wiki/fw1.html",
            fetched_at="2026-06-18T10:30:00+08:00",
        )
        md = rune_to_markdown(rune)
        assert "# 强攻" in md
        assert "**类别**: 精密" in md
        assert "**等级**: 基石" in md
        assert "用3次连续的普攻命中一名敌方英雄" in md
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_writer.py -v
```
预期: FAIL

- [ ] **Step 3: 实现 src/writer.py**

```python
"""Markdown 格式化与文件写入"""

import os
import re
import logging
from src.models import Hero, Equipment, Rune

logger = logging.getLogger(__name__)

# 文件名中不允许的字符
_FILENAME_ILLEGAL = re.compile(r'[<>:"/\\|?*]')


def sanitize_filename(name: str) -> str:
    """清理文件名，移除非法字符。"""
    return _FILENAME_ILLEGAL.sub("", name).strip()


def hero_to_markdown(hero: Hero) -> str:
    """将 Hero 数据类格式化为 Markdown 字符串。"""
    lines = []
    lines.append(f"# {hero.name_cn} — {hero.name_en}")
    lines.append("")
    if hero.image_url:
        lines.append(f"![{hero.name_cn}]({hero.image_url})")
        lines.append("")
    if hero.role:
        lines.append(f"**定位**: {hero.role}")
        lines.append("")
    lines.append("---")
    lines.append("")

    if hero.background:
        lines.append("## 背景故事")
        lines.append("")
        lines.append(hero.background)
        lines.append("")

    if hero.initial_attrs or hero.max_attrs:
        lines.append("## 属性")
        lines.append("")
        lines.append("| 属性 | 初始值 | 满级值 |")
        lines.append("|------|--------|--------|")
        all_keys = set(hero.initial_attrs.keys()) | set(hero.max_attrs.keys())
        for key in sorted(all_keys):
            init = hero.initial_attrs.get(key, "—")
            maxv = hero.max_attrs.get(key, "—")
            lines.append(f"| {key} | {init} | {maxv} |")
        lines.append("")

    skills = []
    if hero.passive_skill:
        skills.append(("被动", hero.passive_skill))
    for i, s in enumerate(hero.skills):
        label = ["Q", "W", "E", "R"][i] if i < 4 else f"技能{i + 1}"
        skills.append((label, s))

    if skills:
        lines.append("## 技能")
        lines.append("")
        for label, s in skills:
            lines.append(f"### {label}：{s.name}")
            lines.append("")
            if s.icon_url:
                lines.append(f"![{s.name}]({s.icon_url})")
                lines.append("")
            if s.cost:
                lines.append(f"- **消耗**: {s.cost}")
            if s.cooldown:
                lines.append(f"- **冷却**: {s.cooldown}")
            if s.range:
                lines.append(f"- **范围**: {s.range}")
            if s.cost or s.cooldown or s.range:
                lines.append("")
            lines.append(s.description)
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"> 来源: <{hero.source_url}>  ")
    lines.append(f"> 抓取时间: {hero.fetched_at}  ")
    lines.append("")
    return "\n".join(lines)


def equip_to_markdown(equip: Equipment) -> str:
    """将 Equipment 数据类格式化为 Markdown 字符串。"""
    lines = [f"# {equip.name}", ""]
    if equip.icon_url:
        lines.append(f"![{equip.name}]({equip.icon_url})")
        lines.append("")
    lines.append(f"**等级**: {equip.tier}")
    lines.append(f"**售价**: {equip.price}")
    lines.append("")
    lines.append("---")
    lines.append("")

    if equip.base_attrs:
        lines.append("## 基础属性")
        lines.append("")
        for attr in equip.base_attrs:
            lines.append(f"- {attr}")
        lines.append("")

    if equip.active_effect:
        lines.append("## 主动效果")
        lines.append("")
        lines.append(equip.active_effect)
        lines.append("")

    if equip.passive_effect:
        lines.append("## 被动效果")
        lines.append("")
        lines.append(equip.passive_effect)
        lines.append("")

    if equip.mythic_bonus:
        lines.append("## 神话加成")
        lines.append("")
        lines.append(equip.mythic_bonus)
        lines.append("")

    if equip.recipe:
        lines.append("## 合成路线")
        lines.append("")
        for item in equip.recipe:
            lines.append(f"- {item}")
        lines.append("")

    if equip.recommended_heroes:
        lines.append("## 推荐英雄")
        lines.append("")
        lines.append("、".join(equip.recommended_heroes))
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"> 来源: <{equip.source_url}>  ")
    lines.append(f"> 抓取时间: {equip.fetched_at}  ")
    lines.append("")
    return "\n".join(lines)


def rune_to_markdown(rune: Rune) -> str:
    """将 Rune 数据类格式化为 Markdown 字符串。"""
    lines = [f"# {rune.name}", ""]
    if rune.icon_url:
        lines.append(f"![{rune.name}]({rune.icon_url})")
        lines.append("")
    lines.append(f"**类别**: {rune.category}")
    lines.append(f"**等级**: {rune.tier}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 效果")
    lines.append("")
    lines.append(rune.description)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"> 来源: <{rune.source_url}>  ")
    lines.append(f"> 抓取时间: {rune.fetched_at}  ")
    lines.append("")
    return "\n".join(lines)


def write_markdown(content: str, filepath: str) -> None:
    """将 Markdown 内容写入文件。"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    logger.debug(f"Written: {filepath}")
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_writer.py -v
```
预期: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/writer.py tests/test_writer.py
git commit -m "feat: add markdown writer with hero/equip/rune formatters"
```

---

### Task 5: URL 构造与分派工具

**Files:**
- Create: `src/url_builder.py`
- Create: `tests/test_url_builder.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_url_builder.py
import pytest
from src.url_builder import (
    build_hero_urls, build_equip_urls, build_rune_urls,
    build_all_urls, detect_category, get_category_dir,
)


class TestUrlBuilder:
    def test_build_hero_urls(self):
        urls = build_hero_urls()
        assert len(urls) == 153
        assert urls[0] == "https://www.ali213.net/zt/LOL/wiki/yx1.html"
        assert urls[-1] == "https://www.ali213.net/zt/LOL/wiki/yx153.html"

    def test_build_equip_urls(self):
        urls = build_equip_urls()
        assert len(urls) == 162
        assert urls[0] == "https://www.ali213.net/zt/LOL/wiki/zb1.html"

    def test_build_rune_urls(self):
        urls = build_rune_urls()
        assert len(urls) == 63
        assert urls[0] == "https://www.ali213.net/zt/LOL/wiki/fw1.html"

    def test_build_all_urls(self):
        hero, equip, rune = build_all_urls()
        assert len(hero) == 153
        assert len(equip) == 162
        assert len(rune) == 63

    def test_detect_category(self):
        assert detect_category("https://www.ali213.net/zt/LOL/wiki/yx1.html") == "heroes"
        assert detect_category("https://www.ali213.net/zt/LOL/wiki/zb99.html") == "equipment"
        assert detect_category("https://www.ali213.net/zt/LOL/wiki/fw5.html") == "runes"

    def test_detect_category_unknown(self):
        with pytest.raises(ValueError, match="Unknown category"):
            detect_category("https://www.ali213.net/zt/LOL/wiki/other.html")

    def test_get_category_dir(self):
        from src import config
        assert get_category_dir("heroes") == config.HERO_OUTPUT_DIR
        assert get_category_dir("equipment") == config.EQUIP_OUTPUT_DIR
        assert get_category_dir("runes") == config.RUNE_OUTPUT_DIR
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_url_builder.py -v
```
预期: FAIL

- [ ] **Step 3: 实现 src/url_builder.py**

```python
"""URL 构造与分类工具"""

from src.config import (
    HERO_DETAIL_TMPL, EQUIP_DETAIL_TMPL, RUNE_DETAIL_TMPL,
    HERO_COUNT, EQUIP_COUNT, RUNE_COUNT,
    HERO_OUTPUT_DIR, EQUIP_OUTPUT_DIR, RUNE_OUTPUT_DIR,
)


def build_hero_urls() -> list[str]:
    return [HERO_DETAIL_TMPL.format(id=i) for i in range(1, HERO_COUNT + 1)]


def build_equip_urls() -> list[str]:
    return [EQUIP_DETAIL_TMPL.format(id=i) for i in range(1, EQUIP_COUNT + 1)]


def build_rune_urls() -> list[str]:
    return [RUNE_DETAIL_TMPL.format(id=i) for i in range(1, RUNE_COUNT + 1)]


def build_all_urls() -> tuple[list[str], list[str], list[str]]:
    """返回 (hero_urls, equip_urls, rune_urls)。"""
    return build_hero_urls(), build_equip_urls(), build_rune_urls()


def detect_category(url: str) -> str:
    """根据 URL 模式识别所属板块。

    Returns: "heroes" | "equipment" | "runes"
    """
    if "/yx" in url:
        return "heroes"
    if "/zb" in url:
        return "equipment"
    if "/fw" in url:
        return "runes"
    raise ValueError(f"Unknown category for URL: {url}")


def get_category_dir(category: str) -> str:
    """根据板块名返回输出目录路径。"""
    mapping = {
        "heroes": HERO_OUTPUT_DIR,
        "equipment": EQUIP_OUTPUT_DIR,
        "runes": RUNE_OUTPUT_DIR,
    }
    return mapping[category]
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_url_builder.py -v
```
预期: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/url_builder.py tests/test_url_builder.py
git commit -m "feat: add URL builder and category detection"
```

---

### Task 6: Orchestrator 编排器 — 串联完整流水线

**Files:**
- Create: `src/orchestrator.py`
- Create: `tests/test_orchestrator.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_orchestrator.py
import asyncio
import tempfile
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from src.orchestrator import Orchestrator


class TestOrchestrator:
    @pytest.fixture
    def output_dir(self):
        with tempfile.TemporaryDirectory() as d:
            yield d

    @pytest.mark.asyncio
    async def test_run_respects_skipped_urls(self, output_dir):
        """已成功的 URL 应被跳过，不被 fetcher 调用。"""
        orch = Orchestrator(output_dir=output_dir, force=False)
        # 预填一条成功记录
        orch.repo.record_success(
            "https://www.ali213.net/zt/LOL/wiki/yx1.html",
            "heroes", "安妮",
            os.path.join(output_dir, "heroes", "安妮.md"),
        )
        # 创建对应的输出文件
        os.makedirs(os.path.join(output_dir, "heroes"), exist_ok=True)
        with open(os.path.join(output_dir, "heroes", "安妮.md"), "w") as f:
            f.write("test")

        orch.fetcher.fetch_all = AsyncMock(return_value=[])

        stats = await orch.run()
        # yx1 已被跳过，不应出现在传给 fetch_all 的 URL 中
        call_args = orch.fetcher.fetch_all.call_args[0][0]
        assert "https://www.ali213.net/zt/LOL/wiki/yx1.html" not in call_args
        assert stats["skipped"] >= 1

    @pytest.mark.asyncio
    async def test_run_counts_success_and_failure(self, output_dir):
        """验证成功/失败统计正确。"""
        orch = Orchestrator(output_dir=output_dir, force=True, concurrency=1)

        async def mock_fetch_all(urls):
            results = []
            for url in urls:
                if "yx1" in url:
                    results.append((url, "<html>hero1</html>", None))
                elif "yx2" in url:
                    results.append((url, None, "Connection error"))
                else:
                    results.append((url, "<html>default</html>", None))
            return results

        # Mock parser to return a usable Hero
        orch.fetcher.fetch_all = mock_fetch_all

        with patch("src.orchestrator.parse_hero_page") as mock_parse:
            mock_parse.return_value = MagicMock(
                name_cn="TestHero", name_en="Test",
                image_url="", title="", role="", background="",
                initial_attrs={}, max_attrs={},
                passive_skill=None, skills=[],
                source_url="", fetched_at="",
            )
            with patch("src.orchestrator.hero_to_markdown", return_value="# markdown"):
                with patch("src.orchestrator.write_markdown"):
                    stats = await orch.run()

        assert stats["total"] > 0
        assert "success" in stats
        assert "failed" in stats
        assert "skipped" in stats
        assert stats["success"] + stats["failed"] + stats["skipped"] == stats["total"]
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_orchestrator.py -v
```
预期: FAIL

- [ ] **Step 3: 实现 src/orchestrator.py**

```python
"""编排器：组合各模块完成完整抓取流水线"""

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta

from src.config import (
    OUTPUT_DIR, CONCURRENCY, REQUEST_DELAY, MAX_RETRIES, RETRY_BACKOFF,
)
from src.fetcher import Fetcher
from src.parser import parse_hero_page, parse_equip_page, parse_rune_page
from src.repository import FetchRepository
from src.writer import hero_to_markdown, equip_to_markdown, rune_to_markdown, write_markdown, sanitize_filename
from src.url_builder import build_all_urls, detect_category, get_category_dir

logger = logging.getLogger(__name__)
TZ = timezone(timedelta(hours=8))


class Orchestrator:
    def __init__(
        self,
        output_dir: str = OUTPUT_DIR,
        force: bool = False,
        concurrency: int = CONCURRENCY,
        delay: float = REQUEST_DELAY,
        max_retries: int = MAX_RETRIES,
        backoff: list[float] | None = None,
    ):
        self.output_dir = output_dir
        self.force = force
        self.fetcher = Fetcher(
            delay=delay, max_retries=max_retries,
            backoff=backoff, concurrency=concurrency,
        )
        self.repo = FetchRepository(
            record_path=os.path.join(output_dir, ".fetch_record.json")
        )

    async def run(self) -> dict:
        """执行完整抓取流水线，返回统计摘要。"""
        # 1. 加载历史记录
        self.repo.load()

        # 2. 生成 URL 列表并分类
        hero_urls, equip_urls, rune_urls = build_all_urls()
        all_urls = hero_urls + equip_urls + rune_urls

        # 3. 过滤待抓取 URL
        pending = self.repo.get_pending_urls(all_urls, force=self.force)
        skipped = len(all_urls) - len(pending)

        stats = {"total": len(all_urls), "success": 0, "failed": 0, "skipped": skipped}

        if not pending:
            logger.info("No pending URLs to fetch.")
            return stats

        # 4. 并发抓取
        results = await self.fetcher.fetch_all(pending)

        # 5-6. 逐条处理
        now = datetime.now(TZ).isoformat()
        for url, html, error in results:
            category = detect_category(url)

            if error:
                self.repo.record_failure(url, category, error)
                stats["failed"] += 1
                continue

            if html is None:
                self.repo.record_failure(url, category, "Empty response")
                stats["failed"] += 1
                continue

            # 解析
            try:
                if category == "heroes":
                    data = parse_hero_page(html, url, now)
                    if data is None:
                        raise ValueError("Failed to parse hero page")
                    name = data.name_cn
                    content = hero_to_markdown(data)
                elif category == "equipment":
                    data = parse_equip_page(html, url, now)
                    if data is None:
                        raise ValueError("Failed to parse equipment page")
                    name = data.name
                    content = equip_to_markdown(data)
                else:
                    data = parse_rune_page(html, url, now)
                    if data is None:
                        raise ValueError("Failed to parse rune page")
                    name = data.name
                    content = rune_to_markdown(data)
            except Exception as e:
                self.repo.record_failure(url, category, f"Parse error: {e}")
                stats["failed"] += 1
                logger.warning(f"Parse failed for {url}: {e}")
                continue

            # 写入文件
            out_dir = get_category_dir(category)
            filename = sanitize_filename(name) + ".md"
            filepath = os.path.join(out_dir, filename)
            write_markdown(content, filepath)

            # 记录成功
            self.repo.record_success(url, category, name, filepath)
            stats["success"] += 1
            logger.info(f"✓ {name} → {filepath}")

        # 7. 持久化记录
        self.repo.save()

        # 8. 打印摘要
        logger.info(
            f"Done. Total: {stats['total']}, "
            f"Success: {stats['success']}, "
            f"Failed: {stats['failed']}, "
            f"Skipped: {stats['skipped']}"
        )
        return stats
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_orchestrator.py -v
```
预期: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add orchestrator for end-to-end scraping pipeline"
```

---

### Task 7: Parser 模块 — HTML 解析器

**Files:**
- Create: `src/parser.py`
- Create: `tests/test_parser.py`

> **注意**：Parser 的实现依赖目标网站的实际 HTML 结构。以下实现基于常见的 Wiki 页面布局模式，实际使用时需根据真实 HTML 调整 CSS 选择器。

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_parser.py
import pytest
from src.parser import parse_hero_page, parse_equip_page, parse_rune_page
from src.models import Hero, Equipment, Rune

# 模拟 HTML 片段（基于常见 Wiki 布局，实际需根据网站结构调整）
HERO_HTML = """
<html><body>
<div class="detail-main">
  <h1>祖安怒兽 沃里克</h1>
  <img class="hero-img" src="https://img.ali213.net/warwick.png" />
  <div class="hero-info">
    <p class="name">沃里克</p>
    <p class="role">战士</p>
  </div>
  <div class="story">
    <p>沃里克是祖安城中一个传奇人物，曾经是一名冷酷的赏金猎人...</p>
  </div>
  <table class="attr-table" id="initial">
    <tr><th>攻击力</th><td>65</td></tr>
    <tr><th>攻击速度</th><td>0.67</td></tr>
    <tr><th>攻击距离</th><td>125</td></tr>
    <tr><th>移动速度</th><td>335</td></tr>
    <tr><th>生命值</th><td>620</td></tr>
    <tr><th>魔法值</th><td>280</td></tr>
    <tr><th>护甲值</th><td>33</td></tr>
    <tr><th>魔抗值</th><td>32</td></tr>
  </table>
  <table class="attr-table" id="max">
    <tr><th>攻击力</th><td>115</td></tr>
    <tr><th>攻击速度</th><td>1.05</td></tr>
  </table>
  <div class="skill passive">
    <img src="https://img.ali213.net/passive.png" />
    <h4>血之饥渴</h4>
    <p>沃里克的普通攻击造成额外魔法伤害。</p>
  </div>
  <div class="skill q">
    <img src="https://img.ali213.net/q.png" />
    <h4>野兽之口</h4>
    <p class="cost">消耗: 50/60/70/80/90 法力</p>
    <p class="cd">冷却: 6秒</p>
    <p class="range">范围: 350</p>
    <p>沃里克向前猛扑...</p>
  </div>
</div>
</body></html>
"""


class TestParseHeroPage:
    def test_parse_basic_hero(self):
        hero = parse_hero_page(HERO_HTML, "http://test.com/yx1.html", "2026-06-18T10:00:00+08:00")
        assert hero is not None
        assert isinstance(hero, Hero)
        assert hero.name_cn == "祖安怒兽"
        assert hero.name_en == "沃里克"
        assert hero.role == "战士"
        assert "沃里克" in hero.background
        assert hero.image_url == "https://img.ali213.net/warwick.png"

    def test_parse_attrs(self):
        hero = parse_hero_page(HERO_HTML, "http://test.com/yx1.html", "2026-06-18T10:00:00+08:00")
        assert hero.initial_attrs.get("攻击力") == "65"
        assert hero.initial_attrs.get("移动速度") == "335"
        assert hero.max_attrs.get("攻击力") == "115"

    def test_parse_skills(self):
        hero = parse_hero_page(HERO_HTML, "http://test.com/yx1.html", "2026-06-18T10:00:00+08:00")
        assert hero.passive_skill is not None
        assert hero.passive_skill.name == "血之饥渴"
        assert len(hero.skills) == 1
        assert hero.skills[0].name == "野兽之口"
        assert hero.skills[0].cost == "50/60/70/80/90 法力"
        assert hero.skills[0].cooldown == "6秒"
        assert hero.skills[0].range == "350"

    def test_empty_html_returns_none(self):
        hero = parse_hero_page("", "http://test.com/yx1.html", "")
        assert hero is None

    def test_source_url_stored(self):
        hero = parse_hero_page(HERO_HTML, "http://test.com/yx1.html", "2026-06-18T10:00:00+08:00")
        assert hero.source_url == "http://test.com/yx1.html"


EQUIP_HTML = """
<html><body>
<div class="detail-main">
  <h1>冰霜之心</h1>
  <img src="https://img.ali213.net/ice.png" />
  <p class="tier">传说</p>
  <p class="price">2700</p>
  <ul class="base-attrs">
    <li>+400 法力值</li>
    <li>+20 技能急速</li>
    <li>+50 护甲</li>
  </ul>
  <div class="passive"><p>坚如磐石：使受到的伤害减少</p></div>
  <div class="recipe">
    <li>冰川圆盾</li><li>守望者铠甲</li><li>900 金币</li>
  </div>
  <div class="rec-heroes"><li>盖伦</li><li>德莱厄斯</li></div>
</div>
</body></html>
"""


class TestParseEquipPage:
    def test_parse_basic_equip(self):
        equip = parse_equip_page(EQUIP_HTML, "http://test.com/zb1.html", "2026-06-18T10:00:00+08:00")
        assert equip is not None
        assert equip.name == "冰霜之心"
        assert equip.tier == "传说"
        assert equip.price == "2700"
        assert len(equip.base_attrs) == 3
        assert "+400 法力值" in equip.base_attrs

    def test_parse_passive(self):
        equip = parse_equip_page(EQUIP_HTML, "http://test.com/zb1.html", "2026-06-18T10:00:00+08:00")
        assert equip.passive_effect is not None
        assert "坚如磐石" in equip.passive_effect

    def test_parse_recipe(self):
        equip = parse_equip_page(EQUIP_HTML, "http://test.com/zb1.html", "2026-06-18T10:00:00+08:00")
        assert len(equip.recipe) == 3
        assert "冰川圆盾" in equip.recipe

    def test_parse_rec_heroes(self):
        equip = parse_equip_page(EQUIP_HTML, "http://test.com/zb1.html", "2026-06-18T10:00:00+08:00")
        assert len(equip.recommended_heroes) == 2
        assert "盖伦" in equip.recommended_heroes


RUNE_HTML = """
<html><body>
<div class="detail-main">
  <h1>强攻</h1>
  <img src="https://img.ali213.net/pta.png" />
  <p class="category">精密</p>
  <p class="tier">基石</p>
  <div class="desc"><p>用3次连续的普攻命中一名敌方英雄</p></div>
</div>
</body></html>
"""


class TestParseRunePage:
    def test_parse_basic_rune(self):
        rune = parse_rune_page(RUNE_HTML, "http://test.com/fw1.html", "2026-06-18T10:00:00+08:00")
        assert rune is not None
        assert rune.name == "强攻"
        assert rune.category == "精密"
        assert rune.tier == "基石"
        assert "普攻" in rune.description
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_parser.py -v
```
预期: FAIL

- [ ] **Step 3: 实现 src/parser.py**

```python
"""HTML 解析器：从 Wiki 页面提取结构化数据

注意：CSS 选择器需要根据目标网站的实际 HTML 结构调整。
当前选择器基于常见 Wiki 布局模式。首次运行前务必验证选择器正确性。
"""

import logging
from bs4 import BeautifulSoup
from src.models import Hero, Equipment, Rune, Skill

logger = logging.getLogger(__name__)


# ============================================================
# 通用工具
# ============================================================

def _text(el, default=""):
    """安全获取元素文本。"""
    return el.get_text(strip=True) if el else default


def _src(el, default=""):
    """安全获取元素 src 属性。"""
    return el.get("src", default) if el else default


def _parse_table_to_dict(table) -> dict[str, str]:
    """将 HTML <table> 解析为 {key: value} 字典。
    假定每行结构为 <tr><th>key</th><td>value</td></tr>
    """
    result = {}
    if not table:
        return result
    for row in table.find_all("tr"):
        th = row.find("th")
        td = row.find("td")
        if th and td:
            result[_text(th)] = _text(td)
    return result


# ============================================================
# 英雄页解析
# ============================================================

def parse_hero_page(html: str, url: str, fetched_at: str) -> Hero | None:
    """从英雄详情页 HTML 提取 Hero 数据。"""
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")

    try:
        # 标题区：h1 通常包含 "称号 名字" 格式
        h1 = soup.find("h1")
        title_text = _text(h1).strip()
        # 尝试拆分 "称号 名字"（如 "祖安怒兽 沃里克"）
        parts = title_text.rsplit(" ", 1)
        name_cn = parts[0] if len(parts) == 2 else title_text
        name_en = parts[1] if len(parts) == 2 else ""

        # 图片
        img = soup.select_one("img.hero-img, .detail-main img:first-of-type")
        image_url = _src(img)

        # 角色定位
        role_el = soup.select_one(".role, [class*='role']")
        role = _text(role_el)

        # 背景故事
        story_el = soup.select_one(".story, [class*='story'], .background")
        background = _text(story_el) if story_el else ""

        # 初始属性表
        initial_table = soup.select_one("#initial, .initial-attrs, table:has(th:contains('攻击力'))")
        initial_attrs = _parse_table_to_dict(initial_table)

        # 满级属性表
        max_table = soup.select_one("#max, .max-attrs, table:nth-of-type(2)")
        max_attrs = _parse_table_to_dict(max_table)

        # 技能解析
        passive_skill = None
        skills = []

        skill_divs = soup.select(".skill, [class*='skill-item'], .ability")
        for div in skill_divs:
            classes = div.get("class", [])
            is_passive = any("passive" in c.lower() for c in classes)

            s_name = _text(div.find("h4") or div.find("h3") or div.find("strong"))
            s_icon = _src(div.find("img"))
            s_desc = _text(div.find("p:last-of-type") or div.select_one(".desc"))
            s_cost = _text(div.select_one(".cost, [class*='cost']")) or None
            s_cd = _text(div.select_one(".cd, [class*='cd'], [class*='cooldown']")) or None
            s_range = _text(div.select_one(".range, [class*='range']")) or None

            skill = Skill(
                name=s_name, icon_url=s_icon, description=s_desc,
                cost=s_cost, cooldown=s_cd, range=s_range,
            )
            if is_passive:
                passive_skill = skill
            else:
                skills.append(skill)

        return Hero(
            name_cn=name_cn, name_en=name_en, title=title_text,
            image_url=image_url, role=role, background=background,
            initial_attrs=initial_attrs, max_attrs=max_attrs,
            passive_skill=passive_skill, skills=skills,
            source_url=url, fetched_at=fetched_at,
        )
    except Exception as e:
        logger.error(f"Error parsing hero page {url}: {e}")
        return None


# ============================================================
# 装备页解析
# ============================================================

def parse_equip_page(html: str, url: str, fetched_at: str) -> Equipment | None:
    """从装备详情页 HTML 提取 Equipment 数据。"""
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")

    try:
        name = _text(soup.find("h1")).strip()
        icon_url = _src(soup.select_one("img:first-of-type"))
        tier = _text(soup.select_one(".tier, [class*='tier']"))
        price = _text(soup.select_one(".price, [class*='price']"))

        # 基础属性列表
        base_attrs_el = soup.select(".base-attrs li, [class*='base'] li, .attrs li")
        base_attrs = [_text(li) for li in base_attrs_el if _text(li)]

        # 主动 / 被动效果
        active_el = soup.select_one(".active, [class*='active']")
        active_effect = _text(active_el) or None
        passive_el = soup.select_one(".passive, [class*='passive']")
        passive_effect = _text(passive_el) or None

        # 神话加成
        mythic_el = soup.select_one(".mythic, [class*='mythic']")
        mythic_bonus = _text(mythic_el) or None

        # 合成路线
        recipe_els = soup.select(".recipe li, [class*='recipe'] li")
        recipe = [_text(r) for r in recipe_els if _text(r)]

        # 推荐英雄
        hero_els = soup.select(".rec-heroes li, [class*='hero'] li, .recommend li")
        recommended_heroes = [_text(h) for h in hero_els if _text(h)]

        return Equipment(
            name=name, icon_url=icon_url, tier=tier, price=price,
            base_attrs=base_attrs, active_effect=active_effect,
            passive_effect=passive_effect, mythic_bonus=mythic_bonus,
            recipe=recipe, recommended_heroes=recommended_heroes,
            source_url=url, fetched_at=fetched_at,
        )
    except Exception as e:
        logger.error(f"Error parsing equipment page {url}: {e}")
        return None


# ============================================================
# 符文页解析
# ============================================================

def parse_rune_page(html: str, url: str, fetched_at: str) -> Rune | None:
    """从符文详情页 HTML 提取 Rune 数据。"""
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")

    try:
        name = _text(soup.find("h1")).strip()
        icon_url = _src(soup.select_one("img:first-of-type"))
        category = _text(soup.select_one(".category, [class*='category']"))
        tier = _text(soup.select_one(".tier, [class*='tier']"))
        description = _text(soup.select_one(".desc, [class*='desc'], .effect"))

        return Rune(
            name=name, icon_url=icon_url, category=category, tier=tier,
            description=description, source_url=url, fetched_at=fetched_at,
        )
    except Exception as e:
        logger.error(f"Error parsing rune page {url}: {e}")
        return None
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_parser.py -v
```
预期: 10 passed

- [ ] **Step 5: Commit**

```bash
git add src/parser.py tests/test_parser.py
git commit -m "feat: add HTML parser for heroes, equipment, and runes"
```

---

### Task 8: CLI 入口 — 命令行界面

**Files:**
- Create: `src/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_cli.py
import pytest
from unittest.mock import patch, MagicMock
from src.cli import parse_args, main


class TestCLI:
    def test_default_args(self):
        with patch("sys.argv", ["cli"]):
            args = parse_args()
        assert args.force is False
        assert args.concurrency == 5
        assert args.output_dir == "data"

    def test_force_flag(self):
        with patch("sys.argv", ["cli", "--force"]):
            args = parse_args()
        assert args.force is True

    def test_concurrency(self):
        with patch("sys.argv", ["cli", "--concurrency", "10"]):
            args = parse_args()
        assert args.concurrency == 10

    def test_output_dir(self):
        with patch("sys.argv", ["cli", "--output-dir", "/tmp/lol_data"]):
            args = parse_args()
        assert args.output_dir == "/tmp/lol_data"

    def test_category_filter(self):
        with patch("sys.argv", ["cli", "--category", "heroes"]):
            args = parse_args()
        assert args.category == "heroes"

    def test_invalid_category(self):
        with patch("sys.argv", ["cli", "--category", "invalid"]):
            with pytest.raises(SystemExit):
                parse_args()

    @pytest.mark.asyncio
    async def test_main_calls_orchestrator(self):
        with patch("src.cli.parse_args") as mock_args:
            mock_args.return_value = MagicMock(
                force=False, concurrency=5, output_dir="/tmp/test",
                delay=0.2, max_retries=3, category=None,
            )
            with patch("src.cli.Orchestrator") as mock_orch:
                mock_instance = MagicMock()
                mock_instance.run = MagicMock(return_value={"total": 0, "success": 0, "failed": 0, "skipped": 0})
                mock_orch.return_value = mock_instance

                await main()

                mock_orch.assert_called_once()
                mock_instance.run.assert_called_once()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_cli.py -v
```
预期: FAIL

- [ ] **Step 3: 实现 src/cli.py**

```python
"""CLI 入口：命令行参数解析与编排器启动"""

import argparse
import asyncio
import logging
import sys

from src.config import OUTPUT_DIR, CONCURRENCY, REQUEST_DELAY, MAX_RETRIES
from src.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

VALID_CATEGORIES = ["heroes", "equipment", "runes"]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        prog="lol-scraper",
        description="LOL Wiki 资料抓取器 — 为 RAG 系统准备游戏资料数据",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="强制重新抓取全部页面（忽略已有的成功记录）",
    )
    parser.add_argument(
        "--concurrency", type=int, default=CONCURRENCY,
        help=f"并发请求数上限（默认: {CONCURRENCY}）",
    )
    parser.add_argument(
        "--output-dir", type=str, default=OUTPUT_DIR,
        help=f"输出目录（默认: {OUTPUT_DIR}）",
    )
    parser.add_argument(
        "--delay", type=float, default=REQUEST_DELAY,
        help=f"请求间延迟秒数（默认: {REQUEST_DELAY}）",
    )
    parser.add_argument(
        "--max-retries", type=int, default=MAX_RETRIES,
        help=f"单页最大重试次数（默认: {MAX_RETRIES}）",
    )
    parser.add_argument(
        "--category", type=str, choices=VALID_CATEGORIES,
        help="只抓取指定板块（默认: 全部）",
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别（默认: INFO）",
    )
    return parser.parse_args(argv)


async def main(argv: list[str] | None = None) -> None:
    """主入口。"""
    args = parse_args(argv)

    # 配置日志
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.info("=" * 60)
    logger.info("LOL Wiki Scraper — Starting")
    logger.info(f"  Force: {args.force}")
    logger.info(f"  Concurrency: {args.concurrency}")
    logger.info(f"  Output: {args.output_dir}")
    logger.info(f"  Delay: {args.delay}s")
    logger.info(f"  Max retries: {args.max_retries}")
    if args.category:
        logger.info(f"  Category: {args.category}")
    logger.info("=" * 60)

    orch = Orchestrator(
        output_dir=args.output_dir,
        force=args.force,
        concurrency=args.concurrency,
        delay=args.delay,
        max_retries=args.max_retries,
    )

    stats = await orch.run()

    logger.info("=" * 60)
    logger.info(
        f"Complete — "
        f"Total: {stats['total']}, "
        f"Success: {stats['success']}, "
        f"Failed: {stats['failed']}, "
        f"Skipped: {stats['skipped']}"
    )
    logger.info("=" * 60)

    # 如果有失败，以非零退出码退出
    if stats["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_cli.py -v
```
预期: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/cli.py tests/test_cli.py
git commit -m "feat: add CLI entry point with argparse"
```

---

### Task 9: 集成测试 — 端到端验证

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: 编写集成测试**

```python
# tests/test_integration.py
"""集成测试：验证各模块协同工作"""

import asyncio
import os
import tempfile
import pytest
from unittest.mock import AsyncMock, patch

from src.orchestrator import Orchestrator
from src.writer import sanitize_filename, hero_to_markdown, write_markdown, equip_to_markdown, rune_to_markdown
from src.models import Hero, Equipment, Rune, Skill
from src.url_builder import detect_category, build_hero_urls


class TestIntegration:
    """端到端流程测试"""

    def test_url_to_markdown_pipeline_hero(self):
        """验证：URL 构造 → 分类识别 → Markdown 生成 的串联流程"""
        urls = build_hero_urls()
        assert len(urls) == 153
        for url in urls[:5]:
            assert detect_category(url) == "heroes"

        # 模拟解析后的数据
        hero = Hero(
            name_cn="安妮", name_en="Annie", title="黑暗之女 安妮",
            image_url="https://img.example.com/annie.png",
            role="法师", background="安妮是一个强大的火系法师。",
            initial_attrs={"攻击力": "52", "生命值": "524"},
            max_attrs={"攻击力": "98", "生命值": "1980"},
            passive_skill=Skill(name="嗜火", icon_url="https://img.example.com/p.png",
                                description="每施放4次技能后，下一次伤害技能会眩晕目标。"),
            skills=[Skill(name="碎裂之火", icon_url="https://img.example.com/q.png",
                          description="投出一团火球。", cost="60/65/70/75/80 法力",
                          cooldown="4秒", range="625")],
            source_url=urls[0], fetched_at="2026-06-18T10:00:00+08:00",
        )

        md = hero_to_markdown(hero)
        assert "# 安妮 — Annie" in md
        assert "来源: <https://www.ali213.net/zt/LOL/wiki/yx1.html>" in md

        # 写入临时目录
        with tempfile.TemporaryDirectory() as d:
            filepath = os.path.join(d, sanitize_filename("安妮") + ".md")
            write_markdown(md, filepath)
            assert os.path.exists(filepath)
            with open(filepath, "r", encoding="utf-8") as f:
                written = f.read()
            assert "安妮" in written

    def test_url_to_markdown_pipeline_equip(self):
        """验证装备完整流程"""
        equip = Equipment(
            name="冰霜之心", icon_url="https://img.example.com/ice.png",
            tier="传说", price="2700",
            base_attrs=["+400 法力值", "+20 技能急速", "+50 护甲"],
            passive_effect="坚如磐石：使受到的伤害减少",
            recipe=["冰川圆盾", "守望者铠甲"],
            recommended_heroes=["盖伦"],
            source_url="https://www.ali213.net/zt/LOL/wiki/zb1.html",
            fetched_at="2026-06-18T10:00:00+08:00",
        )
        md = equip_to_markdown(equip)
        assert "# 冰霜之心" in md
        assert "**等级**: 传说" in md
        assert "**售价**: 2700" in md
        assert "+400 法力值" in md
        assert "坚如磐石" in md
        assert "冰川圆盾" in md

        with tempfile.TemporaryDirectory() as d:
            filepath = os.path.join(d, "冰霜之心.md")
            write_markdown(md, filepath)
            assert os.path.exists(filepath)

    def test_url_to_markdown_pipeline_rune(self):
        """验证符文完整流程"""
        rune = Rune(
            name="强攻", icon_url="https://img.example.com/pta.png",
            category="精密", tier="基石",
            description="用3次连续的普攻命中一名敌方英雄",
            source_url="https://www.ali213.net/zt/LOL/wiki/fw1.html",
            fetched_at="2026-06-18T10:00:00+08:00",
        )
        md = rune_to_markdown(rune)
        assert "# 强攻" in md
        assert "**类别**: 精密" in md
        assert "**等级**: 基石" in md

        with tempfile.TemporaryDirectory() as d:
            filepath = os.path.join(d, "强攻.md")
            write_markdown(md, filepath)
            assert os.path.exists(filepath)

    def test_markdown_ends_with_metadata(self):
        """验证所有输出的 Markdown 均包含来源和时间的元数据"""
        hero = Hero("test", "test", "test", "", "", "",
                    {}, {}, None, [],
                    source_url="http://test.com/yx1.html",
                    fetched_at="2026-06-18T10:00:00+08:00")
        md = hero_to_markdown(hero)
        assert "来源: <http://test.com/yx1.html>" in md
        assert "抓取时间: 2026-06-18T10:00:00+08:00" in md

    @pytest.mark.asyncio
    async def test_orchestrator_skips_successful_urls(self):
        """集成测试：Orchestrator 应跳过已成功抓取的 URL"""
        with tempfile.TemporaryDirectory() as d:
            orch = Orchestrator(output_dir=d, force=False)
            # 预填记录
            hero_dir = os.path.join(d, "heroes")
            os.makedirs(hero_dir, exist_ok=True)
            filepath = os.path.join(hero_dir, "安妮.md")
            with open(filepath, "w") as f:
                f.write("test")

            orch.repo.record_success(
                "https://www.ali213.net/zt/LOL/wiki/yx1.html",
                "heroes", "安妮", filepath,
            )

            orch.fetcher.fetch_all = AsyncMock(return_value=[])

            stats = await orch.run()

            # yx1 不应出现在 fetch_all 调用中
            if orch.fetcher.fetch_all.called:
                called_urls = orch.fetcher.fetch_all.call_args[0][0]
                assert "https://www.ali213.net/zt/LOL/wiki/yx1.html" not in called_urls

            assert stats["skipped"] >= 1
```

- [ ] **Step 2: 运行集成测试**

```bash
python -m pytest tests/test_integration.py -v
```
预期: 6 passed

- [ ] **Step 3: 运行全部测试**

```bash
python -m pytest tests/ -v
```
预期: 全部通过（约 42 tests）

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add end-to-end integration tests"
```

---

## 附录 A：运行说明

### 安装

```bash
pip install -r requirements.txt
```

### 基本使用

```bash
# 普通模式（跳过已成功抓取）
python -m src.cli

# 强制重新抓取全部
python -m src.cli --force

# 只抓取英雄
python -m src.cli --category heroes

# 自定义参数
python -m src.cli --concurrency 10 --delay 0.5 --output-dir ./my_data

# 详细日志
python -m src.cli --log-level DEBUG
```

### 输出

```bash
data/
├── heroes/           # 153 个英雄 Markdown
├── equipment/        # 162 个装备 Markdown
├── runes/            # 63 个符文 Markdown
└── .fetch_record.json  # 抓取状态记录
```

## 附录 B：Parser 选择器校准指南

Parser 模块中的 CSS 选择器基于常见 Wiki 布局。**首次运行前**需根据实际 HTML 校准：

1. 先手动抓取一个示例页面并保存 HTML：
   ```bash
   curl https://www.ali213.net/zt/LOL/wiki/yx1.html -o sample_hero.html
   ```
2. 用 BS4 交互式探索结构：
   ```python
   from bs4 import BeautifulSoup
   soup = BeautifulSoup(open("sample_hero.html"), "html.parser")
   # 定位各字段的实际选择器
   ```
3. 更新 `src/parser.py` 中对应选择器
4. 运行解析测试验证 `pytest tests/test_parser.py`

## 附录 C：模块依赖关系图

```
cli.py
  └── orchestrator.py
        ├── config.py          (常量)
        ├── models.py          (数据类)
        ├── url_builder.py     (URL 构造)
        ├── repository.py      (抓取记录) ← models.py
        ├── fetcher.py         (HTTP 抓取) ← config.py
        ├── parser.py          (HTML 解析) ← models.py
        └── writer.py          (Markdown)  ← models.py
```
