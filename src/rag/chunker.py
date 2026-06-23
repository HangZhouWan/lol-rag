"""语义分块 — 按内容类别将 Markdown 文档拆分为独立 chunk"""

from __future__ import annotations

import logging
import re
from copy import deepcopy

from langchain_core.documents import Document

logger = logging.getLogger(__name__)


def _split_by_headings(content: str, levels: int = 2) -> list[tuple[str, str, str]]:
    """按指定层级的 Markdown 标题分割内容。

    Args:
        content: 要分割的 Markdown 文本
        levels: 2 = 只匹配 ##，3 = 只匹配 ###，23 = 匹配两者

    返回 [(标题级别 "h2"|"h3", 标题文本, 内容), ...]
    """
    if levels == 2:
        prefix = "##"
        pattern = re.compile(r"^(##)\s+(.+)$", re.MULTILINE)
    elif levels == 3:
        prefix = "###"
        pattern = re.compile(r"^(###)\s+(.+)$", re.MULTILINE)
    else:
        prefix = "##"
        pattern = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)

    matches = list(pattern.finditer(content))

    if not matches:
        return [("h0", "", content.strip())]

    sections = []
    for i, match in enumerate(matches):
        level = "h2" if match.group(1) == "##" else "h3"
        title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end].strip()
        sections.append((level, title, body))

    # 第一个标题之前的内容作为 overview
    if matches:
        first_start = matches[0].start()
        preamble = content[:first_start].strip()
        if preamble:
            sections.insert(0, ("h0", "", preamble))

    return sections


def chunk_hero(doc: Document) -> list[Document]:
    """英雄文档分块：概览、背景故事、属性、被动、Q/W/E/R 各技能"""
    content = doc.page_content
    metadata = deepcopy(doc.metadata)
    sections = _split_by_headings(content, levels=2)  # 只按 ## 分割顶层
    chunks: list[Document] = []

    # 概览：h2 之前的内容
    overview_content = ""
    h2_sections = [(lvl, title, body) for lvl, title, body in sections if lvl == "h2"]

    first_h2_idx = next(
        (i for i, (lvl, _, _) in enumerate(sections) if lvl == "h2"), len(sections)
    )
    for i in range(first_h2_idx):
        _, _, body = sections[i]
        overview_content += body + "\n"

    if overview_content.strip():
        m = deepcopy(metadata)
        m["section"] = "overview"
        chunks.append(Document(page_content=overview_content.strip(), metadata=m))

    # 处理 h2 区块
    for level, title, body in h2_sections:
        # 判断是否为技能区块（包含 ### 子标题）
        sub_sections = _split_by_headings(body, levels=3)  # 只匹配 ### 子标题
        h3_subs = [(lvl, t, b) for lvl, t, b in sub_sections if lvl == "h3"]

        if "背景" in title or "故事" in title:
            m = deepcopy(metadata)
            m["section"] = "background"
            chunks.append(Document(page_content=body.strip(), metadata=m))
        elif "属性" in title:
            m = deepcopy(metadata)
            m["section"] = "attributes"
            chunks.append(Document(page_content=body.strip(), metadata=m))
        elif "技能" in title or h3_subs:
            if h3_subs:
                # 将所有技能（被动 + Q/W/E/R）作为一个组合 chunk，
                # 确保检索时 LLM 能获取完整的英雄技能信息
                m = deepcopy(metadata)
                m["section"] = "skills"
                chunks.append(
                    Document(
                        page_content=f"## {title}\n\n{body.strip()}",
                        metadata=m,
                    )
                )
            elif body.strip():
                # 回退：没有 h3 子标题的技能区块
                m = deepcopy(metadata)
                if "被动" in title:
                    m["section"] = "passive_skill"
                else:
                    m["section"] = "skill"
                chunks.append(
                    Document(
                        page_content=f"## {title}\n\n{body.strip()}",
                        metadata=m,
                    )
                )
        else:
            # 无法识别的 h2 区块，保留为通用 section
            if body.strip():
                m = deepcopy(metadata)
                m["section"] = "general"
                m["heading"] = title
                chunks.append(
                    Document(
                        page_content=f"## {title}\n\n{body.strip()}",
                        metadata=m,
                    )
                )

    logger.debug("英雄 %s → %d chunks", metadata.get("name"), len(chunks))
    return chunks


def chunk_equipment(doc: Document) -> list[Document]:
    """装备文档分块：概览（含基本信息）、属性+效果、合成+推荐"""
    content = doc.page_content
    metadata = deepcopy(doc.metadata)
    sections = _split_by_headings(content, levels=3)  # 装备用 ### 子标题

    overview_parts: list[str] = []
    effects_parts: list[str] = []
    build_parts: list[str] = []

    for level, title, body in sections:
        title_lower = title.lower().strip()
        if level == "h0":
            overview_parts.append(body)
        elif "基础属性" in title_lower or "属性" in title_lower:
            effects_parts.append(f"### {title}\n{body}")
        elif "主动" in title_lower or "被动" in title_lower or "神话" in title_lower or "效果" in title_lower:
            effects_parts.append(f"### {title}\n{body}")
        elif "合成" in title_lower or "推荐" in title_lower or "路线" in title_lower:
            build_parts.append(f"### {title}\n{body}")
        else:
            # 未识别子标题，归入 effects
            effects_parts.append(f"### {title}\n{body}")

    chunks: list[Document] = []

    if overview_parts:
        m = deepcopy(metadata)
        m["section"] = "overview"
        chunks.append(Document(page_content="\n\n".join(overview_parts).strip(), metadata=m))

    if effects_parts:
        m = deepcopy(metadata)
        m["section"] = "effects"
        chunks.append(Document(page_content="\n\n".join(effects_parts).strip(), metadata=m))

    if build_parts:
        m = deepcopy(metadata)
        m["section"] = "build"
        chunks.append(Document(page_content="\n\n".join(build_parts).strip(), metadata=m))

    logger.debug("装备 %s → %d chunks", metadata.get("name"), len(chunks))
    return chunks


def chunk_rune(doc: Document) -> list[Document]:
    """符文文档不分块 — 每个符文一个 chunk"""
    metadata = deepcopy(doc.metadata)
    metadata["section"] = "full"
    return [Document(page_content=doc.page_content, metadata=metadata)]


def chunk_documents(documents: list[Document]) -> list[Document]:
    """按语义分块所有文档。根据 category 分发到对应的分块函数。

    如果某文档分块失败（格式变体不匹配），则记录 WARNING 并用整个文档
    作为单个 chunk 回退，不阻塞整体流程。
    """
    all_chunks: list[Document] = []

    for doc in documents:
        category = doc.metadata.get("category", "")
        name = doc.metadata.get("name", "unknown")

        try:
            if category == "heroes":
                chunks = chunk_hero(doc)
            elif category == "equipment":
                chunks = chunk_equipment(doc)
            elif category == "runes":
                chunks = chunk_rune(doc)
            else:
                logger.warning("未知类别 '%s'，按 rune 不分块处理: %s", category, name)
                chunks = chunk_rune(doc)
            all_chunks.extend(chunks)
        except Exception:
            logger.warning(
                "分块异常，用整文档回退: %s（类别=%s）", name, category, exc_info=True
            )
            # 回退：整文档作为单个 chunk
            m = deepcopy(doc.metadata)
            m["section"] = "full"
            all_chunks.append(Document(page_content=doc.page_content, metadata=m))

    logger.info(
        "分块完成: %d 文档 → %d chunks", len(documents), len(all_chunks)
    )
    return all_chunks
