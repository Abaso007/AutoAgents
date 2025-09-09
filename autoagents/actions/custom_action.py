#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import os
import json
from typing import List, Tuple

from autoagents.actions.action import Action
from .action.action_output import ActionOutput
from .action_bank.search_and_summarize import SearchAndSummarize, SEARCH_AND_SUMMARIZE_SYSTEM_EN_US

from autoagents.system.logs import logger
from autoagents.system.utils.common import OutputParser
from autoagents.system.schema import Message
from autoagents.system.const import WORKSPACE_ROOT
from autoagents.system.utils.common import CodeParser

PROMPT_TEMPLATE = '''
-----
{role} Based on prior agents' results and completed steps, complete the task as best you can.

# Task {context}

# Suggestions
{suggestions}

# Execution Result of Previous Agents {previous}

# Completed Steps and Responses {completed_steps}

You have access to the following tools:
# Tools {tool}

# Steps
1. Review and understand previous agents' outputs.
2. Analyze and decompose the task; use tools where appropriate.
3. Decide the single current step to complete and output it in 'CurrentStep'.
   - If no steps are completed yet, design a minimal step-by-step plan and accomplish the first step.
   - If some steps are completed, pick the next logical step.
4. Choose one Action from [{tool}] to execute the current step.
   - If using 'Write File', 'ActionInput' MUST be:
```
>>>file name
file content
>>>END
```
   - If all steps are complete, choose 'Final Output' and summarize all step outputs in 'ActionInput'. The final output must be helpful, relevant, accurate, and detailed.

# Format example
Your final output MUST follow this format:
{format_example}

# Attention
1. The task you must finish is: {context}
2. Do not ask the user questions.
3. The final output MUST be helpful, relevant, accurate, and detailed.
-----
'''

FORMAT_EXAMPLE = '''
---
## Thought 
you should always think about what step you need to complete now and how to complet this step.

## Task
the input task you must finish

## CurrentStep
the current step to be completed

## Action
the action to take, must be one of [{tool}]

## ActionInput
the input to the action
---
'''

OUTPUT_MAPPING = {
    "CurrentStep": (str, ...),
    "Action": (str, ...),
    "ActionInput": (str, ...),
}

INTERMEDIATE_OUTPUT_MAPPING = {
    "Step": (str, ...),
    "Response": (str, ...),
    "Action": (str, ...),
}

FINAL_OUTPUT_MAPPING = {
    "Step": (str, ...),
    "Response": (str, ...),
}

class CustomAction(Action):

    def __init__(self, name="CustomAction", context=None, llm=None, **kwargs):
        super().__init__(name, context, llm, **kwargs)

    def _save(self, filename, content):        
        file_path = os.path.join(WORKSPACE_ROOT, filename)

        # Ensure workspace exists and any subdirectories for the file are created
        if not os.path.exists(WORKSPACE_ROOT):
            os.mkdir(WORKSPACE_ROOT)
        dir_name = os.path.dirname(file_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)

        with open(file_path, mode='w+', encoding='utf-8') as f:
            f.write(content)
        
    async def run(self, context):
        # steps = ''
        # for i, step in enumerate(list(self.steps)):
        #     steps += str(i+1) + '. ' + step + '\n'

        # Robustly extract sections; fall back to empty string if anchors are missing
        ctx_str = str(context)
        m_prev = re.search(r'## Previous Steps and Responses([\s\S]*?)## Current Step', ctx_str)
        previous_context = m_prev.group(1).strip() if m_prev else ""

        m_task = re.search(r'## Current Step([\s\S]*?)### Completed Steps and Responses', ctx_str)
        if not m_task:
            # Fallback: until end of string
            m_task = re.search(r'## Current Step([\s\S]*)', ctx_str)
        task_context = m_task.group(1).strip() if m_task else ""

        m_done = re.search(r'### Completed Steps and Responses([\s\S]*?)###', ctx_str)
        if not m_done:
            # Fallback: until end of string
            m_done = re.search(r'### Completed Steps and Responses([\s\S]*)', ctx_str)
        completed_steps = m_done.group(1).strip() if m_done else ""
        # print('-------------Previous--------------')
        # print(previous_context)
        # print('--------------Task-----------------')
        # print(task_context)
        # print('--------------completed_steps-----------------')
        # print(completed_steps)
        # print('-----------------------------------')
        # exit()
        
        tools = list(self.tool) + ['Print', 'Write File', 'Final Output']
        prompt = PROMPT_TEMPLATE.format(
            context=task_context,
            previous=previous_context,
            role=self.role_prompt,
            tool=str(tools),
            suggestions=self.suggestions,
            completed_steps=completed_steps,
            format_example=FORMAT_EXAMPLE
        )

        rsp = await self._aask_v1(prompt, "task", OUTPUT_MAPPING)

        if 'Write File' in rsp.instruct_content.Action:
            ai_text = str(rsp.instruct_content.ActionInput)

            def _parse_write_file_block(text: str):
                # Try several tolerant patterns
                patterns = [
                    r">>>\s*([^\n]+)\n([\s\S]*?)>>>END",  # canonical
                    r">>>\s*([^\n]+)\r?\n([\s\S]*?)>>>END\s*$",  # allow trailing spaces
                ]
                for pat in patterns:
                    m = re.search(pat, text)
                    if m:
                        fname = m.group(1).strip()
                        content = m.group(2)
                        return fname, content
                # Last resort: take first line as filename and rest as content
                lines = text.splitlines()
                if lines:
                    fname = lines[0].strip().lstrip('>')  # in case the model omitted markers
                    body = "\n".join(lines[1:])
                    if fname:
                        return fname, body
                return None

            parsed = _parse_write_file_block(ai_text)
            if not parsed:
                # Attempt an LLM-based repair to enforce the exact block format
                try:
                    repair_prompt = (
                        "Normalize the following Write File action input into EXACTLY this format:\n"
                        "```\n>>>file name\nfile content\n>>>END\n```\n"
                        "Rules:\n- Keep only one block.\n- Do not add commentary.\n- Ensure the filename is on the first line after >>>.\n- Preserve the intended file content.\n- Return ONLY the block above (no backticks).\n\n"
                        f"Input:\n{ai_text}"
                    )
                    repaired = await self._aask(repair_prompt)
                    parsed = _parse_write_file_block(repaired)
                except Exception as e:
                    logger.warning(f"LLM repair for Write File failed: {e}")

            if parsed:
                filename, content = parsed
                try:
                    self._save(filename, content)
                    response = f"\n{ai_text}\n"
                except Exception as e:
                    logger.warning(f"Saving file failed: {e}")
                    response = f"\n{ai_text}\n"
            else:
                logger.warning("Could not parse Write File ActionInput; echoing content without saving.")
                response = f"\n{ai_text}\n"
        elif rsp.instruct_content.Action in self.tool:
            sas = SearchAndSummarize(serpapi_api_key=self.serpapi_api_key, llm=self.llm)
            sas_rsp = await sas.run(context=[Message(rsp.instruct_content.ActionInput)], system_text=SEARCH_AND_SUMMARIZE_SYSTEM_EN_US)
            # response = f"\n{sas_rsp}\n"
            response = f">>> Search Results\n{sas.result}\n\n>>> Search Summary\n{sas_rsp}"
        else:
            response = f"\n{rsp.instruct_content.ActionInput}\n"

        if 'Final Output' in rsp.instruct_content.Action:
            info = f"\n## Step\n{task_context}\n## Response\n{completed_steps}>>>> Final Output\n{response}\n>>>>"
            output_class = ActionOutput.create_model_class("task", FINAL_OUTPUT_MAPPING)
            parsed_data = OutputParser.parse_data_with_mapping(info, FINAL_OUTPUT_MAPPING)
        else:
            info = f"\n## Step\n{task_context}\n## Response\n{response}\n## Action\n{rsp.instruct_content.CurrentStep}\n"
            output_class = ActionOutput.create_model_class("task", INTERMEDIATE_OUTPUT_MAPPING)
            parsed_data = OutputParser.parse_data_with_mapping(info, INTERMEDIATE_OUTPUT_MAPPING)
        
        instruct_content = output_class(**parsed_data)

        return ActionOutput(info, instruct_content)
