# LOL Wiki 资料抓取器 — 使用手册

## 环境要求

- Python 3.10+
- pip

## 安装

```bash
cd /home/rag-demo
pip install -r requirements.txt
```

依赖项：

| 包 | 版本 | 用途 |
|---|------|------|
| `aiohttp` | ≥3.9.0 | 异步 HTTP 并发抓取 |
| `beautifulsoup4` | ≥4.12.0 | HTML 解析 |

## 基本使用

### 增量抓取（推荐首次使用）

```bash
python3 -m src.cli
```

- 自动加载 `data/.fetch_record.json` 中的历史记录
- 已成功抓取且输出文件存在的 URL 会被**跳过**
- 失败未达重试上限的 URL 会被**重试**
- 抓取完成后更新记录文件

### 强制全量抓取

```bash
python3 -m src.cli --force
```

忽略所有历史记录，重新抓取全部 378 个页面。

### 自定义参数

```bash
# 提高并发数
python3 -m src.cli --concurrency 10

# 增大请求间隔（降低被 ban 风险）
python3 -m src.cli --delay 0.5

# 自定义输出目录
python3 -m src.cli --output-dir ./my_lol_data

# 组合使用
python3 -m src.cli --concurrency 8 --delay 0.3 --output-dir /data/lol-wiki
```

### 调试模式

```bash
python3 -m src.cli --log-level DEBUG
```

## 命令行参数一览

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--force` | flag | `False` | 忽略历史记录，强制全量抓取 |
| `--concurrency` | int | `5` | 并发请求数上限 |
| `--output-dir` | str | `data` | 输出根目录 |
| `--delay` | float | `0.2` | 请求间最小间隔（秒） |
| `--max-retries` | int | `3` | 单页失败最大重试次数 |
| `--log-level` | str | `INFO` | 日志级别: DEBUG / INFO / WARNING / ERROR |

## 输出结构

```
data/
├── heroes/
│   ├── 黑暗之女.md
│   ├── 狂战士.md
│   └── ...（最多 153 个文件）
├── equipment/
│   ├── 冰霜之心.md
│   └── ...（最多 162 个文件）
├── runes/
│   ├── 强攻.md
│   └── ...（最多 63 个文件）
└── .fetch_record.json    # 抓取状态记录
```

每个 Markdown 文件末尾包含来源 URL 和抓取时间的元数据：

```markdown
> 来源: <https://www.ali213.net/zt/LOL/wiki/yx1.html>  
> 抓取时间: 2026-06-18T10:30:00+08:00  
```

## 断点续抓机制

程序维护 `data/.fetch_record.json` 记录每个 URL 的状态：

```json
{
  "https://www.ali213.net/zt/LOL/wiki/yx1.html": {
    "category": "heroes",
    "name": "黑暗之女",
    "output_file": "data/heroes/黑暗之女.md",
    "fetched_at": "2026-06-18T10:30:00+08:00",
    "status": "success",
    "error": null,
    "retries": 0,
    "last_attempt": null
  }
}
```

**重启行为**：
- `status: "success"` 且输出文件存在 → **跳过**
- `status: "success"` 但输出文件被删除 → **重新抓取**
- `status: "failed"` 且 `retries < 3` → **重试**
- `status: "failed"` 且 `retries >= 3` → **跳过**（已达上限）
- 无记录 → **正常抓取**

## 运行测试

```bash
# 全部测试
python3 -m pytest tests/ -v

# 单个模块
python3 -m pytest tests/test_fetcher.py -v
python3 -m pytest tests/test_parser.py -v
```
