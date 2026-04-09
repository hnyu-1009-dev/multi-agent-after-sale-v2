from typing import List

from langchain_core.documents import Document
from langchain_openai import ChatOpenAI

from knowledge.config.settings import settings


class QueryService:
    """知识库问答生成器。"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model_name=settings.MODEL,
            openai_api_key=settings.API_KEY,
            openai_api_base=settings.BASE_URL,
            temperature=0.7,
            timeout=40,
            max_retries=1,
        )

    def generate_answer(
        self, user_question: str, retrival_context: List[Document]
    ) -> str:
        if not retrival_context:
            return "知识库里没有检索到足够相关的内容。"

        retrival_context = "\n\n".join(
            [
                f"片段{index + 1}:{document}"
                for index, document in enumerate(retrival_context)
            ]
        )

        prompt = f"""
 你是一位经验丰富的高级技术支持专家。请基于下方的【参考资料】回答【用户问题】。

         【参考资料】：
         ```
         {retrival_context}
         ```

         【用户问题】：
         ```
         {user_question}
         ```

         【回答要求】：
         1.  **基于事实**：如果查询到具体内容就：严格基于【参考资料】的内容回答，严禁编造资料中未提及的信息。如果资料无法回答问题，请回答按照你的理解进行回答，不用告诉用户这是你通过网络检索到的，不要出现没有查询到的字眼,如果查到了就说是通过知识库检索得到
         2.  **去特定化处理**：(重要)
             - 除非用户问题中明确指明了特定型号/品牌，否则在回答中请**移除**具体的设备型号、品牌名称（如“联想”、“K900”等）。
             - 例如：将“联想手机设置”泛化为“手机设置”；将“打开联想电脑管家”泛化为“打开系统管理软件”或“相关设置工具”。
         3.  **结构清晰**：
             - 如果是操作步骤，请使用有序列表（1. 2. 3.）。
             - 语言风格应简洁、专业、直接，避免寒暄和废话。
         4. 引用来源：以参考知识库中的知识
         
         5.如果再知识库中没检索到相关信息，一定不要说没有查询到直接回答就行。

        """

        llm_response = self.llm.invoke(prompt)
        return llm_response.content
