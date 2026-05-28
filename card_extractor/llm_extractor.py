"""
Call LLM API to extract character cards from novel/story text.
Supports OpenAI-compatible APIs (OpenAI, DeepSeek, local models, etc.).
"""

import json
import os
from openai import OpenAI


EXTRACTION_SYSTEM_PROMPT = """你是一个专业的角色卡片提取助手。你的任务是从给定的小说/故事文本中提取所有角色的信息，并以严格的 JSON 格式输出，用于生成 SillyTavern 兼容的角色卡片。

## 输出格式要求

你必须返回一个 JSON 数组，每个元素是一个角色对象。每个角色对象包含以下字段：

{
  "name": "角色名（必填）",
  "description": "外貌描述、穿着、体态等视觉特征，尽量详细",
  "personality": "性格特征、说话风格、行为习惯等",
  "scenario": "角色所处的背景设定、世界观、故事场景",
  "first_mes": "角色见面时最可能说的第一句话，要体现其性格",
  "mes_example": "<START>\n{{char}}: 角色的一段典型对话示例\n{{user}}: 用户的回复\n{{char}}: 角色继续回复\n<END>",
  "creator_notes": "从原文中提取这个角色的补充说明、作者备注等",
  "system_prompt": "如果需要为这个角色定制系统提示词，填在这里，否则留空",
  "post_history_instructions": "对话后指令，否则留空",
  "alternate_greetings": ["备选开场白1", "备选开场白2"],
  "tags": ["标签1", "标签2"],
  "creator": "如果知道原作者或创建者，填在这里，否则留空",
  "character_version": "1.0"
}

## 提取规则

1. 只提取原文中明确出现或有充分依据的角色信息，不要编造。
2. description 必须基于原文中对该角色的外貌描写。
3. personality 必须基于原文中对该角色行为、对话、心理活动的描写。
4. first_mes 应该体现角色的性格特点和说话风格。
5. mes_example 中的对话要尽可能贴近原文的语言风格。
6. 如果某个字段在原文中没有相关信息，填写空字符串 ""。
7. tags 应该用简短的标签概括角色属性，如 ["女性", "战士", "傲娇"]。
8. 确保 JSON 格式正确，可以被直接解析。

请只返回 JSON 数组，不要包含任何其他解释性文字。"""

EXTRACTION_USER_TEMPLATE = """请从以下小说/故事文本中提取所有角色的角色卡片信息：

---
{text}
---

请以 JSON 数组格式返回所有提取到的角色卡片。"""


class LLMExtractor:
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

    def extract(self, text: str, temperature: float = 0.3) -> list[dict]:
        """
        Extract character cards from text.

        Args:
            text: Novel/story text to extract characters from
            temperature: LLM temperature (lower = more consistent)

        Returns:
            List of character card dicts in Spec V2 compatible format
        """
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

    def _parse_response(self, content: str) -> list[dict]:
        content = content.strip()
        if content.startswith('```'):
            lines = content.split('\n')
            content = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            start = content.find('[')
            end = content.rfind(']')
            if start != -1 and end != -1:
                data = json.loads(content[start:end + 1])
            else:
                raise ValueError(f'Failed to parse LLM response as JSON:\n{content[:500]}')

        if isinstance(data, dict):
            if 'characters' in data:
                data = data['characters']
            elif 'data' in data:
                data = data['data']
            else:
                values = list(data.values())
                if values and isinstance(values[0], list):
                    data = values[0]
                else:
                    data = [data]

        if not isinstance(data, list):
            raise ValueError(f'Expected a list of characters, got: {type(data)}')

        return data


def split_text(text: str, max_chars: int = 8000) -> list[str]:
    """
    Split text into chunks by paragraphs, keeping each chunk under max_chars.
    """
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
