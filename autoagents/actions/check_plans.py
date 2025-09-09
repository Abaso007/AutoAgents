#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import List, Tuple
from .action import Action
import re

PROMPT_TEMPLATE = '''
-----
You are an executive observer. Review the Execution Plan for clarity, completeness, and correctness, and provide concrete improvement suggestions. Use History for reference but avoid repeating suggestions.

# Question or Task
{context}

# Role List
{roles}

# Execution Plan
{plan}

# History
{history}

# Steps
Check the Execution Plan as follows:
1. Understand and decompose the user's problem.
2. Validate the plan against these requirements:
   - Multi-step progression that cumulatively solves the problem.
   - Each step assigns at least one expert role; if multiple, clarify contributions and integration.
   - Step descriptions are sufficiently detailed and show how steps connect.
   - Each step defines expected output and the input required for the next step; ensure consistency.
   - The final step is the language expert producing the synthesized answer.
3. Provide a concise summary of issues and improvements. If none, write 'No Suggestions'.

# Format example
Your final output should ALWAYS in the following format:
{format_example}

# Attention
1. Only use existing tools {tools}; do NOT create new tools.
2. Use History for reference; avoid repeating suggestions.
3. Do not ask the user questions. Ensure the language expert final step.
-----
'''

FORMAT_EXAMPLE = '''
---
## Thought
you should always think about if there are any errors or suggestions for the Execution Plan.

## Suggestions
1. ERROR1/SUGGESTION1
2. ERROR2/SUGGESTION2
2. ERROR3/SUGGESTION3
---
'''

OUTPUT_MAPPING = {
    "Suggestions": (str, ...),
}

# TOOLS = 'tool: SearchAndSummarize, description: useful for when you need to answer unknown questions'
TOOLS = 'None'


class CheckPlans(Action):
    def __init__(self, name="Check Plan", context=None, llm=None):
        super().__init__(name, context, llm)

    async def run(self, context, history=''):

        roles = re.findall('## Selected Roles List:([\s\S]*?)##', str(context))[-1]
        agents = re.findall('{[\s\S]*?}', roles)
        if len(agents) <= 0: roles = ''
        roles += re.findall('## Created Roles List:([\s\S]*?)##', str(context))[-1]
        plan = re.findall('## Execution Plan:([\s\S]*?)##', str(context))[-1]
        context = re.findall('## Question or Task:([\s\S]*?)##', str(context))[-1]
        prompt = PROMPT_TEMPLATE.format(context=context, plan=plan, roles=roles, format_example=FORMAT_EXAMPLE, history=history, tools=TOOLS)
        rsp = await self._aask_v1(prompt, "task", OUTPUT_MAPPING)
        return rsp
