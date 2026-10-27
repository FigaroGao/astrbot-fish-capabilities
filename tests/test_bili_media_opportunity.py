from types import SimpleNamespace

import pytest
from astrbot_plugin_fish_capabilities.services.bili_media import CommentMedia


async def test_emote_failure_does_not_remove_public_image_candidates():
    media=CommentMedia(None,None,{})
    async def failed():raise RuntimeError('emoji unavailable')
    media.codes=failed
    media.images=lambda:[{'meme_id':'public-1','description':'开心吃鱼','image_text':'好吃'}]
    result=await media.opportunity('开心吃鱼')
    assert result['emotes']==[] and result['images'][0]['meme_id']=='public-1'
    assert result['status']['emotes']=='unavailable'


async def test_candidates_small_contextual_and_not_forced():
    media=CommentMedia(None,None,{})
    async def codes():return ['[doge]']
    media.codes=codes
    media.images=lambda:[{'meme_id':str(i),'description':'开心吃鱼' if i==12 else '晚上好','image_text':''} for i in range(20)]
    result=await media.opportunity('开心吃鱼')
    assert len(result['images'])==6 and result['images'][0]['meme_id']=='12'
    assert result['emotes']==['[doge]']


async def test_duty_receives_media_and_passes_selected_image_to_review_path(tmp_path):
    from test_services import BiliFake,BV
    from astrbot_plugin_fish_capabilities.services.bilibili import BiliReader
    from astrbot_plugin_fish_capabilities.services.bili_duty import BiliDuty
    reader=BiliReader(tmp_path/'bili.db',BiliFake());prompts=[];posted=[]
    async def opportunity(context):return {'emotes':['[doge]'],'images':[{'meme_id':'public-1','description':'开心','image_text':'好耶'}]}
    async def post(reading,text,evidence_ids,**options):posted.append(options);return {'submitted':True}
    comments=SimpleNamespace(media=SimpleNamespace(opportunity=opportunity),post=post)
    async def generate(prompt):
        import json
        prompts.append(prompt)
        if len(prompts)==1:return json.dumps({'bvid':BV})
        return json.dumps({'bvid':BV,'comment':'这段有意思[doge]','comment_meme_id':'public-1','evidence_ids':[BV+':s0'],'recommend':False})
    async def deliver(text):raise AssertionError('no private recommendation expected')
    await BiliDuty(reader,comments,{'bili_comment_enabled':True},generate,deliver).once('media-test')
    assert 'available_media' in prompts[-1] and 'public-1' in prompts[-1] and 'comment_meme_id' in prompts[-1]
    assert posted==[{'meme_id':'public-1'}]
