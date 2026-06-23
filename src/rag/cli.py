"""英雄联盟 RAG 助手 — CLI 交互界面

用法:
    python -m src.rag.cli              # 启动交互模式
    python -m src.rag.cli --rebuild-index  # 强制重建索引
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

from src.rag.config import RAGConfig
from src.rag.conversation import ConversationHistory

logger = logging.getLogger(__name__)

WELCOME = """
╔══════════════════════════════════════════╗
║      欢迎使用 英雄联盟 RAG 助手            ║
║                                          ║
║  输入问题开始查询，输入 /help 查看帮助      ║
║  指令: /clear 清空历史  /quit 退出         ║
╚══════════════════════════════════════════╝
"""

HELP_TEXT = """
可用命令:
  /help       显示此帮助信息
  /clear      清空对话历史
  /quit       退出程序
  /exit       退出程序
  Ctrl+C      退出程序
  Ctrl+D      退出程序

其他输入均视为查询问题，系统将检索相关资料后生成回答。
"""


def setup_logging(config: RAGConfig) -> None:
    """配置日志系统"""
    log_dir = Path(config.log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, config.log_level.upper(), logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(config.log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )


def validate_input(user_input: str, max_length: int = 2000) -> tuple[bool, str]:
    """验证用户输入。

    Returns:
        (is_query, message)
        - is_query=True: 输入有效，作为查询
        - is_query=False: 输入是命令/无效，message 为提示信息
    """
    stripped = user_input.strip()

    # 空输入
    if not stripped:
        return False, "请输入问题，输入 /help 查看帮助"

    # 命令
    if stripped.startswith("/"):
        cmd = stripped.lower()
        if cmd in ("/help", "/clear", "/quit", "/exit"):
            return False, cmd  # message 直接返回命令字符串
        else:
            return False, f"未知命令: {stripped}，输入 /help 查看可用命令"

    # 长度检查
    if len(stripped) > max_length:
        return False, f"输入过长（{len(stripped)} 字符），请精简到 {max_length} 字符以内"

    # 过短检查
    if len(stripped) <= 1:
        return False, "请输入更详细的问题"

    return True, ""


async def process_query(
    pipeline, history: ConversationHistory, question: str
) -> str:
    """处理一次查询并返回格式化输出"""
    response = await pipeline.query(question, history)

    # 更新对话历史
    history.add_user_message(question)
    history.add_assistant_message(response.answer)

    return format_response(response)


def format_response(response) -> str:
    """格式化 RAG 响应用于终端输出"""
    retrieval_s = response.retrieval_time_ms / 1000
    generation_s = response.generation_time_ms / 1000
    total_s = retrieval_s + generation_s

    lines = [
        f"\n[检索: {retrieval_s:.1f}s | 生成: {generation_s:.1f}s | 总计: {total_s:.1f}s]",
        f"参考资料: {len(response.chunks_used)} 条",
        "-" * 50,
        response.answer,
        "-" * 50,
    ]

    # 追加引用列表
    if response.citations:
        lines.append("")
        for i, citation in enumerate(response.citations, 1):
            lines.append(f"[{i}] 来源: {citation}")

    return "\n".join(lines)


async def run_interactive(config: RAGConfig, rebuild_index: bool = False) -> None:
    """运行交互式 REPL"""
    from src.rag import RAGPipeline

    # 初始化
    pipeline = RAGPipeline(config)
    await pipeline.initialize()

    if rebuild_index:
        print("正在重建索引...")
        await pipeline.rebuild_index()
        print("索引重建完成！")

    # 输出统计信息
    stats = pipeline.stats
    print(WELCOME)
    print(f"  模型: {stats['embedding_model']} ({stats['embedding_dim']}d)")
    print(f"  索引状态: {'已就绪' if stats['index_exists'] else '未构建'}")
    print()

    history = ConversationHistory(max_turns=config.max_history_turns)

    # 信号处理：Ctrl+C 优雅退出
    running = True

    def _on_sigint(signum, frame):
        nonlocal running
        running = False
        print("\n\n再见！")
        sys.exit(0)

    signal.signal(signal.SIGINT, _on_sigint)

    while running:
        try:
            user_input = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        is_query, result = validate_input(user_input, config.max_input_length)

        if not is_query:
            if result == "/help":
                print(HELP_TEXT)
            elif result == "/clear":
                history.clear()
                print("对话历史已清空")
            elif result in ("/quit", "/exit"):
                print("再见！")
                break
            else:
                print(result)
            continue

        # 处理查询
        try:
            output = await process_query(pipeline, history, result)
            print(output)
        except Exception as e:
            logger.error("查询处理失败", exc_info=True)
            print(f"\n处理查询时出错: {e}")


def main():
    """CLI 入口点"""
    parser = argparse.ArgumentParser(
        description="英雄联盟 RAG 助手 — 基于本地数据的智能问答系统"
    )
    parser.add_argument(
        "--rebuild-index",
        action="store_true",
        help="启动时强制重建向量索引和 BM25 索引",
    )
    parser.add_argument(
        "--config",
        default=".env",
        help=".env 配置文件路径（默认: .env）",
    )
    args = parser.parse_args()

    # 加载配置
    config = RAGConfig.from_env(args.config)

    # 校验配置
    try:
        config.validate()
    except ValueError as e:
        print(f"配置错误: {e}", file=sys.stderr)
        sys.exit(1)

    # 配置日志
    setup_logging(config)

    # 启动交互循环
    asyncio.run(run_interactive(config, rebuild_index=args.rebuild_index))


if __name__ == "__main__":
    main()
