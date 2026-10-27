"""Owner-controlled per-group quiet window, including already queued segments."""
import functools
import json
import time


class GroupQuiet:
    def __init__(self, path, *, clock=time.time):
        self.path, self.clock = path, clock
        try:
            self.state = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.state = {}

    def set(self, scope, seconds):
        old = self.state.get(scope, {})
        self.state[scope] = {'until':self.clock()+seconds if seconds else 0,
                             'epoch':int(old.get('epoch',0))+1}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp=self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.state),encoding='utf-8');tmp.chmod(0o600);tmp.replace(self.path)

    def muted(self, scope):
        return self.state.get(scope,{}).get('until',0)>self.clock()

    def mark(self, event):
        if event.get_extra('fish_quiet_epoch') is None:
            event.set_extra('fish_quiet_epoch',self.state.get(event.unified_msg_origin,{}).get('epoch',0))

    def suppress(self, event):
        if event.is_private_chat() or event.get_extra('fish_quiet_ack'):
            return False
        scope=getattr(event,'unified_msg_origin','')
        epoch=event.get_extra('fish_quiet_epoch')
        return self.muted(scope) or (epoch is not None and epoch!=self.state.get(scope,{}).get('epoch',0))


def install_send_guard(event_class, quiet, before_send=None):
    original=event_class.send
    if getattr(original,'_fish_quiet_guard',False):raise RuntimeError('Quiet send guard already installed')
    @functools.wraps(original)
    async def send(event,*args,**kwargs):
        if quiet.suppress(event) or (before_send is not None and not await before_send(event)) or quiet.suppress(event):
            event.clear_result()
            event.stop_event()
            return
        return await original(event,*args,**kwargs)
    send._fish_quiet_guard=True
    event_class.send=send
    def uninstall():
        if event_class.send is send:event_class.send=original
    return uninstall
