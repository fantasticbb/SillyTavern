"""
Call LLM API to extract world info / lorebook entries from novel/story text.
Supports OpenAI-compatible APIs (OpenAI, DeepSeek, local models, etc.).
"""

import json
import os
from openai import OpenAI


EXTRACTION_SYSTEM_PROMPT = """你是一个专业的世界设定提取助手。你的任务是从给定的故事/小说文本中提取世界设定（世界观、地点、势力、种族、魔法体系、历史事件、特殊物品等），并以严格的 JSON 格式输出，用于生成 SillyTavern 兼容的世界书 (World Info / Lorebook)。

## 输出格式要求

你必须返回一个 JSON 对象，包含一个 "entries" 字段和一个 "name" 字段：

{
  "name": "世界书的名称（用于在 SillyTavern 中展示，简洁明了）",
  "entries": [
    {
      "uid": 0,
      "key": ["触发关键词1", "触发关键词2"],
      "keysecondary": [],
      "comment": "条目的简短名称/描述，用于标识这个条目",
      "content": "世界设定的详细描述，可以是客观叙事、百科式说明或角色间的对话形式。\n描述应当详细、准确，包含所有原文中提到的相关设定细节。"
    }
  ]
}

## 提取规则

1. **条目标识（comment）**：每个条目应该有一个简短的中文或英文名称，方便在编辑器中识别，如 "艾尔多瑞亚"、"暗影獠牙"、"魔法体系"等。

2. **触发关键词（key）**：为每个条目设置 2-6 个触发关键词。关键词应该包括：
   - 条目的正式名称（如 "Eldoria"）
   - 常见简称或别名（如 "森林"、"魔法森林"）
   - 相关概念词（如 "守望者" 对应 "guardian"）
   - 注意区分中英文，如果原文是英文名，同时添加中文翻译

3. **内容丰富度（content）**：content 字段要尽可能全面、详细，包含原文中关于该设定要素的全部信息。可以使用客观叙事体来描述，也可以使用角色对话体。格式可以是多段落。

4. **世界书名称（name）**：给这个世界书取一个有意义的名字，最好能概括整个世界观，如 "艾尔多瑞亚世界设定"。

5. **提取范围**：只提取以下类型的世界设定要素：
   - 地点/场景（城市、森林、建筑、秘境等）
   - 势力/组织（王国、公会、教派、家族等）  
   - 种族/生物（精灵、魔兽、特殊生物等）
   - 魔法/科技体系（魔法规则、能量系统、特殊技术等）
   - 历史事件（重大战争、灾难、变革等）
   - 重要人物（只在作为世界设定的一部分时，如神明、传说英雄）
   - 特殊物品/神器
   - 文化/信仰/习俗
   - 政治/社会结构
   - 自然法则/物理规则（如世界观特有的规则）

6. **不要编造**：只提取原文中明确出现或有充分依据的设定信息，不要编造不存在的内容。

7. **UID 从 0 开始递增**。

8. **确保 JSON 格式正确**，可以被直接解析。

请只返回 JSON 对象，不要包含任何其他解释性文字。"""

EXTRACTION_USER_TEMPLATE = """请从以下故事/小说文本中提取世界设定条目：

---
{text}
---

请以 JSON 格式返回提取到的世界设定条目。"""


class WorldInfoLLMExtractor:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = 'gpt-4o',
    ):
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        self.base_url = base_url or os.environ.get('OPENAI_BASE_URL')
        self.model = model

        if not self.api_key:
            raise ValueError(
                'API key is required. Set OPENAI_API_KEY environment variable '
                'or pass api_key parameter.'
            )

        client_kwargs = {'api_key': self.api_key}
        if self.base_url:
            client_kwargs['base_url'] = self.base_url
        self.client = OpenAI(**client_kwargs)

    def extract(self, text: str, temperature: float = 0.3) -> dict:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {'role': 'system', 'content': EXTRACTION_SYSTEM_PROMPT},
                {'role': 'user', 'content': EXTRACTION_USER_TEMPLATE.format(text=text)},
            ],
            temperature=temperature,
            response_format={'type': 'json_object'},
        )

        content = response.choices[0].message.content
        if not content:
            raise RuntimeError('LLM returned empty response')

        return self._parse_response(content)

    def _parse_response(self, content: str) -> dict:
        content = content.strip()
        if content.startswith('```'):
            lines = content.split('\n')
            content = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1:
                data = json.loads(content[start:end + 1])
            else:
                raise ValueError(f'Failed to parse LLM response as JSON:\n{content[:500]}')

        if not isinstance(data, dict):
            raise ValueError(f'Expected a JSON object, got: {type(data)}')

        if 'entries' not in data:
            raise ValueError('Response missing "entries" field')

        return data


def split_text(text: str, max_chars: int = 8000) -> list[str]:
    paragraphs = text.split('\n\n')
    chunks = []
    current = ''

    for para in paragraphs:
        if len(current) + len(para) + 2 > max_chars and current:
            chunks.append(current.strip())
            current = para
        else:
            current = current + '\n\n' + para if current else para

    if current.strip():
        chunks.append(current.strip())

    return chunks


def merge_entries(
    all_entries: list[dict],
    max_entries: int | None = None,
) -> list[dict]:
    """
    Merge entries from multiple chunks, deduplicating by comment/similarity.
    """
    seen_comments = set()
    merged = []

    for chunk_data in all_entries:
        entries = chunk_data.get('entries', [])
        for entry in entries:
            comment = entry.get('comment', '').strip().lower()
            if comment and comment in seen_comments:
                continue
            if comment:
                seen_comments.add(comment)
            merged.append(entry)

    for i, entry in enumerate(merged):
        entry['uid'] = i

    if max_entries and len(merged) > max_entries:
        merged = merged[:max_entries]

    return merged
