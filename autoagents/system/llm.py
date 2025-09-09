"""
@Time    : 2023/5/11 14:45
@Author  : alexanderwu
@File    : llm.py
@From    : https://github.com/geekan/MetaGPT/blob/main/metagpt/llm.py
"""
from .provider.llm_api import LLMAPI as LLM

DEFAULT_LLM = LLM()


async def ai_func(prompt):
    return await DEFAULT_LLM.aask(prompt)
