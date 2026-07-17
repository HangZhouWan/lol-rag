# 英雄联盟 RAG 系统 — 第一阶段技术实现文档

> 版本: 1.0
> 日期: 2026-06-22
> 对应需求: docs/rag-requirements.md 第 3.1 节（CLI 交互界面）

---

## 一、概述

本文档描述英雄联盟 RAG 系统第一阶段的详细技术实现方案。本阶段目标：构建一个终端交互式 CLI，用户输入中文问题，系统从已抓取的 378 个 Markdown 资料文件中检索相关内容，调用 LLM 生成带来源引用的答案。

### 1.1 技术选型总览

| 层面 | 选型 | 说明 |
|------|------|------|
| LLM | DeepSeek-V4 | 通过 DeepSeek API 调用 |
| Embedding | BGE-small-zh-v1.5 | 本地运行，sentence-transformers 加载 |
| 向量存储 | ChromaDB | 本地持久化，Python 原生 |
| RAG 框架 | LangChain | 文档加载、Chain 编排 |
| 重排序 | BGE-Reranker (Cross-Encoder) | 粗筛后精排 |
| 配置管理 | .env + python-dotenv | API key、路径、模型参数 |
| 日志 | Python logging → logs/rag.log | 关键操作、耗时、命中记录 |

---

## 二、目录结构

```
src/
├── scraper/                  # [已有] 第一阶段抓取模块，不动
│   ├── __init__.py
│   ├── config.py
│   ├── fetcher.py
│   ├── models.py
│   ├── orchestrator.py
│   ├── parser.py
│   ├── repository.py
│   ├── url_builder.py
│   └── writer.py
│
├── rag/                      # [新增] RAG 系统模块
│   ├── __init__.py
│   ├── cli.py                # RAG CLI 入口 + 交互循环
│   ├── config.py             # 配置加载（从 .env 读取）
│   ├── models.py             # 数据模型
│   ├── loader.py             # Markdown 文档加载
│   ├── chunker.py            # 语义分块策略
│   ├── embedder.py           # Embedding 包装器
│   ├── vector_store.py       # ChromaDB 管理
│   ├── bm25_index.py         # BM25 关键词索引
│   ├── retriever.py          # 混合检索 + 精排
│   ├── generator.py          # LLM 生成（DeepSeek）
│   ├── conversation.py       # 对话历史管理
│   └── prompt.py             # System Prompt + 模板

data/
├── heroes/                   # [已有]
├── equipment/                # [已有]
├── runes/                    # [已有]
├── chroma_db/                # [新增] ChromaDB 持久化目录
└── .fetch_record.json        # [已有]

logs/
└── rag.log                   # [新增] RAG 运行日志

tests/
├── ...                       # [已有] 抓取模块测试
├── test_rag_loader.py        # [新增]
├── test_rag_chunker.py       # [新增]
├── test_rag_retriever.py     # [新增]
├── test_rag_conversation.py  # [新增]
└── test_rag_cli.py           # [新增]

.env                          # [新增] 环境配置（不入 git）
.env.example                  # [新增] 配置模板（入 git）
```

---

## 三、配置设计 (.env)

### 3.1 配置项定义

```ini
# .env.example — 复制为 .env 后填入实际值

# --- LLM ---
DEEPSEEK_API_KEY=sk-your-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_MAX_TOKENS=2048
DEEPSEEK_TEMPERATURE=0.3

# --- Embedding ---
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
EMBEDDING_DEVICE=cpu
EMBEDDING_NORMALIZE=true

# --- 向量存储 ---
CHROMA_PERSIST_DIR=data/chroma_db
CHROMA_COLLECTION=lol-wiki

# --- 检索 ---
RETRIEVAL_TOP_K=10              # 粗筛返回数量（每种检索方式）
RERANK_TOP_K=3                  # 精排后保留数量
RERANK_MODEL=BAAI/bge-reranker-base
HYBRID_BM25_WEIGHT=0.3          # BM25 权重（0~1），向量权重=1-weight。0.3=偏向量，精确查询可调高

# --- 对话 ---
MAX_HISTORY_TURNS=10            # 最大对话轮数
MAX_INPUT_LENGTH=2000           # 用户输入最大字符数

# --- 数据 ---
DATA_DIR=data                    # Markdown 资料根目录

# --- 日志 ---
LOG_LEVEL=INFO
LOG_FILE=logs/rag.log
```

### 3.2 配置加载模块 ([src/rag/config.py](src/rag/config.py))

- 使用 `python-dotenv` 加载 `.env` 文件
- 每个配置项提供默认值，`.env` 中缺失时使用默认值
- 启动时做必要的校验：API key 非空、路径存在
- 配置值通过模块级函数 `get_config() -> dict` 获取，或通过 `RAGConfig` dataclass 封装

---

## 四、数据模型 ([src/rag/models.py](src/rag/models.py))

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Message:
    """单条对话消息"""
    role: str                    # "user" | "assistant"
    content: str
    timestamp: str = ""          # ISO 8601

@dataclass
class RetrievedChunk:
    """检索结果"""
    content: str                 # 文本内容
    metadata: dict               # source_file, category, section, ...
    score: float                 # 相似度分数
    rerank_score: float = 0.0    # 精排分数（粗筛阶段为 0）

@dataclass
class RAGResponse:
    """RAG 响应"""
    answer: str                  # 最终回答
    citations: list[str]         # 引用来源列表 ["data/heroes/九尾妖狐.md", ...]
    chunks_used: list[RetrievedChunk]  # 使用的检索结果
    generation_time_ms: int      # LLM 生成耗时
    retrieval_time_ms: int       # 检索耗时
```

---

## 五、文档加载与分块

### 5.1 文档加载 ([src/rag/loader.py](src/rag/loader.py))

职责：遍历 `data/heroes/`, `data/equipment/`, `data/runes/` 三个目录，将所有 `.md` 文件读入内存，解析为结构化文档对象。

**实现要点：**

- 使用 LangChain 的 `DirectoryLoader` 或直接 `glob` + 自定义解析
- 每个文档附加 metadata：`source`（相对路径）、`category`（heroes/equipment/runes）、`name`（文件名去扩展名）
- 解析文件末尾的 `来源` 和 `抓取时间` 行，存入 metadata
- 返回 `list[langchain_core.documents.Document]`

**接口：**

```python
def load_documents(data_dir: str = "data") -> list[Document]:
    """加载所有 Markdown 文件，返回 LangChain Document 列表"""
    ...
```

### 5.2 语义分块 ([src/rag/chunker.py](src/rag/chunker.py))

职责：根据内容类别，将文档按语义边界拆分为独立的 chunk，每个 chunk 保留原始文件的来源信息。

**分块策略：**

#### 英雄文档分块

原始结构：
```
# 中文名 — 英文名
称号 | 图片 | 定位
## 背景故事
...
## 属性
| 属性 | 初始值 | 满级值 |
## 技能
### 被动：技能名
### Q：技能名
### W：技能名
### E：技能名
### R：技能名
```

分块方案（每个英雄产出 7 个 chunk）：

| Chunk | 内容 | 元数据标记 |
|-------|------|-----------|
| 概览 | 中文名、英文名、称号、定位、图片URL | `section: overview` |
| 背景故事 | 背景故事段落 | `section: background` |
| 属性 | 属性表格 | `section: attributes` |
| 被动 | 被动技能名、图标、完整描述 | `section: passive_skill` |
| Q/W/E/R | 各技能：名称、消耗/冷却/范围、描述 | `section: skill`, `skill_key: Q` |

分块方式：按 `## ` 二级标题分割；对于技能区块，再按 `### ` 三级标题细分。

#### 装备文档分块

原始结构：
```
# 名称
图片 | 等级 | 售价
### 基础属性
### 主动效果
### 被动效果
### 神话加成
### 合成路线
### 推荐英雄
```

分块方案（每个装备产出 3 个 chunk）：

| Chunk | 内容 | 元数据标记 |
|-------|------|-----------|
| 概览 | 名称、等级、售价、图标 | `section: overview` |
| 属性+效果 | 基础属性、主动效果、被动效果、神话加成 | `section: effects` |
| 合成+推荐 | 合成路线、推荐英雄 | `section: build` |

#### 符文文档分块

符文文档较短，**每个符文作为一个 chunk**，不拆分。元数据标记 `section: full`。

**接口：**

```python
def chunk_documents(documents: list[Document]) -> list[Document]:
    """按语义分块，返回 chunk 列表，每个 chunk 携带 metadata"""
    ...

def chunk_hero(doc: Document) -> list[Document]:
    """英雄文档分块"""
    ...

def chunk_equipment(doc: Document) -> list[Document]:
    """装备文档分块"""
    ...
```

**分块实现方式：**

- 使用 LangChain 的 `RecursiveCharacterTextSplitter` 或自定义的 `MarkdownHeaderTextSplitter`（基于 `##` / `###` 标题层级）
- 英雄技能按 `###` 标题细分；装备按 `###` 标题细分后合并为 3 个逻辑组
- 每个 chunk 的 `metadata` 中保留 `source`（相对文件路径）、`category`、`section`、`name`（英雄/装备/符文名）

**⚠️ 格式变体容错（实施前必须完成）：**

真实数据可能存在以下格式变体，分块逻辑必须在 ~378 个真实文件上做样例测试后再固化规则：

| 可能的格式变体 | 容错策略 |
|--------------|----------|
| 某些英雄无 `## 背景故事` 标题（直接接在属性前） | 按 `## 属性` 标题反向定位，其前的内容归为背景故事；若无则背景故事 chunk 为空字符串，不生成该 chunk |
| 技能数量 ≠ 5（被动+Q/W/E/R） | 不硬编码技能标签（Q/W/E/R），改为按 `###` 出现顺序依次编号；通过技能名中的"被动"关键词识别被动技能 |
| 装备文档缺少某些 `###` 子标题（如无神话加成、无主动效果） | 合并时检查子标题是否存在，缺失则对应分区为空，不抛异常 |
| 符文文档实际篇幅差异大（某些符文有多段效果描述） | 符文始终不拆分；但如果单个符文超过 1000 字，WARNING 日志记录，人工确认是否需要分段 |
| 文件内 `##` / `###` 标题层级不规范（如用了 `####` 或 `**加粗**` 代替） | 预处理阶段做标题归一化：`####` → `###`，无标题的纯文本块附加到前一个最近的 chunk |
| 某些文件开头没有 `# 名称` 而直接是内容 | 用文件名（去扩展名）作为 name 回退值 |

**测试流程：**

1. 在完整 `data/` 目录上运行分块脚本，统计每种类型的 chunk 数量分布
2. 抽查 10-20 个文件的分块输出，验证语义边界正确
3. 对边界案例（技能不足5个的英雄、缺少子标题的装备）做人工确认
4. 分块结果确认后，再写入 ChromaDB

---

## 六、Embedding 与向量存储

### 6.1 Embedding 包装器 ([src/rag/embedder.py](src/rag/embedder.py))

职责：封装 sentence-transformers 模型，提供统一的 embed 接口。

**实现要点：**

- 使用 `sentence_transformers.SentenceTransformer` 加载 `BAAI/bge-small-zh-v1.5`
- 模型在进程启动时加载一次（懒加载或模块级单例）
- 支持单条和多条文本 embed
- BGE 模型要求：检索时 query 前加 `"为这个句子生成表示以用于检索相关文章："` 前缀，文档不加前缀
- `EMBEDDING_NORMALIZE=true` 时对向量做 L2 归一化

**接口：**

```python
class Embedder:
    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5",
                 device: str = "cpu", normalize: bool = True): ...
    def embed_query(self, query: str) -> list[float]: ...
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    @property
    def dimension(self) -> int: ...  # 返回向量维度
```

### 6.2 向量存储管理 ([src/rag/vector_store.py](src/rag/vector_store.py))

职责：管理 ChromaDB 的索引构建、持久化、查询。

**实现要点：**

- 使用 `langchain_chroma.Chroma` 封装
- `build_index()` 方法：加载文档 → 分块 → 生成 embedding → 写入 ChromaDB
- 索引构建是一次性操作（数据是静态快照），构建后持久化到 `data/chroma_db/`
- 启动时检查 ChromaDB 是否已存在：若存在则直接加载；若不存在则自动构建
- 提供 `--rebuild-index` 参数强制重建

**索引构建流程：**

```
load_documents("data/")
    → chunk_documents(docs)       # 378 文件 → ~1500 chunks
    → embedder.embed_documents()  # 批量生成向量 → ChromaDB
    → bm25_index.build(chunks)    # 中文分词 → BM25 序列化
```

**接口：**

```python
class VectorStoreManager:
    def __init__(self, persist_dir: str, collection_name: str,
                 embedder: Embedder): ...
    def index_exists(self) -> bool: ...
    def build_index(self, chunks: list[Document], force: bool = False) -> None: ...
    def as_retriever(self, top_k: int = 10) -> BaseRetriever: ...
```

---

## 七、检索策略 — 混合检索 + 两阶段 ([src/rag/retriever.py](src/rag/retriever.py))

### 7.1 设计动机

纯向量检索对语义模糊查询效果好，但对**精确名词查询**（英雄名"阿狸"、装备名"冰霜之心"、符文名"强攻"）容易漏检或排序靠后——嵌入模型将专有名词映射到语义空间时可能与字面匹配偏差较大。引入 **BM25 关键词检索**作为并行通路，两者互补。

### 7.2 整体流程

```
用户问题
    │
    ├─────────────────────────────────────┐
    ▼                                     ▼
向量检索通路                            BM25 关键词检索通路
    │                                     │
    ├─ embed_query(question)              ├─ jieba 分词(question)
    ├─ ChromaDB.similarity_search(k=10)   ├─ BM25 索引查询(k=10)
    └─ 获得 top-10 + 向量分数              └─ 获得 top-10 + BM25 分数
    │                                     │
    └──────────┬──────────────────────────┘
               ▼
         结果融合（Reciprocal Rank Fusion）
               │
               ├─ RRF 对两路结果合并去重
               ├─ 按融合分数降序，取 top-N（N = coarse_k）
               │
               ▼
         Cross-Encoder 精排
               │
               ├─ 对 (question, chunk_i) 逐一打分
               ├─ 按 rerank_score 降序
               └─ 取 top-3
               │
               ▼
        返回 3 个最相关的 chunk
```

### 7.3 BM25 索引构建

- 在索引构建阶段，从所有 chunk 的文本内容构建 BM25 索引
- 使用 `jieba` 分词（中文文本必须分词后才能用 BM25）
- 使用 `rank_bm25` 库（纯 Python，轻量）
- 索引随 ChromaDB 一起持久化（pickle 到 `data/chroma_db/bm25_index.pkl`）
- 新增模块：`src/rag/bm25_index.py`

**BM25 索引接口：**

```python
class BM25Index:
    def __init__(self): ...
    def build(self, chunks: list[Document]) -> None:
        """对所有 chunk 分词后构建 BM25 索引"""
        ...
    def search(self, query: str, k: int = 10) -> list[tuple[Document, float]]:
        """返回 (chunk, bm25_score) 列表，分数归一化到 [0, 1]"""
        ...
    def save(self, path: str) -> None: ...
    @classmethod
    def load(cls, path: str) -> "BM25Index": ...
```

### 7.4 结果融合（Reciprocal Rank Fusion）

```
RRF_score(chunk) = Σ  1 / (k + rank_i)
                   i∈{vector, bm25}

其中 k = 60（经典常量），rank_i 从 1 开始
```

- 对于只在某一通路出现的 chunk，另一通路的 rank 视为 ∞（贡献 0）
- RRF 的优点：不需要分数归一化，对排名差异鲁棒
- 融合后取 top-10 送入精排

### 7.5 精排（Cross-Encoder）

- 使用 `sentence_transformers.CrossEncoder` 加载 `BAAI/bge-reranker-base`
- 对每个 (query, chunk.content) 对计算相关性分数
- 按分数降序，取 top-3
- CrossEncoder 模型在模块级单例加载

### 7.6 边界处理

- 精排分数阈值默认设为 `0`（即不过滤，保留所有精排结果）。BGE-Reranker 输出的是 logits（可为负数），实际有效阈值需在真实数据上跑一轮后根据分数分布确定，**标注为待调优项（TODO）**
- 阈值调优方法：启动后运行若干典型查询，记录精排分数分布，再设定合理阈值
- 如果融合后结果 < 3，则跳过精排，直接用全部结果
- 如果 BM25 索引加载失败，降级为纯向量检索（WARNING 日志记录）

### 7.7 接口

```python
class HybridRetriever:
    def __init__(self, vector_store: VectorStoreManager,
                 embedder: Embedder,
                 bm25_index: BM25Index,
                 coarse_k: int = 10, rerank_k: int = 3,
                 rerank_model: str = "BAAI/bge-reranker-base",
                 min_relevance: float = 0): ...  # 0 = 不过滤，待调优

    async def retrieve(self, query: str) -> list[RetrievedChunk]:
        """混合检索 → 融合 → 精排，返回 top-k"""
        ...

    def _vector_search(self, query: str) -> list[RetrievedChunk]: ...
    def _bm25_search(self, query: str) -> list[RetrievedChunk]: ...
    def _rrf_fusion(self, results_a: list, results_b: list) -> list[RetrievedChunk]: ...
    def _rerank(self, query: str,
                chunks: list[RetrievedChunk]) -> list[RetrievedChunk]: ...
```

---

## 八、LLM 生成 ([src/rag/generator.py](src/rag/generator.py))

### 8.1 实现要点

- 使用 `langchain_deepseek.ChatDeepSeek`（或直接调用 `openai` SDK 兼容的 DeepSeek API）
- 支持同步和异步调用（CLI 下使用同步或 `asyncio.run`）
- 生成参数从配置读取：model、max_tokens、temperature
- 响应中解析 `[N]` 引用标记，用于后处理

### 8.2 接口

```python
class Generator:
    def __init__(self, api_key: str, base_url: str, model: str,
                 max_tokens: int = 2048, temperature: float = 0.3): ...

    def generate(self, prompt: str) -> str:
        """同步生成回答"""
        ...

    async def agenerate(self, prompt: str) -> str:
        """异步生成回答"""
        ...
```

---

## 九、System Prompt 与提示词模板 ([src/rag/prompt.py](src/rag/prompt.py))

### 9.1 系统提示词

```
你是英雄联盟游戏助手，专门回答关于 LOL 英雄、装备、符文的问题。
你的回答必须严格基于下方提供的资料内容。

规则：
1. 只使用下方「参考資料」中的信息，不要编造不存在的信息
2. 当资料不足以回答问题时，明确告知：「当前数据中未找到相关信息」
3. 关键事实后标注内联引用 [N]，如「冰霜之心被动可使附近敌人攻速降低15% [1]」
4. 回答末尾附上引用列表，格式为：[N] 来源: data/xxx/xxx.md
5. 回答使用中文，简洁清晰
6. 推理类问题先列出分析依据，再给出结论
7. 用户描述不清时，列出可能的匹配项让用户确认
```

### 9.2 消息构造模板

```python
def build_messages(
    query: str,
    chunks: list[RetrievedChunk],
    history: list[Message],
    system_prompt: str,
) -> list[dict]:
    """构造发送给 LLM 的消息列表"""
    # 构建参考资料文本
    context_parts = []
    for i, chunk in enumerate(chunks):
        context_parts.append(
            f"[{i+1}] 来源: {chunk.metadata['source']}\n{chunk.content}"
        )
    context = "\n\n---\n\n".join(context_parts)

    # 组装消息
    messages = [{"role": "system", "content": system_prompt}]

    # 加入参考资料（作为系统消息）
    messages.append({
        "role": "system",
        "content": f"## 参考资料\n\n{context}"
    })

    # 加入历史对话（最近 MAX_HISTORY_TURNS 轮）
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    # 加入当前问题
    messages.append({"role": "user", "content": query})

    return messages
```

---

## 十、对话历史管理 ([src/rag/conversation.py](src/rag/conversation.py))

### 10.1 实现要点

- 内存中维护 `deque`，最大长度 = `MAX_HISTORY_TURNS * 2`（每轮 = user + assistant 各一条）
- 支持的操作：添加消息、获取历史、清空、获取轮数
- 超出上限时自动丢弃最早的消息，并给出提示

### 10.2 接口

```python
class ConversationHistory:
    def __init__(self, max_turns: int = 10): ...
    def add_user_message(self, content: str) -> None: ...
    def add_assistant_message(self, content: str) -> None: ...
    def get_history(self) -> list[Message]: ...
    def clear(self) -> None: ...
    def turn_count(self) -> int: ...
    def is_full(self) -> bool: ...
```

---

## 十一、CLI 交互界面 ([src/rag/cli.py](src/rag/cli.py))

### 11.1 启动流程

```
python3 -m src.rag.cli
    │
    ├── 1. 加载 .env 配置
    ├── 2. 初始化各模块（Embedder, ChromaDB, BM25Index, Generator, Retriever）
    │      - 如果 ChromaDB 索引不存在 → 自动构建（含向量索引和 BM25 索引）
    │      - 如果索引已存在 → 直接加载
    ├── 3. 输出欢迎信息 + 可用命令说明
    └── 4. 进入交互循环
```

### 11.2 交互循环

```
┌─────────────────────────────────────┐
│  欢迎使用 英雄联盟 RAG 助手           │
│  输入问题开始查询，输入 /help 查看帮助  │
│  指令: /clear 清空历史  /quit 退出     │
│  加载资料: 英雄 X, 装备 X, 符文 X      │
└─────────────────────────────────────┘

>>> 冰霜之心的被动是什么？

[检索中...] (2.3s)
冰霜之心的被动「凛冬之拥」可使附近敌人攻速降低 15% [1]...

---
[1] 来源: data/equipment/冰霜之心.md
```

### 11.3 命令处理

| 输入 | 行为 |
|------|------|
| 空行 | 提示 "请输入问题，输入 /help 查看帮助" |
| `/help` | 显示可用命令列表 |
| `/clear` | 清空对话历史，提示 "对话历史已清空" |
| `/quit` 或 `/exit` | 退出程序（也支持 Ctrl+C / Ctrl+D） |
| 纯空格 | 同空行处理 |
| 超过 2000 字符 | 提示 "输入过长，请精简到 2000 字符以内" |
| 其他 | 作为查询问题，进入 RAG 流程 |

### 11.4 输出格式

- 回答前显示检索耗时
- 回答中内联引用 `[N]`
- 回答末尾显示引用列表（格式：`[N] 来源: data/xxx/xxx.md`）
- 数据不足时显示 "当前数据中未找到相关信息" 并列出可能的匹配项

### 11.5 日志记录

每次查询记录（写入 `logs/rag.log`）：

```
2026-06-22 10:30:00 [INFO] query="冰霜之心的被动是什么？" retrieval_ms=2300 generation_ms=3200 total_ms=5500 chunks=3 hit=true
```

日志级别控制：
- `INFO`: 查询内容、耗时、命中状态
- `DEBUG`: 检索结果详情、完整 prompt、完整响应
- `WARNING`: 检索分数低、历史截断、文件读取跳过
- `ERROR`: API 调用失败、文件读取错误

---

## 十二、核心 Pipeline 流程 ([src/rag/__init__.py](src/rag/__init__.py))

`RAGPipeline` 类作为总编排器，串联各模块：

```python
class RAGPipeline:
    def __init__(self, config: dict): ...
    async def initialize(self) -> None:
        """初始化所有子模块（Embedder, ChromaDB, BM25Index, Retriever, Generator）"""
        ...
    async def query(self, question: str,
                    history: ConversationHistory) -> RAGResponse:
        """
        完整 RAG 流程：
        1. 混合检索（向量 + BM25 → RRF 融合 → Cross-Encoder 精排）
        2. 构建 prompt（含 system prompt + chunks + history）
        3. 调用 LLM 生成
        4. 构造 RAGResponse
        """
        ...
```

**完整调用链：**

```
CLI 交互循环
    │
    ▼
RAGPipeline.query(question, history)
    │
    ├── Retriever.retrieve(question)
    │       ├── [并行] Embedder.embed_query(question) → ChromaDB.similarity_search(k=10)
    │       ├── [并行] jieba 分词(question) → BM25Index.search(k=10)
    │       ├── RRF 融合两路结果 → top-10
    │       └── CrossEncoder.predict([(question, chunk) ...]) → top-3
    │
    ├── prompt.build_messages(question, chunks, history, system_prompt)
    │
    ├── Generator.agenerate(messages)
    │
    └── 构造 RAGResponse(answer, citations, chunks_used, timings)
```

---

## 十三、错误与边界处理

| 场景 | 处理方式 |
|------|----------|
| .env 中 API key 缺失 | 启动时报错退出，提示配置 API key |
| ChromaDB 索引不存在 | 自动构建，输出进度（"正在构建索引... X/1500"） |
| ChromaDB 索引构建失败 | 报错退出，指示用户检查 data/ 目录 |
| Embedding 模型下载失败 | 启动时报错，提示网络问题或手动下载 |
| LLM API 调用超时 | 重试 1 次，仍失败则告知用户"服务暂时不可用，请稍后重试" |
| LLM API 返回错误 | 记录错误日志，告知用户错误信息 |
| 所有 chunk 精排分数过低 | 阈值默认 0（不过滤），待调优后生效。届时回复"当前数据中未找到相关信息"，并尝试列出可能匹配的数据项 |
| 用户输入过短（≤1 字符） | 提示"请输入更详细的问题" |
| 用户输入超长（>2000 字符） | 提示"输入过长，请精简到 2000 字符以内" |
| 对话历史超限 | 自动截断最早的轮次，DEBUG 级别记录 |
| 某文件读取失败 | WARNING 级别记录，跳过该文件继续加载 |
| 某文件分块异常（格式变体不匹配） | WARNING 级别记录文件路径和异常原因，用文件名回退生成单个 chunk，不阻塞整体流程 |
| BM25 索引文件缺失或加载失败 | WARNING 级别记录，降级为纯向量检索，功能不受影响 |
| Ctrl+C | 捕获 KeyboardInterrupt，优雅退出（提示"再见！"） |
| 未知命令 | 提示"未知命令，输入 /help 查看可用命令" |

---

## 十四、依赖项

```
# requirements.txt 新增
langchain>=0.3.0
langchain-chroma>=0.2.0
langchain-deepseek>=0.1.0
sentence-transformers>=3.0.0
chromadb>=0.5.0
python-dotenv>=1.0.0
jieba>=0.42.0
rank-bm25>=0.2.2
```

---

## 十五、索引构建进度估算

| 步骤 | 数据量 | 预计耗时 |
|------|--------|----------|
| 加载 378 个 Markdown 文件 | ~2MB | <1s |
| 语义分块 | 378 → ~1,500 chunks | ~2s |
| 生成 Embedding（BGE-small, CPU） | ~1,500 chunks × 512d | ~10-30s |
| 写入 ChromaDB | ~1,500 向量 | ~5s |
| 构建 BM25 索引（jieba 分词） | ~1,500 chunks | ~2s |
| **总计（首次构建）** | | **~20-45s** |

GPU 环境下 embedding 生成可显著加速。后续启动直接加载已有索引，<2s。

---

## 十六、测试策略

### 16.1 单元测试

| 模块 | 测试内容 |
|------|----------|
| `chunker.py` | 英雄/装备/符文分块数量、分块元数据正确性 |
| `conversation.py` | 消息添加、历史截断、清空、轮数计算 |
| `models.py` | dataclass 构造与序列化 |
| `prompt.py` | 消息构造格式、引用编号对应 |

### 16.2 集成测试

| 场景 | 测试内容 |
|------|----------|
| 索引构建 | 用少量 fixture 数据测试 build_index 流程 |
| 检索流程 | 已知查询 → 期望的 chunk 被检索到 |
| 端到端 | 完整 pipeline（需 mock LLM 响应） |

### 16.3 CLI 测试

- 使用 `subprocess` 或 `pexpect` 测试 CLI 交互
- 测试 `/clear`, `/quit`, 空输入等命令
- 测试 Ctrl+C 退出行为

### 16.4 测试数据

- 在 `tests/fixtures/rag/` 下放置少量 Markdown 文件（2-3 个英雄、2-3 个装备、2-3 个符文）
- 用于分块、索引、检索测试

---

## 十七、实现优先级

| 优先级 | 模块 | 说明 |
|--------|------|------|
| P0 | `config.py` | 所有模块依赖配置 |
| P0 | `models.py` | 所有模块依赖数据模型 |
| P0 | `loader.py` + `chunker.py` | 数据入口 |
| P0 | `embedder.py` + `vector_store.py` | 向量索引构建与存储 |
| P0 | `bm25_index.py` | BM25 关键词索引（与向量索引并行构建） |
| P1 | `prompt.py` | System Prompt 和消息构造 |
| P1 | `retriever.py` | 混合检索 + 精排 |
| P1 | `generator.py` | LLM 调用 |
| P1 | `conversation.py` | 对话历史 |
| P2 | `pipeline.py`（`__init__.py`） | 总编排 |
| P2 | `cli.py` | 交互界面 |
| P3 | 单元测试 | 随模块编写 |
| P3 | 集成测试 | CLI 完成后编写 |
