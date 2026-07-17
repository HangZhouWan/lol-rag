# LOL Wiki 资料抓取器 — 注意事项

## 一、首次运行前：校准 Parser 选择器

Parser 模块 (`src/parser.py`) 中的 CSS 选择器是基于常见 Wiki 布局的**预设值**。首次运行前必须根据目标网站的实际 HTML 结构进行校准，否则解析可能返回空字段。

### 校准步骤

**1. 手动抓取样本页面**

```bash
# 英雄页
curl -o sample_hero.html https://www.ali213.net/zt/LOL/wiki/yx1.html

# 装备页
curl -o sample_equip.html https://www.ali213.net/zt/LOL/wiki/zb1.html

# 符文页
curl -o sample_rune.html https://www.ali213.net/zt/LOL/wiki/fw1.html
```

**2. 交互式探索 DOM 结构**

```python
from bs4 import BeautifulSoup

soup = BeautifulSoup(open("sample_hero.html"), "html.parser")

# 逐一确认各字段的实际 CSS 选择器
soup.select_one("h1")                # 标题
soup.select_one("img.hero-img")      # 图片
soup.select_one(".role")             # 定位
soup.select_one(".story")            # 背景故事
soup.select("table")                 # 属性表
soup.select(".skill")                # 技能区块
```

**3. 更新 `src/parser.py` 中对应的选择器**

关键函数和对应的选择器位置：
- `parse_hero_page`: 标题 `h1`、图片、定位、背景故事、初始/满级属性表、技能区块
- `parse_equip_page`: 名称、图标、等级、价格、基础属性、主动/被动效果、神话加成、合成路线、推荐英雄
- `parse_rune_page`: 名称、图标、类别、等级、效果描述

**4. 验证修改**

```bash
python3 -m pytest tests/test_parser.py -v
```

> **注意**：测试中的 HTML fixture 是模拟数据，修改选择器后可能需要同步更新测试 fixture。

---

## 二、请求频率与反爬

### 默认限速

程序内置了以下反爬措施：

| 机制 | 默认值 | 说明 |
|------|--------|------|
| 请求间隔 | ≥0.2 秒 | Semaphore + asyncio.Lock 双重保障 |
| 并发上限 | 5 | 同时最多 5 个请求 |
| 单请求超时 | 30 秒 | 超时视为失败进入重试 |
| 重试退避 | 1s → 3s → 5s | 每次重试间隔递增 |

### 调整建议

- **保守模式**（避免 IP 被封）：`--delay 1.0 --concurrency 2`
- **激进模式**（网络稳定时）：`--delay 0.1 --concurrency 10`

### 警告

> 如果目标网站更新了反爬策略（如 Cloudflare 防护、验证码），本程序会因 HTTP 非 200 状态码而失败。请根据实际情况调整请求头或引入 `playwright` / `selenium`。

---

## 三、失败处理

### 单页失败

- 单个页面抓取或解析失败**不会阻塞**整体流程
- 失败信息记录到 `data/.fetch_record.json`，包含错误原因和重试次数
- 下次运行时会自动重试未达上限的失败 URL

### 全部失败

- 程序退出码为 `1`
- 适用于 CI/CD 流水线中检测异常

### 常见失败原因

| 现象 | 可能原因 | 解决 |
|------|----------|------|
| `HTTP 403` | IP 被限制 | 降低并发和频率，使用代理 |
| `Timeout` | 网络不稳定或服务器响应慢 | 检查网络，考虑增大 `--delay` |
| `Parse error` | 网站 HTML 结构变化 | 重新校准 Parser 选择器 |
| `Empty response` | 页面内容为空或重定向 | 检查 URL 是否仍有效 |

---

## 四、输出文件命名

- 文件名使用抓取到的**中文名称**（如"黑暗之女.md"）
- 文件名中的非法字符（`<>:"/\|?*`）会被自动移除
- 如果中文名称为空（解析失败），会生成空文件名 — 此时需检查 Parser 校准
- **极长名称**可能超出文件系统 255 字节限制，当前版本未做截断处理

---

## 五、并发安全

### 单进程场景（当前设计目标）

本程序设计为**单进程运行**。`FetchRepository.save()` 没有文件锁保护，**不要同时运行多个实例指向同一个 `data/` 目录**，否则抓取记录可能被覆盖。

### 多进程需求

如果需要多进程并发抓取，需要：
1. 对 `.fetch_record.json` 引入文件锁（`fcntl.flock`）
2. 或将抓取记录迁移到 SQLite

---

## 六、Parser 的容错设计

### 已知限制

1. **名称拆分**：`h1` 文本按最后一个空格拆分为中文名和英文名。对于无空格的标题（如某些特殊英雄），英文名会留空。
2. **属性表解析**：假定表格结构为 `<tr><th>key</th><td>value</td></tr>`。如果网站使用 `div` 布局，需要重写 `_parse_table_to_dict`。
3. **技能标签**：Q/W/E/R 标签按出现顺序分配。如果网站上的技能数量不等于 4 或顺序不同，标签可能不匹配。
4. **`:contains()` 伪类**：已替换为标准 CSS 选择器。如果网站使用动态类名（如 CSS Modules），需要基于属性选择器重新定位。

### 健壮性

- 所有解析函数包裹在 `try/except` 中，解析失败返回 `None`
- 空 HTML 输入直接返回 `None`
- 缺失字段填充默认值（`""`、`None`、`[]`），不会抛异常

---

## 七、运行环境

| 项目 | 说明 |
|------|------|
| Python 版本 | 3.10+（使用了 `str \| None` 联合类型语法和 `from __future__ import annotations`） |
| 操作系统 | Linux / macOS / Windows（路径使用 `os.path.join`，跨平台兼容） |
| 编码 | 所有 I/O 使用 UTF-8 |
| 时区 | 抓取时间戳使用东八区 (UTC+8)，硬编码于各模块中 |

---

## 八、数据用于 RAG 系统的建议

输出的 Markdown 文件可直接被 LangChain 的标准 Loader 加载：

```python
from langchain_community.document_loaders import DirectoryLoader

# 加载全部英雄资料
loader = DirectoryLoader("data/heroes/", glob="*.md")
documents = loader.load()

# 按需分块
from langchain.text_splitter import RecursiveCharacterTextSplitter
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
chunks = splitter.split_documents(documents)
```

每个 Markdown 文件末尾的元数据行（`来源` 和 `抓取时间`）可作为文档的 metadata 来源进行解析和索引。

---

## 九、故障排查清单

1. **所有解析结果为空** → Parser 选择器需要校准，网站结构可能已变化
2. **所有请求超时** → 检查网络连通性，尝试 `curl` 目标 URL
3. **部分页面解析失败** → 查看 DEBUG 日志定位具体选择器问题
4. **`python3 -m src.cli` 报错** → 确认已 `pip install -r requirements.txt`
5. **断点续抓不生效** → 检查 `data/.fetch_record.json` 是否存在且格式正确
