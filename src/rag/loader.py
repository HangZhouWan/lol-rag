"""Markdown 文档加载器 — 遍历 data/ 目录，加载所有 .md 文件为 LangChain Document"""

from __future__ import annotations

import logging
from pathlib import Path

from langchain_core.documents import Document

logger = logging.getLogger(__name__)

CATEGORY_DIRS = {
    "heroes": "heroes",
    "equipment": "equipment",
    "runes": "runes",
}


def load_documents(data_dir: str = "data") -> list[Document]:
    """递归加载 data/heroes/, data/equipment/, data/runes/ 下所有 .md 文件。

    每个 Document 携带 metadata：
        - source: 相对于 data_dir 的文件路径
        - category: "heroes" | "equipment" | "runes"
        - name: 文件名去扩展名（作为英雄名/装备名/符文名）
    """
    documents: list[Document] = []
    data_path = Path(data_dir)

    if not data_path.exists():
        logger.warning("数据目录不存在: %s", data_dir)
        return documents

    for category, subdir in CATEGORY_DIRS.items():
        category_path = data_path / subdir
        if not category_path.exists():
            logger.warning("子目录不存在，跳过: %s", category_path)
            continue

        for md_file in category_path.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                if not content.strip():
                    logger.warning("跳过空文件: %s", md_file)
                    continue

                relative_path = str(md_file.relative_to(data_path))
                name = md_file.stem  # 文件名去扩展名

                doc = Document(
                    page_content=content,
                    metadata={
                        "source": relative_path,
                        "category": category,
                        "name": name,
                    },
                )
                documents.append(doc)

            except Exception:
                logger.warning("读取文件失败，跳过: %s", md_file, exc_info=True)

    logger.info("加载完成: 共 %d 个文档", len(documents))
    return documents
