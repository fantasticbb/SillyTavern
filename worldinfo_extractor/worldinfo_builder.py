"""
Build SillyTavern-compatible World Info (Lorebook) JSON from structured data.
"""

import json
import os


ENTRY_TEMPLATE = {
    'key': [],
    'keysecondary': [],
    'comment': '',
    'content': '',
    'constant': False,
    'vectorized': False,
    'selective': True,
    'selectiveLogic': 0,
    'addMemo': True,
    'order': 100,
    'position': 0,
    'disable': False,
    'ignoreBudget': False,
    'excludeRecursion': False,
    'preventRecursion': False,
    'matchPersonaDescription': False,
    'matchCharacterDescription': False,
    'matchCharacterPersonality': False,
    'matchCharacterDepthPrompt': False,
    'matchScenario': False,
    'matchCreatorNotes': False,
    'delayUntilRecursion': False,
    'probability': 100,
    'useProbability': True,
    'depth': 4,
    'outletName': '',
    'group': '',
    'groupOverride': False,
    'groupWeight': 100,
    'scanDepth': None,
    'caseSensitive': None,
    'matchWholeWords': None,
    'useGroupScoring': None,
    'automationId': '',
    'role': None,
    'sticky': 0,
    'cooldown': 0,
    'delay': 0,
    'triggers': [],
}


def build_world_info(name: str, entries: list[dict]) -> dict:
    """
    Build a SillyTavern-compatible World Info JSON from LLM-extracted entries.

    Args:
        name: World book name (display name in SillyTavern)
        entries: List of entry dicts from LLM extraction, each with:
            - uid: unique id
            - key: list of trigger keywords
            - keysecondary: list of secondary keys (optional)
            - comment: short label for the entry
            - content: detailed world setting description

    Returns:
        Dict with the SillyTavern World Info format
    """
    built_entries = {}
    display_idx = 0

    for entry in entries:
        uid = str(entry.get('uid', display_idx))

        built = dict(ENTRY_TEMPLATE)
        built['uid'] = entry.get('uid', display_idx)
        built['key'] = entry.get('key', [])
        built['keysecondary'] = entry.get('keysecondary', [])
        built['comment'] = entry.get('comment', '')
        built['content'] = entry.get('content', '')
        built['displayIndex'] = display_idx

        built_entries[uid] = built
        display_idx += 1

    return {
        'name': name,
        'entries': built_entries,
    }


def export_world_info_file(
    world_info: dict,
    output_dir: str,
    world_name: str | None = None,
) -> str:
    """
    Export world info to a JSON file in SillyTavern-compatible format.

    Args:
        world_info: World Info dict from build_world_info()
        output_dir: Directory to output the file
        world_name: Filename (without extension), defaults to world_info['name']

    Returns:
        Path to the saved JSON file
    """
    os.makedirs(output_dir, exist_ok=True)

    name = world_name or world_info.get('name', 'world_info')
    safe_name = _safe_filename(name)

    json_path = os.path.join(output_dir, f'{safe_name}.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(world_info, f, ensure_ascii=False, indent=2)

    return json_path


def _safe_filename(name: str) -> str:
    unsafe = '<>:"/\\|?*'
    for ch in unsafe:
        name = name.replace(ch, '_')
    return name.strip() or 'world_info'
