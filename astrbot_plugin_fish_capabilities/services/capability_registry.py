"""Single registry for tool switches, access requirements and dashboard display."""
from .policy import CapabilityError,require_owner

TOOL_FEATURES = {'fish_bili_activity': 'bili_activity',
 'fish_bili_browse': 'bili',
 'fish_bili_comment': 'bili_comment',
 'fish_bili_comment_media': 'bili',
 'fish_bili_followings': 'bili',
 'fish_bili_group_watch': 'bili_group',
 'fish_bili_interact': 'bili',
 'fish_bili_memory': 'bili',
 'fish_bili_public_shelf': 'bili_public_shelf',
 'fish_bili_read': 'bili',
 'fish_bili_reflect': 'bili',
 'fish_bili_replies': 'bili_reply',
 'fish_bili_review': 'bili_public_review',
 'fish_bili_scroll': 'bili',
 'fish_bili_status': 'bili',
 'fish_bili_up_videos': 'bili',
 'fish_group_history': 'history',
 'fish_group_pause': 'intent_self_pause',
 'fish_knowledge_search': 'knowledge',
 'fish_learning': 'learning',
 'fish_meme': 'meme',
 'fish_meme_catalog': 'meme',
 'fish_meme_search': 'meme',
 'fish_memory_edit': 'memory_edit',
 'fish_quota': 'quota',
 'fish_recall': 'cold_archive',
 'fish_sister_mail': 'sister_mail',
 'fish_speak': 'tts',
 'fish_tasks': 'timetable',
 'fish_timeline': 'timeline',
 'fish_usage_details': 'quota',
 'fish_valorant_match': 'valorant',
 'fish_valorant_profile': 'valorant',
 'fish_valorant_records': 'valorant',
 'fish_valorant_shop': 'valorant_shop',
 'fish_weather': 'weather'}
GROUP_FEATURES = {'weather','meme','knowledge','quota','bili_group','intent_self_pause','asr','companionship','conversation_depth'}
TOOL_FEATURES['fish_group_observation']='group_learning'
TOOL_FEATURES['fish_tone_diagnose']='tone_diagnostics'
TOOL_FEATURES['fish_codex_resets']='codex_resets'
GROUP_FEATURES.add('group_learning')
FEATURE_ACCESS = {feature:('authorized_group_or_owner_private' if feature in GROUP_FEATURES else 'owner_private')
                  for feature in set(TOOL_FEATURES.values())}
FEATURE_ACCESS.update({feature:'authorized_group_or_owner_private' for feature in ('asr','companionship','conversation_depth','homophone')})


def authorize(config,actor,feature,*,owner=False,cold_private=False):
    if feature not in FEATURE_ACCESS:
        raise CapabilityError('此能力未在统一权限表登记。')
    if not config.get('enabled',False) or not config.get(feature+'_enabled',False):
        raise CapabilityError('这个能力尚未启用。')
    if 'command_platform_ids' in config and actor.platform_id not in config.get('command_platform_ids',[]):
        raise CapabilityError('当前平台未获能力授权。')
    if feature in ('bili_comment','bili_reply') and cold_private:
        raise CapabilityError('本会话引用过私有冷档，请换新会话讨论公开内容。')
    if owner or actor.private or FEATURE_ACCESS[feature]=='owner_private':
        require_owner(actor,list(map(str,config.get('owners',[]))))
    elif actor.conversation not in config.get('allowed_group_sessions',[]):
        raise CapabilityError('本群尚未启用这个能力。')
    return actor


def catalog(config):
    return [{'tool':name,'feature':feature,'enabled':bool(config.get('enabled') and config.get(feature+'_enabled')),
             'access':FEATURE_ACCESS[feature],'public_write':name in {'fish_bili_comment','fish_bili_replies','fish_bili_activity'}}
            for name,feature in TOOL_FEATURES.items()]
