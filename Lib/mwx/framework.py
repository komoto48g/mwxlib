#! python3
# -*- coding: utf-8 -*-
"""mwxlib framework

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
__version__ = "0.84.4"
__author__ = "Kazuya O'moto <komoto@jeol.co.jp>"

from functools import wraps, partial
from importlib import reload
import traceback
import builtins
import datetime
import textwrap
import time
import sys
import os
import re
import wx
from wx import aui
from wx import stc
from wx.py import dispatcher

from .utilus import funcall as _F
from .utilus import FSM, TreeList, apropos, typename, where, mro, pp
from .utilus import get_rootpath


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

def speckey_state(key):
    """Returns GetKeyState for abbreviation key:str."""
    try:
        return wx.GetKeyState(_speckeys_wxkmap[key])
    except KeyError:
        pass
_speckeys_wxkmap = dict((v, k) for k, v in _speckeys.items())


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
    
    key = _speckeys.get(key) or chr(key).lower()
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


class KeyCtrlInterfaceMixin:
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
                    '* pressed' : [ state, self.post_command_hook ],
                 '*alt pressed' : [ keymap, _Pass ],
                '*ctrl pressed' : [ keymap, _Pass ],
               '*shift pressed' : [ keymap, _Pass ],
             '*[LR]win pressed' : [ keymap, _Pass ],
            },
        })
    
    def pre_command_hook(self, evt):
        """Enter extension mode.
        Check text selection for [C-c/C-x].
        """
        wnd = wx.Window.FindFocus()
        if isinstance(wnd, wx.TextEntry) and wnd.StringSelection\
        or isinstance(wnd, stc.StyledTextCtrl) and wnd.SelectedText:
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
            _f = _F(action, *args, **kwargs)
            @wraps(_f)
            def f(*v, **kw):
                self.message(f.__name__)
                return _f(*v, **kw)
            if map != state:
                self.handler.update({map: {key: [state, self.post_command_hook, f]}})
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


class CtrlInterface(KeyCtrlInterfaceMixin):
    """Mouse/Key event interface mixin
    """
    handler = property(lambda self: self.__handler)
    
    def __init__(self):
        self.__key = ''
        self.__handler = FSM({None:{}, 0:{}}, default=0)
        
        _M = self._mouse_handler
        
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
        self.Bind(wx.EVT_LEFT_DCLICK, lambda v: _M('Lbutton dblclick', v))
        self.Bind(wx.EVT_RIGHT_DCLICK, lambda v: _M('Rbutton dblclick', v))
        self.Bind(wx.EVT_MIDDLE_DCLICK, lambda v: _M('Mbutton dblclick', v))
        
        self.Bind(wx.EVT_MOUSE_AUX1_UP, lambda v: _M('Xbutton1 released', v))
        self.Bind(wx.EVT_MOUSE_AUX2_UP, lambda v: _M('Xbutton2 released', v))
        self.Bind(wx.EVT_MOUSE_AUX1_DOWN, lambda v: _M('Xbutton1 pressed', v))
        self.Bind(wx.EVT_MOUSE_AUX2_DOWN, lambda v: _M('Xbutton2 pressed', v))
        self.Bind(wx.EVT_MOUSE_AUX1_DCLICK, lambda v: _M('Xbutton1 dblclick', v))
        self.Bind(wx.EVT_MOUSE_AUX2_DCLICK, lambda v: _M('Xbutton2 dblclick', v))
    
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
        Trigger event: 'key+[LMRX]button pressed/released/dblclick'
        """
        event = self.__key + event # 'C-M-S-K+[LMRX]button pressed/released/dblclick'
        key, sep, st = event.rpartition(' ') # removes st:'pressed/released/dblclick'
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
                    owner.Bind(wx.EVT_MENU, handlers[0], menu_item)
                    owner.Bind(wx.EVT_UPDATE_UI, handlers[1], menu_item)
                    owner.Bind(wx.EVT_MENU_HIGHLIGHT, handlers[2], menu_item)
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
                self.Enable(submenu_item.Id, len(subitems)) # Disable an empty menu.
                submenu.Id = submenu_item.Id # <- ID_ANY (dummy to check empty sbumenu)
    
    @staticmethod
    def Popup(parent, menu, *args, **kwargs):
        menu = Menu(parent, menu)
        parent.PopupMenu(menu, *args, **kwargs)
        menu.Destroy()


class MenuBar(wx.MenuBar, TreeList):
    """MenuBar control
    
    Construct menubar in the order of menu<TreeList>::
    
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
        if self.Parent:
            menu = self.getmenu(key)
            if not menu:
                self.reset()
                return
            
            for item in menu.MenuItems: # delete all items
                self.Parent.Unbind(wx.EVT_MENU, item)
                self.Parent.Unbind(wx.EVT_UPDATE_UI, item)
                self.Parent.Unbind(wx.EVT_MENU_HIGHLIGHT, item)
                menu.Delete(item)
            
            menu2 = Menu(self.Parent, self[key]) # new menu2 to swap menu
            for item in menu2.MenuItems:
                menu.Append(menu2.Remove(item)) # 重複しないようにいったん切り離して追加する
            
            if hasattr(menu, 'Id'):
                self.Enable(menu.Id, menu.MenuItemCount > 0) # Disable empty submenu.
    
    def reset(self):
        """Recreates menubar if the Parent were attached by SetMenuBar.
        Call when the menulist is changed.
        """
        if self.Parent:
            for j in range(self.GetMenuCount()): # remove and del all top-level menu
                menu = self.Remove(0)
                for item in menu.MenuItems: # delete all items
                    self.Parent.Unbind(wx.EVT_MENU, item)
                    self.Parent.Unbind(wx.EVT_UPDATE_UI, item)
                    self.Parent.Unbind(wx.EVT_MENU_HIGHLIGHT, item)
                menu.Destroy()
            
            for j, (key, values) in enumerate(self):
                menu = Menu(self.Parent, values)
                self.Append(menu, key)
                if not values:
                    self.EnableTop(j, False) # Disable empty main menu.


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
    
    def message(self, *args, **kwargs):
        if self.statusbar:
            return self.statusbar(*args, **kwargs)
    
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
                   '* released' : (0, skip),
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
    
    def message(self, *args, **kwargs):
        if self.statusbar:
            return self.statusbar(*args, **kwargs)
    
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
                   '* released' : (0, skip),
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
            ^ aui.AUI_NB_CLOSE_ON_ACTIVE_TAB
            ^ aui.AUI_NB_MIDDLE_CLICK_CLOSE
        )
        aui.AuiNotebook.__init__(self, *args, **kwargs)
        
        self._mgr = self.EventHandler # internal use only
        
        self.Bind(aui.EVT_AUINOTEBOOK_TAB_RIGHT_DOWN, self.on_show_menu)
    
    def on_show_menu(self, evt): #<wx._aui.AuiNotebookEvent>
        obj = evt.EventObject
        try:
            win = obj.Pages[evt.Selection].window # GetPage for split notebook
            Menu.Popup(self, win.menu)
        except AttributeError:
            evt.Skip()
    
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
                self.Selection = j # the focus is moved
            if wnd and wnd is not org: # restore focus other window
                wnd.SetFocus()
            return win
    
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
    
    ## Note: Should be called after all pages have been added.
    @postcall
    def loadPerspective(self, spec):
        """Loads a saved perspective.
        
        Note:
            This function will be called after the session is loaded.
            At that point, some pages may be missing.
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
            
            ## all_names = [self.find_tab(win)[1].caption for win in self.all_pages]
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
            print("- Failed to load perspective: {}".format(e))
            pass
        finally:
            self.Parent.Thaw()


class ShellFrame(MiniFrame):
    """MiniFrame of the Shell.
    
    Args:
        target  : target object of the rootshell.
                  If None, it will be `__main__`.
        debrc   : session file for deb run command.
                  SESSION_FILE will be overwritten.
        ensureClose : A flag for the shell standalone.
                      If True, EVT_CLOSE will close the window.
                      Otherwise it will be only hidden.
        **kwargs    : Nautilus arguments
    
    Attributes:
        console     : Notebook of shells
        ghost       : Notebook of editors/buffers
        watcher     : Notebook of global/locals watcher
        Scratch     : Book of scratch (tooltip)
        Help        : Book of help
        Log         : Book of logging
        History     : Book of shell history
        monitor     : wxmon.EventMonitor object
        inspector   : wxwit.Inspector object
        debugger    : wxpdb.Debugger object
        ginfo/linfo : globals/locals list
    
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
        @load       : Load file in Log.
        @where      : Displays filename:lineno or the module name.
        @mro        : Displays mro list and filename:lineno or the module name.
        @debug      : Open pdb or event-monitor.
        @highlight  : Highlight the widget.
    """
    rootshell = property(lambda self: self.__shell) #: the root shell
    
    def __init__(self, parent, target=None, debrc=None, ensureClose=False,
                 title=None, size=(1280,720), style=wx.DEFAULT_FRAME_STYLE,
                 **kwargs):
        MiniFrame.__init__(self, parent, size=size, style=style)
        
        self.statusbar.resize((-1,120))
        self.statusbar.Show(1)
        
        if debrc:
            self.SESSION_FILE = os.path.abspath(debrc)
        
        self.__standalone = bool(ensureClose)
        
        ## Add useful global abbreviations to builtins
        builtins.apropos = apropos
        builtins.typename = typename
        builtins.reload = reload
        builtins.partial = partial
        builtins.p = print
        builtins.pp = pp
        builtins.mro = mro
        builtins.where = where
        builtins.filling = filling
        builtins.profile = profile
        builtins.timeit = timeit
        builtins.info = self.info
        builtins.help = self.help
        builtins.dive = self.clone_shell
        builtins.load = self.load
        builtins.debug = self.debug
        builtins.watch = self.watch
        builtins.highlight = self.highlight
        
        from .nutshell import Nautilus, EditorBook
        
        self.__shell = Nautilus(self,
                                target or __import__("__main__"),
                                style=(wx.CLIP_CHILDREN | wx.BORDER_NONE),
                                **kwargs)
        
        self.Scratch = EditorBook(self, name="Scratch")
        self.Log = EditorBook(self, name="Log")
        self.Help = EditorBook(self, name="Help")
        self.History = EditorBook(self, name="History")
        
        from .wxpdb import Debugger
        from .wxwit import Inspector
        from .wxmon import EventMonitor
        from .wxwil import LocalsWatcher
        from .controls import Icon, Indicator
        
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
        self.inspector = Inspector(self, name="Inspector")
        self.monitor = EventMonitor(self, name="Monitor")
        self.ginfo = LocalsWatcher(self, name="globals")
        self.linfo = LocalsWatcher(self, name="locals")
        
        self.console = AuiNotebook(self, size=(600,400))
        self.console.AddPage(self.__shell, "root", bitmap=Icon('core'))
        self.console.TabCtrlHeight = 0
        self.console.Name = "console"
        
        ## self.console.Bind(aui.EVT_AUINOTEBOOK_BUTTON, self.OnConsoleCloseBtn)
        self.console.Bind(aui.EVT_AUINOTEBOOK_PAGE_CLOSE, self.OnConsolePageClose)
        self.console.Bind(aui.EVT_AUINOTEBOOK_PAGE_CHANGED, self.OnConsolePageChanged)
        
        self.ghost = AuiNotebook(self, size=(600,400))
        self.ghost.AddPage(self.Scratch, "Scratch")
        self.ghost.AddPage(self.Log,     "Log")
        self.ghost.AddPage(self.Help,    "Help")
        self.ghost.AddPage(self.History, "History")
        self.ghost.Name = "ghost"
        
        ## self.ghost.Bind(wx.EVT_SHOW, self.OnGhostShow)
        
        self.watcher = AuiNotebook(self, size=(300,200))
        self.watcher.AddPage(self.ginfo, "globals")
        self.watcher.AddPage(self.linfo, "locals")
        self.watcher.AddPage(self.monitor, "Monitor", bitmap=Icon('ghost'))
        self.watcher.AddPage(self.inspector, "Inspector", bitmap=Icon('inspect'))
        self.watcher.Name = "watcher"
        
        self.watcher.Bind(wx.EVT_SHOW, self.OnGhostShow)
        
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
                             .Caption("Watchdog in the Shell").Right().Position(1).Show(0))
        
        self._mgr.Update()
        
        self.Unbind(wx.EVT_CLOSE)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(wx.EVT_SHOW, self.OnShow)
        
        self.__autoload = True
        
        def on_activate(evt):
            evt.Skip()
            if not evt.Active:
                ## Reset autoload when active focus going outside.
                self.__autoload = True
            elif evt.GetActivationReason() == evt.Reason_Mouse\
              and self.__autoload:
                ## Check all buffers that need to be loaded.
                for book in self.all_books:
                    for buf in book.all_buffers:
                        if buf.need_buffer_load:
                            if wx.MessageBox( # Confirm load.
                                    "The file has been modified externally.\n\n"
                                    "The contents of the buffer will be overwritten.\n"
                                    "Continue loading?",
                                    "Load {!r}".format(buf.name),
                                    style=wx.YES_NO|wx.ICON_INFORMATION) != wx.YES:
                                self.__autoload = False # Don't ask any more.
                                return
                            book.load_file(buf)
        self.Bind(wx.EVT_ACTIVATE, on_activate)
        
        self.findDlg = None
        self.findData = wx.FindReplaceData(wx.FR_DOWN | wx.FR_MATCHCASE)
        
        self.Bind(wx.EVT_FIND, self.OnFindNext)
        self.Bind(wx.EVT_FIND_NEXT, self.OnFindNext)
        self.Bind(wx.EVT_FIND_CLOSE, self.OnFindClose)
        
        self.indicator = Indicator(self.statusbar, value=1, tip='Normal')
        self.indicator.background = None # wx.SystemSettings.GetColour(wx.SYS_COLOUR_MENU)
        self.indicator.ToolTip = "[R] Invalid [Y] Debug/Trace [G] Normal"
        
        self.timer = wx.Timer(self)
        self.timer.Start(1000)
        
        def on_timer(evt):
            if self.indicator.Value not in (1, 3):
                self.indicator.blink(500)
            evt.Skip()
        self.Bind(wx.EVT_TIMER, on_timer)
        
        def on_size(evt):
            rect = self.statusbar.GetFieldRect(1)
            self.indicator.Position = (-44+rect.x, 2+rect.y)
            evt.Skip()
        self.Bind(wx.EVT_SIZE, on_size)
        
        def skip(v):
            if self.debugger.handler.current_state:
                if self.debugger.tracing:
                    self.message("- The current status is tracing. "
                                 "- Press [C-g] to quit.")
                elif not self.debugger.busy:
                    self.message("- The current status is inconsistent. "
                                 "- Press [C-g] to quit.")
                    self.indicator.Value = 7
            v.Skip()
        
        def dispatch(v):
            """Fork key events to the debugger."""
            self.debugger.handler(self.handler.current_event, v)
        
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
                    'shell_new' : [ None, ],
                      'add_log' : [ None, self.add_log ],
                     'add_help' : [ None, self.add_help ],
                  'add_history' : [ None, self.add_history ],
                 'title_window' : [ None, self.on_title_window ],
            },
            0 : {
                    '* pressed' : (0, skip, dispatch), # => debugger
                   '* released' : (0, skip, dispatch), # => debugger
                  'C-g pressed' : (0, self.Quit, skip, dispatch), # => debugger
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
            },
        })
        
        ## py-mode
        self.Scratch.set_attributes(Style=Nautilus.STYLE)
        
        self.set_hookable(self.Scratch)
        
        @self.Scratch.define_key('C-j')
        def eval_line():
            shell = self.current_shell
            self.Scratch.buffer.py_eval_line(shell.globals, shell.locals)
        
        @self.Scratch.define_key('M-j')
        def exec_buffer():
            shell = self.current_shell
            self.Scratch.buffer.py_exec_region(shell.globals, shell.locals)
        
        ## text-mode
        self.set_hookable(self.Log)
        
        self.Log.set_attributes(ReadOnly=True)
        self.Help.set_attributes(ReadOnly=True)
        self.History.set_attributes(ReadOnly=True)
        
        self.Init()
    
    SESSION_FILE = get_rootpath(".debrc")
    SCRATCH_FILE = get_rootpath("scratch.py")
    LOGGING_FILE = get_rootpath("deb-logging.log")
    HISTORY_FILE = get_rootpath("deb-history.log")
    
    def load_session(self, rc=None, flush=True):
        """Load session from file."""
        if not rc:
            with wx.FileDialog(self, 'Load session',
                    wildcard="Session file (*.debrc)|*.debrc",
                    style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST|wx.FD_CHANGE_DIR) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                rc = dlg.Path
        
        if flush:
            for book in self.all_books:
                book.delete_all_buffers()
        
        self.SESSION_FILE = os.path.abspath(rc)
        try:
            scratch = self.Scratch.default_buffer
            if not scratch or scratch.mtdelta is not None:
                scratch = self.Scratch.new_buffer()
            scratch.LoadFile(self.SCRATCH_FILE)
        except FileNotFoundError as e:
            print(e)
        try:
            with open(self.SESSION_FILE, encoding='utf-8', newline='') as i:
                exec(i.read())
        except Exception:
            ## pass
            traceback.print_exc()
    
    def save_session_as(self):
        """Save session as a new file."""
        with wx.FileDialog(self, "Save session as",
                defaultFile=self.SESSION_FILE or '',
                wildcard="Session file (*.debrc)|*.debrc",
                style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.SESSION_FILE = dlg.Path
                self.save_session()
    
    def save_session(self):
        """Save session to file."""
        scratch = self.Scratch.default_buffer
        if scratch and scratch.mtdelta is None:
            scratch.SaveFile(self.SCRATCH_FILE)
        
        with open(self.SESSION_FILE, 'w', encoding='utf-8', newline='') as o:
            o.write("#! Session file (This file is generated automatically)\n")
            
            for book in self.all_books:
                for buf in book.all_buffers:
                    if buf.mtdelta is not None:
                        o.write("self._load({!r}, {!r}, {!r})\n"
                                .format(buf.filename, buf.markline+1, book.Name))
            o.write('\n'.join((
                "self.SetSize({})".format(self.Size),
                "self.SetPosition({})".format(self.Position),
                "self.ghost.SetSelection({})".format(self.ghost.Selection),
                "self.watcher.SetSelection({})".format(self.watcher.Selection),
                "self._mgr.LoadPerspective({!r})".format(self._mgr.SavePerspective()),
                "self.ghost.loadPerspective({!r})".format(self.ghost.savePerspective()),
                "self.watcher.loadPerspective({!r})".format(self.watcher.savePerspective()),
                ## "self._mgr.GetPane('ghost').FloatingPosition(self.Position)",
                ## "self._mgr.GetPane('watcher').FloatingPosition(self.Position)",
                "self._mgr.Update()\n",
            )))
    
    def Init(self):
        msg = "#! Opened: <{}>\r\n".format(datetime.datetime.now())
        self.add_history(msg)
        self.add_log(msg)
        self.load_session(self.SESSION_FILE)
    
    def Destroy(self):
        try:
            self.timer.Stop()
            self.save_session()
            if self.Log.default_buffer:
                self.Log.default_buffer.SaveFile(self.LOGGING_FILE)
            if self.History.default_buffer:
                self.History.default_buffer.SaveFile(self.HISTORY_FILE)
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
        
        for book in self.all_books:
            for buf in book.all_buffers:
                if buf.need_buffer_save:
                    self.popup_window(book)
                    buf.SetFocus()
                    if wx.MessageBox( # Confirm close.
                            "You are closing unsaved content.\n\n"
                            "Changes to the content will be discarded.\n"
                            "Continue closing?",
                            "Close {!r}".format(buf.name),
                            style=wx.YES_NO|wx.ICON_INFORMATION) != wx.YES:
                        self.message("The close has been canceled.")
                        evt.Veto()
                        return
        if self.__standalone:
            evt.Skip() # Close the window
        else:
            self.Show(0) # Don't destroy the window
    
    def OnShow(self, evt):
        pane = self._mgr.GetPane(self.watcher)
        if evt.IsShown():
            if pane.IsShown():
                self.inspector.watch() # restart
                self.monitor.watch()
        else:
            if pane.IsDocked():
                self.inspector.unwatch()
                self.monitor.unwatch()
                self.ginfo.unwatch()
                self.linfo.unwatch()
        evt.Skip()
    
    def OnGhostShow(self, evt):
        if evt.IsShown():
            self.inspector.watch() # restart
            self.monitor.watch()
        else:
            self.inspector.unwatch()
            self.monitor.unwatch()
            self.ginfo.unwatch()
            self.linfo.unwatch()
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
        ## win = nb.CurrentPage # NG
        win = nb.all_pages[evt.Selection]
        if win is self.rootshell:
            ## self.message("- Don't close the root shell.")
            nb.WindowStyle &= ~aui.AUI_NB_CLOSE_ON_ACTIVE_TAB
            evt.Veto()
        elif self.debugger.busy and win is self.debugger.interactive_shell:
            wx.MessageBox("The debugger is running.\n\n"
                          "Enter [q]uit to exit before closing.")
            evt.Veto()
        else:
            evt.Skip()
    
    def About(self, evt=None):
        buf = self.Help.buffer
        with buf.off_readonly():
            buf.SetText('\n\n'.join((
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
        self.popup_window(win, show=None, focus=focus)
    
    def popup_window(self, win, show=True, focus=True):
        """Show the notebook page and move the focus.
        
        Args:
            win  : window to popup
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
        
        if wnd and win.IsShown(): # restore focus
            wnd.SetFocus()
        
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
        ## self.inspector.unwatch()
        self.monitor.unwatch()
        self.ginfo.unwatch()
        self.linfo.unwatch()
        self.debugger.unwatch()
        self.debugger.send_input('\n') # terminates the reader
        shell = self.debugger.interactive_shell # reset interp locals
        del shell.locals
        del shell.globals
        self.indicator.Value = 1
        self.message("Quit")
    
    def _load(self, filename, lineno, bookname):
        """Load file in the session (internal use only)."""
        try:
            book = getattr(self, bookname)
            return self.load(filename, lineno, book, show=0)
        except Exception:
            pass
    
    def load(self, filename, lineno=0, book=None, show=True, focus=False):
        """Load file @where the object is defined.
        
        Args:
            filename : target filename:str or object.
                       It also supports <'filename:lineno'> format.
            lineno   : Set mark to lineno on load.
            book     : book of the buffer to load.
            show     : Show the book.
            focus    : Set the focus if the window is displayed.
        """
        if not isinstance(filename, str):
            filename = where(filename)
            if filename is None:
                return False
        if not lineno:
            m = re.match("(.*?):([0-9]+)", filename)
            if m:
                filename, ln = m.groups()
                lineno = int(ln)
        if not book:
            book = next((x for x in self.all_books
                            if x.find_buffer(filename)), self.Log)
        if show:
            self.popup_window(book, focus=focus)
        
        if re.match(r"https?://[\w/:%#\$&\?()~.=+-]+", filename): # url_re
            return book.load_url(filename, lineno)
        else:
            return book.load_file(filename, lineno)
    
    def info(self, obj):
        self.rootshell.info(obj)
    
    def help(self, obj):
        self.rootshell.help(obj)
    
    def watch(self, obj):
        self.monitor.watch(obj)
        if obj:
            self.popup_window(self.monitor, focus=0)
            self.linfo.watch(obj.__dict__)
            self.ginfo.watch({})
    
    def highlight(self, obj, *args, **kwargs):
        self.inspector.highlight(obj, *args, **kwargs)
    
    ## Note: history 変数に余計な文字列が入らないようにする
    @postcall
    def debug(self, obj, *args, **kwargs):
        if isinstance(obj, wx.Object) or obj is None:
            if args or kwargs:
                self.message("- Args:{} and kwargs:{} were given,"
                             " but ignored for object monitoring.")
            self.monitor.watch(obj)
            if obj:
                self.popup_window(self.monitor, focus=0)
                self.linfo.watch(obj.__dict__)
                self.ginfo.watch({})
        elif isinstance(obj, type(print)):
            wx.MessageBox("Builtin method or function.\n\n"
                          "Unable to debug {!r}".format(obj))
        elif callable(obj):
            try:
                shell = self.debugger.interactive_shell
                self.debugger.interactive_shell = self.current_shell
                self.debugger.editor = self.Log # set default logger
                self.debugger.debug(obj, *args, **kwargs)
            finally:
                self.debugger.interactive_shell = shell
        elif isinstance(obj, str):
            try:
                shell = self.debugger.interactive_shell
                self.debugger.interactive_shell = self.current_shell
                self.debugger.editor = self.Log # set default logger
                filename = "<string>"
                buf = self.Log.find_buffer(filename) or self.Log.create_buffer(filename)
                with buf.off_readonly():
                    buf.Text = obj
                self.debugger.run(obj)
            finally:
                self.debugger.interactive_shell = shell
        elif hasattr(obj, '__dict__'):
            self.message("Building locals info list...")
            self.linfo.watch(obj.__dict__)
            self.ginfo.watch({})
            self.popup_window(self.linfo, focus=0)
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
        self.indicator.Value = 2
    
    def on_debug_next(self, frame):
        """Called from cmdloop."""
        shell = self.debugger.interactive_shell
        shell.globals = gs = frame.f_globals
        shell.locals = ls = frame.f_locals
        if self.ginfo.target is not gs:
            self.ginfo.watch(gs)
        if self.linfo.target is not ls:
            self.linfo.watch(ls)
        self.on_title_window(frame)
        self.popup_window(self.debugger.editor, focus=0)
        dispatcher.send(signal='Interpreter.push',
                        sender=shell, command=None, more=False)
        command = shell.cmdline
        if command and not command.isspace():
            command = re.sub(r"^(.*)", r"    \1", command, flags=re.M)
            self.add_log(command)
        self.message("Debugger is busy now (Press [C-g] to quit).")
    
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
        self.indicator.Value = 1
    
    def set_hookable(self, book, traceable=True):
        """Bind pointer to set/unset trace."""
        if traceable:
            book.handler.bind('pointer_set', _F(self.start_trace, book=book))
            book.handler.bind('pointer_unset', _F(self.stop_trace, book=book))
        else:
            book.handler.unbind('pointer_set')
            book.handler.unbind('pointer_unset')
    
    set_traceable = set_hookable # for backward compatibility
    
    def start_trace(self, line, book):
        if not self.debugger.busy:
            self.debugger.unwatch()
            self.debugger.editor = book
            self.debugger.watch((book.buffer.filename, line+1))
            self.debugger.send_input('') # clear input
        book.buffer.del_marker(4)
    
    def stop_trace(self, line, book):
        if self.debugger.busy:
            return
        if self.debugger.tracing:
            self.debugger.editor = None
            self.debugger.unwatch()
        book.buffer.set_marker(line, 4)
    
    def on_trace_begin(self, frame):
        """Called when set-trace."""
        self.message("Debugger has started tracing {!r}.".format(frame))
        self.indicator.Value = 3
    
    def on_trace_hook(self, frame):
        """Called when a breakpoint is reached."""
        self.message("Debugger hooked {!r}".format(frame))
    
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
    
    def add_log(self, text):
        """Add text to the logging buffer."""
        buf = self.Log.default_buffer or self.Log.new_buffer()
        with buf.off_readonly():
            buf.write(text)
        ## Logging text every step in case of crash.
        with open(self.LOGGING_FILE, 'a', encoding='utf-8', newline='') as o:
            o.write(text)
    
    def add_help(self, text):
        """Add text to the help buffer."""
        buf = self.Help.default_buffer or self.Help.new_buffer()
        with buf.off_readonly():
            buf.SetText(text)
        ## Overwrite text and popup the window.
        self.popup_window(self.Help, focus=0)
        self.Help.swap_page(buf)
    
    def add_history(self, text, noerr=None):
        """Add text to the history buffer."""
        if not text or text.isspace():
            return
        buf = self.History.default_buffer or self.History.new_buffer()
        with buf.off_readonly():
            buf.goto_char(buf.TextLength) # line to set an arrow marker
            buf.write(text)
        ## Set a marker on the current line.
        if noerr is not None:
            buf.add_marker(buf.cline, 1 if noerr else 2) # 1:white 2:red-arrow
    
    def other_window(self, p=1, mod=True):
        "Move focus to other window"
        pages = [x for x in self.get_all_pages() if x.IsShownOnScreen()]
        wnd = wx.Window.FindFocus()
        while wnd:
            if wnd in pages:
                j = pages.index(wnd) + p
                if mod:
                    j %= len(pages)
                pages[j].SetFocus()
                break
            wnd = wnd.Parent
    
    def clone_shell(self, target):
        if not hasattr(target, '__dict__'):
            raise TypeError("Unable to target primitive object: {!r}".format(target))
        
        shell = self.rootshell.__class__(self, target, name="clone",
                    style=(wx.CLIP_CHILDREN | wx.BORDER_NONE),
                    )
        self.handler('shell_new', shell)
        self.console.AddPage(shell, typename(shell.target))
        self.Show()
        self.popup_window(shell, focus=1)
        return shell
    
    def delete_shell(self, shell):
        """Close the current shell."""
        if shell is self.rootshell:
            ## self.message("- Don't close the root shell.")
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
    
    get_pages = get_all_pages # for backward compatibility
    
    @property
    def all_books(self):
        """Yields all books in the notebooks."""
        yield from self.get_all_pages(type(self.Log))
    
    @property
    def current_shell(self):
        """Currently selected shell or rootshell."""
        return self.console.CurrentPage
    
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
                            style=(wx.FR_NOWHOLEWORD | wx.FR_NOUPDOWN))
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


## Monkey-patch for wx.core
try:
    from wx import core # PY3

    def _EvtHandler_Bind(self, event, handler=None, source=None, id=wx.ID_ANY, id2=wx.ID_ANY):
        """
        Bind an event to an event handler.
        (override) Record the handler in the list and return the handler.
        """
        assert isinstance(event, wx.PyEventBinder)
        assert callable(handler) or handler is None
        assert source is None or hasattr(source, 'GetId')
        if handler is None:
            return lambda f: _EvtHandler_Bind(self, event, f, source, id, id2)
        if source is not None:
            id  = source.GetId()
        event.Bind(self, id, id2, handler)
        ## Record all handlers as a single state machine
        try:
            if not hasattr(self, '__event_handler__'):
                self.__event_handler__ = {}
            if event.typeId not in self.__event_handler__:
                self.__event_handler__[event.typeId] = [handler]
            else:
                self.__event_handler__[event.typeId].insert(0, handler)
        except Exception as e:
            print("An error occurred in Bind: {}".format(e))
            t, v, tb = sys.exc_info()
            traceback.print_stack(tb.tb_frame.f_back)
            traceback.print_exc()
        return handler

    core.EvtHandler.Bind = _EvtHandler_Bind
    ## del _EvtHandler_Bind

    def _EvtHandler_Unbind(self, event, source=None, id=wx.ID_ANY, id2=wx.ID_ANY, handler=None):
        """
        Disconnects the event handler binding for event from `self`.
        Returns ``True`` if successful.
        (override) Delete the handler from the list.
        """
        if source is not None:
            id  = source.GetId()
        retval = event.Unbind(self, id, id2, handler)
        ## Remove the specified handler or all handlers
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

## class wxpyInspectionTools:

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


def filling(obj=None, **kwargs):
    """Wx.py tool for watching ingredients of the widget.
    """
    from .py.filling import FillingFrame
    frame = FillingFrame(rootObject=obj,
                         rootLabel=typename(obj),
                         pos=wx.GetMousePosition(),
                         **kwargs)
    frame.filling.text.WrapMode = 0 # no wrap
    frame.filling.text.Zoom = -1 # zoom level of size of fonts
    frame.Show()
    return frame


def timeit(f, *args, **kwargs):
    from timeit import timeit
    try:
        dt = timeit(lambda: f(*args, **kwargs), number=1)
        print("duration time: {:g} s".format(dt))
    except TypeError as e:
        print(e)


def profile(obj, *args, **kwargs):
    from profile import Profile
    pr = Profile()
    pr.runcall(obj, *args, **kwargs)
    pr.print_stats()


def dump(widget=None):
    def _dump(widget):
        for obj in widget.Children:
            yield obj
            yield from _dump(obj) # dump as flatiter
    if widget:
        return list(_dump(widget))
    else:
        return [[w, list(_dump(w))] for w in wx.GetTopLevelWindows()]


if __name__ == "__main__":
    from mwx.nutshell import Buffer
    
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
        style=wx.DEFAULT_FRAME_STYLE,
        size=(200,80),
    )
    frm.editor = Buffer(frm)
    
    frm.handler.debug = 4
    frm.editor.handler.debug = 4
    
    frm.shellframe.Show()
    frm.shellframe.rootshell.SetFocus()
    frm.shellframe.rootshell.Execute(SHELLSTARTUP)
    frm.Show()
    app.MainLoop()
