#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Unified LiteLLM-based provider for chat completions.

Replaces separate OpenAI/Anthropic provider variants and ensures
unsupported parameters are safely dropped for each model.
"""
import asyncio
import time
from functools import wraps
from typing import NamedTuple

import litellm

import cfg
from autoagents.system.logs import logger
from autoagents.system.provider.base_gpt_api import BaseGPTAPI
from autoagents.system.utils.singleton import Singleton
from autoagents.system.utils.token_counter import (
    TOKEN_COSTS,
    count_message_tokens,
    count_string_tokens,
)


def retry(max_retries):
    def decorator(f):
        @wraps(f)
        async def wrapper(*args, **kwargs):
            for i in range(max_retries):
                try:
                    return await f(*args, **kwargs)
                except Exception:
                    if i == max_retries - 1:
                        raise
                    await asyncio.sleep(2 ** i)
        return wrapper
    return decorator


class RateLimiter:
    """Simple RPM-based rate limiter."""

    def __init__(self, rpm):
        self.last_call_time = 0
        self.interval = 1.1 * 60 / rpm
        self.rpm = rpm

    def split_batches(self, batch):
        return [batch[i:i + self.rpm] for i in range(0, len(batch), self.rpm)]

    async def wait_if_needed(self, num_requests):
        current_time = time.time()
        elapsed_time = current_time - self.last_call_time

        if elapsed_time < self.interval * num_requests:
            remaining_time = self.interval * num_requests - elapsed_time
            logger.info(f"sleep {remaining_time}")
            await asyncio.sleep(remaining_time)

        self.last_call_time = time.time()


class Costs(NamedTuple):
    total_prompt_tokens: int
    total_completion_tokens: int
    total_cost: float
    total_budget: float


class CostManager(metaclass=Singleton):
    """Track API usage cost."""

    def __init__(self):
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost = 0
        self.total_budget = float(getattr(cfg, "MAX_BUDGET", 0.0) or 0.0)

    def update_cost(self, prompt_tokens, completion_tokens, model):
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        # Prefer litellm dynamic pricing; fallback to static TOKEN_COSTS
        try:
            prompt_cost, completion_cost = litellm.cost_per_token(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            cost = float(prompt_cost) + float(completion_cost)
        except Exception:
            try:
                cost = (
                    prompt_tokens * TOKEN_COSTS[model]["prompt"]
                    + completion_tokens * TOKEN_COSTS[model]["completion"]
                ) / 1000
            except Exception:
                cost = 0.0
        self.total_cost += cost
        logger.info(
            f"Total running cost: ${self.total_cost:.3f} | Max budget: ${cfg.MAX_BUDGET:.3f} | "
            f"Current cost: ${cost:.3f}, {prompt_tokens=}, {completion_tokens=}"
        )
        cfg.TOTAL_COST = self.total_cost

    def get_costs(self) -> Costs:
        return Costs(self.total_prompt_tokens, self.total_completion_tokens, self.total_cost, self.total_budget)


class LLMAPI(BaseGPTAPI, RateLimiter):
    """Unified LLM provider using LiteLLM for routing."""

    def __init__(self, proxy: str = "", api_key: str = ""):
        self.proxy = proxy
        self.api_key = api_key
        self.stops = cfg.STOP
        self.model = cfg.LLM_MODEL
        # Ensure LiteLLM drops unsupported params automatically
        litellm.drop_params = True
        # Configure bases/types/versions where applicable (e.g., Azure)
        if cfg.OPENAI_API_BASE:
            litellm.api_base = cfg.OPENAI_API_BASE
        if cfg.OPENAI_API_TYPE:
            litellm.api_type = cfg.OPENAI_API_TYPE
        if cfg.OPENAI_API_VERSION:
            litellm.api_version = cfg.OPENAI_API_VERSION

        self._cost_manager = CostManager()
        self.rpm = int(cfg.RPM)
        RateLimiter.__init__(self, rpm=self.rpm)

    def _select_api_key(self) -> str:
        """Pick API key based on model family if possible."""
        if self.api_key:
            return self.api_key
        m = (self.model or "").lower()
        if "anthropic" in m or "claude" in m:
            return cfg.CLAUDE_API_KEY or cfg.LLM_API_KEY
        return cfg.LLM_API_KEY

    def _cons_kwargs(self, messages: list[dict]) -> dict:
        # Base kwargs, include commonly supported params; LiteLLM will drop unsupported
        base = {
            "messages": messages,
            "max_tokens": cfg.MAX_TOKENS,
            "n": cfg.N,
            "stop": self.stops,
            "temperature": cfg.TEMPERATURE,
            "top_p": cfg.TOP_P,
            "presence_penalty": cfg.PRESENCE_PENALTY,
            "frequency_penalty": cfg.FREQUENCY_PENALTY,
            "timeout": cfg.LLM_TIMEOUT,
        }

        if cfg.OPENAI_API_TYPE == "azure":
            base.update({"deployment_id": cfg.DEPLOYMENT_ID})
        else:
            base.update({"model": self.model})
        return base

    async def _achat_completion_stream(self, messages: list[dict]) -> str:
        # Configure key per-call to support multiple providers
        litellm.api_key = self._select_api_key()
        response = await litellm.acompletion(
            **self._cons_kwargs(messages),
            stream=True,
        )

        collected_messages = []
        async for chunk in response:
            chunk_message = chunk["choices"][0]["delta"]
            collected_messages.append(chunk_message)
            content = chunk_message.get("content")
            if isinstance(content, str) and content:
                print(content, end="")

        # Some streaming deltas may include content=None; coerce to empty string
        full_reply_content = "".join([(m.get("content") or "") for m in collected_messages])
        usage = self._calc_usage(messages, full_reply_content)
        self._update_costs(usage)
        return full_reply_content

    async def _achat_completion(self, messages: list[dict]) -> dict:
        litellm.api_key = self._select_api_key()
        rsp = await litellm.acompletion(**self._cons_kwargs(messages))
        usage = rsp.get("usage")
        if usage is None:
            usage = self._calc_usage(messages, rsp.get("choices", [{}])[0].get("message", {}).get("content", ""))
        self._update_costs(usage)
        return rsp

    def _chat_completion(self, messages: list[dict]) -> dict:
        litellm.api_key = self._select_api_key()
        rsp = litellm.completion(**self._cons_kwargs(messages))
        usage = rsp.get("usage")
        if usage is None:
            usage = self._calc_usage(messages, rsp.get("choices", [{}])[0].get("message", {}).get("content", ""))
        self._update_costs(usage)
        return rsp

    def completion(self, messages: list[dict]) -> dict:
        return self._chat_completion(messages)

    async def acompletion(self, messages: list[dict]) -> dict:
        return await self._achat_completion(messages)

    @retry(max_retries=6)
    async def acompletion_text(self, messages: list[dict], stream: bool = False) -> str:
        if stream:
            return await self._achat_completion_stream(messages)
        rsp = await self._achat_completion(messages)
        try:
            return self.get_choice_text(rsp)
        except Exception:
            # Fallback to empty string for rare provider anomalies
            return rsp.get("choices", [{}])[0].get("message", {}).get("content", "") or ""

    def _calc_usage(self, messages: list[dict], rsp: str) -> dict:
        prompt_tokens = count_message_tokens(messages, self.model)
        completion_tokens = count_string_tokens(rsp, self.model)
        return {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}

    async def acompletion_batch(self, batch: list[list[dict]]) -> list[dict]:
        split_batches = self.split_batches(batch)
        all_results = []
        for small_batch in split_batches:
            logger.info(small_batch)
            await self.wait_if_needed(len(small_batch))
            future = [self.acompletion(prompt) for prompt in small_batch]
            results = await asyncio.gather(*future)
            logger.info(results)
            all_results.extend(results)
        return all_results

    async def acompletion_batch_text(self, batch: list[list[dict]]) -> list[str]:
        raw_results = await self.acompletion_batch(batch)
        results = []
        for idx, raw_result in enumerate(raw_results, start=1):
            result = self.get_choice_text(raw_result)
            results.append(result)
            logger.info(f"Result of task {idx}: {result}")
        return results

    def _update_costs(self, usage: dict):
        prompt_tokens = int(usage["prompt_tokens"])
        completion_tokens = int(usage["completion_tokens"])
        self._cost_manager.update_cost(prompt_tokens, completion_tokens, self.model)

    def get_costs(self) -> Costs:
        return self._cost_manager.get_costs()
