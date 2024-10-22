#! python3
"""mwxlib framework.
"""
__version__ = "1.0.0"
__author__ = "Kazuya O'moto <komoto@jeol.co.jp>"

from contextlib import contextmanager
from functools import wraps, partial
from importlib import reload
import traceback
import builtins
import datetime
import textwrap
import time
import os
import re
import wx
from wx import aui
from wx import stc
from wx.py import dispatcher

from .utilus import funcall as _F
from .utilus import get_rootpath, ignore, warn
from .utilus import FSM, TreeList, apropos, typename, where, mro, pp


def deb(target=None, loop=True, locals=None, debrc=None, **kwargs):
    """Dive into the process.
    
    Args:
        target  : Object or module (default None).
                  If None, the target is set to `__main__`.
        loop    : If True, the app and the mainloop will be created.
        locals  : Additional context of the shell
        debrc   : file name of the session; defaults to None.
                  If None, no session will be created or saved.
        
        **kwargs: Nautilus ShellFrame arguments
        
            - introText         : introductory of the shell
            - startupScript     : startup script file (default None)
            - execStartupScript : True => Execute the startup script.
            - ensureClose       : True => EVT_CLOSE will close the window.
                                  False => EVT_CLOSE will hide the window.
    
    Note:
        This will execute the startup script $(PYTHONSTARTUP).
    """
    kwargs.setdefault("introText", f"mwx {__version__}\n")
    kwargs.setdefault("execStartupScript", True)
    kwargs.setdefault("ensureClose", True)

    app = wx.GetApp() or wx.App()
    frame = ShellFrame(None, target, session=debrc, **kwargs)
    frame.Show()
    frame.rootshell.SetFocus()
    if locals:
        frame.rootshell.locals.update(locals)
    if loop and not app.GetMainLoop():
        app.MainLoop()
    return frame


def postcall(f):
    """A decorator of wx.CallAfter.
    Wx posts the message that forces `f` to take place in the main thread.
    """
    @wraps(f)
    def _f(*v, **kw):
        wx.CallAfter(f, *v, **kw)
    return _f


@contextmanager
def save_focus_excursion():
    """Save window focus excursion."""
    wnd = wx.Window.FindFocus() # original focus
    try:
        yield wnd
    finally:
        if wnd and wnd.IsShownOnScreen():
            wnd.SetFocus() # restore focus


_speckeys = {
    wx.WXK_ALT                  : 'alt',
    wx.WXK_BACK                 : 'backspace',
    wx.WXK_CANCEL               : 'break',
    wx.WXK_CAPITAL              : 'caps_lock',
    wx.WXK_CONTROL              : 'ctrl',
    wx.WXK_DELETE               : 'delete',
    wx.WXK_DOWN                 : 'down',
    wx.WXK_END                  : 'end',
    wx.WXK_ESCAPE               : 'escape',
    wx.WXK_F1                   : 'f1',
    wx.WXK_F2                   : 'f2',
    wx.WXK_F3                   : 'f3',
    wx.WXK_F4                   : 'f4',
    wx.WXK_F5                   : 'f5',
    wx.WXK_F6                   : 'f6',
    wx.WXK_F7                   : 'f7',
    wx.WXK_F8                   : 'f8',
    wx.WXK_F9                   : 'f9',
    wx.WXK_F10                  : 'f10',
    wx.WXK_F11                  : 'f11',
    wx.WXK_F12                  : 'f12',
    wx.WXK_F13                  : 'f13',
    wx.WXK_F14                  : 'f14',
    wx.WXK_F15                  : 'f15',
    wx.WXK_F16                  : 'f16',
    wx.WXK_F17                  : 'f17',
    wx.WXK_F18                  : 'f18',
    wx.WXK_F19                  : 'f19',
    wx.WXK_F20                  : 'f20',
    wx.WXK_F21                  : 'f21',
    wx.WXK_F22                  : 'f22',
    wx.WXK_F23                  : 'f23',
    wx.WXK_F24                  : 'f24',
    wx.WXK_HOME                 : 'home',
    wx.WXK_INSERT               : 'insert',
    wx.WXK_LEFT                 : 'left',
    wx.WXK_NONE                 : 'none',
    wx.WXK_NUMLOCK              : 'num_lock',
    wx.WXK_NUMPAD_ADD           : '+',
    wx.WXK_NUMPAD_DECIMAL       : 'dec',
    wx.WXK_NUMPAD_DELETE        : 'delete',
    wx.WXK_NUMPAD_DIVIDE        : '/',
    wx.WXK_NUMPAD_DOWN          : 'down',
    wx.WXK_NUMPAD_END           : 'end',
    wx.WXK_NUMPAD_ENTER         : 'enter',
    wx.WXK_NUMPAD_HOME          : 'home',
    wx.WXK_NUMPAD_INSERT        : 'insert',
    wx.WXK_NUMPAD_LEFT          : 'left',
    wx.WXK_NUMPAD_MULTIPLY      : '*',
    wx.WXK_NUMPAD_PAGEDOWN      : 'pagedown',
    wx.WXK_NUMPAD_PAGEUP        : 'pageup',
    wx.WXK_NUMPAD_RIGHT         : 'right',
    wx.WXK_NUMPAD_SUBTRACT      : '-',
    wx.WXK_NUMPAD_UP            : 'up',
    wx.WXK_NUMPAD0              : '0',
    wx.WXK_NUMPAD1              : '1',
    wx.WXK_NUMPAD2              : '2',
    wx.WXK_NUMPAD3              : '3',
    wx.WXK_NUMPAD4              : '4',
    wx.WXK_NUMPAD5              : '5',
    wx.WXK_NUMPAD6              : '6',
    wx.WXK_NUMPAD7              : '7',
    wx.WXK_NUMPAD8              : '8',
    wx.WXK_NUMPAD9              : '9',
    wx.WXK_PAGEDOWN             : 'pagedown',
    wx.WXK_PAGEUP               : 'pageup',
    wx.WXK_PAUSE                : 'break',
    wx.WXK_RETURN               : 'enter',
    wx.WXK_RIGHT                : 'right',
    wx.WXK_SCROLL               : 'scroll_lock',
    wx.WXK_SHIFT                : 'shift',
    wx.WXK_SNAPSHOT             : 'snapshot',
    wx.WXK_SPACE                : 'space',
    wx.WXK_TAB                  : 'tab',
    wx.WXK_UP                   : 'up',
    wx.WXK_WINDOWS_LEFT         : 'Lwin',
    wx.WXK_WINDOWS_MENU         : 'appskey',
    wx.WXK_WINDOWS_RIGHT        : 'Rwin',
}

_speckeys_wxkmap = dict((v, k) for k, v in _speckeys.items())


def hotkey(evt):
    """Interpret evt.KeyCode as hotkey:str and overwrite evt.key.
    The modifiers are arranged in the same order as matplotlib as
    [LR]win + ctrl + alt(meta) + shift.
    """
    key = evt.GetKeyCode()
    mod = ""
    for k, v in ((wx.WXK_WINDOWS_LEFT, 'Lwin-'),
                 (wx.WXK_WINDOWS_RIGHT, 'Rwin-'),
                 ## (wx.WXK_CONTROL, 'C-'),
                 ## (wx.WXK_ALT,     'M-'),
                 ## (wx.WXK_SHIFT,   'S-')
                 ):
        if key != k and wx.GetKeyState(k): # Note: lazy-eval state
            mod += v
    
    if key != wx.WXK_CONTROL and evt.controlDown: mod += "C-"
    if key != wx.WXK_ALT     and evt.altDown:     mod += "M-"
    if key != wx.WXK_SHIFT   and evt.shiftDown:   mod += "S-"
    
    key = _speckeys.get(key) or chr(key).lower()
    evt.key = mod + key
    return evt.key


def regulate_key(key):
    return (key.replace("ctrl-",  "C-") # modifier keys abbreviation
               .replace("alt-",   "M-")
               .replace("shift-", "S-")
               .replace("M-C-", "C-M-") # modifier key regulation C-M-S-
               .replace("S-M-", "M-S-")
               .replace("S-C-", "C-S-"))


class KeyCtrlInterfaceMixin:
    """Keymap interface mixin.
    
    keymap::
    
        global-map  : 0 (default)
        ctl-x-map   : 'C-x'
        spec-map    : 'C-c'
        esc-map     : 'escape'
    """
    message = print # override this in subclass
    
    @postcall
    def post_message(self, *args, **kwargs):
        return self.message(*args, **kwargs)
    
    @staticmethod
    def getKeyState(key):
        """Returns state of speckey (cf. wx.GetKeyState)."""
        try:
            return wx.GetKeyState(_speckeys_wxkmap[key])
        except KeyError:
            pass
    
    @staticmethod
    def setKeyState(key, state):
        """Makes you feel like having pressed/released speckey."""
        vk = wx.UIActionSimulator()
        if state:
            vk.KeyDown(_speckeys_wxkmap[key])
        else:
            vk.KeyUp(_speckeys_wxkmap[key])
    
    def make_keymap(self, keymap):
        """Make a basis of extension map in the handler.
        """
        assert isinstance(keymap, str)
        
        def _Pass(evt):
            self.message("{} {}".format(keymap, evt.key))
        _Pass.__name__ = str('pass')
        
        state = self.handler.default_state
        event = keymap + ' pressed'
        
        assert state is not None, "Don't make keymap for None:state"
        
        self.handler.update({ # DNA<KeyCtrlInterfaceMixin>
            state : {
                          event : [ keymap, self.pre_command_hook ],
            },
            keymap : {
                         'quit' : [ state, ],
                    '* pressed' : [ state, self.post_command_hook ],
                 '*alt pressed' : [ keymap, _Pass ],
                '*ctrl pressed' : [ keymap, _Pass ],
               '*shift pressed' : [ keymap, _Pass ],
             '*[LR]win pressed' : [ keymap, _Pass ],
            },
        })
    
    def pre_command_hook(self, evt):
        """Called when entering extension mode (internal use only)."""
        ## Check text selection for [C-c/C-x].
        wnd = wx.Window.FindFocus()
        if isinstance(wnd, wx.TextEntry) and wnd.StringSelection\
        or isinstance(wnd, stc.StyledTextCtrl) and wnd.SelectedText:
            ## or any other of pre-selection-p?
            self.handler('quit', evt)
        else:
            self.message(evt.key + '-')
        evt.Skip()
    
    def post_command_hook(self, evt):
        """Called when exiting extension mode (internal use only)."""
        keymap = self.handler.previous_state
        if keymap:
            self.message("{} {}".format(keymap, evt.key))
        else:
            self.message(evt.key)
        evt.Skip()
    
    def define_key(self, keymap, action=None, *args, **kwargs):
        """Define [map key (pressed)] action.
        
        If no action, it invalidates the key and returns @decor(binder).
        The key must be in C-M-S order (ctrl + alt(meta) + shift).
        
        Note:
            kwargs `doc` and `alias` are reserved as kw-only-args.
        """
        assert isinstance(keymap, str)
        assert callable(action) or action is None
        
        state = self.handler.default_state
        map, sep, key = regulate_key(keymap).rpartition(' ')
        if not map:
            map = state
        elif map == '*':
            map = state = None
        key += ' pressed'
        
        if map not in self.handler:
            warn(f"New map to define_key {keymap!r} in {self}.")
            self.make_keymap(map) # make new keymap
        
        transaction = self.handler[map].get(key, [state])
        if len(transaction) > 1:
            warn(f"Duplicate define_key {keymap!r} in {self}.")
        
        if action is None:
            self.handler[map].pop(key, None) # cf. undefine_key
            return lambda f: self.define_key(keymap, f, *args, **kwargs)
        
        F = _F(action, *args, **kwargs)
        @wraps(F)
        def f(*v, **kw):
            self.message(f.__name__)
            return F(*v, **kw)
        
        if map != state:
            self.handler.update({map: {key: [state, self.post_command_hook, f]}})
        else:
            self.handler.update({map: {key: [state, f]}})
        return action
    
    @ignore(UserWarning)
    def undefine_key(self, keymap):
        """Delete [map key (pressed)] context."""
        self.define_key(keymap, None)


class CtrlInterface(KeyCtrlInterfaceMixin):
    """Mouse/Key event interface mixin.
    """
    handler = property(lambda self: self.__handler)
    
    def __init__(self):
        self.__key = ''
        self.__button = ''
        self.__isDragging = False
        self.__handler = FSM({ # DNA<CtrlInterface>
                None : {
                },
                0 : {
                },
            },
        )
        
        _M = self._mouse_handler
        _N = self._normal_handler
        
        def activate(evt):
            self.handler('focus_set', evt)
            evt.Skip()
        self.Bind(wx.EVT_SET_FOCUS, activate)
        
        def inactivate(evt):
            self.__key = ''
            self.__button = ''
            self.__isDragging = False
            self.handler('focus_kill', evt)
            evt.Skip()
        self.Bind(wx.EVT_KILL_FOCUS, inactivate)
        
        self.Bind(wx.EVT_CHAR_HOOK, self.on_hotkey_press)
        self.Bind(wx.EVT_KEY_DOWN, self.on_hotkey_down)
        self.Bind(wx.EVT_KEY_UP, self.on_hotkey_up)
        
        self.Bind(wx.EVT_MOUSEWHEEL, self.on_mousewheel)
        
        self.Bind(wx.EVT_MOTION, self.on_motion)
        
        self.Bind(wx.EVT_LEFT_UP, lambda v: _M('Lbutton released', v))
        self.Bind(wx.EVT_RIGHT_UP, lambda v: _M('Rbutton released', v))
        self.Bind(wx.EVT_MIDDLE_UP, lambda v: _M('Mbutton released', v))
        self.Bind(wx.EVT_LEFT_DOWN, lambda v: _M('Lbutton pressed', v))
        self.Bind(wx.EVT_RIGHT_DOWN, lambda v: _M('Rbutton pressed', v))
        self.Bind(wx.EVT_MIDDLE_DOWN, lambda v: _M('Mbutton pressed', v))
        self.Bind(wx.EVT_LEFT_DCLICK, lambda v: _M('Lbutton dblclick', v))
        self.Bind(wx.EVT_RIGHT_DCLICK, lambda v: _M('Rbutton dblclick', v))
        self.Bind(wx.EVT_MIDDLE_DCLICK, lambda v: _M('Mbutton dblclick', v))
        
        self.Bind(wx.EVT_MOUSE_AUX1_UP, lambda v: _M('Xbutton1 released', v))
        self.Bind(wx.EVT_MOUSE_AUX2_UP, lambda v: _M('Xbutton2 released', v))
        self.Bind(wx.EVT_MOUSE_AUX1_DOWN, lambda v: _M('Xbutton1 pressed', v))
        self.Bind(wx.EVT_MOUSE_AUX2_DOWN, lambda v: _M('Xbutton2 pressed', v))
        self.Bind(wx.EVT_MOUSE_AUX1_DCLICK, lambda v: _M('Xbutton1 dblclick', v))
        self.Bind(wx.EVT_MOUSE_AUX2_DCLICK, lambda v: _M('Xbutton2 dblclick', v))
        
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, lambda v: _N('capture_lost', v))
        self.Bind(wx.EVT_MOUSE_CAPTURE_CHANGED, lambda v: _N('capture_changed', v))
    
    def on_hotkey_press(self, evt): #<wx._core.KeyEvent>
        """Called when a key is pressed."""
        if evt.EventObject is not self:
            evt.Skip()
            return
        key = hotkey(evt)
        self.__key = regulate_key(key + '-')
        if self.handler('{} pressed'.format(key), evt) is None:
            evt.Skip()
    
    def on_hotkey_down(self, evt): #<wx._core.KeyEvent>
        """Called when a key is pressed while dragging.
        Specifically called when the mouse is being captured.
        """
        if self.__isDragging:
            self.on_hotkey_press(evt)
        else:
            evt.Skip()
    
    def on_hotkey_up(self, evt): #<wx._core.KeyEvent>
        """Called when a key is released."""
        key = hotkey(evt)
        self.__key = ''
        if self.handler('{} released'.format(key), evt) is None:
            evt.Skip()
    
    def on_mousewheel(self, evt): #<wx._core.MouseEvent>
        """Called on mouse wheel events.
        Trigger event: 'key+wheel[up|down|right|left] pressed'
        """
        if evt.GetWheelAxis():
            p = 'right' if evt.WheelRotation > 0 else 'left'
        else:
            p = 'up' if evt.WheelRotation > 0 else 'down'
        evt.key = self.__key + "wheel{}".format(p)
        if self.handler('{} pressed'.format(evt.key), evt) is None:
            evt.Skip()
    
    def on_motion(self, evt): #<wx._core.MouseEvent>
        """Called on mouse motion events.
        Trigger event: 'key+[LMR]drag begin/motion/end'
        """
        if self.__button:
            kbtn = self.__key + self.__button
            if not self.__isDragging:
                self.__isDragging = True
                self.handler('{}drag begin'.format(kbtn), evt)
            else:
                self.handler('{}drag move'.format(kbtn), evt)
        else:
            self.handler('motion', evt)
        evt.Skip()
    
    def _mouse_handler(self, event, evt): #<wx._core.MouseEvent>
        """Called on mouse button events.
        Trigger event: 'key+[LMRX]button pressed/released/dblclick'
        """
        event = self.__key + event
        evt.key, action = event.split()
        if action == 'released' and self.__button:
            if self.__isDragging:
                self.__isDragging = False
                kbtn = self.__key + self.__button
                self.handler('{}drag end'.format(kbtn), evt)
        
        k = evt.GetButton() #{1:L, 2:M, 3:R, 4:X1, 5:X2}
        if action == 'pressed' and k in (1,2,3):
            self.__button = 'LMR'[k-1]
        else:
            self.__button = ''
        if self.handler(event, evt) is None:
            evt.Skip()
        try:
            self.SetFocusIgnoringChildren() # let the panel accept keys
        except AttributeError:
            pass
    
    def _normal_handler(self, event, evt): #<wx._core.Event>
        if self.handler(event, evt) is None:
            evt.Skip()


## --------------------------------
## wx Framework and Designer
## --------------------------------

def ID_(id):
    ## Free ID - どこで使っているか検索できるように
    ## do not use [ID_LOWEST(4999):ID_HIGHEST(5999)]
    id += wx.ID_HIGHEST
    assert not wx.ID_LOWEST <= id <= wx.ID_HIGHEST
    return id


def pack(self, items, orient=wx.HORIZONTAL, style=None, label=None):
    """Do layout.
    
    Examples::
    
        self.SetSizer(
            pack(self, (
                (label, 0, wx.ALIGN_CENTER | wx.LEFT, 4),
                ( ctrl, 1, wx.ALIGN_CENTER | wx.LEFT, 4),
            ))
        )
    
    Args:
        items   : wx objects (with some packing parameters)
        
            - (obj, 1) -> sized with ratio 1 (parallel to `orient`)
            - (obj, 1, wx.EXPAND) -> expanded with ratio 1 (perpendicular to `orient`)
            - (obj, 0, wx.ALIGN_CENTER | wx.LEFT, 4) -> center with 4 pixel at wx.LEFT
            - ((-1,-1), 1, wx.EXPAND) -> stretched space
            - (-1,-1) -> padding space
            - None -> phantom
        
        orient  : HORIZONTAL or VERTICAL
        label   : StaticBox label
        style   : Sizer option (proportion, flag, border)
        
            - flag-expansion -> EXPAND, SHAPED
            - flag-border -> TOP, BOTTOM, LEFT, RIGHT, ALL
            - flag-align -> ALIGN_CENTER, ALIGN_LEFT, ALIGN_TOP, ALIGN_RIGHT, ALIGN_BOTTOM,
                            ALIGN_CENTER_VERTICAL, ALIGN_CENTER_HORIZONTAL
    """
    if style is None:
        style = (0, wx.EXPAND | wx.ALL, 0) # DEFALT_STYLE (prop, flag, border)
    if label is None:
        sizer = wx.BoxSizer(orient)
    else:
        box = wx.StaticBox(self, -1, label)
        sizer = wx.StaticBoxSizer(box, orient)
    for item in items:
        if not isinstance(item, (wx.Object, list, tuple, type(None))):
            warn(f"pack items must be a wx.Object, tuple or None, not {type(item)}")
        if item is None:
            item = (0, 0), 0, 0, 0 # null space
        elif not item:
            item = (0, 0) # padding space
        try:
            try:
                sizer.Add(item, *style)
            except TypeError:
                sizer.Add(*item) # using item-specific style
        except TypeError as e:
            traceback.print_exc()
            bmp = wx.StaticBitmap(self, bitmap=wx.ArtProvider.GetBitmap(wx.ART_ERROR))
            bmp.SetToolTip(str(e))
            sizer.Add(bmp, 0, wx.EXPAND | wx.ALL, 0)
            wx.Bell()
    return sizer


class Menu(wx.Menu):
    """Construct the menu.
    
    Args:
        menulist : list of MenuItem args
        owner    : window object to bind handlers
    
    (id, text, hint, style, icon,  ... Menu.Append arguments
       action, updater, highlight) ... Menu Event handlers
    
        - style -> menu style (ITEM_NORMAL, ITEM_CHECK, ITEM_RADIO)
        - icon -> menu icon (bitmap)
        - action -> EVT_MENU handler
        - updater -> EVT_UPDATE_UI handler
        - highlight -> EVT_MENU_HIGHLIGHT handler
    """
    def __init__(self, owner, menulist):
        wx.Menu.__init__(self)
        self.owner = owner
        
        for item in menulist:
            if not item:
                self.AppendSeparator()
                continue
            id = item[0]
            handlers = [x for x in item if callable(x)]
            icons =  [x for x in item if isinstance(x, wx.Bitmap)]
            argv = [x for x in item if x not in handlers and x not in icons]
            if isinstance(id, int):
                menu_item = wx.MenuItem(self, *argv) # <- menu_item.Id
                if icons:
                    menu_item.SetBitmaps(*icons)
                self.Append(menu_item)
                try:
                    self.owner.Bind(wx.EVT_MENU, handlers[0], menu_item)
                    self.owner.Bind(wx.EVT_UPDATE_UI, handlers[1], menu_item)
                    self.owner.Bind(wx.EVT_MENU_HIGHLIGHT, handlers[2], menu_item)
                except IndexError:
                    pass
            else:
                subitems = list(argv.pop()) # extract the last element as submenu
                submenu = Menu(owner, subitems)
                submenu_item = wx.MenuItem(self, wx.ID_ANY, *argv)
                submenu_item.SetSubMenu(submenu)
                if icons:
                    submenu_item.SetBitmaps(*icons)
                self.Append(submenu_item)
                self.Enable(submenu_item.Id, len(subitems)) # Disable an empty menu.
                submenu.Id = submenu_item.Id # <- ID_ANY (dummy to check empty sbumenu)
    
    def _unbind(self):
        for item in self.MenuItems:
            if item.Id != wx.ID_SEPARATOR:
                self.owner.Unbind(wx.EVT_MENU, item)
                self.owner.Unbind(wx.EVT_UPDATE_UI, item)
                self.owner.Unbind(wx.EVT_MENU_HIGHLIGHT, item)
            if item.SubMenu:
                item.SubMenu._unbind()
    
    def Destroy(self):
        try:
            self._unbind()
        finally:
            return wx.Menu.Destroy(self)
    
    @staticmethod
    def Popup(parent, menulist, *args, **kwargs):
        menu = Menu(parent, menulist)
        parent.PopupMenu(menu, *args, **kwargs)
        menu.Destroy()


class MenuBar(wx.MenuBar, TreeList):
    """Construct the menubar.
    
    menu <TreeList>::
    
        root
         ├ [key, [item,
         │        item,...]],
         ├ [key, [item,
         │        submenu => [key, [item,
         ：        ...               item,...]],
    """
    def __init__(self, *args, **kwargs):
        wx.MenuBar.__init__(self, *args, **kwargs)
        TreeList.__init__(self)
    
    def getmenu(self, key, root=None):
        if '/' in key:
            a, b = key.split('/', 1)
            branch = self.getmenu(a, root)
            return self.getmenu(b, branch)
        if root is None:
            return next((menu for menu, label in self.Menus if menu.Title == key), None)
        return next((item.SubMenu for item in root.MenuItems if item.ItemLabel == key), None)
    
    def update(self, key):
        """Update items of the menu that has specified key:root/branch.
        Call when the menulist is changed.
        """
        if not self.Parent:
            warn(f"No parents bound to {self}.")
            return
        
        menu = self.getmenu(key)
        if not menu:
            self.reset()
            return
        
        menu._unbind()
        for item in menu.MenuItems: # delete all items
            menu.Delete(item)
        
        menu2 = Menu(self.Parent, self[key]) # new menu2 to swap menu
        for item in menu2.MenuItems:
            menu.Append(menu2.Remove(item)) # 重複しないようにいったん切り離して追加する
        
        if hasattr(menu, 'Id'):
            self.Enable(menu.Id, menu.MenuItemCount > 0) # Disable empty submenu.
        
        for j, (key, values) in enumerate(self):
            self.EnableTop(j, bool(values)) # Disable empty main menu.
    
    def reset(self):
        """Recreates the menubar if the Parent was attached.
        Call when the menulist is changed.
        """
        if not self.Parent:
            warn(f"No parents bound to {self}.")
            return
        
        for j in range(self.GetMenuCount()): # remove and del all top-level menu
            menu = self.Remove(0)
            menu.Destroy()
        
        for j, (key, values) in enumerate(self):
            menu = Menu(self.Parent, values)
            self.Append(menu, key)
            self.EnableTop(j, bool(values)) # Disable empty main menu.


class StatusBar(wx.StatusBar):
    """Construct the statusbar with read/write interfaces.
    
    Attributes:
        field   : list of field widths
        pane    : index of status text field
    """
    def __init__(self, *args, **kwargs):
        wx.StatusBar.__init__(self, *args, **kwargs)
    
    def __call__(self, *args, **kwargs):
        text = ' '.join(str(v) for v in args)
        if self:
            return self.write(text, **kwargs)
    
    def resize(self, field):
        self.SetFieldsCount(len(field))
        self.SetStatusWidths(list(field)) # oldver requires list type
    
    def write(self, text, pane=0):
        if text and text[0] == '\b':
            text = self.read(pane) + text[1:]
        self.SetStatusText(text, pane % self.GetFieldsCount())
        return text
    
    def read(self, pane=0):
        return self.GetStatusText(pane % self.GetFieldsCount())


class Frame(wx.Frame, KeyCtrlInterfaceMixin):
    """Frame extension class.
    
    Attributes:
        menubar     : MenuBar
        statusbar   : StatusBar
        shellframe  : mini-frame of the shell
    """
    handler = property(lambda self: self.__handler)
    
    message = property(lambda self: self.statusbar)
    
    def post_command_hook(self, evt):
        ## (override) Don't skip events as a TopLevelWindow.
        pass
    post_command_hook.__name__ = str('noskip')
    
    def __init__(self, *args, **kwargs):
        wx.Frame.__init__(self, *args, **kwargs)
        
        self.shellframe = ShellFrame(None, target=self, session='')
        
        self.menubar = MenuBar()
        self.menubar["File"] = [
            (ID_(1), "&Shell\tF12", "Shell for inspection", wx.ITEM_CHECK,
                lambda v: (self.shellframe.Show(),
                           self.shellframe.current_shell.SetFocus()),
                lambda v: v.Check(self.shellframe.IsShown())),
            (),
            (wx.ID_EXIT, "E&xit\tCtrl-w", "Exit the program",
                lambda v: self.Close()),
                
            (wx.ID_ABOUT, "&About\tF1", "About this software",
                lambda v: self.About()),
        ]
        self.SetMenuBar(self.menubar)
        self.menubar.reset()
        
        self.statusbar = StatusBar(self)
        self.statusbar.resize((-1,78))
        self.SetStatusBar(self.statusbar)
        
        self.timer = wx.Timer(self)
        self.timer.Start(1000)
        
        def on_timer(evt):
            self.message(time.strftime('%m/%d %H:%M'), pane=-1)
        self.Bind(wx.EVT_TIMER, on_timer)
        
        ## AcceleratorTable mimic
        def hook_char(evt):
            """Called when key down."""
            if isinstance(evt.EventObject, wx.TextEntry): # prior to handler
                evt.Skip()
            else:
                if self.handler('{} pressed'.format(hotkey(evt)), evt) is None:
                    evt.Skip()
        self.Bind(wx.EVT_CHAR_HOOK, hook_char)
        
        self.__handler = FSM({ # DNA<Frame>
                None : {
                },
                0 : {
                },
            },
        )
        self.make_keymap('C-x')
    
    def About(self):
        wx.MessageBox(__import__("__main__").__doc__ or "no information",
                      "About this software")
    
    def Destroy(self):
        try:
            self.timer.Stop()
            self.shellframe.Destroy() # shellframe is not my child
        finally:
            return wx.Frame.Destroy(self)


class MiniFrame(wx.MiniFrame, KeyCtrlInterfaceMixin):
    """MiniFrame extension class.
    
    Attributes:
        menubar     : MenuBar
        statusbar   : StatusBar (not shown by default)
    """
    handler = property(lambda self: self.__handler)
    
    message = property(lambda self: self.statusbar)
    
    def post_command_hook(self, evt):
        ## (override) Don't skip events as a TopLevelWindow.
        pass
    post_command_hook.__name__ = str('noskip')
    
    def __init__(self, *args, **kwargs):
        wx.MiniFrame.__init__(self, *args, **kwargs)
        
        ## To disable, self.SetMenuBar(None)
        self.menubar = MenuBar()
        self.SetMenuBar(self.menubar)
        
        self.statusbar = StatusBar(self)
        self.statusbar.Show(0)
        self.SetStatusBar(self.statusbar)
        
        ## AcceleratorTable mimic
        def hook_char(evt):
            """Called when key down."""
            if isinstance(evt.EventObject, wx.TextEntry): # prior to handler
                evt.Skip()
            else:
                if self.handler('{} pressed'.format(hotkey(evt)), evt) is None:
                    evt.Skip()
        self.Bind(wx.EVT_CHAR_HOOK, hook_char)
        
        ## To default close >>> self.Unbind(wx.EVT_CLOSE)
        self.Bind(wx.EVT_CLOSE, lambda v: self.Show(0))
        
        self.__handler = FSM({ # DNA<MiniFrame>
                None : {
                },
                0 : {
                },
            },
        )
        self.make_keymap('C-x')
    
    def Destroy(self):
        return wx.MiniFrame.Destroy(self)


class AuiNotebook(aui.AuiNotebook):
    """AuiNotebook extension class.
    """
    def __init__(self, *args, name=None, **kwargs):
        kwargs.setdefault('style',
            (aui.AUI_NB_DEFAULT_STYLE | aui.AUI_NB_BOTTOM)
            ^ aui.AUI_NB_CLOSE_ON_ACTIVE_TAB
            ^ aui.AUI_NB_MIDDLE_CLICK_CLOSE
        )
        aui.AuiNotebook.__init__(self, *args, **kwargs)
        
        self._mgr = self.EventHandler
        if name:
            self.Name = name
        
        def tab_menu(evt):
            tabs = evt.EventObject #<AuiTabCtrl>
            page = tabs.Pages[evt.Selection] # GetPage for split notebook.
            try:
                Menu.Popup(self, page.window.menu)
            except AttributeError:
                pass
        self.Bind(aui.EVT_AUINOTEBOOK_TAB_RIGHT_DOWN, tab_menu)
    
    @property
    def all_pages(self):
        """Returns all window pages."""
        return [self.GetPage(i) for i in range(self.PageCount)]
    
    @property
    def all_tabs(self):
        """Returns all AuiTabCtrl objects."""
        return [x for x in self.Children if isinstance(x, aui.AuiTabCtrl)]
    
    @property
    def all_panes(self):
        """Returns all AuiPaneInfo excluding `dummy` one."""
        return list(self._mgr.AllPanes)[1:]
    
    def get_pages(self, type=None):
        """Yields pages of the specified window type."""
        for win in self.all_pages:
            if type is None or isinstance(win, type):
                yield win
    
    def swap_page(self, win):
        """Replace the page with the specified page w/o focusing."""
        j = self.GetPageIndex(win)
        if j != -1:
            wnd = wx.Window.FindFocus() # original focus
            org = self.CurrentPage
            if j != self.Selection:
                self.Selection = j      # the focus moves if shown
            self.CurrentPage.SetFocus() # reset focus
            if wnd and wnd is not org:  # restore focus other window
                wnd.SetFocus()
    
    def get_caption(self, win):
        """Get caption of tab/page for specifiend window."""
        tab, page = self.find_tab(win)
        return page.caption
    
    def set_caption(self, win, caption):
        """Set caption of tab/page for specifiend window.
        Returns True if the caption has changed.
        """
        tab, page = self.find_tab(win)
        if page.caption != caption:
            page.caption = caption
            tab.Refresh()
            return True
    
    def find_tab(self, win):
        """Returns AuiTabCtrl and AuiNotebookPage for the window.
        
        cf. aui.AuiNotebook.FindTab -> bool, tab, idx
        Note:
            Argument `win` can also be page.window.Name (not page.caption).
        """
        for tabs in self.all_tabs: #<aui.AuiTabCtrl>
            for page in tabs.Pages: #<aui.AuiNotebookPage>
                ## if page.window is win or page.caption == win:
                if page.window is win or page.window.Name == win:
                    return tabs, page
    
    def move_tab(self, win, tabs):
        """Move the window page to the specified tabs."""
        try:
            tc1, nb1 = self.find_tab(win)
            win = nb1.window
        except Exception: # object not found
            return
        page = wx.aui.AuiNotebookPage(nb1) # copy-ctor
        tc1.RemovePage(win)     # Accessing nb1 will crash at this point.
        tabs.AddPage(win, page) # Add a page with the copied info.
        if tc1.PageCount == 0:
            ## Delete an empty tab and the corresponding pane.
            j = self.all_tabs.index(tc1)
            pane = self.all_panes[j]
            tc1.Destroy()
            self._mgr.DetachPane(pane.window)
        self._mgr.Update()
    
    ## Methods to save / load the perspectives.
    ## *** Inspired by wx.lib.agw.aui.AuiNotebook ***
    
    def savePerspective(self):
        """Saves the entire user interface layout into an encoded string,
        which can then be stored by the application.
        
        Note:
            Perspectives are saved according to page.window.Name.
            User should give it (not page.caption) a unique name.
        """
        for j, pane in enumerate(self.all_panes):
            pane.name = f"pane{j+1}"
        spec = ""
        for j, tabs in enumerate(self.all_tabs):
            k = next(k for k, page in enumerate(tabs.Pages)
                                   if page.window.Shown) # get active window
            ## names = [page.caption for page in tabs.Pages]
            names = [page.window.Name for page in tabs.Pages]
            spec += f"pane{j+1}={names};{k}|"
        return spec + '@' + self._mgr.SavePerspective()
    
    def loadPerspective(self, spec):
        """Loads a saved perspective.
        
        Note:
            Perspectives are loaded after the session is resumed.
            At that point, some user-cusotm pages may be missing.
        """
        tabs, frames = spec.split('@')
        tabinfo = re.findall(r"pane\w+?=(.*?);(.*?)\|", tabs)
        try:
            self.Parent.Freeze()
            ## Collapse all tabs to main tabctrl
            maintab = self.all_tabs[0]
            for win in self.all_pages:
                self.move_tab(win, maintab)
            
            ## Create a new tab using Split method.
            ## Note: The normal way of creating panes with `_mgr` crashes.
            
            all_names = [win.Name for win in self.all_pages]
            for names, k in tabinfo[1:]:
                names, k = eval(names), int(k)
                i = all_names.index(names[0]) # Assuming 0:tab is included.
                self.Split(i, wx.LEFT)
                newtab = self.all_tabs[-1]
                for name in names[1:]:
                    self.move_tab(name, newtab)
                self.Selection = all_names.index(names[k]) # new tabs active window
            else:
                names, k = tabinfo[0]
                names, k = eval(names), int(k)
                self.Selection = all_names.index(names[k]) # main tabs active window
            
            for j, pane in enumerate(self.all_panes):
                pane.name = f"pane{j+1}"
            self._mgr.LoadPerspective(frames)
            self._mgr.Update()
        except Exception as e:
            print("- Failed to load perspective.", e)
        finally:
            self.Parent.Thaw()


class FileDropLoader(wx.DropTarget):
    """DnD loader for files and URL text.
    """
    def __init__(self, target):
        wx.DropTarget.__init__(self)
        
        self.target = target
        self.textdo = wx.TextDataObject()
        self.filedo = wx.FileDataObject()
        self.DataObject = wx.DataObjectComposite()
        self.DataObject.Add(self.textdo)
        self.DataObject.Add(self.filedo, True)
    
    def OnData(self, x, y, result):
        editor = self.target.current_editor
        self.GetData()
        if self.textdo.TextLength > 1:
            f = self.textdo.Text.strip()
            res = editor.load_file(f)
            if res:
                editor.buffer.SetFocus()
                result = wx.DragCopy
            elif res is None:
                editor.post_message("Load canceled.")
                result = wx.DragCancel
            else:
                editor.post_message(f"Loading {f!r} failed.")
                result = wx.DragNone
            self.textdo.Text = ''
        else:
            for f in self.filedo.Filenames:
                if editor.load_file(f):
                    editor.buffer.SetFocus()
                    editor.post_message(f"Loaded {f!r} successfully.")
            self.filedo.SetData(wx.DF_FILENAME, None)
        return result


class ShellFrame(MiniFrame):
    """MiniFrame of the Shell.
    
    Args:
        target  : target object of the rootshell.
                  If None, it will be __main__.
        session : file name of the session; defaults to None.
                  If None, no session will be created or saved.
        ensureClose : flag for the shell standalone.
                      If True, EVT_CLOSE will close the window.
                      Otherwise the window will be only hidden.
        **kwargs    : Nautilus arguments
    
    Attributes:
        console     : Notebook of shells
        ghost       : Notebook of editors/buffers
        watcher     : Notebook of global/locals watcher
        Scratch     : Book of scratch (tooltip)
        Help        : Book of help
        Log         : Book of logging
        monitor     : wxmon.EventMonitor object
        inspector   : wxwit.Inspector object
        debugger    : wxpdb.Debugger object
        ginfo/linfo : globals/locals list
    
    Built-in utility::
    
        @p          : Synonym of print.
        @pp         : Synonym of pprint.
        @mro        : Display mro list and filename:lineno.
        @where      : Display filename:lineno.
        @info       : Short info.
        @help       : Full description.
        @load       : Load a file in Log.
        @dive       : Clone the shell with new target.
        @debug      : Open pdb debugger or event monitor.
        @watch      : Watch for events using event monitor.
        @timeit     : Measure CPU time (per one execution).
        @profile    : Profile a single function call.
        @highlight  : Highlight the widget.
        @filling    : Inspection using ``wx.lib.filling.Filling``.
    """
    rootshell = property(lambda self: self.__shell) #: the root shell
    
    def __init__(self, parent, target=None, session=None, ensureClose=False, **kwargs):
        MiniFrame.__init__(self, parent, size=(1280,720), style=wx.DEFAULT_FRAME_STYLE)
        
        self.statusbar.resize((-1,120))
        self.statusbar.Show(1)
        
        self.__standalone = bool(ensureClose)
        
        self.Init()
        
        from .nutshell import Nautilus, EditorBook
        from .bookshelf import EditorTreeCtrl
        
        self.__shell = Nautilus(self,
                                target or __import__("__main__"),
                                style=wx.CLIP_CHILDREN|wx.BORDER_NONE,
                                **kwargs)
        
        self.Scratch = EditorBook(self, name="Scratch")
        self.Log = EditorBook(self, name="Log")
        self.Help = EditorBook(self, name="Help")
        
        self.Bookshelf = EditorTreeCtrl(self, name="Bookshelf",
                                        style=wx.TR_DEFAULT_STYLE|wx.TR_HIDE_ROOT)
        
        from .wxpdb import Debugger
        from .wxwit import Inspector
        from .wxmon import EventMonitor
        from .wxwil import LocalsWatcher
        from .controls import Icon, Indicator
        
        self.debugger = Debugger(self,
                                 stdin=self.__shell.interp.stdin,
                                 stdout=self.__shell.interp.stdout,
                                 skip=[Debugger.__module__, # Don't enter debugger
                                       EventMonitor.__module__, # Don't enter event-hook
                                       FSM.__module__,
                                       'wx.core', 'wx.lib.eventwatcher',
                                       'fnmatch', 'warnings', 'bdb', 'pdb', 'contextlib',
                                       ],
                                 )
        self.inspector = Inspector(self, name="Inspector")
        self.monitor = EventMonitor(self, name="Monitor")
        self.ginfo = LocalsWatcher(self, name="globals")
        self.linfo = LocalsWatcher(self, name="locals")
        
        self.console = AuiNotebook(self, size=(600,400), name='console')
        self.console.AddPage(self.__shell, "root", bitmap=Icon('core'))
        self.console.TabCtrlHeight = 0
        ## self.console.Name = "console"
        
        ## self.console.Bind(aui.EVT_AUINOTEBOOK_BUTTON, self.OnConsoleCloseBtn)
        self.console.Bind(aui.EVT_AUINOTEBOOK_PAGE_CLOSE, self.OnConsolePageClose)
        self.console.Bind(aui.EVT_AUINOTEBOOK_PAGE_CHANGED, self.OnConsolePageChanged)
        
        self.ghost = AuiNotebook(self, size=(600,400), name="ghost")
        self.ghost.AddPage(self.Scratch, "Scratch", bitmap=Icon('ghost'))
        self.ghost.AddPage(self.Log, "Log")
        self.ghost.AddPage(self.Help, "Help")
        
        self.ghost.AddPage(self.Bookshelf, "Bookshelf", bitmap=Icon('book'))
        
        self.ghost.SetDropTarget(FileDropLoader(self))
        
        self.watcher = AuiNotebook(self, size=(600,400), name="watcher")
        self.watcher.AddPage(self.ginfo, "globals")
        self.watcher.AddPage(self.linfo, "locals")
        self.watcher.AddPage(self.monitor, "Monitor", bitmap=Icon('tv'))
        self.watcher.AddPage(self.inspector, "Inspector", bitmap=Icon('inspect'))
        
        self.watcher.Bind(wx.EVT_SHOW, self.OnGhostShow)
        
        self._mgr = aui.AuiManager()
        self._mgr.SetManagedWindow(self)
        self._mgr.SetDockSizeConstraint(1, 1)
        
        self._mgr.AddPane(self.console,
                          aui.AuiPaneInfo().Name("console").CenterPane()
                             .MaximizeButton().Show(1))
        
        self._mgr.AddPane(self.ghost,
                          aui.AuiPaneInfo().Name("ghost")
                             .Caption("Ghost in the Shell").Right()
                             .MaximizeButton().Show(0))
        
        self._mgr.AddPane(self.watcher,
                          aui.AuiPaneInfo().Name("watcher")
                             .Caption("Watchdog in the Shell").Right().Position(1)
                             .MaximizeButton().Show(0))
        
        self._mgr.Update()
        
        self.Unbind(wx.EVT_CLOSE)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(wx.EVT_SHOW, self.OnShow)
        
        self.__autoload = True
        
        self.Bind(wx.EVT_ACTIVATE, self.OnActivate)
        
        self.findDlg = None
        self.findData = wx.FindReplaceData(wx.FR_DOWN | wx.FR_MATCHCASE)
        
        self.Bind(wx.EVT_FIND, self.OnFindNext)
        self.Bind(wx.EVT_FIND_NEXT, self.OnFindNext)
        self.Bind(wx.EVT_FIND_CLOSE, self.OnFindClose)
        
        self.indicator = Indicator(self.statusbar, value=1)
        self.indicator.SetToolTip("[R] Invalid [Y] Debug/Trace [G] Normal")
        
        self.timer = wx.Timer(self)
        self.timer.Start(1000)
        
        def on_timer(evt):
            if self.indicator.Value & 0b110:
                self.indicator.blink(500)
            evt.Skip()
        self.Bind(wx.EVT_TIMER, on_timer)
        
        def on_size(evt):
            rect = self.statusbar.GetFieldRect(1)
            self.indicator.Position = (-44+rect.x, 2+rect.y)
            evt.Skip()
        self.Bind(wx.EVT_SIZE, on_size)
        
        def fork_debugger(evt):
            """Fork key events to the debugger."""
            self.debugger.handler(self.handler.current_event, evt)
            if self.debugger.handler.current_state:
                if self.debugger.tracing:
                    self.message("Current status is tracing. Press [C-g] to quit.")
                elif not self.debugger.busy:
                    self.message("Current status is inconsistent. Press [C-g] to quit.")
                    self.indicator.Value = 7
            evt.Skip()
        
        self.handler.update({ # DNA<ShellFrame>
            None : {
                  'debug_begin' : [ None, self.on_debug_begin ],
                   'debug_next' : [ None, self.on_debug_next ],
                    'debug_end' : [ None, self.on_debug_end ],
                  'trace_begin' : [ None, self.on_trace_begin ],
                   'trace_hook' : [ None, self.on_trace_hook ],
                    'trace_end' : [ None, self.on_trace_end ],
                'monitor_begin' : [ None, self.on_monitor_begin ],
                  'monitor_end' : [ None, self.on_monitor_end ],
                   'buffer_new' : [ None, ],
                    'shell_new' : [ None, ],
                      'add_log' : [ None, self.add_log ],
                     'add_help' : [ None, self.add_help ],
                 'title_window' : [ None, self.on_title_window ],
       'buffer_caption_updated' : [ None, self.on_buffer_caption ], # => self.OnActivate
            },
            0 : {
                    '* pressed' : (0, fork_debugger),
                   '* released' : (0, fork_debugger),
                  'C-g pressed' : (0, self.Quit, fork_debugger),
                   'f1 pressed' : (0, self.About),
                  'C-f pressed' : (0, self.OnFindText),
                   'f3 pressed' : (0, self.OnFindNext),
                 'S-f3 pressed' : (0, self.OnFindPrev),
                  'f11 pressed' : (0, _F(self.toggle_window, self.ghost, alias='toggle_ghost')),
                'S-f11 pressed' : (0, _F(self.toggle_window, self.watcher, alias='toggle_watcher')),
                  'f12 pressed' : (0, _F(self.Close, alias="close")),
             '*f[0-9]* pressed' : (0, ),
            },
        })
        
        ## Session files
        self.SESSION_FILE = get_rootpath(".debrc")
        self.SCRATCH_FILE = get_rootpath("scratch.py")
        self.LOGGING_FILE = get_rootpath("deb-logging.log")
        
        if session is not None:
            self.load_session(session or self.SESSION_FILE)
        else:
            self.SESSION_FILE = None
        
        self.postInit()
    
    def load_session(self, filename):
        """Load session from file.
        Buffers, pointers, and the entire layout are loaded.
        """
        def _fload(editor, filename):
            try:
                buffer = editor.default_buffer or editor.new_buffer()
                buffer.LoadFile(filename)
                buffer.EmptyUndoBuffer()
            except Exception:
                pass
        
        _fload(self.Scratch, self.SCRATCH_FILE) # restore scratch
        
        ## Re-open the *log* file.
        self.add_log("#! Opened: <{}>\r\n".format(datetime.datetime.now()))
        
        session = os.path.abspath(filename)
        try:
            with open(session) as i:
                exec(i.read())
        except FileNotFoundError:
            pass
        self.SESSION_FILE = session
        
        ## Reposition the window if it is not on the desktop.
        if wx.Display.GetFromWindow(self) == -1:
            self.Position = (0, 0)
    
    def save_session(self):
        """Save session to file.
        Buffers, pointers, and the entire layout are saved.
        """
        def _fsave(editor, filename):
            try:
                buffer = editor.default_buffer
                buffer.SaveFile(filename)
                buffer.SetSavePoint()
            except Exception:
                pass
        
        _fsave(self.Scratch, self.SCRATCH_FILE) # save scratch
        _fsave(self.Log,     self.LOGGING_FILE) # save log
        
        if not self.SESSION_FILE:
            return
        
        with open(self.SESSION_FILE, 'w') as o:
            o.write("#! Session file (This file is generated automatically)\n")
            o.write("self.SetSize({})\n".format(self.Size))
            o.write("self.SetPosition({})\n".format(self.Position))
            
            for book in self.all_editors:
                for buf in book.all_buffers:
                    if buf.mtdelta is not None:
                        o.write("self.{}.load_file({!r}, {})\n"
                                .format(book.Name, buf.filename, buf.markline+1))
                o.write("self.{}.loadPerspective({!r})\n"
                        .format(book.Name, book.savePerspective()))
            o.write('\n'.join((
                "self.ghost.loadPerspective({!r})".format(self.ghost.savePerspective()),
                "self.watcher.loadPerspective({!r})".format(self.watcher.savePerspective()),
                "self._mgr.LoadPerspective({!r})".format(self._mgr.SavePerspective()),
                "self._mgr.Update()\n",
            )))
    
    def postInit(self):
        """Set shell and editor styles.
        Note:
            This is called after loading session.
        """
        from .nutshell import Stylus
        
        self.Scratch.set_attributes(Style=Stylus.py_shell_mode)
        
        self.Log.set_attributes(ReadOnly=True,
                                Style=Stylus.py_log_mode)
        
        self.Help.set_attributes(ReadOnly=False,
                                 Style=Stylus.py_log_mode)
        
        self.set_hookable(self.Scratch)
        self.set_hookable(self.Log)
        
        @self.Scratch.define_key('C-j')
        def eval_line(evt):
            self.Scratch.buffer.eval_line()
            evt.Skip(False) # Don't skip explicitly.
        
        @self.Scratch.define_key('M-j')
        def eval_buffer(evt):
            self.Scratch.buffer.exec_region()
            evt.Skip(False) # Don't skip explicitly.
    
    def Init(self):
        """Initialize self-specific builtins.
        Note:
            This should be called before creating root shell.
        """
        try:
            builtins.dive
        except AttributeError:
            ## Add useful built-in functions and methods
            builtins.apropos = apropos
            builtins.typename = typename
            builtins.reload = reload
            builtins.partial = partial
            builtins.p = print
            builtins.pp = pp
            builtins.mro = mro
            builtins.where = where
            builtins.info = self.info
            builtins.help = self.help
            builtins.load = self.load
            builtins.dive = self.clone_shell
            builtins.debug = self.debug
            builtins.watch = self.watch
            builtins.timeit = self.timeit
            builtins.profile = self.profile
            builtins.highlight = self.highlight
            builtins.filling = filling
    
    def Destroy(self):
        try:
            ## Remove built-in self methods
            del builtins.info
            del builtins.help
            del builtins.load
            del builtins.dive
            del builtins.debug
            del builtins.watch
            del builtins.timeit
            del builtins.profile
            del builtins.highlight
        except AttributeError:
            pass
        try:
            self.timer.Stop()
            self.save_session()
        finally:
            self._mgr.UnInit()
            return MiniFrame.Destroy(self)
    
    def OnClose(self, evt):
        if self.debugger.busy:
            if wx.MessageBox( # Confirm debugger close.
                    "The debugger is running.\n\n"
                    "Enter [q]uit to exit before closing.\n"
                    "Continue closing?",
                    style=wx.YES_NO|wx.ICON_INFORMATION) != wx.YES:
                self.message("The close has been canceled.")
                evt.Veto()
                return
            #? RuntimeError('wrapped C/C++ object ... has been deleted')
            self.Quit()
        
        if self.debugger.tracing:
            wx.MessageBox("The debugger ends tracing.\n\n"
                          "The trace pointer will be cleared.")
            self.debugger.unwatch() # cf. [pointer_unset] stop_trace
        
        for book in self.all_editors:
            for buf in book.all_buffers:
                if buf.need_buffer_save:
                    self.popup_window(book)
                    buf.SetFocus()
                    if wx.MessageBox( # Confirm close.
                            "You are closing unsaved content.\n\n"
                            "Changes to the content will be discarded.\n"
                            "Continue closing?",
                            "Close {!r}".format(book.Name),
                            style=wx.YES_NO|wx.ICON_INFORMATION) != wx.YES:
                        self.message("The close has been canceled.")
                        evt.Veto()
                        return
                    break # Don't ask any more.
        if self.__standalone:
            evt.Skip() # Close the window
        else:
            self.Show(0) # Don't destroy the window
    
    def OnActivate(self, evt):
        if not evt.Active:
            ## Reset autoload when active focus going outside.
            self.__autoload = True
        elif evt.GetActivationReason() == evt.Reason_Mouse\
          and self.__autoload:
            ## Check all buffers that need to be loaded.
            for book in self.all_editors:
                for buf in book.all_buffers:
                    if buf.need_buffer_load:
                        if wx.MessageBox( # Confirm load.
                                "The file has been modified externally.\n\n"
                                "The contents of the buffer will be overwritten.\n"
                                "Continue loading {}/{}?".format(book.Name, buf.name),
                                "Load {!r}".format(buf.name),
                                style=wx.YES_NO|wx.ICON_INFORMATION) != wx.YES:
                            self.__autoload = False # Don't ask any more.
                            return
                        book.load_file(buf.filename)
        ## Reinitialize self-specific builtins if other instances are destroyed.
        if evt.Active:
            self.Init()
        evt.Skip()
    
    def OnShow(self, evt):
        pane = self._mgr.GetPane(self.watcher)
        if evt.IsShown():
            if pane.IsShown():
                self.inspector.watch()
                self.monitor.watch()
        else:
            if pane.IsDocked():
                self.inspector.unwatch()
                self.monitor.unwatch()
        evt.Skip()
    
    def OnGhostShow(self, evt):
        if evt.IsShown():
            self.inspector.watch()
            self.monitor.watch()
        else:
            self.inspector.unwatch()
            self.monitor.unwatch()
        evt.Skip()
    
    def OnConsolePageChanged(self, evt): #<wx._aui.AuiNotebookEvent>
        nb = evt.EventObject
        win = nb.CurrentPage
        if win is self.rootshell:
            nb.WindowStyle &= ~aui.AUI_NB_CLOSE_ON_ACTIVE_TAB
        else:
            nb.WindowStyle |= aui.AUI_NB_CLOSE_ON_ACTIVE_TAB
        nb.TabCtrlHeight = 0 if nb.PageCount == 1 else -1
        evt.Skip()
    
    ## def OnConsoleCloseBtn(self, evt): #<wx._aui.AuiNotebookEvent>
    ##     tabs = evt.EventObject
    ##     win = tabs.Pages[evt.Selection].window # GetPage for split notebook.
    ##     if win is self.rootshell:
    ##         ## self.message("- Don't close the root shell.")
    ##         return
    ##     elif self.debugger.busy and win is self.debugger.interactive_shell:
    ##         wx.MessageBox("The debugger is running.\n\n"
    ##                       "Enter [q]uit to exit before closing.")
    ##         return
    ##     evt.Skip()
    
    def OnConsolePageClose(self, evt): #<wx._aui.AuiNotebookEvent>
        nb = evt.EventObject
        win = nb.all_pages[evt.Selection]
        if win is self.rootshell:
            ## self.message("Don't close the root shell.")
            nb.WindowStyle &= ~aui.AUI_NB_CLOSE_ON_ACTIVE_TAB
            evt.Veto()
        elif self.debugger.busy and win is self.debugger.interactive_shell:
            wx.MessageBox("The debugger is running.\n\n"
                          "Enter [q]uit to exit before closing.")
            evt.Veto()
        else:
            evt.Skip()
    
    def About(self, evt=None):
        self.add_help(
            '\n\n'.join((
                "#<module 'mwx' from {!r}>".format(__file__),
                "Author: {!r}".format(__author__),
                "Version: {!s}".format(__version__),
                self.__class__.__doc__,
                self.rootshell.__class__.__doc__,
                
                ## Thanks to wx.py.shell.
                "#{!r}".format(wx.py),
                "Author: {!r}".format(wx.py.version.__author__),
                "Version: {!s}".format(wx.py.version.VERSION),
                wx.py.shell.Shell.__doc__,
                textwrap.indent("*original" + wx.py.shell.HELP_TEXT, ' '*4),
                
                ## Thanks are also due to wx.
                "#{!r}".format(wx),
                "To show the credit, press C-M-Mbutton.\n",
                ))
            )
    
    def toggle_window(self, win):
        pane = self._mgr.GetPane(win)
        if pane.IsDocked():
            if not self.console.IsShown():
                self._mgr.RestoreMaximizedPane() # いったん表示切替
                self._mgr.Update()               # 更新後に best_size 取得
        if pane.IsShown():
            pane.best_size = win.Size
        self.popup_window(win, not pane.IsShown())
    
    @save_focus_excursion()
    def popup_window(self, win, show=True):
        """Show the notebook page and keep the focus."""
        for pane in self._mgr.GetAllPanes():
            nb = pane.window
            if nb is win:
                break
            j = nb.GetPageIndex(win) # find and select page
            if j != -1:
                if j != nb.Selection:
                    nb.Selection = j # the focus moves
                break
        else:
            return # no such pane.window
        
        ## Modify the floating position of the pane when displayed.
        ## Note: This is a known bug in wxWidgets 3.17 -- 3.20,
        ##       and will be fixed in wxPython 4.2.1.
        if wx.Display.GetFromWindow(pane.window) == -1:
            pane.floating_pos = wx.GetMousePosition()
        
        nb.Show(show)
        pane.Show(show)
        self._mgr.Update()
    
    ## --------------------------------
    ## Actions for handler
    ## --------------------------------
    
    def Quit(self, evt=None):
        """Stop debugger and monitor."""
        self.debugger.unwatch()
        self.debugger.send_input('\n') # terminates the reader of threading pdb
        shell = self.debugger.interactive_shell # reset interp locals
        del shell.locals
        del shell.globals
        self.indicator.Value = 1
        self.message("Quit")
    
    @save_focus_excursion()
    def load(self, filename, lineno=0, show=True):
        """Load file @where the object is defined.
        
        Args:
            filename : target filename:str or object.
                       It also supports <'filename:lineno'> format.
            lineno   : Set mark to lineno on load.
            show     : Show the page.
        """
        if not isinstance(filename, str):
            filename = where(filename)
            if filename is None:
                return None
        if not lineno:
            m = re.match("(.*?):([0-9]+)", filename)
            if m:
                filename, ln = m.groups()
                lineno = int(ln)
        editor = self.find_editor(filename) or self.Log
        ret = editor.load_file(filename, lineno)
        if ret:
            self.popup_window(editor, show)
        return ret
    
    def info(self, obj):
        self.rootshell.info(obj)
    
    def help(self, obj):
        self.rootshell.help(obj)
    
    def watch(self, obj):
        if isinstance(obj, wx.Object):
            self.monitor.watch(obj)
            self.popup_window(self.monitor)
        if hasattr(obj, '__dict__'):
            self.linfo.watch(obj.__dict__)
            self.ginfo.watch(None)
            self.popup_window(self.linfo)
    
    def highlight(self, obj, *args, **kwargs):
        self.inspector.highlight(obj, *args, **kwargs)
    
    def timeit(self, obj, *args, **kwargs):
        """Measure the duration cpu time (per one execution)."""
        from timeit import timeit
        if callable(obj):
            try:
                dt = timeit(lambda: obj(*args, **kwargs), number=1)
                print("duration time: {:g} s".format(dt))
            except TypeError as e:
                print(e)
        elif isinstance(obj, str):
            try:
                dt = timeit(obj, number=1,
                            globals=self.current_shell.globals)
                print("duration time: {:g} s".format(dt))
            except Exception as e:
                print(e)
        else:
            print("- obj is neither a string nor callable")
    
    def profile(self, obj, *args, **kwargs):
        """Profile a single function call."""
        from profile import Profile
        if callable(obj):
            try:
                pr = Profile()
                pr.runcall(obj, *args, **kwargs)
                pr.print_stats()
            except TypeError as e:
                print(e)
        elif isinstance(obj, str):
            try:
                pr = Profile()
                pr.runctx(obj, self.current_shell.globals,
                               self.current_shell.locals)
                pr.print_stats()
            except TypeError as e:
                print(e)
        else:
            print("- obj must be callable or be a string, bytes or code object")
    
    ## Note: history に余計な文字列が入らないようにする
    @postcall
    def debug(self, obj, *args, **kwargs):
        shell = self.debugger.interactive_shell
        self.debugger.interactive_shell = self.current_shell
        try:
            if isinstance(obj, type(print)):
                wx.MessageBox("Unable to debug builtin functions.\n\n"
                              "Target must be callable or wx.Object.",
                              style=wx.ICON_ERROR)
            elif callable(obj):
                self.debugger.debug(obj, *args, **kwargs)
            elif isinstance(obj, str):
                filename = "<string>"
                editor = self.Scratch
                buf = editor.find_buffer(filename) or editor.create_buffer(filename)
                with buf.off_readonly():
                    buf.Text = obj
                self.debugger.run(obj, filename)
            elif isinstance(obj, wx.Object):
                self.watch(obj)
            else:
                wx.MessageBox("Unable to debug non-callable objects.\n\n"
                              "Target must be callable or wx.Object.",
                              style=wx.ICON_ERROR)
        finally:
            self.debugger.interactive_shell = shell
    
    def on_debug_begin(self, frame):
        """Called before set_trace."""
        if not self:
            return
        shell = self.debugger.interactive_shell
        shell.write("#<-- Enter [n]ext to continue.\n", -1)
        shell.prompt()
        shell.SetFocus()
        self.Show()
        self.popup_window(self.ghost)
        self.popup_window(self.linfo)
        self.add_log("<-- Beginning of debugger\r\n")
        self.indicator.Value = 2
        if wx.IsBusy():
            wx.EndBusyCursor()
    
    def on_debug_next(self, frame):
        """Called from cmdloop."""
        if not self:
            return
        shell = self.debugger.interactive_shell
        shell.globals = gs = frame.f_globals
        shell.locals = ls = frame.f_locals
        if self.ginfo.target is not gs:
            self.ginfo.watch(gs)
        if self.linfo.target is not ls:
            self.linfo.watch(ls)
        self.on_title_window(frame)
        self.popup_window(self.debugger.editor)
        dispatcher.send(signal='Interpreter.push',
                        sender=shell, command=None, more=False)
        command = shell.cmdline
        if command and not command.isspace():
            command = re.sub(r"^(.*)", r"    \1", command, flags=re.M)
            self.add_log(command)
        self.message("Debugger is busy now (Press [C-g] to quit).")
    
    def on_debug_end(self, frame):
        """Called after set_quit."""
        if not self:
            return
        shell = self.debugger.interactive_shell
        shell.write("#--> Debugger closed successfully.\n", -1)
        shell.prompt()
        self.add_log("--> End of debugger\r\n")
        self.linfo.unwatch()
        self.ginfo.unwatch()
        self.on_title_window(shell.target)
        del shell.locals
        del shell.globals
        self.indicator.Value = 1
        if wx.IsBusy():
            wx.EndBusyCursor()
    
    def set_hookable(self, editor, traceable=True):
        """Bind pointer to set/unset trace."""
        if traceable:
            editor.handler.bind('pointer_set', _F(self.start_trace, editor=editor))
            editor.handler.bind('pointer_unset', _F(self.stop_trace, editor=editor))
        else:
            editor.handler.unbind('pointer_set')
            editor.handler.unbind('pointer_unset')
    
    def start_trace(self, line, editor):
        if not self.debugger.busy:
            self.debugger.unwatch()
            self.debugger.editor = editor
            self.debugger.watch((editor.buffer.filename, line+1))
            self.debugger.send_input('') # clear input
    
    def stop_trace(self, line, editor):
        if self.debugger.busy:
            return
        if self.debugger.tracing:
            self.debugger.editor = None
            self.debugger.unwatch()
    
    def on_trace_begin(self, frame):
        """Called when set-trace."""
        self.message("Debugger has started tracing {!r}.".format(frame))
        self.indicator.Value = 3
    
    def on_trace_hook(self, frame):
        """Called when a breakpoint is reached."""
        self.message("Debugger hooked {!r}.".format(frame))
    
    def on_trace_end(self, frame):
        """Called when unset-trace."""
        self.message("Debugger has stopped tracing {!r}.".format(frame))
        self.indicator.Value = 1
    
    def on_monitor_begin(self, widget):
        """Called when monitor watch."""
        self.inspector.set_colour(widget, 'blue')
        self.message("Started monitoring {!r}.".format(widget))
    
    def on_monitor_end(self, widget):
        """Called when monitor unwatch."""
        self.inspector.set_colour(widget, 'black')
        self.message("Stopped monitoring {!r}.".format(widget))
    
    def on_title_window(self, obj):
        """Set title to the frame."""
        title = obj if isinstance(obj, str) else repr(obj)
        self.SetTitle("Nautilus - {}".format(title))
    
    def on_buffer_caption(self, buf):
        """Called when the buffer caption is updated."""
        if buf.caption_prefix.startswith('!'):
            v = wx.ActivateEvent(wx.wxEVT_ACTIVATE, True,
                                 buf.Id, ActivationReason=0)
            self.EventHandler.ProcessEvent(v) # => self.OnActivate
    
    def add_log(self, text, noerr=None):
        """Add text to the logging buffer.
        If noerr <bool> is specified, add a line-marker.
        """
        buf = self.Log.default_buffer or self.Log.new_buffer()
        with buf.off_readonly():
            buf.goto_char(buf.TextLength) # line to set an arrow marker
            buf.write(text)
        if noerr is not None:
            ## Set a marker on the current line.
            buf.add_marker(buf.cline, 1 if noerr else 2) # 1:white 2:red-arrow
            return
        
        ## Logging text every step in case of crash.
        ## with open(self.LOGGING_FILE, 'a', encoding='utf-8', newline='') as o:
        ##     o.write(text)
    
    def add_help(self, text):
        """Add text to the help buffer."""
        buf = self.Help.default_buffer or self.Help.new_buffer()
        with buf.off_readonly():
            buf.SetText(text)
        ## Overwrite text and popup the window.
        self.popup_window(self.Help)
        self.Help.swap_page(buf)
    
    def clone_shell(self, target):
        if not hasattr(target, '__dict__'):
            raise TypeError("primitive objects cannot be targeted")
        
        shell = self.rootshell.__class__(self, target, name="clone",
                    style=wx.CLIP_CHILDREN|wx.BORDER_NONE)
        self.handler('shell_new', shell)
        self.Show()
        self.console.AddPage(shell, typename(shell.target))
        self.popup_window(shell)
        shell.SetFocus()
        return shell
    
    def delete_shell(self, shell):
        """Close the current shell."""
        if shell is self.rootshell:
            ## self.message("- Don't close the root shell.")
            return
        if self.debugger.busy and shell is self.debugger.interactive_shell:
            wx.MessageBox("The debugger is running.\n\n"
                          "Enter [q]uit to exit before closing.")
            return
        j = self.console.GetPageIndex(shell)
        if j != -1:
            self.console.DeletePage(j) # Destroy the window
    
    ## --------------------------------
    ## Attributes for notebook pages
    ## --------------------------------
    
    def get_all_pages(self, type=None):
        """Yields all pages of the specified type in the notebooks."""
        yield from self.console.get_pages(type)
        yield from self.ghost.get_pages(type)
    
    @property
    def all_shells(self):
        """Yields all books in the notebooks."""
        return self.console.get_pages(type(self.rootshell))
    
    @property
    def current_shell(self):
        """Currently selected shell or rootshell."""
        return self.console.CurrentPage
    
    @property
    def all_editors(self):
        """Yields all editors in the notebooks."""
        return self.ghost.get_pages(type(self.Log))
    
    @property
    def current_editor(self):
        """Currently selected editor or scratch."""
        editor = self.ghost.CurrentPage
        if isinstance(editor, type(self.Log)):
            return editor
        return next((x for x in self.all_editors if x.IsShown()), self.Scratch)
    
    def find_editor(self, fn):
        """Find an editor with the specified fn:filename or code.
        If found, switch to the buffer page.
        """
        return next(self.find_editors(fn), None)
    
    def find_editors(self, fn):
        """Yields all editors with the specified fn:filename or code."""
        def _f(book):
            buf = book.find_buffer(fn)
            if buf:
                book.swap_page(buf)
            return buf
        return filter(_f, self.all_editors)
    
    ## --------------------------------
    ## Find text dialog
    ## --------------------------------
    ## *** The following code is a modification of <wx.py.frame.Frame> ***
    
    __find_target = None
    
    def OnFindText(self, evt):
        if self.findDlg is not None:
            self.findDlg.SetFocus()
            return
        
        wnd = wx.Window.FindFocus()
        if not isinstance(wnd, stc.StyledTextCtrl):
            return
        self.__find_target = wnd
        self.findData.FindString = wnd.topic_at_caret
        self.findDlg = wx.FindReplaceDialog(wnd, self.findData, "Find",
                            style=wx.FR_NOWHOLEWORD|wx.FR_NOUPDOWN)
        self.findDlg.Show()
    
    def OnFindNext(self, evt, backward=False): #<wx._core.FindDialogEvent>
        data = self.findData
        down_p = data.Flags & wx.FR_DOWN
        if (backward and down_p) or (not backward and not down_p):
            data.Flags ^= wx.FR_DOWN # toggle up/down flag
        
        wnd = wx.Window.FindFocus()
        if not isinstance(wnd, stc.StyledTextCtrl):
            wnd = self.__find_target
            if not wnd:
                return
        wnd.DoFindNext(data, self.findDlg or wnd)
        if self.findDlg:
            self.OnFindClose(None)
        wnd.EnsureVisible(wnd.cline)
        wnd.EnsureLineMoreOnScreen(wnd.cline)
    
    def OnFindPrev(self, evt):
        self.OnFindNext(evt, backward=True)
    
    def OnFindClose(self, evt): #<wx._core.FindDialogEvent>
        self.findDlg.Destroy()
        self.findDlg = None


def filling(obj=None, **kwargs):
    """Wx.py tool for watching widget ingredients."""
    from .py.filling import FillingFrame
    frame = FillingFrame(rootObject=obj,
                         rootLabel=typename(obj),
                         pos=wx.GetMousePosition(),
                         **kwargs)
    frame.filling.text.WrapMode = 0 # no wrap
    frame.filling.text.Zoom = -1 # zoom level of size of fonts
    frame.Show()
    return frame
