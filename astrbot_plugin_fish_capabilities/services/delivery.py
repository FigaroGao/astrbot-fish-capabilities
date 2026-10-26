"""Small proactive message batches; no model call for segmentation."""
import re

def segments(text):
    text=str(text).strip()
    urls=re.findall(r'https://www\.bilibili\.com/video/BV[0-9A-Za-z]{10}',text)
    for url in urls:text=text.replace(url,'')
    text=text.strip()[:240]
    parts=[p.strip() for p in re.split(r'\n+|(?<=[。！？!?])\s*',text) if p.strip()]
    expanded=[]
    for part in parts:
        while len(part)>90:
            cut=max(part.rfind('，',25,76),part.rfind('；',25,76),part.rfind(' ',25,76))
            cut=cut+1 if cut>=25 else 75
            expanded.append(part[:cut]);part=part[cut:].strip()
        if part:expanded.append(part)
    out=[]
    for part in expanded:
        if out and len(out[-1])+len(part)<=75:out[-1]+=part
        else:out.append(part)
    if 2<=len(expanded)<=3 and sum(map(len,expanded))>30:out=expanded
    if len(out)>3:out=out[:2]+[''.join(out[2:])]
    if urls:
        if not out:out=['']
        out[-1]+='\n'+urls[0]
    return out or []


def dialog_segments(text,limit=120):
    """Keep all ordinary reply text; protect URLs and fenced code."""
    text=str(text)
    tokens=re.split(r'(```[\s\S]*?```|https?://[^\s<>]+)',text)
    result=[];pending=''
    def flush():
        nonlocal pending
        if pending.strip():result.append(pending.strip())
        pending=''
    for token in tokens:
        if not token:continue
        if token.startswith('```') or re.match(r'^https?://',token):
            flush();result.append(token);continue
        for paragraph in re.split(r'\n\s*\n',token):
            if not paragraph.strip():continue
            while len(paragraph)>limit:
                cut=max(paragraph.rfind(c,limit//2,limit) for c in ['。','！','？','；','，','\n',' '])
                cut=cut+1 if cut>=limit//2 else limit
                flush();result.append(paragraph[:cut].strip());paragraph=paragraph[cut:]
            if len(pending)+len(paragraph)>limit:flush()
            pending+=paragraph
            flush()
    flush()
    return [p for p in result if p.strip()]
