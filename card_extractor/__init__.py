"""
card_extractor - 从小说/故事文本中提取 SillyTavern 兼容的角色卡片

Usage:
    python -m card_extractor.extract story.txt -o ./output
"""

from .card_builder import build_spec_v2, export_card
from .llm_extractor import LLMExtractor
from .png_utils import write_character_card, read_character_card

__all__ = [
    'build_spec_v2',
    'export_card',
    'LLMExtractor',
    'write_character_card',
    'read_character_card',
]
