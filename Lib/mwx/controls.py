#! python3
# -*- coding: utf-8 -*-
"""mwxlib param controller and wx custom controls

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
from functools import wraps
from itertools import chain
import wx
import numpy as np
from numpy import nan, inf
try:
    from utilus import SSM
    from framework import pack, Menu
    import images
except ImportError:
    from .utilus import SSM
    from .framework import pack, Menu
    from . import images
import wx.lib.platebtn as pb
import wx.lib.scrolledpanel as scrolled


class Param(object):
    """Standard Parameter
    
    Args:
        name    : label
        range   : range
        value   : std_value (default is None)
        fmt     : text formatter or format:str (default is '%g')
                  `hex` specifies hexadecimal format
        handler : called when control changed
        updater : called when check changed
        tip     : tooltip:str shown on the associated knobs
    
    Attributes:
        knobs       : knob list
        tip         : doc:str also shown as a tooltip
        callback    : single state machine that handles following events
        
            - control -> when index changed by knobs or reset (handler)
            - check   -> when check ticks on/off (updater)
            - overflow -> when value overflows
            - underflow -> when value underflows
    """
    def __init__(self, name, range=None, value=None, fmt=None,
                 handler=None, updater=None, tip=None):
        self.knobs = []
        self.name = name
        self.range = range
        self.__std_value = value
        self.__value = value if value is not None else self.min
        self.__check = 0
        if fmt is hex:
            self.__eval = lambda v: int(v, 16)
            self.__format = lambda v: '{:04X}'.format(int(v))
        else:
            self.__eval = lambda v: eval(v)
            self.__format = fmt if callable(fmt) else (lambda v: (fmt or "%g") % v)
        self.callback = SSM({
            'control' : [ handler ] if handler else [],
             'update' : [ updater ] if updater else [],
              'check' : [ updater ] if updater else [],
           'overflow' : [],
          'underflow' : [],
        })
        tip = '\n'.join(filter(None, (tip,
                                      handler and handler.__doc__,
                                      updater and updater.__doc__)))
        self.tip = tip.strip()
    
    def __str__(self, v=None):
        v = self.value if v is None else v
        try:
            return self.__format(v)
        except ValueError:
            return str(v)
    
    def __int__(self):
        return int(self.value)
    
    def __float__(self):
        return float(self.value)
    
    def __len__(self):
        return len(self.range)
    
    def bind(self, f=None, target='control'):
        la = self.callback[target]
        if not f:
            return lambda f: self.bind(f, target)
        if f not in la:
            la.append(f)
        return f
    
    def unbind(self, f=None, target='control'):
        la = self.callback[target]
        if not f:
            la[:] = [a for a in la if not callable(a)]
            return
        if f in la:
            la.remove(f)
    
    def reset(self, v=None, backcall=True):
        """Reset value when indexed (by knobs) with callback."""
        if v is None or v == '':
            v = self.std_value
            if v is None:
                return
        elif v == 'nan': v = nan
        elif v == 'inf': v = inf
        elif isinstance(v, str):
            v = self.__eval(v.replace(',', '')) # eliminates commas
        self._set_value(v)
        if backcall:
            self.callback('control', self)
    
    def _set_value(self, v):
        """Set value and check the limit.
        If the value is out of range, modify the value.
        """
        if v is None:
            v = nan
        if v in (nan, inf):
            self.__value = v
            for knob in self.knobs:
                knob.update_ctrl(None)
            return
        elif v == self.__value:
            return
        
        valid = (self.min <= v <= self.max)
        if valid:
            self.__value = v
        elif v < self.min:
            self.__value = self.min
            self.callback('underflow', self)
        else:
            self.__value = self.max
            self.callback('overflow', self)
        for knob in self.knobs:
            knob.update_ctrl(valid, notify=True)
    
    @property
    def check(self):
        """A knob check property (user defined)."""
        return self.__check
    
    @check.setter
    def check(self, v):
        self.__check = v
        self.callback('check', self)
        for knob in self.knobs:
            knob.update_label()
    
    @property
    def name(self):
        return self.__name
    
    @name.setter
    def name(self, v):
        self.__name = v
        for knob in self.knobs:
            knob.update_label()
    
    @property
    def value(self):
        """Current value := std_value + offset"""
        return self.__value
    
    @value.setter
    def value(self, v):
        self._set_value(v)
    
    @property
    def std_value(self):
        """A standard value (default None)."""
        return self.__std_value
    
    @std_value.setter
    def std_value(self, v):
        self.__std_value = v
        for knob in self.knobs:
            knob.update_label()
    
    @property
    def offset(self):
        """Offset value
        If std_value is None, this is the same as value.
        """
        if self.std_value is not None:
            return self.value - self.std_value
        return self.value
    
    @offset.setter
    def offset(self, v):
        if self.std_value is not None:
            if v is not nan: # Note: nan +x is not nan
                v += self.std_value
        self._set_value(v)
    
    min = property(lambda self: self.__range[0])
    max = property(lambda self: self.__range[-1])
    
    @property
    def range(self):
        """Index range"""
        return self.__range
    
    @range.setter
    def range(self, v):
        if v is None:
            self.__range = [nan] # dummy data
        else:
            self.__range = sorted(v)
        for knob in self.knobs:
            knob.update_range() # list range of related knobs
    
    @property
    def index(self):
        """A knob index -> value"""
        return int(np.searchsorted(self.range, self.value))
    
    @index.setter
    def index(self, j):
        n = len(self)
        i = (0 if j<0 else j if j<n else -1)
        self._set_value(self.range[i])


class LParam(Param):
    """Linear Parameter
    
    Args:
        name    : label
        range   : range [min:max:step]
        value   : std_value (default is None)
        fmt     : text formatter or format:str (default is '%g')
                  `hex` specifies hexadecimal format
        handler : called when control changed
        updater : called when check changed
        tip     : tooltip:str shown on the associated knobs
    
    Attributes:
        knobs       : knob list
        tip         : doc:str also shown as a tooltip
        callback    : single state machine that handles following events
        
            - control -> when index changed by knobs or reset (handler)
            - check   -> when check ticks on/off (updater)
            - overflow -> when value overflows
            - underflow -> when value underflows
    """
    min = property(lambda self: self.__min)
    max = property(lambda self: self.__max)
    step = property(lambda self: self.__step)
    
    def __len__(self):
        return 1 + int(round((self.max - self.min) / self.step)) # includes [min,max]
    
    @property
    def range(self):
        """Index range"""
        return np.arange(self.min, self.max + self.step, self.step)
    
    @range.setter
    def range(self, v):
        if v is None:
            v = (0, 0)
        self.__min = v[0]
        self.__max = v[1]
        self.__step = v[2] if len(v) > 2 else 1
        for knob in self.knobs:
            knob.update_range() # linear range of related knobs
    
    @property
    def index(self):
        """A knob index -> value
        Returns -1 if the value is nan or inf.
        """
        if self.value in (nan, inf):
            return -1
        return int(round((self.value - self.min) / self.step))
    
    @index.setter
    def index(self, j):
        return self._set_value(self.min + j * self.step)


## --------------------------------
## Knob unit for Parameter Control 
## --------------------------------

class Knob(wx.Panel):
    """Parameter controller unit
    
    In addition to direct key input to the textctrl,
    [up][down][wheelup][wheeldown] keys can be used,
    with modifiers S- 2x, C- 16x, and M- 256x steps.
    [Mbutton] resets to the std. value if it exists.
    
    Args:
        param   : <Param> or <LParam> object
        type    : ctrl type (slider[*], [hv]spin, choice, None)
        style   : style of label
                  None -> static text (default)
                  chkbox -> label with check box
                  button -> label with flat button
        editable: textctrl is editable or readonly
        lw      : width of label
        tw      : width of textbox
        cw      : width of ctrl
        h       : height of widget (defaults to 22)
    """
    @property
    def param(self):
        """Param object referred from knobs."""
        return self.__par
    
    @param.setter
    def param(self, v):
        self.__par.knobs.remove(self)
        self.__par = v
        self.__par.knobs.append(self)
        self.update_range()
        self.update_ctrl()
    
    def __init__(self, parent, param, type='slider',
                 style=None, editable=1, lw=-1, tw=-1, cw=-1, h=22,
                 **kwargs):
        wx.Panel.__init__(self, parent, **kwargs)
        self.__bit = 1
        self.__par = param
        self.__par.knobs.append(self) # パラメータの関連付けを行う
        
        if type is None:
            type = 'slider'
            cw = 0
        elif type == 'choice':
            if cw < 0:
                cw = 20
            cw += tw
            tw = 0
        
        label = self.__par.name + '  '
        
        if style == 'chkbox':
            if lw >= 0:
                lw += 16
            self.label = wx.CheckBox(self, label=label, size=(lw,-1))
            self.label.Bind(wx.EVT_CHECKBOX, self.OnCheck)
            
        elif style == 'button':
            if lw >= 0:
                lw += 16
            self.label = pb.PlateButton(self, label=label, size=(lw,-1),
                            style=(pb.PB_STYLE_DEFAULT | pb.PB_STYLE_SQUARE))
            self.label.Bind(wx.EVT_BUTTON, self.OnPress)
            
        elif not style:
            self.label = wx.StaticText(self, label=label, size=(lw,-1))
        else:
            raise Exception("unknown style: {!r}".format(style))
        
        self.label.Enable(lw)
        self.label.Bind(wx.EVT_MIDDLE_DOWN, lambda v: self.__par.reset())
        
        self.label.SetToolTip(self.__par.tip)
        
        if editable:
            self.text = wx.TextCtrl(self, size=(tw,h), style=wx.TE_PROCESS_ENTER)
            self.text.Bind(wx.EVT_TEXT_ENTER, self.OnTextEnter)
            self.text.Bind(wx.EVT_KILL_FOCUS, self.OnTextExit)
            self.text.Bind(wx.EVT_KEY_DOWN, self.OnTextKeyDown)
            self.text.Bind(wx.EVT_KEY_UP, self.OnTextKeyUp)
            self.text.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)
            self.text.Bind(wx.EVT_MIDDLE_DOWN, lambda v: self.__par.reset())
        else:
            self.text = wx.TextCtrl(self, size=(tw,h), style=wx.TE_READONLY)
        
        self.text.Enable(tw)
        
        if type == 'slider':
            self.ctrl = wx.Slider(self, size=(cw,h), style=wx.SL_HORIZONTAL)
            self.ctrl.Bind(wx.EVT_SCROLL_CHANGED, self.OnScroll)
            self.ctrl.Bind(wx.EVT_KEY_DOWN, self.OnCtrlKeyDown)
            self.ctrl.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)
            
        elif type == 'slider*':
            self.ctrl = wx.Slider(self, size=(cw,h), style=wx.SL_HORIZONTAL)
            self.ctrl.Bind(wx.EVT_SCROLL, self.OnScroll) # called while dragging
            self.ctrl.Bind(wx.EVT_SCROLL_CHANGED, lambda v: None) # pass no action
            self.ctrl.Bind(wx.EVT_KEY_DOWN, self.OnCtrlKeyDown)
            self.ctrl.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)
            
        elif type == 'spin' or type =='hspin':
            self.ctrl = wx.SpinButton(self, size=(cw,h), style=wx.SP_HORIZONTAL)
            self.ctrl.Bind(wx.EVT_SPIN, self.OnScroll)
            self.ctrl.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)
            
        elif type == 'vspin':
            self.ctrl = wx.SpinButton(self, size=(cw,h), style=wx.SP_VERTICAL)
            self.ctrl.Bind(wx.EVT_SPIN, self.OnScroll)
            self.ctrl.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)
            
        elif type == 'choice':
            self.ctrl = wx.Choice(self, size=(cw,h))
            self.ctrl.Bind(wx.EVT_CHOICE, self.OnScroll)
            self.ctrl.SetValue = self.ctrl.SetSelection # setter of choice
            self.ctrl.GetValue = self.ctrl.GetSelection # getter (ditto)
            
        else:
            raise Exception("unknown type: {!r}".format(type))
        
        c = bool(cw)
        self.ctrl.Enable(c)
        self.ctrl.Bind(wx.EVT_MIDDLE_DOWN, lambda v: self.__par.reset())
        
        self.SetSizer(
            pack(self, (
                (self.label, 0, wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT, lw and 1),
                (self.text,  0, wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT, tw and 1),
                (self.ctrl,  c, wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT, cw and 1),
            ))
        )
        self.update_range()
        self.update_ctrl()
        
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
    
    def OnDestroy(self, evt):
        self.__par.knobs.remove(self) # パラメータの関連付けを解除する
        evt.Skip()
    
    def update_range(self):
        v = self.__par
        if isinstance(self.ctrl, wx.Choice): #<wx.Choice>
            items = [v.__str__(x) for x in v.range]
            if items != self.ctrl.Items:
                self.ctrl.SetItems(items)
        else:
            self.ctrl.SetRange(0, len(v)-1) #<wx.Slider> <wx.SpinButton>
    
    def update_label(self):
        v = self.__par
        if isinstance(self.label, wx.CheckBox):
            self.label.SetValue(bool(v.check))
        
        if self.label.IsEnabled():
            t = '  ' if v.std_value is None or v.value == v.std_value else '*'
            self.label.SetLabel(v.name + t)
            self.label.Refresh()
    
    def update_ctrl(self, valid=True, notify=False):
        v = self.__par
        try:
            j = v.index
        except (OverflowError, ValueError):
            ## OverflowError: cannot convert float infinity to integer
            ## ValueError: cannot convert float NaN to integer
            j = -1
        
        self.ctrl.SetValue(j)
        self.text.SetValue(str(v))
        if valid:
            if notify:
                if self.text.BackgroundColour != '#ffff80':
                    wx.CallAfter(wx.CallLater, 1000,
                        self.set_textcolour, '#ffffff')
                    self.set_textcolour('#ffff80') # light-yellow
            else:
                self.set_textcolour('#ffffff') # True: white
        elif valid is None:
            self.set_textcolour('#ffff80') # None: light-yellow
        else:
            self.set_textcolour('#ff8080') # False: light-red
        self.update_label()
    
    def set_textcolour(self, c):
        if self:
            if self.text.IsEditable():
                self.text.BackgroundColour = c
            self.text.Refresh()
    
    def shift(self, evt, bit):
        if bit:
            if evt.ShiftDown():   bit *= 2
            if evt.ControlDown(): bit *= 16
            if evt.AltDown():     bit *= 256
        v = self.__par
        j = self.ctrl.GetValue() + bit
        if j != v.index:
            v.index = j
            v.reset(v.value)
    
    def OnScroll(self, evt): #<wx._core.ScrollEvent><wx._controls.SpinEvent><wx._core.CommandEvent>
        v = self.__par
        j = self.ctrl.GetValue()
        if j != v.index:
            v.index = j
            v.reset(v.value)
        evt.Skip()
    
    def OnMouseWheel(self, evt): #<wx._core.MouseEvent>
        self.shift(evt, 1 if evt.WheelRotation>0 else -1)
        evt.Skip(False)
    
    def OnCtrlKeyDown(self, evt): #<wx._core.KeyEvent>
        key = evt.GetKeyCode()
        if key == wx.WXK_LEFT: return self.shift(evt, -1)
        if key == wx.WXK_RIGHT: return self.shift(evt, 1)
        
        def focus(c):
            if isinstance(c, Knob) and c.ctrl.IsEnabled():
                c.ctrl.SetFocus()
                return True
        
        ls = next(x for x in self.Parent.layout_groups if self in x)
        i = ls.index(self)
        if key == wx.WXK_DOWN: return any(focus(c) for c in ls[i+1:])
        if key == wx.WXK_UP: return any(focus(c) for c in ls[i-1::-1])
    
    def OnTextKeyUp(self, evt): #<wx._core.KeyEvent>
        evt.Skip()
    
    def OnTextKeyDown(self, evt): #<wx._core.KeyEvent>
        key = evt.GetKeyCode()
        if key == wx.WXK_DOWN: return self.shift(evt, -1)
        if key == wx.WXK_UP: return self.shift(evt, 1)
        if key == wx.WXK_ESCAPE:
            self.__par.reset(self.__par.value, backcall=None) # restore value
        evt.Skip()
    
    def OnTextEnter(self, evt): #<wx._core.CommandEvent>
        evt.Skip()
        x = self.text.Value.strip()
        self.__par.reset(x)
    
    def OnTextExit(self, evt): #<wx._core.FocusEvent>
        x = self.text.Value.strip()
        if x != str(self.__par):
            try:
                self.__par.reset(x) # reset value if focus out
            except Exception:
                self.text.SetValue(str(self.__par))
                self.__par.reset(self.__par.value, backcall=None) # restore value
        evt.Skip()
    
    def OnCheck(self, evt): #<wx._core.CommandEvent>
        self.__par.check = int(evt.IsChecked())
        evt.Skip()
    
    def OnPress(self, evt): #<wx._core.CommandEvent>
        self.__par.callback('update', self.__par)
        evt.Skip()
    
    def Enable(self, p=True):
        self.label.Enable(p)
        self.ctrl.Enable(p)
        self.text.Enable(p)


class ControlPanel(scrolled.ScrolledPanel):
    """Scrollable Control Panel
    """
    def __init__(self, *args, **kwargs):
        scrolled.ScrolledPanel.__init__(self, *args, **kwargs)
        
        self.SetSizer(pack(self, [], orient=wx.VERTICAL))
        self.SetupScrolling()
        
        self.__groups = []
        self.__params = []
        
        self.menu = [
            (wx.ID_COPY, "&Copy params", "Copy params",
                lambda v: self.copy_to_clipboard(checked_only=wx.GetKeyState(wx.WXK_SHIFT)),
                lambda v: v.Enable(self.__params != [])),
                
            (wx.ID_PASTE, "&Paste params", "Read params",
                lambda v: self.paste_from_clipboard(checked_only=wx.GetKeyState(wx.WXK_SHIFT)),
                lambda v: v.Enable(self.__params != [])),
            (),
            (wx.ID_RESET, "&Reset params", "Reset params",
                lambda v: self.reset_params(checked_only=wx.GetKeyState(wx.WXK_SHIFT)),
                lambda v: v.Enable(self.__params != [])),
        ]
        self.Bind(wx.EVT_CONTEXT_MENU, lambda v: Menu.Popup(self, self.menu))
        self.Bind(wx.EVT_LEFT_DOWN, self.OnToggleFold)
        
        self.Bind(wx.EVT_SCROLLWIN_THUMBRELEASE, self.OnRecalcLayout)
        self.Bind(wx.EVT_MOUSEWHEEL, self.OnRecalcLayout)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnRecalcLayout)
    
    def OnRecalcLayout(self, evt): #<wx._core.ScrollWinEvent>
        self.Layout()
        evt.Skip()
    
    def OnToggleFold(self, evt): #<wx._core.MouseEvent>
        x, y = evt.Position
        for child in self.Sizer.Children: # child <wx._core.SizerItem>
            if child.IsShown():
                obj = child.Sizer or child.Window
                if isinstance(obj, (wx.StaticBoxSizer, wx.StaticBox)):
                    cx, cy = obj.Position
                    if cx < x < cx + obj.Size[0] and cy < y < cy+22:
                        for cc in obj.Children: # child of child <wx._core.SizerItem>
                            cc.Show(not cc.IsShown())
                        self.Layout()
                        self.SendSizeEvent()
                        break
        evt.Skip()
    
    def Scroll(self, *args):
        """Scrolls a window so the view start is at the given point.
        (override) Ignore DeprecationWarning: an integer is required.
        """
        if len(args) == 1:
            args = args[0]
        x, y = [int(v) for v in args]
        return scrolled.ScrolledPanel.Scroll(self, x, y)
    
    ## --------------------------------
    ## Layout commands and attributes
    ## --------------------------------
    @property
    def layout_groups(self):
        return self.__groups
    
    def is_enabled(self, groupid, pred=all):
        return pred(win.Enabled for win in self.__groups[groupid])
    
    def enable(self, groupid, p=True):
        for win in self.__groups[groupid]: # child could be deep nesting
            win.Enable(p)
    
    def is_shown(self, groupid):
        ## child = self.Sizer.Children[groupid]
        ## return child.IsShown()
        return self.Sizer.IsShown(groupid % len(self.__groups))
    
    def show(self, groupid, p=True):
        """Show/hide all including the box."""
        ## child = self.Sizer.Children[groupid]
        ## child.Show(p)
        self.Sizer.Show(groupid % len(self.__groups), p)
        ## self.Sizer.Fit(self) # do Fit(self.Parent) if needed
        self.Layout()
        self.Parent.SendSizeEvent() # let parent redraw the child panel
    
    def is_folded(self, groupid):
        child = self.Sizer.Children[groupid]
        return not any(cc.IsShown() for cc in child.Sizer.Children)
    
    def fold(self, groupid, p=True):
        """Fold/unfold the boxed group."""
        child = self.Sizer.Children[groupid]
        if isinstance(child.Sizer, wx.StaticBoxSizer) and child.IsShown():
            for cc in child.Sizer.Children: # child of child <wx._core.SizerItem>
                cc.Show(not p)
            ## self.Sizer.Fit(self) # do Fit(self.Parent) if needed
            self.Layout()
            self.Parent.SendSizeEvent() # let parent redraw the child panel
    
    def layout(self, objs, title=None,
               row=1, expand=0, border=2, hspacing=1, vspacing=1,
               show=True, visible=True, fix=True, align=wx.ALIGN_LEFT,
               **kwargs):
        """Do layout (cf. Layout).
        
        Args:
            title   : box header string (default is None - no box)
            objs    : list of Params, wx.Objects, tuple of sizing, or None
            row     : number of row to arange widgets
            show    : fold or unfold the boxed group
            expand  : (0) fixed size
                      (1) to expand horizontally
                      (2) to exapnd horizontally and vertically
            border  : size of outline border
            hspacing: horizontal spacing among packed objs inside the group
            vspacing: vertical spacing among packed objs inside the group
            fix     : tell sizer to fix the minimum layout
            align   : alignment flag (wx.ALIGN_*) default is ALIGN_LEFT
            **kwargs: extra keyword arguments given for Knob
        """
        ## assert all((key in inspect.getargspec(Knob)[0]) for key in kwargs)
        assert not isinstance(objs, str)
        
        objs = [Knob(self, c, **kwargs) if isinstance(c, Param)
                ## else (c, 0, wx.EXPAND) if isinstance(c, wx.StatusBar)
                ## else (c, 1, wx.EXPAND | wx.ALL, 1) if isinstance(c, wx.StaticLine)
                else c for c in objs]
        
        p = wx.EXPAND if expand > 0 else wx.ALIGN_CENTER
        if row > 0:
            oblist = [pack(self, objs[i:i+row], orient=wx.HORIZONTAL,
                           style=(expand>0, p | wx.LEFT | wx.RIGHT, hspacing))
                           for i in range(0, len(objs), row)]
        else:
            oblist = objs
        
        p = wx.EXPAND if expand > 0 else align
        sizer = pack(self, oblist, label=title, orient=wx.VERTICAL,
                     style=(expand>1, p | wx.BOTTOM | wx.TOP, vspacing))
        
        self.Sizer.Add(sizer, expand>1, p | wx.ALL, border)
        
        ## Register object and parameter groups
        def flatiter(a):
            for c in a:
                if isinstance(c, tuple):
                    yield from flatiter(c)
                elif isinstance(c, wx.Object):
                    yield c
        self.__groups.append(list(flatiter(objs)))
        
        def variter(a):
            for c in a:
                if isinstance(c, Knob):
                    yield c.param
                elif hasattr(c, 'value'):
                    yield c
        self.__params.append(list(variter(objs)))
        
        ## Set appearance of the layout group
        self.show(-1, visible)
        self.fold(-1, not show)
        if fix:
            self.Sizer.Fit(self)
    
    pack = pack
    
    ## --------------------------------
    ## 外部入出力／クリップボード通信
    ## --------------------------------
    @property
    def parameters(self):
        return [p.value for p in chain(*self.__params)]
    
    @parameters.setter
    def parameters(self, v):
        self.reset_params(v)
    
    def get_params(self, checked_only=False):
        params = chain(*self.__params)
        if not checked_only:
            return params
        return filter(lambda c: getattr(c, 'check', None), params)
    
    def reset_params(self, argv=None, checked_only=False, **kwargs):
        params = self.get_params(checked_only)
        if argv is None:
            for p in params:
                try:
                    p.reset(**kwargs)
                except AttributeError:
                    pass
        else:
            for p,v in zip(params, argv):
                try:
                    p.reset(v, **kwargs) # eval v:str -> value
                except AttributeError:
                    p.value = v
                except Exception as e: # failed to eval
                    print("- Failed to reset {!r}: {}".format(p, e))
                    pass
    
    def copy_to_clipboard(self, checked_only=False):
        params = self.get_params(checked_only)
        text = '\t'.join(str(p) if isinstance(p, Param)
                         else str(p.value) for p in params)
        Clipboard.write(text)
    
    def paste_from_clipboard(self, checked_only=False, **kwargs):
        text = Clipboard.read()
        if text:
            self.reset_params(text.split('\t'), checked_only, **kwargs)


class Clipboard:
    """Clipboard interface of text
    
    This does not work unless wx.App instance exists.
    The clipboard data cannot be transferred unless wx.Frame exists.
    """
    verbose = True
    
    @staticmethod
    def read():
        do = wx.TextDataObject()
        wx.TheClipboard.Open() or print("- Unable to open the clipboard")
        wx.TheClipboard.GetData(do)
        wx.TheClipboard.Close()
        text = do.GetText()
        if Clipboard.verbose:
            print("From clipboard: {}".format(text))
        return text
    
    @staticmethod
    def write(text):
        do = wx.TextDataObject(str(text))
        wx.TheClipboard.Open() or print("- Unable to open the clipboard")
        wx.TheClipboard.SetData(do)
        wx.TheClipboard.Close()
        if Clipboard.verbose:
            print("To clipboard: {}".format(text))


## --------------------------------
## Wx custom controls and bitmaps 
## --------------------------------
if 1:
    provided_arts = {
            'cut' : wx.ART_CUT,
           'copy' : wx.ART_COPY,
          'paste' : wx.ART_PASTE,
           'book' : wx.ART_HELP_BOOK,
           'page' : wx.ART_HELP_PAGE,
            'exe' : wx.ART_EXECUTABLE_FILE,
           'file' : wx.ART_NORMAL_FILE,
       'file_new' : wx.ART_NEW,
    'file_delete' : wx.ART_DELETE,
   'file_missing' : wx.ART_MISSING_IMAGE,
           'find' : wx.ART_FIND,
           'open' : wx.ART_FILE_OPEN,
           'save' : wx.ART_FILE_SAVE,
         'saveas' : wx.ART_FILE_SAVE_AS,
         'folder' : wx.ART_FOLDER,
    'folder_open' : wx.ART_FOLDER_OPEN,
             #'x' : wx.ART_CLOSE,
             #'v' : wx.ART_TICK_MARK,
              '?' : wx.ART_QUESTION,
              '!' : wx.ART_INFORMATION,
             '!!' : wx.ART_WARNING,
            '!!!' : wx.ART_ERROR,
              '+' : wx.ART_PLUS,
              '-' : wx.ART_MINUS,
              '~' : wx.ART_GO_HOME,
             'up' : wx.ART_GO_UP,
             'dn' : wx.ART_GO_DOWN,
             '<-' : wx.ART_GO_BACK,
             '->' : wx.ART_GO_FORWARD,
            '|<-' : wx.ART_GOTO_FIRST,
            '->|' : wx.ART_GOTO_LAST,
    }

def Icon(key, size=None):
    if key:
        try:
            art = getattr(images, key)
            if not size:
                bmp = art.GetBitmap()
            else:
                bmp = (art.GetImage()
                          .Scale(*size, wx.IMAGE_QUALITY_NEAREST)
                          .ConvertToBitmap())
        except Exception:
            bmp = wx.ArtProvider.GetBitmap(
                    provided_arts.get(key) or key,
                    size=size or (16,16))
        return bmp
    
    ## Note: null (0-shaped) bitmap fails with AssertionError from 4.1.0
    if key == '':
        bmp = wx.Bitmap(size or (16,16))
        if 1:
            dc = wx.MemoryDC(bmp)
            dc.SetBackground(wx.Brush('black'))
            dc.Clear()
            del dc
        bmp.SetMaskColour('black') # return dummy-sized blank bitmap
        return bmp
    return wx.NullBitmap # The standard wx controls accept this,

Icon.provided_arts = provided_arts

Icon.custom_images = dict((k, v) for k, v in images.__dict__.items()
                          if isinstance(v, wx.lib.embeddedimage.PyEmbeddedImage))


def _Icon(v):
    if isinstance(v, str):
        return Icon(v)
    return v


def _F(f, obj):
    if callable(f):
        return wraps(f)(lambda v: f(obj))


class Button(pb.PlateButton):
    """Flat button
    
    Args:
        label   : button label
        handler : event handler when the button is pressed
        icon    : key:str or bitmap for button icon
        tip     : tip:str displayed on the button
        **kwargs: keywords for wx.lib.platebtn.PlateButton
    """
    @property
    def icon(self):
        """key:str or bitmap"""
        return self.__icon
    
    @icon.setter
    def icon(self, v):
        self.__icon = v
        self.SetBitmap(_Icon(v))
        self.Refresh()
    
    def __init__(self, parent, label='',
                 handler=None, icon=None, tip='', **kwargs):
        kwargs.setdefault('style', pb.PB_STYLE_DEFAULT | pb.PB_STYLE_SQUARE)
        pb.PlateButton.__init__(self, parent, -1, label, **kwargs)
        
        if handler:
            self.Bind(wx.EVT_BUTTON, handler)
        
        tip = '\n  '.join(filter(None, (tip, handler.__doc__)))
        self.ToolTip = tip.strip()
        self.icon = icon
    
    def SetBitmap(self, bmp):
        """Set the bitmap displayed in the button.
        (override) If it fails, it clears the bitmap.
        """
        try:
            pb.PlateButton.SetBitmap(self, bmp)
        except Exception:
            self._bmp = dict(enable=None, disable=None)


class ToggleButton(wx.ToggleButton):
    """Togglable button
    
    Args:
        label   : button label
        handler : event handler when the button is pressed
        icon    : key:str or bitmap for button icon
        tip     : tip:str displayed on the button
        **kwargs: keywords for wx.ToggleButton
    
    Note:
        To get the status, check Value or event.GetInt or event.IsChecked.
    """
    @property
    def icon(self):
        """key:str or bitmap"""
        return self.__icon
    
    @icon.setter
    def icon(self, v):
        self.__icon = v
        if isinstance(v, tuple):
            v, w = v
            self.SetBitmapPressed(_Icon(w))
        if v:
            self.SetBitmap(_Icon(v))
        self.Refresh()
    
    def __init__(self, parent, label='',
                 handler=None, icon=None, tip='', **kwargs):
        wx.ToggleButton.__init__(self, parent, -1, label, **kwargs)
        
        if handler:
            self.Bind(wx.EVT_TOGGLEBUTTON, handler)
        
        tip = '\n  '.join(filter(None, (tip, handler.__doc__)))
        self.ToolTip = tip.strip()
        self.icon = icon


class TextCtrl(wx.Panel):
    """Text panel
    
    Args:
        label   : button label
        handler : event handler when text is entered
        updater : event handler when the button is pressed
        icon    : key:str or bitmap for button icon
        tip     : tip:str displayed on the button
        readonly: flag:bool for wx.TE_READONLY
        **kwargs: keywords for wx.TextCtrl
                  e.g., value:str
    """
    Value = property(
        lambda self: self._ctrl.GetValue(),
        lambda self,v: self._ctrl.SetValue(v),
        doc="textctrl value:str")
    
    value = Value # internal use only
    
    @property
    def icon(self):
        """key:str or bitmap"""
        return self._btn.icon
    
    @icon.setter
    def icon(self, v):
        self._btn.icon = v
    
    def __init__(self, parent, label='',
                 handler=None, updater=None,
                 icon=None, tip='', readonly=0, **kwargs):
        wx.Panel.__init__(self, parent, size=kwargs.get('size') or (-1,22))
        
        kwargs['style'] = (kwargs.get('style', 0)
                            | wx.TE_PROCESS_ENTER
                            | (wx.TE_READONLY if readonly else 0))
        
        self._ctrl = wx.TextCtrl(self, **kwargs)
        self._btn = Button(self, label, _F(updater, self), icon, tip,
                                size=(-1,-1) if label or icon else (0,0))
        self.SetSizer(
            pack(self, (
                (self._btn, 0, wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT, 0),
                (self._ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 0),
            ))
        )
        if handler:
            def _f(v):
                self.Value = v
                handler(self)
            self.reset = _f
            self._ctrl.Bind(wx.EVT_TEXT_ENTER, lambda v: handler(self))
        
        self.GetValue = self._ctrl.GetValue
        self.SetValue = self._ctrl.SetValue


class Choice(wx.Panel):
    """Editable Choice (ComboBox) panel
    
    Args:
        label   : button label
        handler : event handler when text is entered or item is selected
        updater : event handler when the button is pressed
        icon    : key:str or bitmap for button icon
        tip     : tip:str displayed on the button
        readonly: flag:bool for wx.TE_READONLY
        selection: initial selection:int for combobox
        **kwargs: keywords for wx.TextCtrl
                  e.g., choices:list
    
    Note:
        If the input item is not found in the choices,
        it will be added to the list (unless readonly)
    """
    Selection = property(
        lambda self: self._ctrl.GetSelection(),
        lambda self,v: self._ctrl.SetSelection(v),
        doc="combobox selection:int")
    
    Value = property(
        lambda self: self._ctrl.GetValue(),
        lambda self,v: self._ctrl.SetValue(v),
        doc="combobox value:str")
    
    value = Value # internal use only
    
    @property
    def icon(self):
        """key:str or bitmap"""
        return self._btn.icon
    
    @icon.setter
    def icon(self, v):
        self._btn.icon = v
    
    def __init__(self, parent, label='',
                 handler=None, updater=None,
                 icon=None, tip='', readonly=0, selection=None, **kwargs):
        wx.Panel.__init__(self, parent, size=kwargs.get('size') or (-1,22))
        
        kwargs['style'] = (kwargs.get('style', 0)
                            | wx.TE_PROCESS_ENTER
                            | (wx.CB_READONLY if readonly else 0))
        
        self._ctrl = wx.ComboBox(self, **kwargs)
        self._btn = Button(self, label, _F(updater, self), icon, tip,
                                size=(-1,-1) if label or icon else (0,0))
        self.SetSizer(
            pack(self, (
                (self._btn, 0, wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT, 0),
                (self._ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 0),
            ))
        )
        if handler:
            def _f(v):
                self.Value = v
                handler(self)
            self.reset = _f
            self._ctrl.Bind(wx.EVT_TEXT_ENTER, lambda v: handler(self))
            self._ctrl.Bind(wx.EVT_COMBOBOX, lambda v: handler(self))
        self._ctrl.Bind(wx.EVT_TEXT_ENTER, self.OnTextEnter)
        
        if selection is not None:
            self._ctrl.Selection = selection # no events?
        
        self.GetSelection = self._ctrl.GetSelection
        self.SetSelection = self._ctrl.SetSelection
        self.GetValue = self._ctrl.GetValue
        self.SetValue = self._ctrl.SetValue
    
    def OnTextEnter(self, evt):
        s = evt.String.strip()
        if not s:
            self._ctrl.SetSelection(-1)
        elif s not in self._ctrl.Items:
            self._ctrl.Append(s)
            self._ctrl.SetStringSelection(s)
        evt.Skip()


class Indicator(wx.Panel):
    """Traffic light indicator tricolor mode
    """
    @property
    def Value(self):
        return self.__value
    
    @Value.setter
    def Value(self, v):
        self.__value = int(v)
        self.Refresh()
    
    tricolor = ('red','yellow','green')
    spacing = 7
    radius = 5
    
    def __init__(self, parent, value=0, tip='', size=(-1,-1), **kwargs):
        s = self.spacing
        size = np.maximum((s*6, s*2+1), size) # set minimum size:(6s,2s)
        wx.Panel.__init__(self, parent, size=size, **kwargs)
        
        self.__value = value
        self.ToolTip = tip.strip()
        
        self.Bind(wx.EVT_PAINT, self.OnPaint)
    
    def OnPaint(self, evt):
        dc = wx.PaintDC(self)
        dc.Clear()
        N = len(self.tricolor)
        s = self.spacing
        r = self.radius
        w, h = self.ClientSize
        dc.SetBrush(wx.Brush("black"))
        dc.DrawRoundedRectangle(0, h//2-s, s*2*N-1, s*2+1, s)
        for j, name in enumerate(self.tricolor):
            if not self.__value & (1 << N-1-j):
                name = 'gray'
            dc.SetBrush(wx.Brush(name))
            dc.DrawCircle(s*(2*j+1)-j, h//2, r)


class Gauge(wx.Panel):
    """Rainbow gauge panel
    """
    @property
    def Value(self):
        return self.__value
    
    @Value.setter
    def Value(self, v):
        self.__value = int(v)
        self.Draw()
    
    @property
    def Range(self):
        return self.__range
    
    @Range.setter
    def Range(self, v):
        self.__range = int(v)
        self.Draw()
    
    def __init__(self, parent, range=24, value=0, tip='', **kwargs):
        wx.Panel.__init__(self, parent, **kwargs)
        
        self.__range = range
        self.__value = value
        self.ToolTip = tip.strip()
        self.canvas = wx.Bitmap(self.ClientSize)
        
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
    
    def OnSize(self, evt):
        if all(self.ClientSize):
            self.canvas = wx.Bitmap(self.ClientSize)
            self.Draw()
    
    def OnPaint(self, evt):
        dc = wx.BufferedPaintDC(self, self.canvas)
    
    def Draw(self):
        dc = wx.BufferedDC(wx.ClientDC(self), self.canvas)
        dc.Clear()
        dc.SetPen(wx.TRANSPARENT_PEN)
        
        def color(x):
            y = 4*x
            if   x < 0.25: rgb = (0, y, 1)
            elif x < 0.50: rgb = (0, 1, 2-y)
            elif x < 0.75: rgb = (y-2, 1, 0)
            else:          rgb = (1, 4-y, 0)
            return [int(round(255 * x)) for x in rgb]
        
        w, h = self.ClientSize
        N = self.__range
        for i in range(N):
            if i < self.__value:
                dc.SetBrush(wx.Brush(wx.Colour(color(i/N))))
            else:
                dc.SetBrush(wx.Brush('white'))
            dc.DrawRectangle(i*w//N, 0, w//N-1, h)


if __name__ == "__main__":
    from numpy import pi
    from framework import CtrlInterface, Frame
    
    class TestPanel(ControlPanel, CtrlInterface):
        def __init__(self, *args, **kwargs):
            ControlPanel.__init__(self, *args, **kwargs)
            CtrlInterface.__init__(self)
            
            self.handler.debug = 6
            
            a = Param('test')
            b = LParam('test', (0,100,1), 50)
            
            self.layout((a, b), title="test")
            self.layout((a, b), hspacing=4, expand=1)
            self.layout((a, b), )
            
            A =  Param('HHH', np.arange(-1, 1, 1e-3), 0.5, tip='amplitude')
            K = LParam('k', (0, 1, 1e-3))
            P = LParam('φ', (-pi, pi, pi/100), 0)
            Q = LParam('universe', (1, 20, 1), inf, handler=print, updater=print)
            R = LParam('lens', (0, 0xffff), 0x8000, handler=print, updater=print, fmt=hex)
            
            self.params = (A, K, P, Q, R,)
            
            for lp in self.params:
                lp.callback.update({
                    'control' : [lambda p: print("control", p.name, p.value)],
                     'update' : [lambda p: print("update", p.name, p.value)],
                      'check' : [lambda p: print("check", p.check)],
                   'overflow' : [lambda p: print("overflow", p)],
                  'underflow' : [lambda p: print("underflow", p)],
                })
            
            self.layout(
                self.params,
                title="test(1)",
                row=1, expand=0, border=2, hspacing=1, vspacing=1, show=1, visible=1,
                type='slider', style='chkbox', lw=-1, tw=-1, cw=-1, h=22,
            )
            self.layout(
                [P, Q],
                title="test(2)",
                row=2, expand=1, border=2, hspacing=1, vspacing=2, show=1, visible=1,
                type='choice', style='button', lw=-1, tw=60, cw=-1,
            )
    
    app = wx.App()
    frm = Frame(None)
    frm.panel = TestPanel(frm)
    frm.Fit()
    frm.Show()
    frm.SetFocus()
    app.MainLoop()
