import json
from types import SimpleNamespace

import pytest
from PIL import Image

from astrbot_plugin_fish_capabilities.services.bili_storyboard import (
    Storyboard,choose_details,distinct,reviewed_ads,
)


def panel(i,color='white'):
    return {'id':f'f{i}','time':float(i*10),'image':Image.new('RGB',(100,100),color)}


def test_dedup_preserves_new_chat_character():
    a=panel(0);b=panel(1);c=panel(2)
    c['image'].putpixel((90,90),(0,0,0))
    assert [p['id'] for p in distinct([a,b,c])]==['f0','f2']


def test_ads_require_seen_endpoints_confidence_explicit_reason():
    frames=[panel(0),panel(1),panel(2)]
    good={'first':'f1','last':'f2','confidence':.95,'explicit_promotion':True,'reason':'明确展示赞助口播购买引导'}
    assert len(reviewed_ads({'ads':[good]},frames))==1
    for change in [{'first':'f999'},{'first':[]},{'confidence':.7},{'confidence':True},{'confidence':float('nan')},{'explicit_promotion':False},{'reason':''},{'first':'f2','last':'f1'}]:
        assert reviewed_ads({'ads':[dict(good,**change)]},frames)==[]


def test_detail_rejects_unseen_ids_invalid_regions_and_ad_frames():
    frames=[panel(0),panel(1),panel(2)]
    ads=[{'start':10,'end':10}]
    plan={'details':[{'id':[]},{'id':'f999'},{'id':'f1'},{'id':'f0','region':[-1,0,1,1]}, {'id':'f2','region':[0,.4,1,1]}],
          'windows':[[0,20],[0,600],[-1,1]]}
    details=choose_details(plan,frames,frames,ads)
    assert details and all(p['id']!='f1' for p,_ in details)
    assert details[0][1]==[0,.4,1,1]


async def test_ad_filter_refills_and_excludes_final_images(tmp_path):
    frames=[panel(i,(i*20,20,20)) for i in range(12)]
    calls=[]
    async def candidates(*args):return frames
    async def generate(prompt,paths,kind,tokens):
        calls.append((prompt,paths,kind))
        if kind=='bili_visual_plan':
            return json.dumps({'type':'ordinary','ads':[{'first':'f4','last':'f7','confidence':.95,'explicit_promotion':True,'reason':'明确赞助推广及购买引导'}],
                               'details':[{'id':'f4'},{'id':'f0','region':[0,.5,1,1]}],'windows':[]})
        return '海边钓鱼的抽样画面。'
    reader=Storyboard(SimpleNamespace(root=tmp_path,candidates=candidates),generate)
    result=await reader.read({'bvid':'BVtest','title':'测试','preview_requested':4},{})
    # The 4-frame overview contains f0/f4/f7/f11. Ad range excludes f4..f7.
    assert result['preview_excluded_ads'][0]['start']==40
    assert all(not 40<=t<=70 for t in result['preview_timestamps'])
    assert result['preview_frames']>2
    assert all(not 40<=p['time']<=70 for p in result['preview_frame_manifest'])
    from astrbot_plugin_fish_capabilities.services.bili_storyboard import VERSION
    assert result['preview_layout_version']==VERSION and not result['full_video_watched']
    assert len(calls)==2 and all(p.exists() for _,paths,_ in calls for p in paths)


async def test_planner_failure_keeps_frames_and_reports_no_ad_detection(tmp_path):
    frames=[panel(0),panel(1)]
    async def candidates(*args):return frames
    async def generate(prompt,paths,kind,tokens):
        return 'invalid json' if kind=='bili_visual_plan' else '一张重复出现的图片，未确认全片。'
    result=await Storyboard(SimpleNamespace(root=tmp_path,candidates=candidates),generate).read({'bvid':'BVtest'}, {})
    assert result['preview_frames']==1
    assert result['preview_ad_filter_status']=='unavailable'
    assert result['preview_plan_status']=='unavailable'


async def test_all_ads_abstains_without_summarizing(tmp_path):
    frames=[panel(0),panel(1,'blue')];calls=[]
    async def candidates(*args):return frames
    async def generate(prompt,paths,kind,tokens):
        calls.append(kind)
        return json.dumps({'ads':[{'first':'f0','last':'f1','confidence':1,'explicit_promotion':True,'reason':'整段明确展示商业购买引导'}]})
    result=await Storyboard(SimpleNamespace(root=tmp_path,candidates=candidates),generate).read({'bvid':'BVtest'}, {})
    assert result['visual_content_seen'] is False and result['preview_frames']==0
    assert result['preview_ad_filter_status']=='all_sampled_frames_excluded'
    assert calls==['bili_visual_plan']


def test_source_page_budget_spans_end_not_first_three_pages(tmp_path,monkeypatch):
    import io,urllib.request
    from astrbot_plugin_fish_capabilities.services.bili_preview import Preview
    raw=io.BytesIO();Image.new('RGB',(20,20),'blue').save(raw,format='PNG');data=raw.getvalue();requested=[]
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,n):return data
    class Opener:
        def open(self,request,**kwargs):requested.append(request.full_url);return Response()
    monkeypatch.setattr(urllib.request,'build_opener',lambda *args:Opener())
    metadata={'img_x_len':1,'img_y_len':1,'img_x_size':20,'img_y_size':20,'image':[f'https://i0.hdslb.com/{i}.png' for i in range(10)]}
    frames=Preview(tmp_path).extract_candidates(metadata,[(i,float(i)) for i in range(10)])
    assert len(requested)==6 and frames[0]['time']==0 and frames[-1]['time']==9


async def test_new_strategy_invalidates_old_visual_cache(tmp_path,monkeypatch):
    import time
    monkeypatch.setattr(time,'time',lambda:1793100000.0)
    from test_services import BiliFake,BV
    from astrbot_plugin_fish_capabilities.services.bilibili import BiliReader
    reader=BiliReader(tmp_path/'cache.db',BiliFake());calls=[]
    async def visual(*args):
        calls.append(reader.visual_cache_version)
        return {'visual_status':'sampled_preview','preview_layout_version':reader.visual_cache_version,'visual_content_seen':True,'visual_summary':'看到海水'}
    reader.visual_reader=visual
    await reader.read(BV)
    reader.visual_cache_version=3
    await reader.read(BV)
    assert (await reader.read(BV))['cached']
    assert calls==[2,3]


async def test_static_gallery_reads_unique_images_only(tmp_path):
    frames=[panel(i,['red','red','blue','blue','green','green'][i]) for i in range(6)]
    async def candidates(*args):return frames
    async def generate(prompt,paths,kind,tokens):
        return json.dumps({'type':'slides','ads':[]}) if kind=='bili_visual_plan' else json.dumps({'pages':[{'id':f'f{i}','status':'read','text':f'第{i}张图'} for i in [0,2,4]]})
    result=await Storyboard(SimpleNamespace(root=tmp_path,candidates=candidates),generate).read({'bvid':'BVtest'}, {})
    assert result['gallery_discovered_pages']==3 and result['preview_frames']==3
    assert result['gallery_all_available_pages_read'] is True
    assert result['gallery_all_video_pages_confirmed'] is False


async def test_planner_changes_nine_hint_to_eighteen_and_preserves_details(tmp_path):
    frames=[panel(i,(i*7,20,30)) for i in range(27)]
    async def candidates(*args):return frames
    async def generate(prompt,paths,kind,tokens):
        if kind=='bili_visual_plan':
            assert 'frame_ids' in prompt and 'frame_count' in prompt
            return json.dumps({'type':'ordinary','frame_count':18,'details':[{'id':'f0','region':[0,.5,1,1]}]})
        return '画面内容。'
    result=await Storyboard(SimpleNamespace(root=tmp_path,candidates=candidates),generate).read({'bvid':'BVtest','preview_requested':9},{})
    assert result['preview_frames']==18 and result['preview_selection_method']=='planner_density'
    assert result['preview_detail_count']==1 and result['preview_detail_manifest'][0]['region']==[0,.5,1,1]


def test_planner_selects_actual_frames_and_rejects_unknown_and_ads():
    from astrbot_plugin_fish_capabilities.services.bili_storyboard import select_overview
    frames=[panel(i,(i,20,30)) for i in range(6)]
    result,method=select_overview({'frame_ids':['f4','f0','f4']},frames,frames,[],9)
    assert [p['id'] for p in result]==['f0','f4'] and method=='planner_frame_ids'
    for plan in [{'frame_ids':['f999']},{'frame_ids':[{}]},{'frame_count':True},{'frame_count':28},{'frame_ids':['f1']}]:
        result,method=select_overview(plan,frames,frames,[{'start':10,'end':10}],3)
        assert method=='request_hint_fallback' and all(p['id']!='f1' for p in result)


async def test_gallery_fallback_still_recognizes_characters(tmp_path):
    import hashlib
    from astrbot_plugin_fish_capabilities.services.character_atlas import CharacterAtlas
    from astrbot_plugin_fish_capabilities.services.policy import CapabilityError
    image=tmp_path/'ref.png';Image.new('RGB',(30,30),'blue').save(image)
    data={'cards':[{'id':'claude','family':'Claude','display_name':'Claude','status':'priority_reference','references':['r'],'visual_features':['orange','sun'],'disambiguation':[]}],
          'references':{'r':{'file':'ref.png','sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'visually_checked':True}}}
    (tmp_path/'cards.json').write_text(json.dumps(data))
    async def unavailable(*a):raise CapabilityError('no preview')
    frames=[panel(0,'blue')]
    async def scan(*a):return frames,{'source':'decoded_video_samples'}
    async def generate(prompt,paths,kind,tokens):
        if kind=='bili_visual_plan':return json.dumps({'type':'slides','characters':[{'character_id':'claude','frame_ids':['f0'],'confidence':.95,'evidence':'实际画面有橙色头发与太阳形头饰'}]})
        return json.dumps({'pages':[{'id':'f0','status':'read','text':'actual frame description'}]})
    result=await Storyboard(SimpleNamespace(root=tmp_path,candidates=unavailable),generate,SimpleNamespace(scan=scan),CharacterAtlas(tmp_path)).read({'bvid':'BVtest'},{})
    assert result['character_matches'][0]['family']=='Claude'
    assert result['character_matches'][0]['source']=='decoded_video_samples'


async def test_character_pass_does_not_skip_a_closeup_between_nine_samples(tmp_path):
    class Atlas:
        def bundle(self):return [],[]
        def matches(self,*a,**kw):return []
        def meme_context(self,*a):return []
    frames=[panel(i,(i*17,30,90)) for i in range(13)]
    async def candidates(*a):return frames
    async def generate(prompt,paths,kind,tokens):
        if kind=='bili_visual_plan':
            # f5 was absent in spread(thirteen, nine); it can be the sole clear
            # close-up. The final read may still select fewer frames.
            assert '"id": "f5"' in prompt and '"id": "f12"' in prompt
            return json.dumps({'type':'ordinary','frame_ids':['f5']})
        return 'A close-up in the actually selected frame.'
    result=await Storyboard(SimpleNamespace(root=tmp_path,candidates=candidates),generate,characters=Atlas()).read({'bvid':'BVtest','preview_requested':9},{})
    assert result['preview_frames']==1 and result['preview_timestamps']==[frames[5]['time']]
