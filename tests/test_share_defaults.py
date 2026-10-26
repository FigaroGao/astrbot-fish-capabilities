"""Public packages must not activate capabilities or bind reference identities."""
import json
from pathlib import Path


def test_share_defaults_are_disabled_and_unbound():
    root = Path(__file__).resolve().parents[1]
    schema = json.loads((root / 'astrbot_plugin_fish_capabilities/_conf_schema.json').read_text(encoding='utf-8'))
    example = json.loads((root / 'examples/config.disabled.json').read_text(encoding='utf-8'))
    assert example == {key: value.get('default') for key, value in schema.items()}
    for key, value in schema.items():
        if key == 'enabled' or key.endswith('_enabled'):
            assert value['default'] is False, key
    for key in ('owners', 'command_platform_ids', 'allowed_group_sessions', 'history_group_sessions', 'knowledge_names', 'slang_knowledge_names'):
        assert schema[key]['default'] == [], key
    for key in ('bili_owner_uid', 'bili_owner_name', 'bili_account_id', 'bili_private_session'):
        assert schema[key]['default'] == '', key
