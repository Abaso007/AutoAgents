#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Description: Implementation of long-term memory
# https://github.com/geekan/MetaGPT/blob/main/metagpt/memory/longterm_memory.py

from typing import Iterable, Type

from autoagents.system.logs import logger
from autoagents.system.schema import Message
from .memory import Memory
from .memory_storage import MemoryStorage


class LongTermMemory(Memory):
    """
    Long-term memory component for a role.
    - Restore historical memory for the role at startup
    - Update storage when memory changes
    """

    def __init__(self):
        self.memory_storage: MemoryStorage = MemoryStorage()
        super(LongTermMemory, self).__init__()
        self.rc = None  # RoleContext
        self.msg_from_recover = False

    def recover_memory(self, role_id: str, rc: "RoleContext"):
        messages = self.memory_storage.recover_memory(role_id)
        self.rc = rc
        if not self.memory_storage.is_initialized:
            logger.warning(f'Likely first run for agent {role_id}; long-term memory is empty')
        else:
            logger.warning(f'Agent {role_id} has an existing memory store with {len(messages)} records; restored')
        self.msg_from_recover = True
        self.add_batch(messages)
        self.msg_from_recover = False

    def add(self, message: Message):
        super(LongTermMemory, self).add(message)
        for action in self.rc.watch:
            if message.cause_by == action and not self.msg_from_recover:
                # Only write messages watched by the role into memory_storage
                # Ignore duplicates from the recovery process
                self.memory_storage.add(message)

    def remember(self, observed: list[Message], k=10) -> list[Message]:
        """
        Retrieve the most similar k memories from observed messages (return all if k=0).
            1. Get candidates from short-term memory (STM)
            2. Integrate STM with long-term memory (LTM)
        """
        stm_news = super(LongTermMemory, self).remember(observed)  # STM candidates
        if not self.memory_storage.is_initialized:
            # memory_storage not initialized; use default `remember` result
            return stm_news

        ltm_news: list[Message] = []
        for mem in stm_news:
            # Integrate STM and LTM
            mem_searched = self.memory_storage.search(mem)
            if len(mem_searched) > 0:
                ltm_news.append(mem)
        return ltm_news[-k:]

    def delete(self, message: Message):
        super(LongTermMemory, self).delete(message)
        # TODO: delete the corresponding message from memory_storage

    def clear(self):
        super(LongTermMemory, self).clear()
        self.memory_storage.clean()
