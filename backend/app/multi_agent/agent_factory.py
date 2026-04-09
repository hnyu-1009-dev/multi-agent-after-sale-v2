import httpx
import time

from agents import Agent, ModelSettings, function_tool, Runner
# function_tool:
# 用来把一个 Python 函数注册成 Agent 可调用的工具。
#
# 也就是说，被 @function_tool 修饰后的函数，不再只是普通业务函数，
# 而是可以被别的 Agent 识别、选择、调用的“工具”。
#
# Runner:
# Agent 的执行器。
# Agent 本身只是一个“角色定义 + 模型 + 工具配置”的对象，
# 真正负责执行 Agent 的是 Runner。

from agents.run import RunConfig
# RunConfig: Agent 运行时配置。
# 用来控制一次具体运行时的行为，比如：
# - 是否关闭 tracing
# - 是否启用某些执行选项
#
# 它和 Agent 自身的静态配置不同：
# - Agent：定义“这个智能体是谁、拥有什么能力”
# - RunConfig：定义“这一次怎么跑”


from app.multi_agent.technical_agent import technical_agent
from app.infrastructure.ai.openai_client import sub_model
# technical_agent: 技术专家智能体。
#
# 它通常负责：
# - 技术咨询
# - 故障分析
# - 使用指导
# - 某些实时资讯（如果它挂了联网工具）
#
# 这里导入它，是为了后续在工具函数里“转交给它处理”。

from app.multi_agent.service_agent import comprehensive_service_agent
# comprehensive_service_agent: 全能业务智能体 / 服务站业务智能体。
#
# 它通常负责：
# - 服务站查询
# - 线下门店查找
# - 导航 / 地图路径规划
# - 地理位置相关业务
#
# 这里同样不是直接自己处理，而是后面封装成工具调用入口。

from app.infrastructure.tools.mcp.mcp_servers import (
    search_mcp_client,
    baidu_mcp_client,
)
from app.config.settings import settings
# search_mcp_client / baidu_mcp_client:
# 这两个 MCP 客户端在这份代码里“当前没有直接使用”。
#
# 从导入关系看，它们大概率已经被 technical_agent 和
# comprehensive_service_agent 自己内部使用或依赖。
#
# 换句话说：
# 当前这个文件只是“做路由分发”，并不直接调这两个 MCP。
#
# 如果这两个变量后续确实没有在本文件里使用，
# 从代码整洁性来说可以删掉这个导入，避免误导阅读者。

from app.infrastructure.logging.logger import logger
# logger: 项目的日志对象。
#
# 这里主要用于记录：
# - 当前用户请求被路由给了哪个专家 Agent
# - 路由时带了什么 query
#
# 这种日志对多 Agent 架构特别重要，
# 因为后续排查问题时，你需要知道：
# - 问题到底被分给了谁
# - 分发路径是否正确

# 这组关键词用于把“强依赖当前时间/最新外部数据”的问题识别为实时资讯类，
# 避免这类问题先去查本地知识库。
REALTIME_QUERY_KEYWORDS = (
    "今天",
    "今日",
    "最新",
    "刚刚",
    "现在",
    "实时",
    "股价",
    "汇率",
    "天气",
    "气温",
    "新闻",
    "比分",
    "版本号",
    "发布会",
    "热搜",
    "股票",
    "price",
    "weather",
    "news",
    "score",
    "version",
)

KNOWLEDGE_MISS_MARKERS = (
    "未检索到任何相关的文档",
    "无法提供回复",
    "未找到",
    "没有相关",
    "无相关",
)

TECHNICAL_UNAVAILABLE_MARKERS = (
    "当前技术专家服务暂时不可用",
    "技术专家暂时无法回答",
    "请稍后再试",
)

KNOWLEDGE_PREQUERY_TIMEOUT_SECONDS = 6.0
KNOWLEDGE_PREQUERY_COOLDOWN_SECONDS = 45.0
_knowledge_retry_after = 0.0

technical_fallback_agent = Agent(
    name="通用技术回退专家",
    instructions="""
你是一名资深中文技术支持工程师。

你的职责：
1. 当知识库未命中，且联网/外部工具不可用时，直接基于通用技术常识回答常见电脑、系统、软件、硬件、安装、排障、操作类问题。
2. 优先给出清晰、可执行、分步骤的中文说明。
3. 不要说“当前服务不可用”“请稍后再试”“无法提供帮助”这类保守话术，除非问题本身确实缺少关键条件无法继续。
4. 如果问题属于通用技术操作，直接给出步骤；如果存在风险点，要简短提醒。
5. 如果你不确定某个强时效事实，就明确说“以下为通用做法”，不要伪造最新数据。

回答要求：
- 使用简洁、专业、面向中文用户的表述
- 操作步骤用有序列表
- 不要提及知识库、工具调用、MCP、模型或系统内部实现
""".strip(),
    model=sub_model,
    model_settings=ModelSettings(temperature=0),
)


def _looks_like_realtime_query(query: str) -> bool:
    normalized_query = (query or "").lower()
    return any(keyword.lower() in normalized_query for keyword in REALTIME_QUERY_KEYWORDS)


async def _query_knowledge_base(query: str) -> dict:
    started_at = time.perf_counter()
    async with httpx.AsyncClient(trust_env=False) as client:
        response = await client.post(
            url=f"{settings.KNOWLEDGE_BASE_URL}/query",
            json={"question": query},
            timeout=httpx.Timeout(
                KNOWLEDGE_PREQUERY_TIMEOUT_SECONDS,
                connect=2.0,
                read=KNOWLEDGE_PREQUERY_TIMEOUT_SECONDS,
                write=2.0,
                pool=2.0,
            ),
        )
        response.raise_for_status()
        logger.info(
            "[Route] Knowledge prequery completed in %.2fs",
            time.perf_counter() - started_at,
        )
        return response.json()


def _knowledge_prequery_available() -> bool:
    return time.monotonic() >= _knowledge_retry_after


def _mark_knowledge_prequery_failed() -> None:
    global _knowledge_retry_after
    _knowledge_retry_after = time.monotonic() + KNOWLEDGE_PREQUERY_COOLDOWN_SECONDS


def _mark_knowledge_prequery_healthy() -> None:
    global _knowledge_retry_after
    _knowledge_retry_after = 0.0



def _extract_knowledge_answer(payload: dict) -> str | None:
    if not isinstance(payload, dict):
        return None

    answer = (payload.get("answer") or "").strip()
    if not answer:
        return None

    if any(marker in answer for marker in KNOWLEDGE_MISS_MARKERS):
        return None

    return answer


def _looks_like_unavailable_answer(answer: str) -> bool:
    normalized_answer = (answer or "").strip()
    if not normalized_answer:
        return True
    return any(marker in normalized_answer for marker in TECHNICAL_UNAVAILABLE_MARKERS)


async def _run_general_technical_fallback(query: str) -> str:
    logger.info("[Route] 启用通用技术回退专家")
    result = await Runner.run(
        technical_fallback_agent,
        input=query,
        run_config=RunConfig(tracing_disabled=True),
    )
    return result.final_output


# ==============================================================================
# 1. 定义技术专家智能体工具
# ==============================================================================
@function_tool
async def consult_technical_expert(
    query: str,
) -> str:
    """Route technical questions through knowledge-first fallback logic."""

    try:
        logger.info(f"[Route] 转交技术专家: {query[:30]}...")

        if not _looks_like_realtime_query(query):
            try:
                if _knowledge_prequery_available():
                    logger.info("[Route] 技术问题先查询知识库")
                    knowledge_payload = await _query_knowledge_base(query)
                    _mark_knowledge_prequery_healthy()
                    knowledge_answer = _extract_knowledge_answer(knowledge_payload)
                    if knowledge_answer:
                        logger.info("[Route] 知识库命中，直接返回知识库结果")
                        return knowledge_answer
                    logger.info("[Route] 知识库未命中，回退技术专家智能体")
                else:
                    logger.info("[Route] 知识库预查询处于冷却期，直接回退技术专家智能体")
            except Exception as knowledge_error:
                _mark_knowledge_prequery_failed()
                logger.warning(
                    f"[Route] 知识库预查询失败，继续回退技术专家智能体: {knowledge_error}"
                )
        else:
            logger.info("[Route] 识别为实时资讯问题，跳过知识库预查询")

        result = await Runner.run(
            technical_agent,
            input=query,
            run_config=RunConfig(tracing_disabled=True),
        )

        final_output = result.final_output
        if not _looks_like_realtime_query(query) and _looks_like_unavailable_answer(
            final_output
        ):
            logger.warning("[Route] 技术专家返回保守兜底话术，改走通用技术回退专家")
            return await _run_general_technical_fallback(query)

        return final_output

    except Exception as e:
        logger.error(f"[Route] 技术专家执行异常: {e}")
        if not _looks_like_realtime_query(query):
            try:
                return await _run_general_technical_fallback(query)
            except Exception as fallback_error:
                logger.error(f"[Route] 通用技术回退专家执行失败: {fallback_error}")
        return f"技术专家服务异常: {str(e)}"

@function_tool
async def query_service_station_and_navigate(
    query: str,
) -> str:
    """
    【服务站专家】处理线下服务站查询、位置查找和地图导航需求。
    当用户询问：
    1. "附近的维修点"、"找小米之家"（服务站查询）。
    2. "怎么去XX"、"导航到XX"（路径规划）。
    3. 任何涉及地理位置和线下门店的请求。
    请调用此工具。

    Args:
        query: 用户的原始问题（包含隐含的位置信息）。
    """
    # 这个工具与 consult_technical_expert 的结构几乎一致，
    # 区别只是：
    # - 它转交的对象不是技术专家
    # - 而是业务/服务站/地图方向的专家 Agent
    #
    # 所以这里也是一个“代理型工具”：
    # 不自己完成业务，而是委派给 comprehensive_service_agent。

    try:
        logger.info(f"[Route] 转交业务专家: {query[:30]}...")
        # 记录一条“路由到业务专家”的日志。
        #
        # 多 Agent 场景里这类日志特别重要，
        # 因为用户问题是否被正确分派，往往决定最终回答质量。

        result = await Runner.run(
            comprehensive_service_agent,
            input=query,
            run_config=RunConfig(tracing_disabled=True),
        )
        # Runner.run(...):
        # 用 comprehensive_service_agent 去处理这个 query。
        #
        # 也就是说：
        # - 当前函数只是一个上层暴露给总控 Agent 的工具入口
        # - 真正干活的是 comprehensive_service_agent
        #
        # 该 Agent 可能在内部进一步：
        # - 调本地服务站查询工具
        # - 调地图 MCP
        # - 做路线规划
        # - 做 POI 检索
        #
        # 这一层相当于把复杂业务能力封装起来，对外只暴露一个统一入口。

        return result.final_output
        # 返回业务专家智能体最终生成的结果字符串。

    except Exception as e:
        # 业务智能体执行失败时的兜底逻辑。
        return f"业务专家暂时无法回答: {str(e)}"
        # 和技术专家类似，这里把异常包装成自然语言字符串返回。
        #
        # 好处是上层不会直接崩。
        # 风险是异常信息可能过于技术化，不够适合直接暴露给最终用户。


# ==============================================================================
# 3. 将两个工具暴露出去
# ==============================================================================
AGENT_TOOLS = [
    consult_technical_expert,
    query_service_station_and_navigate,
]
# AGENT_TOOLS: 对外暴露的工具列表。
#
# 这个列表的意义通常是：
# 让上层“总控 Agent / 路由 Agent / 协调 Agent”统一拿到这些工具。
#
# 例如某个更高层的总控 Agent 可以这样注册：
# tools=AGENT_TOOLS
#
# 然后总控 Agent 在处理用户请求时，就能根据语义决定：
# - 调 consult_technical_expert
# - 还是调 query_service_station_and_navigate
#
# 所以这份代码的角色，不是具体做业务，而是：
# “把多个专家 Agent 封装成统一可调用的工具集合”。

