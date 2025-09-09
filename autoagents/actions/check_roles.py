#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import List, Tuple
from .action import Action
import re
import json

PROMPT_TEMPLATE = '''
-----
You are an executive observer skilled at identifying issues in role design and collaboration. Check whether the selected and newly created Expert Roles meet the requirements and provide improvement suggestions. Use History for reference but do not repeat suggestions.

# Question or Task
{question}

# Existing Expert Roles
{existing_roles}

# Selected Roles List
{selected_roles}

# Created Roles List
{created_roles}

# History
{history}

# Steps
Review the selected and created roles as follows:
1. Understand and decompose the user's problem/task.
2. Validate selected existing roles against the problem and tools ({tools}).
   - Ensure they collectively solve the task efficiently.
   - Ensure roles cooperate or depend sensibly.
   - Ensure each JSON blob preserves original role info (name, description, requirements).
3. Validate each new role against the problem and tools ({tools}).
   - Do not duplicate existing roles.
   - Each must include: name, expertise description, tools (from {tools} only), suggestions, and a prompt template.
   - Scope must be clear; name meaningful; goal concise; constraints practical.
   - Always include one language expert role (no tools) to summarize results.
   - Each new role must be a single JSON blob with keys: name, description, tools, suggestions, prompt. Do NOT return a list.
{{{{
    "name": "ROLE NAME",
    "description": "ROLE DESCRIPTONS",
    "tools": ["ROLE TOOL"],
    "suggestions": "EXECUTION SUGGESTIONS",
    "prompt": "ROLE PROMPT",
}}}}
4. Ensure no tool outside ({tools}) is referenced; remove any that are.
5. Output a summary of findings. If there are no issues, write 'No Suggestions'.

# Format example
Your final output should ALWAYS in the following format:
{format_example}

# Attention
1. Adhere to existing roles' requirements.
2. Include the language expert role.
3. Use History for reference without repeating suggestions.
4. Only use existing tools ({tools}); do NOT create new tools.
5. Do not ask the user questions. The final step must be the language expert synthesis.
-----
'''

FORMAT_EXAMPLE = '''
---
## Thought
you should always think about if there are any errors or suggestions for selected and created expert roles.

## Suggestions
1. ERROR1/SUGGESTION1
2. ERROR2/SUGGESTION2
2. ERROR3/SUGGESTION3
---
'''

OUTPUT_MAPPING = {
    "Suggestions": (str, ...),
}

# TOOLS = '['
# for item in TOOLS_LIST:
#     TOOLS += '(Tool:' + item['toolname'] + '. Description:' + item['description'] + '),'
# TOOLS += ']'

# TOOLS = 'tool: SearchAndSummarize, description: useful for when you need to answer unknown questions'
TOOLS = 'None'


class CheckRoles(Action):
    def __init__(self, name="Check Roles", context=None, llm=None):
        super().__init__(name, context, llm)

    async def run(self, context, history=''):
        from autoagents.roles import ROLES_LIST
        question = re.findall('## Question or Task:([\s\S]*?)##', str(context))[0]
        created_roles = re.findall('## Created Roles List:([\s\S]*?)##', str(context))[0]
        selected_roles = re.findall('## Selected Roles List:([\s\S]*?)##', str(context))[0]
        
        prompt = PROMPT_TEMPLATE.format(question=question, history=history, existing_roles=ROLES_LIST, created_roles=created_roles, selected_roles=selected_roles, format_example=FORMAT_EXAMPLE, tools=TOOLS)
        rsp = await self._aask_v1(prompt, "task", OUTPUT_MAPPING)

        return rsp
