"""
Extract SillyTavern-compatible World Info (Lorebook) from novel/story text using LLM.

Usage:
    python -m worldinfo_extractor.extract --init

    python -m worldinfo_extractor.extract story.txt

    python -m worldinfo_extractor.extract story.txt -o ./worlds --model deepseek-chat
"""

import argparse
import json
import os
import sys

try:
    from .llm_extractor import WorldInfoLLMExtractor, split_text, merge_entries
    from .worldinfo_builder import build_world_info, export_world_info_file
    from .config import load_config, create_default_config
except ImportError:
    from llm_extractor import WorldInfoLLMExtractor, split_text, merge_entries
    from worldinfo_builder import build_world_info, export_world_info_file
    from config import load_config, create_default_config


def main():
    parser = argparse.ArgumentParser(
        description='从小说/故事文本中提取 SillyTavern 世界书 (World Info / Lorebook)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument('input', nargs='?', help='输入文本文件路径')
    parser.add_argument('-o', '--output', help='输出目录（默认: ./worlds）')
    parser.add_argument('--api-key', help='LLM API Key（覆盖配置文件）')
    parser.add_argument('--base-url', help='LLM API Base URL（覆盖配置文件）')
    parser.add_argument('--model', help='LLM 模型名称（覆盖配置文件）')
    parser.add_argument('--temperature', type=float, help='LLM 温度参数（覆盖配置文件）')
    parser.add_argument('--max-chunk', type=int, help='文本分块最大字符数（覆盖配置文件）')
    parser.add_argument('--name', help='世界书名称（可选，不指定则使用 LLM 提取的名称）')
    parser.add_argument('--init', action='store_true', help='生成默认配置文件后退出')

    args = parser.parse_args()

    if args.init:
        create_default_config()
        return

    if not args.input:
        parser.print_help()
        print('\n提示: 首次使用请先运行 python -m worldinfo_extractor.extract --init 生成配置文件')
        sys.exit(1)

    if not os.path.exists(args.input):
        print(f'错误: 找不到输入文件: {args.input}')
        sys.exit(1)

    with open(args.input, 'r', encoding='utf-8') as f:
        text = f.read()

    if not text.strip():
        print('错误: 输入文件为空')
        sys.exit(1)

    config = load_config({
        'api_key': args.api_key,
        'base_url': args.base_url,
        'model': args.model,
        'temperature': args.temperature,
        'max_chunk': args.max_chunk,
        'output': args.output,
    })

    print(f'文本长度: {len(text)} 字符')

    extractor = WorldInfoLLMExtractor(
        api_key=config.get('api_key'),
        base_url=config.get('base_url'),
        model=config.get('model', 'gpt-4o'),
    )

    chunks = split_text(text, config.get('max_chunk', 8000))
    print(f'分块数量: {len(chunks)}')

    all_chunk_data = []
    world_name_from_llm = ''
    for i, chunk in enumerate(chunks):
        print(f'正在处理第 {i + 1}/{len(chunks)} 块...')
        try:
            chunk_result = extractor.extract(chunk, temperature=config.get('temperature', 0.3))
            entry_count = len(chunk_result.get('entries', []))
            print(f'  提取到 {entry_count} 个世界设定条目')
            all_chunk_data.append(chunk_result)

            if not world_name_from_llm and chunk_result.get('name'):
                world_name_from_llm = chunk_result['name']
                print(f'  世界书名称: {world_name_from_llm}')

            for entry in chunk_result.get('entries', []):
                comment = entry.get('comment', '')
                keys = entry.get('key', [])
                print(f'    - {comment}: {keys}')
        except Exception as e:
            print(f'  错误: {e}')
            continue

    if not all_chunk_data:
        print('错误: 未能从文本中提取到任何世界设定')
        sys.exit(1)

    merged_entries = merge_entries(all_chunk_data)
    print(f'\n合并去重后共 {len(merged_entries)} 个世界设定条目')

    world_name = args.name or world_name_from_llm or 'extracted_world_info'

    world_info = build_world_info(world_name, merged_entries)

    os.makedirs(config['output'], exist_ok=True)
    json_path = export_world_info_file(world_info, config['output'], world_name)

    print(f'\n完成！')
    print(f'  世界书名称: {world_name}')
    print(f'  条目数量: {len(merged_entries)}')
    print(f'  输出文件: {os.path.abspath(json_path)}')
    print(f'\n将 {os.path.basename(json_path)} 放入 SillyTavern 的 data/<用户>/worlds/ 目录即可导入。')


if __name__ == '__main__':
    main()
