import json,shutil,os
from types import SimpleNamespace
import pytest
from PIL import Image
from astrbot_plugin_fish_capabilities.services.bili_scene import SceneReader,scene_times,run_ffmpeg
from astrbot_plugin_fish_capabilities.services.bili_storyboard import Storyboard


def test_scene_scan_keeps_ends_and_detects_real_changes():
    raw=b''.join(Image.new('RGB',(64,36),c).tobytes() for c in ['red']*10+['blue']*10+['green']*10)
    rows,status=scene_times(raw,15,8)
    assert rows[0]['time']==0 and rows[-1]['time']==14.5
    assert status['detected_cut_candidates']>=2
    assert [r['time'] for r in rows]==sorted({r['time'] for r in rows})
    assert all(0<=r['start']<r['end']<=15 for r in rows)


async def test_ordinary_gets_scene_reader_but_chat_preserves_original_pages(tmp_path,monkeypatch):
    calls=[];kind=['ordinary']
    frames=[{'id':f'f{i}','time':i,'image':Image.new('RGB',(30,30),(i*30,20,30))} for i in range(4)]
    async def candidates(*a):return frames
    async def scan(*a):calls.append('gallery');return frames,{'source':'decoded_video'}
    async def generate(prompt,paths,name,tokens):
        if name=='bili_visual_plan':return json.dumps({'type':kind[0]})
        return json.dumps({'pages':[{'id':f'f{i}','status':'read','text':'page'} for i in range(4)]})
    async def scene(self,*a):calls.append('scene');return {'visual_summary':'scene result'}
    monkeypatch.setattr(SceneReader,'read',scene)
    board=Storyboard(SimpleNamespace(root=tmp_path,candidates=candidates),generate,SimpleNamespace(ffmpeg='ffmpeg',scan=scan))
    assert (await board.read({'bvid':'BVtest'},{'duration':4}))['visual_summary']=='scene result'
    kind[0]='chat'
    result=await board.read({'bvid':'BVtest'},{'duration':4})
    assert calls==['scene','gallery'] and result['gallery_all_available_pages_read']


async def test_scene_zoom_validates_choices_excludes_ads_and_uses_source_frames(tmp_path):
    frames=[{'id':f's{i}','time':i*5,'start':i*5,'end':i*5+5,'image':Image.new('RGB',(30,30),(i*30,20,30))} for i in range(4)]
    extracted=[];calls=[]
    async def generate(prompt,paths,name,tokens):
        calls.append(name)
        if name=='bili_visual_plan':return json.dumps({'details':[{'id':'bad'},{'id':'s1'},{'id':'s2','region':[0,.5,1,1]}],
            'ads':[{'first':'s1','last':'s1','confidence':.99,'explicit_promotion':True,'reason':'明确商业推广购买引导'}],
            'windows':[[0,60],[10,14]]})
        return 'actual scenes'
    board=Storyboard(SimpleNamespace(root=tmp_path),generate)
    reader=SceneReader(None,board)
    async def frame(path,t,directory,index,limit):extracted.append((t,limit));return Image.new('RGB',(100,100),'red')
    reader.frame=frame
    result=await reader.inspect({'title':'test','evidence':[{'start':10,'end':12,'text':'subtitle'}]},
        {'duration':20},frames,{'limitation':'sampled'},123,None,tmp_path,'')
    assert all(t!=5 and limit==1600 for t,limit in extracted)
    assert result['preview_detail_count']==4 and result['scene_zoom_windows']
    assert calls==['bili_visual_plan','bili_visual']
    assert not result['full_video_watched'] and result['full_video_downloaded']
    assert result['scene_intervals'][2]['subtitle']=='subtitle'


@pytest.mark.skipif(not (os.environ.get('FISH_TEST_FFMPEG') or shutil.which('ffmpeg')),reason='ffmpeg required')
async def test_actual_ffmpeg_scan_and_selected_frame(tmp_path):
    ffmpeg=os.environ.get('FISH_TEST_FFMPEG') or shutil.which('ffmpeg');source=tmp_path/'source.mp4'
    await run_ffmpeg(ffmpeg,'-f','lavfi','-i','testsrc2=size=320x240:rate=8','-t','2',
        '-c:v','mpeg4',str(source))
    raw=await run_ffmpeg(ffmpeg,'-i',str(source),'-vf','fps=2,scale=64:36','-pix_fmt','rgb24','-f','rawvideo','pipe:1')
    rows,status=scene_times(raw,2)
    reader=SceneReader(SimpleNamespace(ffmpeg=ffmpeg),None)
    frame=await reader.frame(source,rows[0]['time'],tmp_path,0,1600)
    assert frame.size==(320,240) and status['sampled_frames']==4
