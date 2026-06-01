"""
worldinfo_extractor - 从小说/故事文本中提取 SillyTavern 兼容的世界书 (World Info / Lorebook)

Usage:
    python -m worldinfo_extractor.extract story.txt -o ./worlds
"""

from .worldinfo_builder import build_world_info, export_world_info_file
from .llm_extractor import WorldInfoLLMExtractor

__all__ = [
    'build_world_info',
    'export_world_info_file',
    'WorldInfoLLMExtractor',
]
