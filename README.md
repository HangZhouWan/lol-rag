# 英雄联盟 RAG 智能问答系统

基于检索增强生成（RAG）技术的《英雄联盟》游戏知识问答助手。整合英雄、装备、符文三大类游戏资料，通过混合检索 + 精排 + DeepSeek LLM 提供精准、有引用的中文回答。

## 项目结构

```
lol-rag/
├── src/
│   ├── rag/                    # RAG 核心模块
│   │   ├── cli.py              # 交互式 CLI 入口
│   │   ├── config.py           # 配置管理（.env 加载）
│   │   ├── pipeline.py         # RAG 总编排器
│   │   ├── loader.py           # Markdown 文档加载器
│   │   ├── chunker.py          # 语义分块（英雄/装备/符文）
│   │   ├── embedder.py         # BGE Embedding 封装
│   │   ├── vector_store.py     # ChromaDB 向量存储
│   │   ├── bm25_index.py       # BM25 关键词索引
│   │   ├── retriever.py        # 混合检索 + RRF 融合 + 精排
│   │   ├── generator.py        # DeepSeek LLM 调用
│   │   ├── prompt.py           # System Prompt & 消息构造
│   │   ├── conversation.py     # 对话历史管理
│   │   └── models.py           # 数据模型定义
│   └── scraper/                # Wiki 资料抓取器
│       ├── config.py           # 抓取器配置
│       ├── fetcher.py          # HTTP 异步抓取
│       ├── parser.py           # HTML 解析
│       ├── url_builder.py      # URL 构造
│       ├── writer.py           # Markdown 输出
│       ├── orchestrator.py     # 抓取流程编排
│       ├── repository.py       # 抓取状态记录
│       └── models.py           # 抓取数据模型
├── data/                       # 游戏资料（Markdown）
│   ├── heroes/                 # 英雄资料
│   ├── equipment/              # 装备资料
│   ├── runes/                  # 符文资料
│   └── chroma_db/              # 向量索引持久化目录
├── tests/                      # 测试
│   └── fixtures/rag/           # 测试用游戏资料
├── docs/                       # 文档
│   ├── requirements.md         # 项目需求
│   ├── rag-phase1-tech-spec.md # RAG 技术规格
│   ├── usage.md                # 使用手册
│   └── caveats.md              # 注意事项
├── logs/                       # 日志输出
├── requirements.txt            # Python 依赖
├── .env.example                # 环境变量模板
└── README.md
```

## 功能特性

### RAG 问答系统

- **混合检索**：向量检索（BGE Embedding + ChromaDB）+ BM25 关键词检索，双路并行
- **RRF 融合**：Reciprocal Rank Fusion 合并双路结果并去重
- **Cross-Encoder 精排**：使用 BGE-Reranker 对候选结果二次排序
- **语义分块**：针对英雄、装备、符文三种内容类型分别设计分块策略
  - 英雄：概览 / 背景故事 / 属性 / 技能组合（被动 + Q/W/E/R 合并为一个 chunk）
  - 装备：概览 / 属性效果 / 合成推荐
  - 符文：整文档不分块
- **内联引用**：回答中关键事实标注引用编号，末尾附来源列表
- **对话记忆**：内存 deque 维护最近 N 轮对话上下文，自动截断
- **首次自动建索引**：启动时检测索引状态，无索引则自动构建

### Wiki 资料抓取器

- 从游侠网 LOL Wiki 抓取英雄、装备、符文三类资料
- 异步并发抓取（aiohttp），支持自定义并发数与请求间隔
- 断点续抓：通过 `data/.fetch_record.json` 记录状态，重启自动跳过已成功页面
- 失败重试（退避 1s → 3s → 5s），不阻塞整体流程
- 输出为结构化 Markdown 文件

## 技术栈

| 组件 | 技术 |
|------|------|
| LLM | DeepSeek Chat API |
| Embedding | BAAI/bge-small-zh-v1.5 |
| 向量存储 | ChromaDB |
| 重排序 | BAAI/bge-reranker-base |
| 关键词检索 | BM25 (rank-bm25 + jieba 分词) |
| 框架 | LangChain |
| HTTP 抓取 | aiohttp |
| HTML 解析 | BeautifulSoup4 |
| 测试 | pytest |

## 快速开始

### 环境要求

- Python 3.10+
- pip

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY
```

关键配置项：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥（必填） | - |
| `DEEPSEEK_MODEL` | 对话模型 | deepseek-chat |
| `EMBEDDING_MODEL` | Embedding 模型 | BAAI/bge-small-zh-v1.5 |
| `RERANK_MODEL` | 精排模型 | BAAI/bge-reranker-base |
| `RETRIEVAL_TOP_K` | 粗筛返回数量 | 10 |
| `RERANK_TOP_K` | 精排返回数量 | 3 |
| `MAX_HISTORY_TURNS` | 最大对话轮数 | 10 |

### 3. 准备游戏资料

> 如果 `data/` 目录下已有资料文件，可跳过此步骤。

```bash
# 增量抓取（推荐首次使用）
python -m src.cli

# 强制全量抓取
python -m src.cli --force
```

抓取完成后，资料文件按类别存储在 `data/heroes/`、`data/equipment/`、`data/runes/` 下。

### 4. 启动 RAG 问答

```bash
# 交互模式
python -m src.rag.cli

# 强制重建索引
python -m src.rag.cli --rebuild-index

# 使用自定义配置文件
python -m src.rag.cli --config /path/to/.env
```

启动后显示欢迎界面和索引状态，输入问题即可查询。

### 5. 交互命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助信息 |
| `/clear` | 清空对话历史 |
| `/quit` / `/exit` | 退出程序 |
| `Ctrl+C` / `Ctrl+D` | 退出程序 |

其他输入均作为查询问题处理。

## 检索流程

```
用户问题
    │
    ├──→ BGE Embedding → ChromaDB 向量检索（粗筛 top-k）
    │
    ├──→ jieba 分词 → BM25 关键词检索（粗筛 top-k）
    │
    ▼
RRF 融合去重（取 top coarse_k）
    │
    ▼
Cross-Encoder 精排（取 top rerank_k）
    │
    ▼
构建 Prompt（系统提示 + 参考资料 + 对话历史 + 当前问题）
    │
    ▼
DeepSeek 生成回答（含内联引用）
    │
    ▼
返回：回答 + 引用列表 + 耗时统计
```

## 运行测试

```bash
# 全部测试
python -m pytest tests/ -v

# 仅 RAG 模块
python -m pytest tests/test_rag_*.py -v

# 仅抓取器
python -m pytest tests/test_fetcher.py tests/test_parser.py -v

# 集成测试
python -m pytest tests/test_rag_integration.py -v
```

## 数据来源

游戏资料抓取自 [游侠网 LOL Wiki](https://www.ali213.net/zt/LOL/wiki/)，包含：

| 类别 | 数量 | URL 模式 |
|------|------|----------|
| 英雄 | 153 | `yx{1..153}.html` |
| 装备 | 162 | `zb{1..162}.html` |
| 符文 | 63 | `fw{1..63}.html` |

> 所有资料版权归原作者所有，仅供学习研究使用。

## License

MIT
