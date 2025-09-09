#!/usr/bin/env python
# -*- coding: utf-8 -*-
from typing import List, Tuple

from autoagents.system.logs import logger
from .action import Action
from .action_bank.search_and_summarize import SearchAndSummarize, SEARCH_AND_SUMMARIZE_SYSTEM_EN_US

PROMPT_TEMPLATE = '''
-----
You are a manager and expert prompt engineer. Break down the task by selecting and, only if necessary, creating LLM expert roles. Analyze dependencies and produce a clear execution plan. Improve iteratively using History suggestions without repeating them.

# Question or Task
{context}

# Existing Expert Roles
{existing_roles}

# History
{history}

# Steps
Produce roles and a plan via:
1. Understand and decompose the user's task.
2. Select existing expert roles (from {tools}) that together can solve the task.
   - Respect each role's requirements and ensure collaboration/dependencies are coherent.
   - Output each selected existing role as a JSON blob with its original information.
3. Create new expert roles only if required.
   - Do not duplicate existing roles' functions.
   - For each new role, provide: name, detailed expertise description, tools (from {tools} only), suggestions, and a prompt template.
   - Ensure clear scope, meaningful name, precise goal, and practical constraints.
   - Always add one language expert role (no tools) to summarize final results.
   - Output each new role as a single JSON blob with keys: name, description, tools, suggestions, prompt.
4. Provide a concise execution plan: a numbered sequence of steps that logically reaches the goal, listing the involved roles, expected output per step, and required input for the next step. End with the language expert synthesis step.

Here is an example JSON blob for a role:
{{{{
    "name": "ROLE NAME",
    "description": "ROLE DESCRIPTONS",
    "tools": ["ROLE TOOL"],
    "suggestions": "EXECUTION SUGGESTIONS",
    "prompt": "ROLE PROMPT",
}}}}

# Format example
Your final output should ALWAYS in the following format:
{format_example}

# Suggestions
{suggestions}

# Attention
1. Adhere to existing roles' requirements.
2. Use only existing tools {tools}; do NOT invent new tools.
3. Split sections with '##' and write '## <SECTION_NAME>' before content and triple quotes.
4. Include the language expert role.
5. Do not ask the user questions. Ensure the final step is the language expert synthesis as specified.
-----
'''

FORMAT_EXAMPLE = '''
---
## Thought 
If you do not receive any suggestions, you should always consider what kinds of expert roles are required and what are the essential steps to complete the tasks. 
If you do receive some suggestions, you should always evaluate how to enhance the previous role list and the execution plan according to these suggestions and what feedback you can give to the suggesters.

## Question or Task:
the input question you must answer / the input task you must finish

## Selected Roles List:
```
JSON BLOB 1,
JSON BLOB 2,
JSON BLOB 3
```

## Created Roles List:
```
JSON BLOB 1,
JSON BLOB 2,
JSON BLOB 3
```

## Execution Plan:
1. [ROLE 1, ROLE2, ...]: STEP 1
2. [ROLE 1, ROLE2, ...]: STEP 2
2. [ROLE 1, ROLE2, ...]: STEP 3

## RoleFeedback
feedback on the historical Role suggestions

## PlanFeedback
feedback on the historical Plan suggestions
---
'''

OUTPUT_MAPPING = {
    "Selected Roles List": (str, ...),
    "Created Roles List": (str, ...),
    "Execution Plan": (str, ...),
    "RoleFeedback": (str, ...),
    "PlanFeedback": (str, ...),
}

# TOOLS = '['
# for item in TOOLS_LIST:
#     TOOLS += '(Tool:' + item['toolname'] + '. Description:' + item['description'] + '),'
# TOOLS += ']'
TOOLS = 'tool: SearchAndSummarize, description: useful for when you need to answer unknown questions'


class CreateRoles(Action):

    def __init__(self, name="CreateRolesTasks", context=None, llm=None):
        super().__init__(name, context, llm)

    async def run(self, context, history='', suggestions=''):
        # sas = SearchAndSummarize()

        # sas = SearchAndSummarize(serpapi_api_key=self.serpapi_api_key, llm=self.llm)
        # context[-1].content = 'How to solve/complete ' + context[-1].content.replace('Question/Task', '')
        # question = 'How to solve/complete' + str(context[-1]).replace('Question/Task:', '')
        # rsp = await sas.run(context=context, system_text=SEARCH_AND_SUMMARIZE_SYSTEM_EN_US)
        # context[-1].content = context[-1].content.replace('How to solve/complete ', '')
        # info = f"## Search Results\n{sas.result}\n\n## Search Summary\n{rsp}"

        from autoagents.roles import ROLES_LIST
        prompt = PROMPT_TEMPLATE.format(context=context, format_example=FORMAT_EXAMPLE, existing_roles=ROLES_LIST, tools=TOOLS, history=history, suggestions=suggestions)
        
        rsp = await self._aask_v1(prompt, "task", OUTPUT_MAPPING)
        return rsp


class AssignTasks(Action):
    async def run(self, *args, **kwargs):
        # Here you should implement the actual action
        pass
