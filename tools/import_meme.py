"""Local operator utility; no model may import or approve its own images."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from astrbot_plugin_fish_capabilities.services.memes import CATEGORIES, CATEGORY_FOLDERS, image_signature


def main():
    parser = argparse.ArgumentParser(description='将已人工确认的表情导入分类目录；不会发送 QQ 消息')
    parser.add_argument('source', type=Path)
    parser.add_argument('--library', required=True, type=Path)
    parser.add_argument('--category', required=True, choices=sorted(CATEGORIES))
    parser.add_argument('--tags', default='')
    parser.add_argument('--description', default='',help='这张表情表达什么、适合什么场景')
    parser.add_argument('--approve', action='store_true', help='人工确认后显式批准；不加则不能发送')
    args = parser.parse_args()
    data = args.source.read_bytes()
    if args.source.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.gif', '.webp'} or not image_signature(data) or len(data) > 4_000_000:
        parser.error('仅支持不超过 4MB 的 PNG/JPEG/GIF/WebP；文件必须有对应图片标识。')
    digest = hashlib.sha256(data).hexdigest()
    args.library.mkdir(parents=True, exist_ok=True)
    manifest = args.library / 'manifest.json'
    rows = json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else []
    if any(row['sha256'] == digest for row in rows):
        parser.error('这张图已导入；编辑已有条目的分类即可。')
    if len(rows) >= 500: parser.error('表情库最多 500 张。')
    relative = CATEGORY_FOLDERS[args.category] + '/' + digest[:20] + args.source.suffix.lower()
    destination = args.library / relative
    destination.parent.mkdir(exist_ok=True)
    shutil.copyfile(args.source, destination)
    rows.append({'id': digest[:20], 'category': args.category, 'file': relative,
                 'description':args.description[:160],
                 'tags': [x.strip()[:40] for x in args.tags.split(',') if x.strip()][:8],
                 'approved': args.approve, 'sha256': digest})
    temporary = manifest.with_suffix('.tmp')
    temporary.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(manifest)
    print(json.dumps({'imported': relative, 'approved': args.approve}, ensure_ascii=False))


if __name__ == '__main__': main()
