"""
Extract SillyTavern-compatible character cards from novel/story text using LLM.

Usage:
    # 首次使用：生成配置文件
    python -m card_extractor.extract --init

    # 编辑 card_extractor/.env 填入 API Key 后，直接用：
    python -m card_extractor.extract story.txt

    # 指定输出目录和头像：
    python -m card_extractor.extract story.txt -o ./output --avatar alice.png

    # 命令行参数会覆盖配置文件：
    python -m card_extractor.extract story.txt --model deepseek-chat --temperature 0.5

配置文件优先级（高到低）：
    命令行参数 > config.json > .env > 系统环境变量 > 默认值
"""

import argparse
import json
import os
import sys

try:
    from .llm_extractor import LLMExtractor, split_text
    from .card_builder import build_spec_v2, export_card
    from .config import load_config, create_default_config
except ImportError:
    from llm_extractor import LLMExtractor, split_text
    from card_builder import build_spec_v2, export_card
    from config import load_config, create_default_config


def main():
    parser = argparse.ArgumentParser(
        description='从小说/故事文本中提取 SillyTavern 角色卡片',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument('input', nargs='?', help='输入文本文件路径')
    parser.add_argument('-o', '--output', help='输出目录（默认: ./characters）')
    parser.add_argument('--api-key', help='LLM API Key（覆盖配置文件）')
    parser.add_argument('--base-url', help='LLM API Base URL（覆盖配置文件）')
    parser.add_argument('--model', help='LLM 模型名称（覆盖配置文件）')
    parser.add_argument('--temperature', type=float, help='LLM 温度参数（覆盖配置文件）')
    parser.add_argument('--avatar', help='角色头像图片路径（可选，不提供则生成默认头像）')
    parser.add_argument('--max-chunk', type=int, help='文本分块最大字符数（覆盖配置文件）')
    parser.add_argument('--json-only', action='store_true', help='只输出 JSON，不生成 PNG')
    parser.add_argument('--init', action='store_true', help='生成默认配置文件后退出')

    args = parser.parse_args()

    if args.init:
        create_default_config()
        return

    if not args.input:
        parser.print_help()
        print('\n提示: 首次使用请先运行 python -m card_extractor.extract --init 生成配置文件')
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
        'avatar': args.avatar,
        'output': args.output,
    })

    print(f'文本长度: {len(text)} 字符')

    extractor = LLMExtractor(
        api_key=config.get('api_key'),
        base_url=config.get('base_url'),
        model=config.get('model', 'gpt-4o'),
    )

    chunks = split_text(text, config.get('max_chunk', 8000))
    print(f'分块数量: {len(chunks)}')

    all_characters = []
    for i, chunk in enumerate(chunks):
        print(f'正在处理第 {i + 1}/{len(chunks)} 块...')
        try:
            characters = extractor.extract(chunk, temperature=config.get('temperature', 0.3))
            print(f'  提取到 {len(characters)} 个角色')
            all_characters.extend(characters)
            for c in characters:
                name = c.get('name', 'Unknown')
                print(f'    - {name}')
        except Exception as e:
            print(f'  错误: {e}')
            continue

    seen_names = set()
    unique_characters = []
    for c in all_characters:
        name = c.get('name', '')
        if name and name not in seen_names:
            seen_names.add(name)
            unique_characters.append(c)

    print(f'\n共提取到 {len(unique_characters)} 个不重复角色')

    os.makedirs(config['output'], exist_ok=True)

    for character in unique_characters:
        card = build_spec_v2(character)
        name = card.get('name', 'character')
        try:
            if args.json_only:
                safe_name = _safe_filename(name)
                json_path = os.path.join(config['output'], f'{safe_name}.json')
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(card, f, ensure_ascii=False, indent=2)
                print(f'  ✓ {name}.json')
            else:
                json_path, png_path = export_card(card, config['output'], config.get('avatar'))
                print(f'  ✓ {os.path.basename(json_path)} + {os.path.basename(png_path)}')
        except Exception as e:
            print(f'  ✗ {name}: {e}')

    print(f'\n完成！输出目录: {os.path.abspath(config["output"])}')

    if not args.json_only:
        print('\n提示: 将生成的 .png 文件放入 SillyTavern 的 data/<user>/characters/ 目录即可导入。')


def _safe_filename(name: str) -> str:
    unsafe = '<>:"/\\|?*'
    for ch in unsafe:
        name = name.replace(ch, '_')
    return name.strip() or 'character'


if __name__ == '__main__':
    main()
