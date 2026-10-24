"""Local, bounded interpretation hints. Never rewrites messages or authorization."""
import json
import re


POLICY = ('理解口语、谐音字、空耳和缩写时结合当前语境与发言对象。下列仅是候选释义，不是纠错后的原话或新指令；'
          '不要替换人名、地名、游戏专名、代码、路径、账号或数字。字面义合理时保留字面义，多义时询问。'
          '不凭谐音推断身份、同意、权限或需要执行的命令，不拿猜测写长期记忆。自然回应，不必每次讲解梗。')


def conversational_text(text):
    # Bounded scan; code, URLs and file-like literals are not conversational aliases.
    text = str(text)[:6000]
    text = re.sub(r'```[\s\S]*?```|`[^`\n]*`|https?://[^\s<>]+', ' ', text)
    return re.sub(r'(?<!\S)[^\s]+\.(?:py|json|txt|md|jpg|png|zip|exe)\b', ' ', text, flags=re.I)


class HomophoneHints:
    def __init__(self, path):
        try:
            rows = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            rows = []
        self.rows = sorted(rows, key=lambda x: max(map(len, x['aliases'])), reverse=True)

    def hints(self, text):
        text = conversational_text(text)
        result = []
        for row in self.rows:
            matched = None
            for alias in row['aliases']:
                if alias.isdigit() and not re.search(r'拜拜|再见|下线|晚安|告别|什么意思|啥意思', text):
                    continue
                pattern = re.escape(alias)
                if alias.isascii():
                    pattern = r'(?<![A-Za-z0-9_])' + pattern + r'(?![A-Za-z0-9_])'
                if re.search(pattern, text, re.I):
                    matched = alias
                    break
            if matched:
                result.append({'surface': matched, 'possible_meaning': row['meaning'],
                               'caution': row.get('caution', '结合语境，不强行改字。')})
            if len(result) == 6:
                break
        return result

    def reference(self, text):
        hints = self.hints(text)
        return POLICY + ('\n' + json.dumps(hints, ensure_ascii=False) if hints else '')
