"""
Build Spec V2 character cards from structured data and export to JSON + PNG.
"""

import json
import os
from datetime import datetime, timezone

try:
    from .png_utils import write_character_card, generate_default_avatar
except ImportError:
    from png_utils import write_character_card, generate_default_avatar

SPEC_VERSION = '2.0'
SPEC = 'chara_card_v2'


def build_spec_v2(data: dict) -> dict:
    """
    Build a SillyTavern-compatible Spec V2 character card from raw dict data.

    Expected input keys:
        name            - Character name (required)
        description     - Physical/visual description
        personality     - Personality traits
        scenario        - Background scenario/world setting
        first_mes       - First message / greeting
        mes_example     - Example dialogue
        creator_notes   - Creator's notes
        system_prompt   - System prompt override
        post_history_instructions - Post-history instructions
        alternate_greetings - List of alternate greetings
        tags            - List of tags
        creator         - Creator name
        character_version - Version string
        extensions      - Dict of extension data
    """
    name = data.get('name', 'Unknown')
    card = {
        'spec': SPEC,
        'spec_version': SPEC_VERSION,
        'name': name,
        'description': data.get('description', ''),
        'personality': data.get('personality', ''),
        'scenario': data.get('scenario', ''),
        'first_mes': data.get('first_mes', ''),
        'mes_example': data.get('mes_example', ''),
        'creatorcomment': data.get('creator_notes', ''),
        'avatar': 'none',
        'chat': f"{name} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        'talkativeness': data.get('talkativeness', 0.5),
        'fav': data.get('fav', False),
        'tags': data.get('tags', []),
        'spec': SPEC,
        'spec_version': SPEC_VERSION,
        'data': {
            'name': name,
            'description': data.get('description', ''),
            'personality': data.get('personality', ''),
            'scenario': data.get('scenario', ''),
            'first_mes': data.get('first_mes', ''),
            'mes_example': data.get('mes_example', ''),
            'creator_notes': data.get('creator_notes', ''),
            'system_prompt': data.get('system_prompt', ''),
            'post_history_instructions': data.get('post_history_instructions', ''),
            'alternate_greetings': data.get('alternate_greetings', []),
            'tags': data.get('tags', []),
            'creator': data.get('creator', ''),
            'character_version': data.get('character_version', ''),
            'extensions': data.get('extensions', {}),
        },
        'create_date': datetime.now(timezone.utc).isoformat(),
    }

    tags = card['data']['tags']
    if isinstance(tags, str):
        card['data']['tags'] = [t.strip() for t in tags.split(',') if t.strip()]
        card['tags'] = card['data']['tags']

    return card


def export_card(card: dict, output_dir: str, avatar_path: str | None = None) -> tuple[str, str]:
    """
    Export a character card to JSON and PNG files.

    Args:
        card: Spec V2 card dict
        output_dir: Directory to output files
        avatar_path: Path to avatar image (optional, generates default if None)

    Returns:
        Tuple of (json_path, png_path)
    """
    os.makedirs(output_dir, exist_ok=True)
    card_json = json.dumps(card, ensure_ascii=False, indent=2)
    safe_name = _safe_filename(card.get('name', 'character'))

    json_path = os.path.join(output_dir, f'{safe_name}.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        f.write(card_json)

    png_path = os.path.join(output_dir, f'{safe_name}.png')

    if avatar_path and os.path.exists(avatar_path):
        temp_avatar = avatar_path
        remove_temp = False
    else:
        temp_path = os.path.join(output_dir, f'_temp_avatar_{safe_name}.png')
        with open(temp_path, 'wb') as f:
            f.write(generate_default_avatar())
        temp_avatar = temp_path
        remove_temp = True

    write_character_card(temp_avatar, card_json, png_path)

    if remove_temp:
        os.remove(temp_avatar)

    return json_path, png_path


def _safe_filename(name: str) -> str:
    unsafe = '<>:"/\\|?*'
    for ch in unsafe:
        name = name.replace(ch, '_')
    return name.strip() or 'character'
