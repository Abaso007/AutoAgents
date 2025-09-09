#!/usr/bin/env python
# coding: utf-8
"""
@Time    : 2023/5/11 14:43
@Author  : alexanderwu
@From    : https://github.com/geekan/MetaGPT/blob/main/metagpt/actions/action.py
"""
from abc import ABC
from typing import Optional, Any, Dict
import json

from tenacity import retry, stop_after_attempt, wait_fixed

from .action_output import ActionOutput
from autoagents.system.llm import LLM
from autoagents.system.utils.common import OutputParser
from autoagents.system.logs import logger

class Action(ABC):
    def __init__(self, name: str = '', context=None, llm: LLM = None, serpapi_api_key=None):
        self.name: str = name
        # if llm is None:
        #     llm = LLM(proxy, api_key)
        self.llm = llm
        self.context = context
        self.prefix = ""
        self.profile = ""
        self.desc = ""
        self.content = ""
        self.serpapi_api_key = serpapi_api_key
        self.instruct_content = None

    def set_prefix(self, prefix, profile, proxy, api_key, serpapi_api_key):
        """Set prefix for later usage"""
        self.prefix = prefix
        self.profile = profile
        self.llm = LLM(proxy, api_key)
        self.serpapi_api_key = serpapi_api_key

    def __str__(self):
        return self.__class__.__name__

    def __repr__(self):
        return self.__str__()

    async def _aask(self, prompt: str, system_msgs: Optional[list[str]] = None) -> str:
        """Append default prefix"""
        if not system_msgs:
            system_msgs = []
        system_msgs.append(self.prefix)
        return await self.llm.aask(prompt, system_msgs)

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(1))
    async def _aask_v1(self, prompt: str, output_class_name: str,
                       output_data_mapping: dict,
                       system_msgs: Optional[list[str]] = None) -> ActionOutput:
        """Append default prefix"""
        if not system_msgs:
            system_msgs = []
        system_msgs.append(self.prefix)
        content = await self.llm.aask(prompt, system_msgs)
        logger.debug(content)
        output_class = ActionOutput.create_model_class(output_class_name, output_data_mapping)
        try:
            parsed_data = OutputParser.parse_data_with_mapping(content, output_data_mapping)
            logger.debug(parsed_data)
            instruct_content = output_class(**parsed_data)
            return ActionOutput(content, instruct_content)
        except Exception as e:
            logger.warning(f"Primary parsing/validation failed: {e}. Attempting LLM repair...")
            repaired = await self._repair_with_llm(content, output_data_mapping, system_msgs)
            logger.debug(repaired)
            instruct_content = output_class(**repaired)
            # Return original content for transparency, with repaired instruct_content
            return ActionOutput(content, instruct_content)

    async def _repair_with_llm(self, raw_text: str, mapping: dict, system_msgs: list[str]) -> Dict[str, Any]:
        """Use LLM to coerce output into the exact schema defined by mapping.

        Strategy: ask the model to output ONLY a strict JSON object whose keys match mapping.
        Missing values become empty string/list. Extraneous content is dropped.
        """
        # Build a simple schema hint text
        def _type_name(t: Any) -> str:
            try:
                name = str(t)
            except Exception:
                name = repr(t)
            return name

        fields = []
        for k, v in mapping.items():
            if isinstance(v, tuple):
                v = v[0]
            fields.append(f"- {k}: {_type_name(v)}")
        schema_hint = "\n".join(fields)

        # Compose the repair prompt
        repair_instructions = (
            "You are a strict output normalizer.\n"
            "Given an assistant response and a target schema, produce ONLY a valid JSON object\n"
            "that strictly uses the required keys and types.\n"
            "Rules:\n"
            "- Output JSON ONLY (no code fences, no comments, no extra text).\n"
            "- Include ALL required keys; if a value is missing, use an empty string '' or an empty list [].\n"
            "- Do not invent content; derive values from the response as-is.\n"
            "- Keep keys exactly as provided.\n"
        )

        user_msg = (
            f"Schema fields and types:\n{schema_hint}\n\n"
            f"Assistant response to normalize:\n"  # not fenced to reduce fence echo
            f"{raw_text}\n\n"
            f"Now return ONLY the JSON object."
        )

        # Reuse existing system messages context + the strict formatter role
        strict_system_msgs = list(system_msgs) + [repair_instructions]

        import cfg  # local import to avoid cycles at module load
        attempts = int(getattr(cfg, "LLM_PARSER_REPAIR_ATTEMPTS", 1) or 1)
        last_err = None
        for _ in range(max(1, attempts)):
            repaired_text = await self.llm.aask(user_msg, strict_system_msgs)
            cleaned = self._extract_json(repaired_text)
            try:
                data = json.loads(cleaned)
                # Ensure all required keys exist
                for k in mapping.keys():
                    if k not in data:
                        data[k] = [] if "List" in str(mapping[k]) else ""
                return data
            except Exception as err:
                last_err = err
                logger.warning(f"LLM repair produced invalid JSON, retrying: {err}")
                continue
        # If all attempts failed, surface error for outer retry policy
        raise ValueError(f"LLM repair failed: {last_err}")

    @staticmethod
    def _extract_json(text: str) -> str:
        """Strip common code fences or leading/trailing noise around JSON."""
        t = text.strip()
        # remove triple backticks if present
        if t.startswith("```") and t.endswith("```"):
            t = t.strip("`")
            # Remove possible language tag e.g., json\n
            first_nl = t.find("\n")
            if first_nl != -1:
                t = t[first_nl + 1 :]
        # Trim accidental leading characters before '{'
        start = t.find("{")
        end = t.rfind("}")
        if start != -1 and end != -1 and end >= start:
            return t[start : end + 1]
        return t

    async def run(self, *args, **kwargs):
        """Run action"""
        raise NotImplementedError("The run method should be implemented in a subclass.")
