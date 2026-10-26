import json
import pytest
from astrbot_plugin_fish_capabilities.services.sister_mail import SisterMail
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError
from test_astrbot_binding import plugin,Event


def test_correspondence_persists_deduplicates_and_ack_is_not_delete(tmp_path):
    path=tmp_path/'mail.db';mail=SisterMail(path)
    first=mail.leave('fish','想要更好的视频画面','功能愿望')
    assert mail.leave('fish','想要更好的视频画面','功能愿望')['id']==first['id']
    assert mail.read('fish')['letters']==[]
    assert SisterMail(path).read('codex')['letters'][0]['author']=='fish'
    mail.acknowledge('codex',first['id'])
    assert mail.read('codex')['letters']==[]
    assert mail.read('codex',unread=False)['letters']
    reply=mail.leave('codex','已看到，待核实',reply_to=first['id'])
    assert mail.read('fish')['letters'][0]['reply_to']==first['id']
    with pytest.raises(CapabilityError):mail.acknowledge('codex',reply['id'])
    with pytest.raises(CapabilityError):mail.leave('fish','x',reply_to=999)
    with pytest.raises(CapabilityError):mail.leave('fish','x'*1201)


async def test_mailbox_tools_cannot_leak_into_group_or_other_private(plugin):
    plugin.config['sister_mail_enabled']=True
    plugin.sister_mail.leave('codex','私有回信')
    for e in [Event(private=False),Event(sender='other',admin=False)]:
        assert json.loads(await plugin.sister_mail_tool(e))['ok'] is False
        assert json.loads(await plugin.sister_mail_tool(e,'leave','冒充留言'))['ok'] is False
    result=json.loads(await plugin.sister_mail_tool(Event()))
    assert result['letters'][0]['author']=='codex'
    note=json.loads(await plugin.sister_mail_tool(Event(),'leave','自己的想法'))
    assert note['saved'] and note['recipient_notified'] is False
    assert plugin.sister_mail.read('codex')['letters'][0]['author']=='fish'
