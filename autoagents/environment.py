#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2023/5/11 22:12
@Author  : alexanderwu
@File    : environment.py
@Modified From: https://github.com/geekan/MetaGPT/blob/main/metagpt/environment.py
"""
import asyncio
import re
import json
import datetime
import websockets
from common import MessageType, format_message, timestamp
from typing import Iterable

from pydantic import BaseModel, Field

from .roles import Role
from .actions import Requirement
from .roles import CustomRole, ActionObserver, Group, ROLES_LIST, ROLES_MAPPING

from .system.memory import Memory
from .system.const import WORKSPACE_ROOT
from pathlib import Path
from .system.schema import Message

class Environment(BaseModel):
    """Environment hosting multiple roles; roles publish messages here, observable by others."""

    roles: dict[str, Role] = Field(default_factory=dict)
    memory: Memory = Field(default_factory=Memory)
    history: str = Field(default='')
    new_roles_args: dict = Field(default_factory=dict)
    new_roles: dict[str, Role] = Field(default_factory=dict)
    steps: list = Field(default_factory=list)
    msg_json: list = Field(default_factory=list)
    json_log: str = Field(default='./logs/json_log.json')
    task_id: str = Field(default='')
    proxy: str = Field(default='')
    llm_api_key: str = Field(default='')
    serpapi_key: str = Field(default='')
    alg_msg_queue: object = Field(default=None)
    log_dir: Path | None = Field(default=None)

    class Config:
        arbitrary_types_allowed = True


    def add_role(self, role: Role):
        """Add a Role to the current environment."""
        role.set_env(self)
        self.roles[role.profile] = role

    def add_roles(self, roles: Iterable[Role]):
        """Add multiple Roles to the current environment."""
        for role in roles:
            self.add_role(role)

    def _parser_roles(self, text):
        """Parse role definitions to be added from text."""
        agents = re.findall('{[\s\S]*?}', text) # re.findall('{{.*}}', agents)
        agents_args = []
        for agent in agents:
            agent = json.loads(agent.strip())
            if len(agent.keys()) > 0:
                agents_args.append(agent)

        print('---------------Agents---------------')
        for i, agent in enumerate(agents_args):
            print('Role', i, agent)

        return agents_args
    
    def _parser_plan(self, context):
        """Parse the generated execution plan from context."""
        plan_context = re.findall('## Execution Plan([\s\S]*?)##', str(context))[0]
        steps = [v.split("\n")[0] for v in re.split("\n\d+\. ", plan_context)[1:]]
        print('---------------Steps---------------')
        for i, step in enumerate(steps):
            print('Step', i, step)
        
        steps.insert(0, '')
        return steps
    
    def create_roles(self, plan: list, args: dict):
        """Create role(s) based on the plan and args.""" 

        requirement_type = type('Requirement_Group', (Requirement,), {})
        self.add_role(Group(roles=args, steps=plan, watch_actions=[Requirement,requirement_type],  proxy=self.proxy, serpapi_api_key=self.serpapi_key, llm_api_key=self.llm_api_key))

        # existing_roles = dict()
        # for item in ROLES_LIST:
        #     existing_roles[item['name']] = item
                
        # init_actions, watch_actions = [], []
        # for role in args:
        #     class_name = role['name'].replace(' ', '_') + '_Requirement'
        #     requirement_type = type(class_name, (Requirement,), {})
        #     if role['name'] in existing_roles.keys():
        #         print('Add a predefiend role:', role['name'])
        #         role_object = ROLES_MAPPING[role['name']]
        #         if 'Engineer' in role['name']:
        #             _role = role_object(n_borg=2, use_code_review=True, proxy=self.proxy, llm_api_key=self.llm_api_key, serpapi_api_key=self.serpapi_key)
        #         else:
        #             _role = role_object(watch_actions=[requirement_type], proxy=self.proxy, llm_api_key=self.llm_api_key, serpapi_api_key=self.serpapi_key)
        #     else:
        #         print('Add a new role:', role['name'])
        #         _role = CustomRole(
        #             name=role['name'],
        #             profile=role['name'],
        #             goal=role['description'],
        #             role_prompt=role['prompt'],
        #             steps=role['steps'],
        #             tool=role['tools'],
        #             watch_actions=[requirement_type],
        #             proxy=self.proxy,
        #             llm_api_key=self.llm_api_key,
        #             serpapi_api_key=self.serpapi_key,
        #         )
                
        #     self.add_role(_role)
        #     watch_actions.append(requirement_type)
        #     init_actions.append(_role.init_actions)
            
        
        # init_actions.append(Requirement)
        # self.add_role(ActionObserver(steps=plan, watch_actions=init_actions, init_actions=watch_actions, proxy=self.proxy, llm_api_key=self.llm_api_key))

    async def publish_message(self, message: Message):
        """Publish a message to the current environment."""
        # self.message_queue.put(message)
        self.memory.add(message)
        self.history += f"\n{message}"

        # Initialize per-task log directory on first message
        if self.log_dir is None:
            try:
                safe_task = (self.task_id or timestamp()).replace('/', '-').replace(' ', '_')
                base = WORKSPACE_ROOT / 'agents_logs' / safe_task
                base.mkdir(parents=True, exist_ok=True)
                self.log_dir = base
            except Exception:
                # Fallback: ensure workspace exists and continue without raising
                (WORKSPACE_ROOT / 'agents_logs').mkdir(parents=True, exist_ok=True)

        # Persist environment history and per-agent process/result
        try:
            # Save full environment history
            if self.log_dir:
                history_path = self.log_dir / 'history.md'
                history_path.write_text(self.history)

                # Per-agent logs
                role_name = (message.role or 'Unknown').strip()
                # Skip empty/observer-only roles in dedicated dirs if needed
                safe_role = role_name.replace('/', '-').replace(' ', '_')
                role_dir = self.log_dir / safe_role
                role_dir.mkdir(parents=True, exist_ok=True)

                # Append to process log
                process_path = role_dir / 'process.md'
                with process_path.open('a', encoding='utf-8') as f:
                    f.write(f"\n## [{timestamp()}] {role_name}\n")
                    if message.cause_by:
                        f.write(f"Action: {getattr(message.cause_by, '__name__', str(message.cause_by))}\n\n")
                    content = message.instruct_content.dict() if getattr(message, 'instruct_content', None) else None
                    if content:
                        f.write("Content (instruct):\n")
                        for k, v in content.items():
                            f.write(f"- {k}: {v}\n")
                        f.write("\n")
                    f.write("Message:\n")
                    f.write(str(message.content).rstrip() + "\n")

                # Update latest result for this agent
                result_path = role_dir / 'result.md'
                # Prefer a clean result: instruct Response if present, else content
                result_text = None
                if getattr(message, 'instruct_content', None):
                    try:
                        ic = message.instruct_content
                        # Common keys: Response or summary-like
                        result_text = getattr(ic, 'Response', None) or getattr(ic, 'Summary', None)
                    except Exception:
                        result_text = None
                if not result_text:
                    result_text = message.content
                result_path.write_text(str(result_text))
        except Exception:
            # Logging to files should never break runtime
            pass

        if 'Manager' in message.role:
            self.steps = self._parser_plan(message.content)
            self.new_roles_args = self._parser_roles(message.content)
            self.new_roles = self.create_roles(self.steps, self.new_roles_args)

        filename, file_content = None, None
        if hasattr(message.instruct_content, 'Type') and 'FILE' in message.instruct_content.Type:
            filename = message.instruct_content.Key
            file_type = re.findall('```(.*?)\n', str(message.content))[0]
            file_content = re.findall(f'```{file_type}([\s\S]*?)```', str(message.content))[0]
        
        if message.role and 'ActionObserver' != message.role:
            if hasattr(message.instruct_content, 'Response'):
                content = message.instruct_content.Response
            else:
                content = message.content

            msg = {   
                'timestamp': timestamp(),
                'role': message.role,
                'content': content,
                'file': {
                    'file_type': filename,
                    'file_data': file_content,
                }
            }

            if self.alg_msg_queue:
                self.alg_msg_queue.put_nowait(format_message(action=MessageType.RunTask.value, data={'task_id': self.task_id, 'task_message':msg}))
        
        if 'Agents Observer' in message.role:
            
            # send role list
            msg = {   
                'timestamp': timestamp(),
                'role': "Revised Role List",
                'content': self.new_roles_args,
                'file': {
                    'file_type': None,
                    'file_data': None,
                }
            }

            if self.alg_msg_queue:
                self.alg_msg_queue.put_nowait(format_message(action=MessageType.RunTask.value, data={'task_id': self.task_id, 'task_message':msg}))



    async def run(self, k=1):
        """Run all roles once per round, for k rounds."""
        old_roles = []
        for _ in range(k):
            futures = []
            for key in self.roles.keys():
                old_roles.append(key)
                role = self.roles[key]
                future = role.run()
                futures.append(future)
            
            await asyncio.gather(*futures)

        if len(old_roles) < len(self.roles):
            while len(self.get_role(name='Group').steps) > 0:
                futures = []
                for key in self.roles.keys():
                    if key not in old_roles:
                        role = self.roles[key]
                        future = role.run()
                        futures.append(future)

                await asyncio.gather(*futures)

    def get_roles(self) -> dict[str, Role]:
        """Get all roles in the environment."""
        return self.roles

    def get_role(self, name: str) -> Role:
        """Get a specific role in the environment by name."""
        return self.roles.get(name, None)

# Ensure pydantic forward refs for RoleContext.env -> Environment are resolved
# This supports both Pydantic v1 (update_forward_refs) and v2 (model_rebuild).
try:
    from .roles.role import RoleContext
    try:
        # Pydantic v2
        RoleContext.model_rebuild(_types_namespace={'Environment': Environment})
    except Exception:
        # Pydantic v1
        try:
            RoleContext.update_forward_refs(Environment=Environment)
        except Exception:
            pass
except Exception:
    # If imports fail during partial initialization, skip silently
    pass
