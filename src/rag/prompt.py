"""System Prompt 定义和消息构造模板"""

from __future__ import annotations

from src.rag.models import RetrievedChunk, Message

SYSTEM_PROMPT = """你是英雄联盟游戏助手，专门回答关于 LOL 英雄、装备、符文的问题。
你的回答必须严格基于下方提供的资料内容。

规则：
1. 只使用下方「参考资料」中的信息，不要编造不存在的信息
2. 当资料不足以回答问题时，明确告知：「当前数据中未找到相关信息」
3. 关键事实后标注内联引用 [N]，如「冰霜之心被动可使附近敌人攻速降低15% [1]」
4. 回答末尾附上引用列表，格式为：[N] 来源: data/xxx/xxx.md
5. 回答使用中文，简洁清晰
6. 推理类问题先列出分析依据，再给出结论
7. 用户描述不清时，列出可能的匹配项让用户确认"""


def build_messages(
    query: str,
    chunks: list[RetrievedChunk],
    history: list[Message],
    system_prompt: str,
) -> list[dict]:
    """构造发送给 LLM 的完整消息列表。

    Args:
        query: 用户当前问题
        chunks: 检索到的 chunk 列表（已精排后的 top-k）
        history: 对话历史（最近 MAX_HISTORY_TURNS 轮）
        system_prompt: 系统提示词

    Returns:
        消息列表，每项 {"role": str, "content": str}
    """
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
    ]

    # 构建参考资料文本（带内联引用编号）
    if chunks:
        context_parts = []
        for i, chunk in enumerate(chunks):
            context_parts.append(
                f"[{i + 1}] 来源: {chunk.metadata['source']}\n{chunk.content}"
            )
        context = "\n\n---\n\n".join(context_parts)
    else:
        context = "（无参考资料）"

    messages.append({
        "role": "system",
        "content": f"## 参考资料\n\n{context}",
    })

    # 加入对话历史
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    # 当前用户问题
    messages.append({"role": "user", "content": query})

    return messages
