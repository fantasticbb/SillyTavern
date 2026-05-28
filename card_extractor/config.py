import json
import os


_CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
_ENV_FILE = os.path.join(_CONFIG_DIR, '.env')
_JSON_FILE = os.path.join(_CONFIG_DIR, 'config.json')

_DEFAULTS = {
    'model': 'gpt-4o',
    'temperature': 0.3,
    'max_chunk': 8000,
    'output': './characters',
}


def _load_env_file() -> dict[str, str]:
    result = {}
    if not os.path.exists(_ENV_FILE):
        return result
    with open(_ENV_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                result[key] = value
    return result


def _load_json_config() -> dict:
    if not os.path.exists(_JSON_FILE):
        return {}
    try:
        with open(_JSON_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def load_config(cli_args: dict | None = None) -> dict:
    """
    Merge config from multiple sources. Priority (high to low):
    1. Command line arguments
    2. config.json
    3. .env file
    4. Environment variables
    5. Defaults
    """
    config = dict(_DEFAULTS)

    for key, value in os.environ.items():
        if key == 'OPENAI_API_KEY':
            config['api_key'] = value
        elif key == 'OPENAI_BASE_URL':
            config['base_url'] = value
        elif key == 'CARD_EXTRACTOR_MODEL':
            config['model'] = value
        elif key == 'CARD_EXTRACTOR_TEMPERATURE':
            config['temperature'] = float(value)
        elif key == 'CARD_EXTRACTOR_OUTPUT':
            config['output'] = value

    env_vars = _load_env_file()
    env_map = {
        'OPENAI_API_KEY': 'api_key',
        'OPENAI_BASE_URL': 'base_url',
        'CARD_EXTRACTOR_MODEL': 'model',
        'CARD_EXTRACTOR_TEMPERATURE': 'temperature',
        'CARD_EXTRACTOR_OUTPUT': 'output',
    }
    for env_key, config_key in env_map.items():
        if env_key in env_vars:
            value = env_vars[env_key]
            if config_key == 'temperature':
                config[config_key] = float(value)
            else:
                config[config_key] = value

    json_config = _load_json_config()
    json_map = {
        'api_key': 'api_key',
        'base_url': 'base_url',
        'model': 'model',
        'temperature': 'temperature',
        'output': 'output',
        'max_chunk': 'max_chunk',
        'avatar': 'avatar',
    }
    for json_key, config_key in json_map.items():
        if json_key in json_config and json_config[json_key]:
            config[config_key] = json_config[json_key]

    if cli_args:
        cli_map = {
            'api_key': 'api_key',
            'base_url': 'base_url',
            'model': 'model',
            'temperature': 'temperature',
            'max_chunk': 'max_chunk',
            'avatar': 'avatar',
        }
        cli_overrides = {k: v for k, v in cli_args.items()
                         if v is not None or k == 'temperature'}
        for key, value in cli_overrides.items():
            if key in cli_map and value is not None:
                config[cli_map[key]] = value
        if cli_overrides.get('output') is not None:
            config['output'] = cli_overrides['output']

    return config


def create_default_config():
    """Create a default .env file and config.json if they don't exist."""
    if not os.path.exists(_ENV_FILE):
        with open(_ENV_FILE, 'w', encoding='utf-8') as f:
            f.write('# Card Extractor 配置文件\n')
            f.write('# 在这里配置你的 LLM API，之后只需运行 python -m card_extractor.extract story.txt\n')
            f.write('\n')
            f.write('# OpenAI / DeepSeek / 兼容 API\n')
            f.write('OPENAI_API_KEY=sk-your-api-key-here\n')
            f.write('OPENAI_BASE_URL=https://api.openai.com/v1\n')
            f.write('\n')
            f.write('# 模型和参数（可选，也可写在 config.json）\n')
            f.write('# CARD_EXTRACTOR_MODEL=gpt-4o\n')
            f.write('# CARD_EXTRACTOR_TEMPERATURE=0.3\n')
            f.write('# CARD_EXTRACTOR_OUTPUT=./characters\n')
        print(f'已创建默认配置文件: {_ENV_FILE}')

    if not os.path.exists(_JSON_FILE):
        default_json = {
            'api_key': '',
            'base_url': 'https://api.openai.com/v1',
            'model': 'gpt-4o',
            'temperature': 0.3,
            'output': './characters',
            'max_chunk': 8000,
            'avatar': '',
        }
        with open(_JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_json, f, ensure_ascii=False, indent=2)
        print(f'已创建默认配置文件: {_JSON_FILE}')
