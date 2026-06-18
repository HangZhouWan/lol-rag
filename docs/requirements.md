# LOL Wiki 资料抓取器 — 需求文档

## 项目背景

为 RAG（检索增强生成）系统准备英雄联盟游戏资料数据源，从游侠网 LOL Wiki 抓取结构化数据并输出为 Markdown 文件。

## 目标网站

- **首页**：`https://www.ali213.net/zt/LOL/wiki/`
- **英雄列表**：`https://www.ali213.net/zt/LOL/wiki/lolyx/`
- **装备列表**：`https://www.ali213.net/zt/LOL/wiki/lolzb/`
- **符文列表**：`https://www.ali213.net/zt/LOL/wiki/lolfw/`

## 抓取范围

| 板块 | 详情页 URL 模式 | 预估数量 |
|------|:---:|:---:|
| 英雄资料 | `yx{1..153}.html` | 153 |
| 装备大全 | `zb{1..162}.html` | 162 |
| 符文大全 | `fw{1..63}.html` | 63 |
| **合计** | | **~378 页** |

> 抓取深度：所有详情页的完整内容。

## 数据字段

### 英雄页

- 标题（如"祖安怒兽"）、图片 URL
- 英雄背景故事
- 名字（如"沃里克"）、定位（如"战士"）
- 初始属性：攻击力、攻击速度、攻击距离、移动速度、生命值、魔法值、护甲值、魔抗值
- 满级属性：同上 8 项
- 被动技能：图标、名称、描述
- Q/W/E/R 技能：图标、名称、技能消耗、冷却时间、施法范围、描述

### 装备页

- 名称、图标 URL
- 等级（如"传说"）、售价
- 基础属性
- 主动效果、被动效果
- 神话加成
- 合成路线
- 推荐英雄

### 符文页

- 名称、图标 URL
- 所属类别（如"精密"）
- 符文等级（如"基石"）
- 效果描述

## 技术方案

- **语言**：Python
- **HTTP 请求**：`requests` + `aiohttp`（并发抓取）
- **HTML 解析**：`BeautifulSoup4`
- **文档管理**：LangChain `Document` + `RecursiveCharacterTextSplitter`
- **不推荐使用 LangChain 原生 Loader**：因为 URL 需要构造发现，且字段提取需要精准解析

## 输出格式

- **格式**：Markdown 文件（.md）
- **目录结构**：按板块分目录平铺

```
data/
├── heroes/
│   ├── 黑暗之女.md
│   ├── 狂战士.md
│   └── ...（153 个文件）
├── equipment/
│   ├── 冰霜之心.md
│   └── ...（162 个文件）
└── runes/
    ├── 强攻.md
    └── ...（63 个文件）
```

- **文件命名**：使用英雄/装备/符文的中文名称

## 本地拉取记录（防重复）

维护一个本地状态文件 `data/.fetch_record.json`，记录每个 URL 的拉取状态：

```json
{
  "https://www.ali213.net/zt/LOL/wiki/yx1.html": {
    "category": "heroes",
    "name": "黑暗之女",
    "output_file": "data/heroes/黑暗之女.md",
    "fetched_at": "2026-06-18T10:30:00+08:00",
    "status": "success"
  },
  "https://www.ali213.net/zt/LOL/wiki/yx99.html": {
    "category": "heroes",
    "name": null,
    "status": "failed",
    "error": "Connection timeout",
    "retries": 3,
    "last_attempt": "2026-06-18T10:31:00+08:00"
  }
}
```

**行为规则**：

- 启动时加载 `data/.fetch_record.json`
- 已成功（`status: "success"`）且输出文件存在的 URL → **跳过**
- 未记录或输出文件缺失的 URL → **正常抓取**
- 失败未达重试上限的 URL → **重试**
- 抓取完成后更新记录文件
- 可选：提供 `--force` 命令行参数强制重新抓取全部

## 非功能性需求

- 请求间延迟 ≥ 0.2 秒，避免被封 IP
- 单页抓取失败重试 3 次（退避 1s / 3s / 5s）
- 最终失败的 URL 记录到拉取记录中，不阻塞整体流程
- 输出 Markdown 末尾应包含来源 URL 和抓取时间元数据
