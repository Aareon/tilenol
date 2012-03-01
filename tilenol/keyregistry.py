import re
import logging

from zorro.di import has_dependencies, dependency

from .xcb import Keysyms, Core


hotkey_re = re.compile('^<[^>]+>|.$')
log = logging.getLogger(__name__)


@has_dependencies
class KeyRegistry(object):

    keysyms = dependency(Keysyms, 'keysyms')
    core = dependency(Core, 'xcore')

    def __init__(self):
        self.keys = {}

    def parse_key(self, keystr):
        mod = 0
        if keystr[0] == '<':
            keystr = keystr[1:-1]
            if '-' in keystr:
                mstr, sym = keystr.split('-')
                if 'S' in mstr:
                    mod |= self.core.ModMask.Shift
                if 'C' in mstr:
                    mod |= self.core.ModMask.Control
                if 'W' in mstr:
                    mod |= getattr(self.core.ModMask, '4')
            else:
                sym = keystr
        else:
            if sym.lower() != sym:
                mod = self.core.ModMask.Shift
            sym = sym.lower()
        code = self.keysyms.name_to_code[sym]
        return mod, code

    def add_key(self, keystr, handler):
        m = hotkey_re.match(keystr)
        if not m:
            raise ValueError(keystr)
        modmask, keysym = self.parse_key(m.group(0))
        self.keys[modmask, keysym] = handler

    def init_modifiers(self):
        # TODO(tailhook) probably calculate them instead of hardcoding
        caps = self.core.ModMask.Lock  # caps lock
        num = getattr(self.core.ModMask, '2')  # mod2 is usually numlock
        mode = getattr(self.core.ModMask, '5')  # mod5 is usually mode_switch
        self.extra_modifiers = [0,
            caps,
            num,
            mode,
            caps|num,
            num|mode,
            caps|num|mode,
            ]
        self.modifiers_mask = ~(caps|num|mode)

    def register_keys(self, win):
        self.init_modifiers()
        for mod, key in self.keys:
            kcode = self.core.keysym_to_keycode[key]
            for extra in self.extra_modifiers:
                self.core.raw.GrabKey(
                    owner_events=False,
                    grab_window=win,
                    modifiers=mod|extra,
                    key=kcode,
                    keyboard_mode=self.core.GrabMode.Async,
                    pointer_mode=self.core.GrabMode.Async,
                    )

    def dispatch_event(self, event):
        try:
            kcode = self.core.keycode_to_keysym[event.detail]
            handler = self.keys[event.state & self.modifiers_mask, kcode]
        except KeyError:
            return False
        else:
            try:
                handler()
            except Exception as e:
                log.exception("Error handling keypress %r", event,
                    exc_info=(type(e), e, e.__traceback__))
