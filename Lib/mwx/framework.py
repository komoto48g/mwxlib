#! python3
# -*- coding: utf-8 -*-
"""mwxlib framework

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
__version__ = "0.71.0"
__author__ = "Kazuya O'moto <komoto@jeol.co.jp>"

from functools import wraps, partial
import traceback
import datetime
import time
import sys
import os
import re
import wx
from wx import aui
from wx import stc
from wx.py import dispatcher
from importlib import reload
import builtins
import textwrap
try:
    import utilus as ut
    from utilus import funcall as _F
    from utilus import FSM, TreeList, apropos, typename, where, mro, pp
except ImportError:
    from . import utilus as ut
    from .utilus import funcall as _F
    from .utilus import FSM, TreeList, apropos, typename, where, mro, pp


def postcall(f):
    """A decorator of wx.CallAfter
    Wx posts the message that forces `f` to take place in the main thread.
    """
    @wraps(f)
    def _f(*args, **kwargs):
        wx.CallAfter(f, *args, **kwargs)
    return _f


def skip(v):
    v.Skip()


speckeys = {
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

def speckey_state(key):
    k = next((k for k, v in speckeys.items() if v == key), None)
    if k:
        return wx.GetKeyState(k) #cf. wx.GetMouseState


def hotkey(evt):
    """Interpret evt.KeyCode as hotkey:str and overwrite evt.key.
    The modifiers are arranged in the same order as matplotlib as
    [LR]win + ctrl + alt(meta) + shift.
    """
    key = evt.GetKeyCode()
    mod = ""
    for k,v in ((wx.WXK_WINDOWS_LEFT, 'Lwin-'),
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
    
    key = speckeys.get(key) or chr(key).lower()
    evt.key = mod + key
    return evt.key


def regulate_key(key):
    return (key.replace("ctrl+",  "C-") # modifier keys abbreviation
               .replace("alt+",   "M-")
               .replace("shift+", "S-")
               .replace("win+", "win-")
               .replace("M-C-", "C-M-") # modifier key regulation C-M-S-
               .replace("S-M-", "M-S-")
               .replace("S-C-", "C-S-"))


class KeyCtrlInterfaceMixin(object):
    """Keymap interface mixin
    
    keymap::
    
        global-map : 0 (default)
         ctl-x-map : 'C-x'
          spec-map : 'C-c'
           esc-map : 'escape'
    """
    message = print # override this in subclass
    post_message = property(lambda self: postcall(self.message))
    
    def make_keymap(self, keymap):
        """Make a basis of extension map in the handler.
        """
        assert isinstance(keymap, str)
        
        def _Pass(v):
            self.message("{} {}".format(keymap, v.key))
        _Pass.__name__ = str('pass')
        
        state = self.handler.default_state
        event = keymap + ' pressed'
        
        assert state is not None, "Don't make keymap for None:state."
        
        self.handler.update({ # DNA<KeyCtrlInterfaceMixin>
            state : {
                          event : [ keymap, self.pre_command_hook ],
            },
            keymap : {
                         'quit' : [ state, ],
                    '* pressed' : [ state, _Pass ],
                 '*alt pressed' : [ keymap, _Pass ],
                '*ctrl pressed' : [ keymap, _Pass ],
               '*shift pressed' : [ keymap, _Pass ],
             '*[LR]win pressed' : [ keymap, _Pass ],
            },
        })
    
    def pre_command_hook(self, evt):
        """Enter extension mode.
        Check selection for [C-c][C-x].
        """
        win = wx.Window.FindFocus()
        if isinstance(win, wx.TextEntry) and win.StringSelection\
        or isinstance(win, stc.StyledTextCtrl) and win.SelectedText:
            ## or any other of pre-selection-p?
            self.handler('quit', evt)
        else:
            self.message(evt.key + '-')
        evt.Skip()
    
    def post_command_hook(self, evt):
        keymap = self.handler.previous_state
        if keymap:
            self.message("{} {}".format(keymap, evt.key))
        else:
            self.message(evt.key)
        evt.Skip()
    post_command_hook.__name__ = str('skip')
    
    def _get_keymap_state(self, keymap, mode='pressed'):
        map, sep, key = regulate_key(keymap).rpartition(' ')
        map = map.strip()
        event = key + ' ' + mode
        state = self.handler.default_state
        if not map:
            map = state
        elif map == '*':
            map = state = None
        return map, event, state
    
    def define_key(self, keymap, action=None, *args, **kwargs):
        """Define [map key (pressed)] action.
        
        If no action, it invalidates the key and returns @decor(binder).
        The key must be in C-M-S order (ctrl + alt(meta) + shift).
        
        Note:
            kwargs `doc` and `alias` are reserved as kw-only-args.
        """
        map, key, state = self._get_keymap_state(keymap)
        if map not in self.handler:
            self.make_keymap(map) # make new keymap
        if action:
            f = self.interactive_call(action, *args, **kwargs)
            if map != state:
                self.handler.update({map: {key: [state, f, self.post_command_hook]}})
            else:
                self.handler.update({map: {key: [state, f]}})
            return action
        else:
            self.handler.update({map: {key: [state]}})
            return lambda f: self.define_key(keymap, f, *args, **kwargs)
    
    def undefine_key(self, keymap):
        """Delete [map key (pressed)] context."""
        map, key, state = self._get_keymap_state(keymap)
        try:
            del self.handler[map][key]
            return True
        except KeyError:
            return False
    
    def interactive_call(self, action, *args, **kwargs):
        f = ut.funcall(action, *args, **kwargs)
        @wraps(f)
        def _echo(*v, **kw):
            self.message(f.__name__)
            return f(*v, **kw)
        return _echo


class CtrlInterface(KeyCtrlInterfaceMixin):
    """Mouse/Key event interface mixin
    """
    handler = property(lambda self: self.__handler)
    
    def __init__(self):
        self.__key = ''
        self.__handler = FSM({None:{}, 0:{}}, default=0)
        
        _M = self._mouse_handler
        _W = self._window_handler
        
        ## self.Bind(wx.EVT_KEY_DOWN, self.on_hotkey_press)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_hotkey_press)
        self.Bind(wx.EVT_KEY_UP, self.on_hotkey_release)
        
        self.Bind(wx.EVT_MOUSEWHEEL, self.on_mousewheel)
        
        self.Bind(wx.EVT_LEFT_UP, lambda v: _M('Lbutton released', v))
        self.Bind(wx.EVT_RIGHT_UP, lambda v: _M('Rbutton released', v))
        self.Bind(wx.EVT_MIDDLE_UP, lambda v: _M('Mbutton released', v))
        self.Bind(wx.EVT_LEFT_DOWN, lambda v: _M('Lbutton pressed', v))
        self.Bind(wx.EVT_RIGHT_DOWN, lambda v: _M('Rbutton pressed', v))
        self.Bind(wx.EVT_MIDDLE_DOWN, lambda v: _M('Mbutton pressed', v))
        self.Bind(wx.EVT_LEFT_DCLICK, lambda v: _M('Lbutton dclick', v))
        self.Bind(wx.EVT_RIGHT_DCLICK, lambda v: _M('Rbutton dclick', v))
        self.Bind(wx.EVT_MIDDLE_DCLICK, lambda v: _M('Mbutton dclick', v))
        
        self.Bind(wx.EVT_MOUSE_AUX1_UP, lambda v: _M('Xbutton1 released', v))
        self.Bind(wx.EVT_MOUSE_AUX2_UP, lambda v: _M('Xbutton2 released', v))
        self.Bind(wx.EVT_MOUSE_AUX1_DOWN, lambda v: _M('Xbutton1 pressed', v))
        self.Bind(wx.EVT_MOUSE_AUX2_DOWN, lambda v: _M('Xbutton2 pressed', v))
        self.Bind(wx.EVT_MOUSE_AUX1_DCLICK, lambda v: _M('Xbutton1 dclick', v))
        self.Bind(wx.EVT_MOUSE_AUX2_DCLICK, lambda v: _M('Xbutton2 dclick', v))
        
        ## self.Bind(wx.EVT_MOTION, lambda v: _W('motion', v))
        
        self.Bind(wx.EVT_SET_FOCUS, lambda v: _W('focus_set', v))
        self.Bind(wx.EVT_KILL_FOCUS, lambda v: _W('focus_kill', v))
        self.Bind(wx.EVT_ENTER_WINDOW, lambda v: _W('window_enter', v))
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda v: _W('window_leave', v))
        self.Bind(wx.EVT_WINDOW_DESTROY, lambda v: _W('window_destroy', v))
        
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, lambda v: _W('capture_lost', v))
        self.Bind(wx.EVT_MOUSE_CAPTURE_CHANGED, lambda v: _W('capture_changed', v))
    
    def on_hotkey_press(self, evt): #<wx._core.KeyEvent>
        """Called when key down."""
        if evt.EventObject is not self:
            evt.Skip()
            return
        key = hotkey(evt)
        self.__key = regulate_key(key + '+')
        if self.handler('{} pressed'.format(key), evt) is None:
            evt.Skip()
    
    def on_hotkey_release(self, evt): #<wx._core.KeyEvent>
        """Called when key up."""
        key = hotkey(evt)
        self.__key = ''
        if self.handler('{} released'.format(key), evt) is None:
            evt.Skip()
    
    def on_mousewheel(self, evt): #<wx._core.MouseEvent>
        """Called when wheel event.
        Trigger event: 'key+wheel[up|down|right|left] pressed'
        """
        if evt.GetWheelAxis():
            p = 'right' if evt.WheelRotation > 0 else 'left'
        else:
            p = 'up' if evt.WheelRotation > 0 else 'down'
        evt.key = self.__key + "wheel{}".format(p)
        if self.handler('{} pressed'.format(evt.key), evt) is None:
            evt.Skip()
        self.__key = ''
    
    def _mouse_handler(self, event, evt): #<wx._core.MouseEvent>
        """Called when mouse event.
        Trigger event: 'key+[LMRX]button pressed/released/dclick'
        """
        event = self.__key + event # 'C-M-S-K+[LMRX]button pressed/released/dclick'
        key, sep, st = event.rpartition(' ') # removes st:'pressed/released/dclick'
        evt.key = key or st
        if self.handler(event, evt) is None:
            evt.Skip()
        self.__key = ''
        try:
            self.SetFocusIgnoringChildren() # let the panel accept keys
        except AttributeError:
            pass
    
    def _window_handler(self, event, evt):
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
    """Do layout
    
    Examples:
        >>> self.SetSizer(
            pack(self, (
                (label, 0, wx.ALIGN_CENTER | wx.LEFT, 4),
                ( ctrl, 1, wx.ALIGN_CENTER | wx.LEFT, 4),
                ))
            )
    
    Args:
        items   : wx objects (with some packing parameters)
        
                - (obj, 1) -> sized with ratio 1 (orient と同方向)
                  他に 0 以外を指定しているオブジェクトとエリアを分け合う
                - (obj, 1, wx.EXPAND) -> expanded with ratio 1 (orient と垂直方向)
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
        style = (0, wx.EXPAND | wx.ALL, 0)
    if label is not None:
        box = wx.StaticBox(self, -1, label)
        sizer = wx.StaticBoxSizer(box, orient)
    else:
        sizer = wx.BoxSizer(orient)
    for item in items:
        if not item:
            if item is None:
                item = (0,0), 0,0,0, # null space
            else:
                item = (0,0) # padding space
        try:
            try:
                sizer.Add(item, *style)
            except TypeError:
                sizer.Add(*item) # using item-specific style
        except TypeError as e:
            traceback.print_exc()
            bmp = wx.StaticBitmap(self,
                    bitmap=wx.ArtProvider.GetBitmap(wx.ART_ERROR))
            bmp.SetToolTip("Pack failure\n{}".format(e))
            sizer.Add(bmp, 0, wx.EXPAND | wx.ALL, 0)
            wx.Bell()
    return sizer


class Menu(wx.Menu):
    """Construct menu
    
    Args:
        values : list of MenuItem args
    
    (id, text, hint, style, icon,  ... Menu.Append arguments
       action, updater, highlight) ... Menu Event handlers
    
        - style -> menu style (ITEM_NORMAL, ITEM_CHECK, ITEM_RADIO)
        - icon -> menu icon (bitmap)
        - action -> EVT_MENU handler
        - updater -> EVT_UPDATE_UI handler
        - highlight -> EVT_MENU_HIGHLIGHT handler
    """
    def __init__(self, owner, values):
        wx.Menu.__init__(self)
        self.owner = owner
        
        for item in values:
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
                    self.owner.Bind(wx.EVT_MENU, handlers[0], id=id)
                    self.owner.Bind(wx.EVT_UPDATE_UI, handlers[1], id=id)
                    self.owner.Bind(wx.EVT_MENU_HIGHLIGHT, handlers[2], id=id)
                except IndexError:
                    pass
            else:
                subitems = list(argv.pop())
                submenu = Menu(owner, subitems)
                submenu_item = wx.MenuItem(self, wx.ID_ANY, *argv)
                submenu_item.SetSubMenu(submenu)
                if icons:
                    submenu_item.SetBitmaps(*icons)
                self.Append(submenu_item)
                self.Enable(submenu_item.Id, len(subitems)) # Disable an empty menu
                submenu.Id = submenu_item.Id # <- ID_ANY
    
    @staticmethod
    def Popup(parent, menu, *args, **kwargs):
        menu = Menu(parent, menu)
        parent.PopupMenu(menu, *args, **kwargs)
        menu.Destroy()


class MenuBar(wx.MenuBar, TreeList):
    """Construct menubar as is ordered menu:list
    リストの順番どおりに GUI 上にマップしたメニューバーを構築する
    
    >>> root
        ├ [key, [item,
        │        item,...]],
        │
        ├ [key, [item,
        │        item,
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
        if self.Parent:
            menu = self.getmenu(key)
            if not menu:     # 新規のメニューアイテムを挿入する
                self.reset() # リセットして終了
                return
            
            for item in menu.MenuItems: # delete all items
                self.Parent.Unbind(wx.EVT_MENU, id=item.Id)
                self.Parent.Unbind(wx.EVT_UPDATE_UI, id=item.Id)
                self.Parent.Unbind(wx.EVT_MENU_HIGHLIGHT, id=item.Id)
                menu.Delete(item)
            
            menu2 = Menu(self.Parent, self[key]) # new menu2 to swap menu
            for item in menu2.MenuItems:
                menu.Append(menu2.Remove(item)) # 重複しないようにいったん切り離して追加する
            
            if hasattr(menu, 'Id'):
                self.Enable(menu.Id, menu.MenuItemCount > 0) # 空のサブメニューは無効にする
    
    def reset(self):
        """Recreates menubar if the Parent were attached by SetMenuBar.
        Call when the menulist is changed.
        """
        if self.Parent:
            for j in range(self.GetMenuCount()): # remove and del all top-level menu
                menu = self.Remove(0)
                for item in menu.MenuItems: # delete all items
                    self.Parent.Unbind(wx.EVT_MENU, id=item.Id)
                    self.Parent.Unbind(wx.EVT_UPDATE_UI, id=item.Id)
                    self.Parent.Unbind(wx.EVT_MENU_HIGHLIGHT, id=item.Id)
                menu.Destroy()
            
            for j, (key, values) in enumerate(self):
                menu = Menu(self.Parent, values) # 空のメインメニューでも表示に追加する
                self.Append(menu, key)
                if not values:
                    self.EnableTop(j, False) # 空のメインメニューは無効にする


class StatusBar(wx.StatusBar):
    """Construct statusbar with read/write
    
    Attributes:
        field   : list of field widths
        pane    : index of status text field
    """
    lock = None
    
    def __init__(self, *args, **kwargs):
        wx.StatusBar.__init__(self, *args, **kwargs)
    
    def __call__(self, *args, **kwargs):
        text = ' '.join(str(v) for v in args)
        if not self.lock:
            return self.write(text, **kwargs)
        return text
    
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
    """Frame base class
    
    Attributes:
        menubar     : MenuBar
        statusbar   : StatusBar
        shellframe  : mini-frame of the shell
    """
    handler = property(lambda self: self.__handler)
    message = property(lambda self: self.statusbar)
    
    def post_command_hook(self, evt):
        pass
    post_command_hook.__name__ = str('noskip') # Don't skip the event
    
    def __init__(self, *args, **kwargs):
        wx.Frame.__init__(self, *args, **kwargs)
        
        self.shellframe = ShellFrame(None, target=self)
        
        self.menubar = MenuBar()
        self.menubar["File"] = [
            (ID_(1), "&Shell\tF12", "Shell for inspection", wx.ITEM_CHECK,
                lambda v: (self.shellframe.Show(),
                           self.shellframe.console.CurrentPage.SetFocus()),
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
        
        ## self.timer = wx.PyTimer(
        ##     lambda: self.statusbar.write(time.strftime('%m/%d %H:%M'), pane=-1))
        self.timer = wx.Timer(self)
        self.timer.Start(1000)
        
        def on_timer(evt):
            self.statusbar.write(time.strftime('%m/%d %H:%M'), pane=-1)
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
        
        def close(v):
            """Close the window."""
            self.Close()
        
        self.__handler = FSM({ # DNA<Frame>
                None : {
                },
                0 : {
                    '* pressed' : (0, skip),
                  'M-q pressed' : (0, close),
                },
            },
            default = 0
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
    """MiniFrame base class
    
    Attributes:
        menubar     : MenuBar (not created by default)
        statusbar   : StatusBar (not shown by default)
    """
    handler = property(lambda self: self.__handler)
    message = property(lambda self: self.statusbar)
    
    def post_command_hook(self, evt):
        pass
    post_command_hook.__name__ = str('noskip') # Don't skip the event
    
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
        
        def close(v):
            """Close the window."""
            self.Close()
        
        self.__handler = FSM({ # DNA<MiniFrame>
                None : {
                },
                0 : {
                    '* pressed' : (0, skip),
                  'M-q pressed' : (0, close),
                },
            },
            default = 0
        )
        self.make_keymap('C-x')
    
    def Destroy(self):
        return wx.MiniFrame.Destroy(self)


class AuiNotebook(aui.AuiNotebook):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('style',
            (aui.AUI_NB_DEFAULT_STYLE | aui.AUI_NB_BOTTOM)
          &~(aui.AUI_NB_CLOSE_ON_ACTIVE_TAB | aui.AUI_NB_MIDDLE_CLICK_CLOSE))
        aui.AuiNotebook.__init__(self, *args, **kwargs)
        
        self.parent = self.Parent
        
        self.Bind(aui.EVT_AUINOTEBOOK_TAB_RIGHT_DOWN, self.on_show_menu)
        self.Bind(aui.EVT_AUINOTEBOOK_PAGE_CHANGED, self.on_page_changed)
        self.Bind(aui.EVT_AUINOTEBOOK_PAGE_CHANGING, self.on_page_changing)
    
    def on_show_menu(self, evt): #<wx._aui.AuiNotebookEvent>
        tab = evt.EventObject                  #<wx._aui.AuiTabCtrl>
        page = tab.Pages[evt.Selection].window # Don't use GetPage for split notebook
        if getattr(page, 'menu', None):
            Menu.Popup(self, page.menu)
    
    def on_page_changed(self, evt): #<wx._aui.AuiNotebookEvent>
        page = self.CurrentPage
        if page:
            page.handler('page_shown', page)
        evt.Skip()
    
    def on_page_changing(self, evt): #<wx._aui.AuiNotebookEvent>
        page = self.CurrentPage
        obj = evt.EventObject #<wx._aui.AuiTabCtrl>, <wx._aui.AuiNotebook>
        if obj is self.ActiveTabCtrl:
            win = obj.Pages[evt.Selection].window #<wx._aui.AuiNotebookPage>
            if not win.IsShownOnScreen():
                ## Check if the (selected) window is hidden now.
                ## False means that the page will be hidden by the window.
                page.handler('page_hidden', page)
        evt.Skip()
    
    def get_page_caption(self, win):
        _p, tab, idx = self.FindTab(win)
        return tab.GetPage(idx).caption
    
    def set_page_caption(self, win, caption):
        _p, tab, idx = self.FindTab(win)
        tab.GetPage(idx).caption = caption
        tab.Refresh()
    
    def all_pages(self, type=None):
        """Yields all pages of the specified type in the notebooks."""
        for j in range(self.PageCount):
            win = self.GetPage(j)
            if type is None or isinstance(win, type):
                yield win


class ShellFrame(MiniFrame):
    """MiniFrame of the Shell.
    
    Args:
         target : target object of the rootshell.
                  If None, it will be `__main__`.
    
    Attributes:
        console     : Notebook of shells
        ghost       : Notebook of editors and inspectors
        watcher     : Notebook of global/locals info watcher
        Scratch     : buffer for scratch (tooltip)
        Help        : buffer for help
        Log         : buffer for logging
        History     : buffer for shell history
        monitor     : wxmon.EventMonitor object
        inspector   : wxwit.Inspector object
    
    Built-in utility::
    
        @p          : Synonym of print.
        @pp         : Synonym of pprint.
        @info       : Short info.
        @help       : Full description.
        @dive       : Clone the shell with new target.
        @timeit     : Measure the duration cpu time (per one execution).
        @profile    : Profile a single function call.
        @filling    : Inspection using ``wx.lib.filling.Filling``.
        @watch      : Inspection using ``wx.lib.inspection.InspectionTool``.
        @load       : Load file in Log buffer.
        @where      : Displays filename:lineno or the module name.
        @mro        : Displays mro list and filename:lineno or the module name.
        @debug      : Open pdb or event-monitor.
    """
    rootshell = property(lambda self: self.__shell) #: the root shell
    
    def __init__(self, parent, target=None, title=None, size=(1280,720),
                 style=wx.DEFAULT_FRAME_STYLE,
                 ensureClose=False, **kwargs):
        MiniFrame.__init__(self, parent, size=size, style=style)
        
        self.statusbar.resize((-1,120))
        self.statusbar.Show(1)
        
        try:
            from nutshell import Editor, Nautilus
        except ImportError:
            from .nutshell import Editor, Nautilus
        
        self.__shell = Nautilus(self,
            target=target or parent or __import__("__main__"),
            style=(wx.CLIP_CHILDREN | wx.BORDER_NONE),
            **kwargs)
        
        self.Scratch = Editor(self, name="Scratch")
        self.Log = Editor(self, name="Log")
        self.Help = Editor(self, name="Help")
        self.History = Editor(self, name="History")
        
        ## Add useful global abbreviations to builtins
        builtins.apropos = apropos
        builtins.typename = typename
        builtins.reload = reload
        builtins.partial = partial
        builtins.p = print
        builtins.pp = pp
        builtins.mro = mro
        builtins.where = where
        builtins.watch = watchit
        builtins.filling = filling
        builtins.profile = profile
        builtins.timeit = timeit
        builtins.help = self.rootshell.help
        builtins.info = self.rootshell.info
        builtins.dive = self.rootshell.clone
        builtins.load = self.load
        builtins.debug = self.debug
        
        try:
            from wxpdb import Debugger
            from wxwit import Inspector
            from wxmon import EventMonitor
            from wxwil import LocalsWatcher
            from controls import Icon
        except ImportError:
            from .wxpdb import Debugger
            from .wxwit import Inspector
            from .wxmon import EventMonitor
            from .wxwil import LocalsWatcher
            from .controls import Icon
        
        self.debugger = Debugger(self,
                                 stdin=self.__shell.interp.stdin,
                                 stdout=self.__shell.interp.stdout,
                                 skip=[Debugger.__module__,
                                       EventMonitor.__module__,
                                       FSM.__module__,
                                       'fnmatch', 'warnings', 'bdb', 'pdb',
                                       'wx.core', 'wx.lib.eventwatcher',
                                       ],
                                 )
        self.inspector = Inspector(self)
        self.monitor = EventMonitor(self)
        self.ginfo = LocalsWatcher(self, name="globals")
        self.linfo = LocalsWatcher(self, name="locals")
        
        self.console = AuiNotebook(self, size=(600,400))
        self.console.AddPage(self.__shell, "root", bitmap=Icon('core'))
        self.console.TabCtrlHeight = 0
        self.console.Name = "console"
        
        self.console.Bind(aui.EVT_AUINOTEBOOK_PAGE_CHANGED, self.OnConsolePageChanged)
        self.console.Bind(aui.EVT_AUINOTEBOOK_BUTTON, self.OnConsolePageClosing)
        
        self.ghost = AuiNotebook(self, size=(600,400))
        self.ghost.AddPage(self.Scratch, "Scratch")
        self.ghost.AddPage(self.Log,     "Log")
        self.ghost.AddPage(self.Help,    "Help")
        self.ghost.AddPage(self.History, "History")
        self.ghost.AddPage(self.monitor, "Monitor", bitmap=Icon('ghost'))
        self.ghost.AddPage(self.inspector, "Inspector", bitmap=Icon('inspect'))
        self.ghost.Name = "ghost"
        
        self.ghost.Bind(wx.EVT_SHOW, self.OnGhostShow)
        
        self.watcher = AuiNotebook(self, size=(300,200))
        self.watcher.AddPage(self.ginfo, "globals")
        self.watcher.AddPage(self.linfo, "locals")
        self.watcher.Name = "watcher"
        
        self._mgr = aui.AuiManager()
        self._mgr.SetManagedWindow(self)
        self._mgr.SetDockSizeConstraint(0.5, 0.5) # (w, h)/N
        
        self._mgr.AddPane(self.console,
                          aui.AuiPaneInfo().Name("console").CenterPane().Show(1))
        
        self._mgr.AddPane(self.ghost,
                          aui.AuiPaneInfo().Name("ghost")
                             .Caption("Ghost in the Shell").Right().Show(0))
        
        self._mgr.AddPane(self.watcher,
                          aui.AuiPaneInfo().Name("watcher")
                             .Caption("Locals watch").Float().Show(0))
        
        self._mgr.Update()
        
        self.__standalone = ensureClose
        
        self.Unbind(wx.EVT_CLOSE)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        
        self.Bind(wx.EVT_SHOW, self.OnShow)
        
        self.findDlg = None
        self.findData = wx.FindReplaceData(wx.FR_DOWN | wx.FR_MATCHCASE)
        
        self.Bind(wx.EVT_FIND, self.OnFindNext)
        self.Bind(wx.EVT_FIND_NEXT, self.OnFindNext)
        self.Bind(wx.EVT_FIND_CLOSE, self.OnFindClose)
        
        def skip(v):
            if self.debugger.handler.current_state:
                if self.debugger.tracing:
                    self.message("- The current status is tracing. "
                                 "- Press C-g to quit.")
                elif not self.debugger.busy:
                    self.message("- The current status of debugger is not valid. "
                                 "- Press C-g to quit.")
            v.Skip()
        
        def fork(v):
            """Fork key events to the debugger."""
            self.debugger.handler(self.handler.event, v)
        
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
                    'add_shell' : [ None, self.add_shell ],
                      'add_log' : [ None, self.add_log ],
                     'add_help' : [ None, self.add_help ],
                  'add_history' : [ None, self.add_history ],
                 'title_window' : [ None, self.on_title_window ],
                 'caption_page' : [ None, self.on_caption_page ]
            },
            0 : {
                    '* pressed' : (0, skip, fork), # => debugger
                  'C-g pressed' : (0, self.Quit, fork), # => debugger
                   'f1 pressed' : (0, self.About),
                  'C-f pressed' : (0, self.OnFindText),
                   'f3 pressed' : (0, self.OnFindNext),
                 'S-f3 pressed' : (0, self.OnFindPrev),
                  'f11 pressed' : (0, _F(self.toggle_window, self.ghost, doc="Toggle ghost")),
                'S-f11 pressed' : (0, _F(self.toggle_window, self.watcher, doc="Toggle watcher")),
                  'f12 pressed' : (0, _F(self.Close, alias="close", doc="Close the window")),
             '*f[0-9]* pressed' : (0, ),
               'M-left pressed' : (0, _F(self.other_window, p=-1)),
              'M-right pressed' : (0, _F(self.other_window, p=+1)),
             'Xbutton1 pressed' : (0, _F(self.other_editor, p=-1, mod=0)),
             'Xbutton2 pressed' : (0, _F(self.other_editor, p=+1, mod=0)),
            },
        })
        
        ## py-mode
        ## self.Scratch.show_folder()
        self.Scratch.set_style(Nautilus.STYLE)
        
        self.set_traceable(self.Scratch)
        
        @self.Scratch.define_key('C-j')
        def eval_line(v):
            self.Scratch.py_eval_line(self.current_shell.globals,
                                      self.current_shell.locals)
        
        @self.Scratch.define_key('M-j')
        def exec_buffer(v):
            self.Scratch.py_exec_region(self.current_shell.globals,
                                        self.current_shell.locals,
                                        "<scratch>")
        
        ## text-mode
        ## self.Log.show_folder()
        self.Log.ReadOnly = True
        
        self.set_traceable(self.Log)
        
        ## self.Help.show_folder()
        self.Help.ReadOnly = True
        
        ## self.History.show_folder()
        self.History.ReadOnly = True
        
        self.Init()
    
    SESSION_FILE = ut.get_rootpath("debrc")
    SCRATCH_FILE = ut.get_rootpath("deb-scratch.py")
    LOGGING_FILE = ut.get_rootpath("deb-logging.log")
    HISTORY_FILE = ut.get_rootpath("deb-history.log")
    
    def load_session(self):
        """Load session from file."""
        try:
            if self.Scratch.buffer.mtdelta is None:
                self.Scratch.LoadFile(self.SCRATCH_FILE) # dummy-load *scratch*
                self.Scratch.push_current()
            with open(self.SESSION_FILE) as i:
                exec(i.read())
            return True
        except FileNotFoundError:
            pass
        except Exception:
            traceback.print_exc()
            print("- Failed to load session")
    
    def save_session(self):
        """Save session to file."""
        try:
            with open(self.SESSION_FILE, 'w') as o:
                o.write('\n'.join((
                    "#! Session file (This file is generated automatically)",
                    "self.SetSize({})".format(self.Size),
                    "self.ghost.SetSelection({})".format(self.ghost.Selection),
                    "self.watcher.SetSelection({})".format(self.watcher.Selection),
                    "self._mgr.LoadPerspective({!r})".format(self._mgr.SavePerspective()),
                    "self._mgr.GetPane('ghost').FloatingPosition(self.Position)",
                    "self._mgr.GetPane('watcher').FloatingPosition(self.Position)",
                    "self._mgr.Update()",
                    ""
                )))
                for buffer in self.Log.buffer_list:
                    if buffer.mtdelta is not None:
                        o.write("self.Log.load_file({!r}, {})\n".format(
                                buffer.filename, buffer.lineno))
                self.Log.push_current()
                with open(self.LOGGING_FILE, 'w', encoding='utf-8', newline='') as f:
                    f.write(self.Log.default_buffer.text)
                
                for buffer in self.Scratch.buffer_list:
                    if buffer.mtdelta is not None:
                        o.write("self.Scratch.load_file({!r}, {})\n".format(
                                buffer.filename, buffer.lineno))
                self.Scratch.push_current()
                with open(self.SCRATCH_FILE, 'w', encoding='utf-8', newline='') as f:
                    f.write(self.Scratch.default_buffer.text)
            return True
        except Exception:
            traceback.print_exc()
            print("- Failed to save session")
    
    def Init(self):
        msg = "#! Opened: <{}>\r\n".format(datetime.datetime.now())
        self.add_history(msg)
        self.add_log(msg)
        self.load_session()
    
    def Destroy(self):
        try:
            self.History.SaveFile(self.HISTORY_FILE)
            self.save_session()
        finally:
            self._mgr.UnInit()
            return MiniFrame.Destroy(self)
    
    def OnShow(self, evt):
        if evt.IsShown():
            self.inspector.watch(self)
    
    def OnGhostShow(self, evt):
        if evt.IsShown():
            self.inspector.watch(self.ghost)
        else:
            self.inspector.unwatch()
            self.monitor.unwatch()
            self.ginfo.unwatch()
            self.linfo.unwatch()
        evt.Skip()
    
    def OnClose(self, evt):
        if self.debugger.busy:
            wx.MessageBox("The debugger is running.\n\n"
                          "Enter [q]uit to exit before closing.")
            return
        if self.debugger.tracing:
            wx.MessageBox("The debugger ends tracing.\n\n"
                          "The trace pointer is cleared.")
            del self.Log.pointer # [pointer_unset] => debugger.unwatch
            del self.Scratch.pointer
        
        pane = self._mgr.GetPane(self.ghost)
        if pane.IsDocked():
            self.inspector.unwatch()
            self.monitor.unwatch()
            self.ginfo.unwatch()
            self.linfo.unwatch()
        
        if self.__standalone:
            evt.Skip() # Close the window
        else:
            self.Show(0) # Don't destroy the window
    
    def OnConsolePageChanged(self, evt): #<wx._aui.AuiNotebookEvent>
        nb = evt.EventObject
        if nb.CurrentPage is self.rootshell:
            nb.WindowStyle &= ~wx.aui.AUI_NB_CLOSE_ON_ACTIVE_TAB
        else:
            nb.WindowStyle |= wx.aui.AUI_NB_CLOSE_ON_ACTIVE_TAB
        nb.TabCtrlHeight = 0 if nb.PageCount == 1 else -1
        evt.Skip()
    
    def OnConsolePageClosing(self, evt): #<wx._aui.AuiNotebookEvent>
        tab = evt.EventObject                 #<wx._aui.AuiTabCtrl>
        win = tab.Pages[evt.Selection].window # Don't use GetPage for split notebook.
        if win is self.rootshell:
            ## self.message("- Don't close the root shell.")
            return
        evt.Skip()
    
    def About(self, evt=None):
        with self.Help.off_readonly():
            self.Help.SetText('\n\n'.join((
                "#<module 'mwx' from {!r}>".format(__file__),
                "Author: {!r}".format(__author__),
                "Version: {!s}".format(__version__),
                self.__class__.__doc__,
                self.rootshell.__class__.__doc__,
                
                # Thanks to wx.py.shell.
                "#{!r}".format(wx.py),
                "Author: {!r}".format(wx.py.version.__author__),
                "Version: {!s}".format(wx.py.version.VERSION),
                wx.py.shell.Shell.__doc__,
                textwrap.indent("*original" + wx.py.shell.HELP_TEXT, ' '*4),
                
                # Thanks are also due to wxWidgets.
                "#{!r}".format(wx),
                "To show the credit, press C-M-Mbutton.\n",
                ))
            )
        self.popup_window(self.Help, focus=0)
    
    def toggle_window(self, win, focus=False):
        self.popup_window(win, None, focus)
    
    def popup_window(self, win, show=True, focus=True):
        """Show the notebook page and move the focus.
        
        Args:
            win  : page or window to popup
            show : True, False, otherwise None:toggle
                   The pane window will be hidden if no show.
        """
        wnd = win if focus else wx.Window.FindFocus() # original focus
        for pane in self._mgr.GetAllPanes():
            nb = pane.window
            if nb is win:
                break
            j = nb.GetPageIndex(win) # find and select page
            if j != -1:
                if j != nb.Selection:
                    nb.Selection = j # the focus is moved
                break
        else:
            return
        if show is None:
            show = not pane.IsShown() # toggle show
        if show:
            ## Modify aui pane floating position when it is shown,
            ## to address a known bug with wxWidgets 3.17 -- 3.20.
            w, h = wx.DisplaySize()
            x, y = pane.floating_pos
            if x > w or y > h:
                pane.floating_pos = wx.GetMousePosition()
        nb.Show(show)
        pane.Show(show)
        self._mgr.Update()
        if wnd and win.IsShown():
            wnd.SetFocus()
    
    ## --------------------------------
    ## Actions for handler
    ## --------------------------------
    
    def Quit(self, evt):
        ## self.inspector.unwatch()
        self.monitor.unwatch()
        self.ginfo.unwatch()
        self.linfo.unwatch()
        self.debugger.unwatch()
        shell = self.debugger.interactive_shell # reset interp locals
        del shell.locals
        del shell.globals
        self.on_title_window(self.current_shell.target) # reset title
        self.message("Quit")
        evt.Skip()
    
    def load(self, obj, show=True, focus=False):
        """Load file @where the object is defined.
        
        Args:
            obj     : target object.
            show    : Popup editor window when success.
                      The pane window will not be hidden even if no show.
            focus   : Set the focus if the window is displayed.
        """
        if not isinstance(obj, str):
            obj = where(obj)
        if obj is None:
            return False
        m = re.match("(.*?):([0-9]+)", obj)
        if m:
            filename, ln = m.groups()
            lineno = int(ln)
        else:
            filename = obj
            lineno = 0
        if self.Log.load_file(filename, lineno):
            if show:
                self.popup_window(self.Log, show, focus)
            return True
        return False
    
    @postcall
    def debug(self, obj, *args, **kwargs):
        if isinstance(obj, wx.Object) or obj is None:
            if args or kwargs:
                self.message("- args:{} and kwargs:{} were given,"
                             " but ignored for object monitoring.")
            self.monitor.watch(obj)
            self.console.SetFocus() # focus orginal-window
            if obj:
                self.linfo.watch(obj.__dict__)
                self.ginfo.watch(eval("globals()", obj.__dict__))
                self.popup_window(self.monitor, focus=0)
                self.popup_window(self.linfo, focus=0)
        elif callable(obj):
            try:
                shell = self.debugger.interactive_shell
                self.debugger.interactive_shell = self.current_shell
                self.debugger.editor = self.Log # set default logger
                self.debugger.debug(obj, *args, **kwargs)
            finally:
                self.debugger.interactive_shell = shell
        else:
            print("- cannot debug {!r}".format(obj))
            print("  The debug target must be callable or wx.Object.")
            wx.MessageBox("Not a callable object\n\n"
                          "Unable to debug {!r}".format(obj))
    
    def on_debug_begin(self, frame):
        """Called before set_trace."""
        shell = self.debugger.interactive_shell
        shell.write("#<-- Enter [n]ext to continue.\n", -1)
        shell.prompt()
        shell.SetFocus()
        self.Show()
        self.popup_window(self.ghost, focus=0)
        self.popup_window(self.linfo, focus=0)
        self.add_log("<-- Beginning of debugger\r\n")
    
    def on_debug_next(self, frame):
        """Called from cmdloop."""
        shell = self.debugger.interactive_shell
        gs = frame.f_globals
        ls = frame.f_locals
        shell.globals = gs
        shell.locals = ls
        if self.ginfo.target is not gs:
            self.ginfo.watch(gs)
        if self.linfo.target is not ls:
            self.linfo.watch(ls)
        self.on_title_window(frame)
        self.popup_window(self.debugger.editor, focus=0)
        dispatcher.send(signal='Interpreter.push',
                        sender=self, command=None, more=False)
        
        command = shell.cmdline
        if command and not command.isspace():
            command = re.sub(r"^(.*)", r"    \1", command, flags=re.M)
            self.add_log(command)
        self.message("Debugger is busy now (Press C-g to quit).")
    
    def on_debug_end(self, frame):
        """Called after set_quit."""
        shell = self.debugger.interactive_shell
        shell.write("#--> Debugger closed successfully.\n", -1)
        shell.prompt()
        self.add_log("--> End of debugger\r\n")
        self.linfo.unwatch()
        self.ginfo.unwatch()
        self.on_title_window(shell.target)
        del shell.locals
        del shell.globals
    
    def set_traceable(self, editor, traceable=True):
        """Bind pointer to trace set/unset functions."""
        if traceable:
            editor.handler.bind('pointer_set', _F(self.start_trace, editor=editor))
            editor.handler.bind('pointer_unset', _F(self.stop_trace, editor=editor))
        else:
            editor.handler.unbind('pointer_set')
            editor.handler.unbind('pointer_unset')
    
    def start_trace(self, line, editor):
        if not self.debugger.busy:
            if not editor.target:
                self.message("- No compiled target")
            else:
                self.debugger.unwatch()
                self.debugger.editor = editor
                self.debugger.watch((editor.target, line+1))
        editor.MarkerDeleteAll(4)
    
    def stop_trace(self, line, editor):
        if self.debugger.busy:
            return
        if self.debugger.tracing:
            self.debugger.editor = None
            self.debugger.unwatch()
        editor.MarkerAdd(line, 4)
    
    def on_trace_begin(self, frame):
        """Called when set-trace."""
        self.message("Debugger has started tracing {}.".format(frame))
    
    def on_trace_hook(self, frame):
        """Called when a breakpoint is reached."""
        self.message("Debugger hooked {}".format(frame))
    
    def on_trace_end(self, frame):
        """Called when unset-trace."""
        self.message("Debugger has stopped tracing {}.".format(frame))
    
    def on_monitor_begin(self, widget):
        """Called when monitor watch."""
        self.inspector.set_colour(widget, 'blue')
        self.load(widget)
    
    def on_monitor_end(self, widget):
        """Called when monitor unwatch."""
        self.inspector.set_colour(widget, 'black')
    
    def on_title_window(self, obj):
        """Set title to the frame."""
        self.SetTitle("Nautilus - {}".format(
                      obj if isinstance(obj, str) else repr(obj)))
    
    def on_caption_page(self, page, caption):
        """Set caption to the tab control."""
        try:
            ## the page must have parent:AuiNotebook
            page.Parent.set_page_caption(page, caption)
        except AttributeError:
            pass
    
    def add_log(self, text):
        """Add text to the logging buffer."""
        buffer = self.Log.default_buffer
        buffer.text += text
        if self.Log.buffer is buffer:
            with self.Log.off_readonly():
                self.Log.Text = buffer.text
        ## Logging text every step in case of crash.
        with open(self.LOGGING_FILE, 'a', encoding='utf-8', newline='') as f:
            f.write(text)
    
    def add_help(self, text):
        """Add text to the help buffer."""
        with self.Help.off_readonly():
            self.Help.Text = text
        self.popup_window(self.Help, focus=0)
    
    def add_history(self, text, noerr=None):
        """Add text to the history buffer."""
        if not text or text.isspace():
            return
        with self.History.off_readonly() as ed:
            ed.goto_char(ed.TextLength) # line to set an arrow marker
            ed.write(text)
            if noerr is not None:
                ed.MarkerAdd(ed.cline, 1 if noerr else 2) # 1:white 2:red-arrow
    
    def other_editor(self, p=1, mod=True):
        "Move focus to other page (no loop)"
        win = wx.Window.FindFocus()
        nb = win.Parent
        if nb in (self.console, self.ghost):
            j = nb.Selection + p
            if mod:
                j %= nb.PageCount
            nb.Selection = j
    
    def other_window(self, p=1, mod=True):
        "Move focus to other window"
        win = wx.Window.FindFocus()
        pages = [win for win in self.all_pages() if win.IsShownOnScreen()]
        if win in pages:
            j = pages.index(win) + p
            if mod:
                j %= len(pages)
            pages[j].SetFocus()
    
    def add_shell(self, shell, caption=None):
        self.console.AddPage(shell, caption or typename(shell.target))
        shell.SetFocus()
    
    def clear_shell(self):
        """Clear the current shell."""
        shell = self.current_shell
        shell.clear()
    
    def clone_shell(self, target=None):
        """Clone the current shell."""
        shell = self.current_shell
        return shell.clone(target or shell.target)
    
    def close_shell(self):
        """Close the current shell."""
        shell = self.current_shell
        if shell is self.rootshell:
            ## self.message("- Don't close the root shell.")
            return
        j = self.console.GetPageIndex(shell)
        if j != -1:
            self.console.DeletePage(j) # Destroy the window
    
    ## --------------------------------
    ## Attributes for Nautilus/Editor
    ## --------------------------------
    
    def all_pages(self, type=None):
        """Yields all pages of the specified type in the notebooks."""
        yield from self.console.all_pages(type)
        yield from self.ghost.all_pages(type)
    
    @property
    def current_editor(self):
        """Currently focused editor or shell."""
        win = wx.Window.FindFocus()
        if win in self.all_pages(stc.StyledTextCtrl):
            return win
    
    @property
    def current_shell(self):
        """Currently selected shell or rootshell."""
        page = self.console.CurrentPage
        if isinstance(page, type(self.rootshell)): #<Nautilus>
            return page
        return self.rootshell
    
    ## --------------------------------
    ## Find text dialog
    ## --------------------------------
    ## *** The following code is a modification of <wx.py.frame.Frame> ***
    
    __find_target = None
    
    def OnFindText(self, evt):
        if self.findDlg is not None:
            self.findDlg.SetFocus()
            return
        
        win = self.current_editor or self.current_shell
        self.__find_target = win
        self.findData.FindString = win.topic_at_caret
        self.findDlg = wx.FindReplaceDialog(win, self.findData, "Find",
                            style=(wx.FR_NOWHOLEWORD | wx.FR_NOUPDOWN))
        self.findDlg.Show()
    
    def OnFindNext(self, evt, backward=False): #<wx._core.FindDialogEvent>
        data = self.findData
        down_p = data.Flags & wx.FR_DOWN
        if (backward and down_p) or (not backward and not down_p):
            data.Flags ^= wx.FR_DOWN # toggle up/down flag
        
        win = self.current_editor or self.__find_target or self.current_shell
        win.DoFindNext(data, self.findDlg or win)
        if self.findDlg:
            self.OnFindClose(None)
        win.EnsureVisible(win.cline)
        win.EnsureLineMoreOnScreen(win.cline)
    
    def OnFindPrev(self, evt):
        self.OnFindNext(evt, backward=True)
    
    def OnFindClose(self, evt): #<wx._core.FindDialogEvent>
        self.findDlg.Destroy()
        self.findDlg = None


## Monkey-patch for wx.core
try:
    from wx import core # PY3

    def _EvtHandler_Bind(self, event, handler=None, source=None, id=wx.ID_ANY, id2=wx.ID_ANY):
        """
        Bind an event to an event handler.
        (override) to recode and return handler
        """
        assert isinstance(event, wx.PyEventBinder)
        assert source is None or hasattr(source, 'GetId')
        if handler is None:
            return lambda f: _EvtHandler_Bind(self, event, f, source, id, id2)
        if source is not None:
            id  = source.GetId()
        event.Bind(self, id, id2, handler)
        ## record all handlers: single state machine
        if not hasattr(self, '__event_handler__'):
            self.__event_handler__ = {}
        if event.typeId not in self.__event_handler__:
            self.__event_handler__[event.typeId] = [handler]
        else:
            self.__event_handler__[event.typeId].insert(0, handler)
        return handler
    
    core.EvtHandler.Bind = _EvtHandler_Bind
    ## del _EvtHandler_Bind

    def _EvtHandler_Unbind(self, event, source=None, id=wx.ID_ANY, id2=wx.ID_ANY, handler=None):
        """
        Disconnects the event handler binding for event from `self`.
        Returns ``True`` if successful.
        (override) to remove handler
        """
        if source is not None:
            id  = source.GetId()
        retval = event.Unbind(self, id, id2, handler)
        ## remove the specified handler or all handlers
        if retval:
            try:
                actions = self.__event_handler__[event.typeId]
                if handler is None:
                    actions.clear()
                else:
                    actions.remove(handler)
                if not actions:
                    del self.__event_handler__[event.typeId]
            except Exception:
                pass
        return retval
    
    core.EvtHandler.Unbind = _EvtHandler_Unbind
    ## del _EvtHandler_Unbind

    del core

except ImportError as e:
    print("- {!r}".format(e))
    print("Python {}".format(sys.version))
    print("wxPython {}".format(wx.version()))
    pass


def timeit(f, *args, **kwargs):
    from timeit import timeit
    try:
        dt = timeit(lambda: f(*args, **kwargs), number=1)
        print("... duration time: {:g} s".format(dt))
    except TypeError as e:
        print(e)


def profile(obj, *args, **kwargs):
    from profile import Profile
    pr = Profile()
    pr.runcall(obj, *args, **kwargs)
    pr.print_stats()


def watchit(widget=None, **kwargs):
    """Diver's watch to go deep into the wx process to inspect the widget.
    Wx.py tool for watching tree structure and events across the wx.Objects.
    
    Args:
        **kwargs: InspectionTool arguments such as
                  pos, size, conifg, locals, and app
    """
    from wx.lib.inspection import InspectionTool
    if widget:
        kwargs.update(locals=widget.__dict__)
    it = InspectionTool()
    it.Init(**kwargs)
    it.Show(widget)
    return it._frame


def monit(widget=None, **kwargs):
    """Wx.py tool for watching events of the widget.
    """
    from wx.lib.eventwatcher import EventWatcher
    ew = EventWatcher(None, **kwargs)
    ew.watch(widget)
    ew.Show()
    return ew


def filling(obj=None, label=None, **kwargs):
    """Wx.py tool for watching ingredients of the widget.
    """
    from wx.py.filling import FillingFrame
    frame = FillingFrame(rootObject=obj,
                         rootLabel=label or typename(obj),
                         static=False, # update each time pushed
                         **kwargs)
    frame.filling.text.WrapMode = 0 # no wrap
    frame.filling.text.Zoom = -1 # zoom level of size of fonts
    frame.Show()
    return frame


if __name__ == "__main__":
    from mwx.nutshell import Editor
    
    SHELLSTARTUP = """
if 1:
    self
    dive(self.shellframe)
    dive(self.shellframe.rootshell)
    """
    ## import numpy as np
    ## from scipy import constants as const
    ## np.set_printoptions(linewidth=256) # default 75
    
    app = wx.App()
    frm = Frame(None,
        title=repr(Frame),
        style=wx.DEFAULT_FRAME_STYLE, #&~(wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX),
        size=(200,80),
    )
    frm.editor = Editor(frm)
    
    frm.handler.debug = 4
    frm.editor.handler.debug = 4
    frm.shellframe.handler.debug = 4
    frm.shellframe.rootshell.handler.debug = 4
    
    frm.shellframe.Show()
    frm.shellframe.rootshell.SetFocus()
    frm.shellframe.rootshell.Execute(SHELLSTARTUP)
    frm.shellframe.debugger.skip.remove(FSM.__module__)
    frm.Show()
    app.MainLoop()
