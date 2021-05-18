#! python
# -*- coding: utf-8 -*-
"""mwxlib param controller and wx custom controls

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
from __future__ import division, print_function
from __future__ import unicode_literals
from __future__ import absolute_import
from itertools import chain
import sys
import wx
import numpy as np
from numpy import pi
from numpy import nan,inf
from . import framework as mwx
from . import images as images
import wx.lib.platebtn as pb
import wx.lib.scrolledpanel as scrolled

LITERAL_TYPE = (str,) if sys.version_info >= (3,0) else (str,unicode)

## EPSILON = sys.float_info.epsilon
## EPSILON = 1e-15


class Param(object):
    """Standard Parameter
    
     name : label
    range : range [min:max:step]
  min,max : extent of parameter
std_value : standard value (default None)
    value : current value := std_value + offset
   offset : ditto (if std_value is None, this is the same as `value)
    knobs : knob list
    index : knob index -> reset -> callback
    check : knob tick (undefined)
      doc : doc:str also shown as a tooltip
 callback : single state machine that handles following events:
        control -> `index is changed (by knobs) or reset, calls handler if given
        check -> when `check ticks on/off, calls updater if given
        overflow -> when `value overflows
        underflow -> when `value underflows
    """
    def __init__(self, name, range=None, value=None,
        fmt=None, dtype=None, handler=None, updater=None, doc=None):
        self.__knobs = [] # used in update
        self.__name = name
        self.range = range if range is not None else [0]
        self.__value = value if value is not None else self.min
        self.__std_value = value
        self.__eval = eval
        self.__format = fmt if callable(fmt) else (lambda v: (fmt or "%g") % v)
        if dtype is hex:
            self.__eval = lambda v: int(v,16)
            self.__format = lambda v: '{:04X}'.format(int(v))
        elif dtype is int:
            self.__eval = int
            self.__format = lambda v:'{:,}'.format(int(v))
        elif dtype:
            print("Param:warning display type must be hex or int"
                  " otherwise None, not {}".format(dtype))
        self.__check = 0
        self.__callback = mwx.SSM({
            'control' : [ handler ] if handler else [],
              'check' : [ updater ] if updater else [],
           'overflow' : [],
          'underflow' : [],
        })
        self.doc = doc
    
    def __str__(self, v=None):
        return self.__format(self.__value if v is None else v)
    
    def __int__(self):
        return int(self.__value)
    
    def __long__(self):
        return long(self.__value)
    
    def __float__(self):
        return float(self.__value)
    
    def __len__(self):
        return len(self.__range)
    
    name = property(
        lambda self: self.__name,
        lambda self,v: self.set_name(v))
    
    value = property(
        lambda self: self.__value,
        lambda self,v: self.set_value(v) and self.notify())
    
    std_value = property(
        lambda self: self.__std_value,
        lambda self,v: self.set_std_value(v))
    
    offset = property(
        lambda self: self.get_offset(),
        lambda self,v: self.set_offset(v))
    
    range = property(
        lambda self: self.get_range(),
        lambda self,v: self.set_range(v))
    
    min = property(lambda self: self.__range[0])
    max = property(lambda self: self.__range[-1])
    
    index = property(
        lambda self: self.get_index(),
        lambda self,j: self.set_index(j))
    
    ## rindex = property(
    ##     lambda self: len(self) - self.get_index() - 1,
    ##     lambda self,j: self.set_index(len(self) - j - 1))
    
    knobs = property(
        lambda self: self.__knobs)
    
    check = property(
        lambda self: self.__check,
        lambda self,v: self.set_check(v))
    
    callback = property(
        lambda self: self.__callback)
    
    def bind(self, f=None, target='control'):
        la = self.__callback[target]
        if not f:
            return lambda f: self.bind(f, target)
        if f not in la:
            la.append(f)
        return f
    
    def unbind(self, f=None, target='control'):
        la = self.__callback[target]
        if not f:
            la[:] = [a for a in la if not callable(a)]
        else:
            la.remove(f)
    
    def reset(self, v=None, backcall=True):
        """Reset value when indexed (by knobs)
        When backcall is True, this calls back default control handler
        """
        if v is None or v == '':
            v = self.__std_value
            if v is None:
                return
        elif isinstance(v, LITERAL_TYPE):
            v = self.__eval(v.replace(',', '')) # eval nums with commas(,)
        
        self.set_value(v)
        if backcall:
            self.__callback('control', self)
    
    def update(self, valid=True):
        for knob in self.knobs:
            knob.set_textcolour('#ffffff' if valid
                           else '#ff8080' if valid is False # light-red
                           else '#ffff80' if valid is None  # light-yellow
                           else '')
            knob.update_ctrl() # update the text:ctrl of related knobs
    
    def notify(self):
        for knob in self.knobs:
            knob.set_textcolour('#ffff80') # light-yellow
            wx.CallAfter(wx.CallLater, 1000, knob.set_textcolour, 'white')
    
    def set_check(self, v):
        self.__check = v
        self.__callback('check', self)
        self.update()
    
    def set_name(self, v):
        self.__name = v
        self.update()
    
    def set_value(self, v):
        """Set value and check the limit.
        If the value is out of range, modify the value.
        """
        if v is None:
            v = nan
        if v in (nan,inf):
            self.__value = v
            self.update(None)
            return
        elif v == self.__value:
            return
        
        valid = (self.min <= v <= self.max)
        if valid:
            self.__value = v
        elif v < self.min:
            self.__value = self.min
            self.__callback('underflow', self)
        else:
            self.__value = self.max
            self.__callback('overflow', self)
        self.update(valid)
        return valid
    
    def set_std_value(self, v):
        self.__std_value = v
        self.update()
    
    def get_offset(self):
        if self.__std_value is not None:
            return self.__value - self.__std_value
        return self.__value
    
    def set_offset(self, v):
        if self.__std_value is not None:
            if v is not nan: # Note! nan +x is not nan
                v += self.__std_value
        self.set_value(v)
    
    def get_range(self):
        return self.__range
    
    def set_range(self, v):
        self.__range = sorted(v)
        for knob in self.knobs:
            knob.update_range() # update the range of related knobs
    
    def get_index(self, v=None):
        if v is None:
            v = self.value
        return int(np.searchsorted(self.__range, v))
    
    def set_index(self, j):
        n = len(self.__range)
        i = (0 if j<0 else j if j<n else -1)
        return self.set_value(self.__range[i])


class LParam(Param):
    """Linear Parameter
    """
    __doc__ = Param.__doc__
    
    min = property(lambda self: self.__min)
    max = property(lambda self: self.__max)
    step = property(lambda self: self.__step)
    
    def __len__(self):
        return 1 + self.get_index(self.max) # includes [min,max]
    
    def get_range(self):
        return np.arange(self.min, self.max + self.step, self.step)
    
    def set_range(self, v):
        self.__min = v[0]
        self.__max = v[1]
        self.__step = v[2] if len(v)>2 else 1
        for knob in self.knobs:
            knob.update_range() # update related knobs range
    
    def get_index(self, v=None):
        if v is None:
            v = self.value
        return int(round((v - self.min) / self.step))
    
    def set_index(self, j):
        return self.set_value(self.min + j * self.step)


## --------------------------------
## Knob unit for Parameter Control 
## --------------------------------

class Knob(wx.Panel):
    """Parameter control unit
    
    In addition to direct key input to the textctrl,
    [up][down][wheelup][wheeldown] keys can be used,
      with modifiers S- 2x, C- 16x, and M- 256x steps.
    [Mbutton] resets to the std. value if it exists.
    
    param : A param <Param> object referred from knobs
  bitstep : minimum step of this knob (>=1)
    """
    param = property(lambda self: self.__par)
    bitstep = property(lambda self: self.__bit)
    
    @param.setter
    def param(self, v):
        self.__par.knobs.remove(self)
        self.__par = v
        self.__par.knobs.append(self)
        self.update_range()
        self.update_ctrl()
    
    @bitstep.setter
    def bitstep(self, v):
        self.__bit = int(v) or 1
    
    def __init__(self, parent, par, type='slider', style=None, editable=1, lw=-1, tw=-1, cw=-1, h=22):
        """パラメータクラスのコントロールノブ
         par : Param <object>
        type : control type (slider[*], [hv]spin, choice, and default None)
       style : style of label
               None - static text
                chk - checkbox (previous style of label with wx.CheckBox)
                btn - button
    editable : textCtrl is editable or readonly
  lw, tw, cw : width of label, textbox, and control (default height `h=22 of widgets)
        """
        wx.Panel.__init__(self, parent)
        self.__bit = 1
        self.__par = par
        self.__par.knobs.append(self) # パラメータの関連付けを行う
        
        if type is None:
            type = 'slider'
            cw = 0
        elif type == 'choice':
            if cw < 0:
                cw = 20
            cw += tw
            tw = 0
        
        label = self.__par.name + ('  ' if lw else '')
        
        if style == 'chk': # or style == 'checkbox':
            if lw > 0:
                lw += 16
            self.label = wx.CheckBox(self, label=label, size=(lw,-1))
            self.label.Bind(wx.EVT_CHECKBOX, self.OnCheck)
            
        elif style == 'btn': # or style == 'button':
            if lw > 0:
                lw += 16
            self.label = pb.PlateButton(self, label=label, size=(lw,-1),
                            style=pb.PB_STYLE_DEFAULT|pb.PB_STYLE_SQUARE)
            self.label.Bind(wx.EVT_BUTTON, self.OnPress)
            
        elif not style:
            self.label = wx.StaticText(self, label=label, size=(lw,-1))
        else:
            raise Exception("unknown style: {!r}".format(style))
        
        self.label.Enable(lw)
        self.label.Bind(wx.EVT_MIDDLE_DOWN, lambda v: self.__par.reset())
        
        if self.__par.doc:
            self.label.SetToolTip(self.__par.doc)
        
        if editable:
            self.text = wx.TextCtrl(self, size=(tw,h), style=wx.TE_PROCESS_ENTER)
            self.text.Bind(wx.EVT_TEXT, self.OnText)
            self.text.Bind(wx.EVT_TEXT_ENTER, self.OnTextEnter)
            self.text.Bind(wx.EVT_SET_FOCUS, self.OnTextFocus)
            self.text.Bind(wx.EVT_KILL_FOCUS, self.OnTextFocusKill)
            
            ## self.text.Bind(wx.EVT_KEY_DOWN, self.OnTextKeyDown)
            if type[-1] == '*':
                self.text.Bind(wx.EVT_KEY_DOWN, self.OnTextKeyDown)
            else:
                self.text.Bind(wx.EVT_KEY_DOWN, self.OnTextKey)
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
            self.ctrl.Bind(wx.EVT_SCROLL, self.OnScroll) # update while dragging
            self.ctrl.Bind(wx.EVT_SCROLL_CHANGED, lambda v: None) # pass no action
            self.ctrl.Bind(wx.EVT_KEY_DOWN, self.OnCtrlKeyDown)
            self.ctrl.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)
            
        elif type == 'spin' or type =='hspin':
            self.ctrl = wx.SpinButton(self, size=(cw,h), style=wx.SP_HORIZONTAL)
            self.ctrl.Bind(wx.EVT_SPIN, self.OnScroll)
            
        elif type == 'vspin':
            self.ctrl = wx.SpinButton(self, size=(cw,h), style=wx.SP_VERTICAL)
            self.ctrl.Bind(wx.EVT_SPIN, self.OnScroll)
            
        elif type == 'choice':
            self.ctrl = wx.Choice(self, size=(cw,h))
            self.ctrl.Bind(wx.EVT_CHOICE, self.OnScroll)
            self.ctrl.SetValue = self.ctrl.SetSelection # setter mimic of controller
            self.ctrl.GetValue = self.ctrl.GetSelection # getter (ditto)
            
        else:
            raise Exception("unknown type: {!r}".format(type))
        
        self.ctrl.Enable(cw)
        self.ctrl.Bind(wx.EVT_MIDDLE_DOWN, lambda v: self.__par.reset())
        
        self.SetSizer(
            mwx.pack(self,
                (self.label, 0, wx.ALIGN_CENTER|wx.LEFT|wx.RIGHT, lw and 1),
                (self.text, 0, wx.ALIGN_CENTER|wx.LEFT|wx.RIGHT, tw and 1),
                (self.ctrl, cw and 1, wx.ALIGN_CENTER|wx.LEFT|wx.RIGHT, cw and 1),
                orient = wx.HORIZONTAL,
            )
        )
        self.update_range()
        self.update_ctrl()
    
    def Destroy(self):
        ## パラメータの関連付けを解除する
        self.__par.knobs.remove(self)
        return wx.Panel.Destroy(self)
    
    def update_range(self):
        v = self.__par
        if isinstance(self.ctrl, wx.Choice):
            self.ctrl.Set([v.__str__(x) for x in v.range]) #<wx.Choice>
        else:
            self.ctrl.SetRange(0, len(v)-1) #<wx.Slider> #<wx.SpinButton>
    
    def update_ctrl(self):
        v = self.__par
        try:
            self.text.SetValue(str(v))
            self.ctrl.SetValue(v.index)
        except Exception:
            pass
        
        if isinstance(self.label, wx.CheckBox):
            self.label.SetValue(bool(v.check))
        
        if self.label.IsEnabled():
            t = '  ' if v.std_value is None or v.value == v.std_value else '*'
            self.label.SetLabel(v.name + t)
            self.label.Refresh()
    
    def set_textcolour(self, c):
        try:
            if self.text.IsEditable():
                self.text.SetBackgroundColour(c)
                self.text.Refresh()
        except RuntimeError:
            pass # wrapped C/C++ object of type TextCtrl has been deleted
    
    def shift(self, evt, sgn, **kwargs):
        bit = self.__bit * sgn
        if evt.ShiftDown():   bit *= 2
        if evt.ControlDown(): bit *= 16
        if evt.AltDown():     bit *= 256
        i = self.ctrl.GetValue()
        self.__par.index = i + int(bit)
        self.__par.reset(self.__par.value, **kwargs)
    
    def OnScroll(self, evt): #<wx._core.ScrollEvent><wx._controls.SpinEvent><wx._core.CommandEvent>
        self.__par.index = self.ctrl.GetValue()
        self.__par.reset(self.__par.value)
        evt.Skip()
    
    def OnMouseWheel(self, evt): #<wx._core.MouseEvent>
        self.shift(evt, +1 if evt.GetWheelRotation()>0 else -1)
        evt.Skip(False)
    
    def OnCtrlKeyDown(self, evt): #<wx._core.KeyEvent>
        key = evt.GetKeyCode()
        if key == wx.WXK_LEFT: return self.shift(evt, -1)
        if key == wx.WXK_RIGHT: return self.shift(evt, 1)
        
        def focus(c):
            if isinstance(c, Knob) and c.ctrl.IsEnabled():
                c.ctrl.SetFocus()
                return True
        
        ls = next(x for x in self.Parent.groups if self in x)
        i = ls.index(self)
        if key == wx.WXK_DOWN: return any(focus(c) for c in ls[i+1:])
        if key == wx.WXK_UP: return any(focus(c) for c in ls[i-1::-1])
    
    def OnTextKey(self, evt): #<wx._core.KeyEvent>
        key = evt.GetKeyCode()
        if key == wx.WXK_DOWN: return self.shift(evt, -1, backcall=None)
        if key == wx.WXK_UP: return self.shift(evt, 1, backcall=None)
        evt.Skip()
    
    def OnTextKeyUp(self, evt): #<wx._core.KeyEvent>
        key = evt.GetKeyCode()
        if key == wx.WXK_DOWN: return self.shift(evt, 0) # only up/down updates (bit=0)
        if key == wx.WXK_UP: return self.shift(evt, 0)
        evt.Skip()
    
    def OnTextKeyDown(self, evt): #<wx._core.KeyEvent>
        key = evt.GetKeyCode()
        if key == wx.WXK_DOWN: return self.shift(evt, -1)
        if key == wx.WXK_UP: return self.shift(evt, 1)
        if key == wx.WXK_ESCAPE:
            self.__par.reset(self.__par.value, backcall=None) # restore value
        evt.Skip()
    
    def OnText(self, evt): #<wx._core.CommandEvent>
        evt.Skip()
        x = self.text.GetValue()
        if x != str(self.__par):
            self.set_textcolour('#ffff80') # light-yellow
    
    def OnTextEnter(self, evt): #<wx._core.CommandEvent>
        evt.Skip()
        x = self.text.GetValue()
        self.__par.reset(x)
    
    def OnTextFocus(self, evt): #<wx._core.FocusEvent>
        evt.Skip()
    
    def OnTextFocusKill(self, evt): #<wx._core.FocusEvent>
        if self.__par.value in (nan,inf):
            evt.Skip()
            return
        x = self.text.GetValue()
        if x != str(self.__par):
            try:
                self.__par.reset(x) # update value if focus out
            except Exception:
                self.text.SetValue(str(self.__par))
                self.__par.reset(self.__par.value, backcall=None) # restore value
        else:
            self.set_textcolour('white')
            self.text.Refresh()
        evt.Skip()
    
    def OnCheck(self, evt): #<wx._core.CommandEvent>
        self.__par.check = int(evt.IsChecked())
        evt.Skip()
    
    def OnPress(self, evt): #<wx._core.CommandEvent>
        self.__par.check = True
        evt.Skip()
    
    def Enable(self, p=True):
        self.label.Enable(p)
        self.ctrl.Enable(p)
        self.text.Enable(p)


class ControlPanel(scrolled.ScrolledPanel):
    """Scrollable control layout panel
    スクロール可能なコントロール配置用パネル
    """
    groups = property(lambda self: self.__groups)
    
    def __init__(self, *args, **kwargs):
        scrolled.ScrolledPanel.__init__(self, *args, **kwargs)
        
        self.SetSizer(mwx.pack(self, orient=wx.VERTICAL))
        self.SetupScrolling()
        
        self.__groups = []
        self.__params = []
        
        self.Menu = [
            (wx.ID_COPY, "&Copy params\t(C-c)", "Copy params",
                lambda v: self.copy_to_clipboard()),
                
            (wx.ID_PASTE, "&Paste params\t(C-v)", "Read params",
                lambda v: self.paste_from_clipboard()),
            (),
            (wx.ID_RESET, "&Reset params\t(C-n)", "Reset params",
                lambda v: self.reset_params()),
        ]
        self.Bind(wx.EVT_CONTEXT_MENU, lambda v: mwx.Menu.Popup(self, self.Menu))
        self.Bind(wx.EVT_LEFT_DOWN, self.OnToggleFold)
        
        @mwx.connect(self, wx.EVT_SCROLLWIN_THUMBRELEASE) #<wx._core.ScrollWinEvent>
        ## @mwx.connect(self, wx.EVT_MOUSE_EVENTS) #<wx._core.MouseEvent>
        @mwx.connect(self, wx.EVT_MOUSEWHEEL)
        @mwx.connect(self, wx.EVT_LEFT_DOWN)
        def recalc_layout(evt):
            self.Layout()
            evt.Skip()
    
    def Destroy(self):
        for k in chain(*self.__groups):
            if isinstance(k, Knob):# パラメータの関連付けを解除する
                k.Destroy()
        return scrolled.ScrolledPanel.Destroy(self)
    
    def OnToggleFold(self, evt): #<wx._core.MouseEvent>
        x, y = evt.Position
        for child in self.Sizer.Children: # child <wx._core.SizerItem>
            if not child.IsShown(): # skip invisible sizer (position is overlapping)
                continue
            cx, cy = child.Position
            if cx < x < cx + child.Size[0] and cy < y < cy+22:
                if isinstance(child.Sizer, wx.StaticBoxSizer):
                    for cc in child.Sizer.Children: # child of child <wx._core.SizerItem>
                        cc.Show(not cc.IsShown())   # toggle show
                    self.Layout()
                    self.SendSizeEvent()
                    self.Refresh() # redraw widgets
                break
        evt.Skip()
    
    ## --------------------------------
    ## Layout commands and attributes
    ## --------------------------------
    
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
        """show/hide all including the box"""
        ## child = self.Sizer.Children[groupid]
        ## child.Show(p)
        self.Sizer.Show(groupid % len(self.__groups), p)
        self.Sizer.Fit(self) # do Fit(self.Parent) if needed
        self.Layout()
        self.Parent.SendSizeEvent() # let parent redraw the child panel
    
    def is_folded(self, groupid):
        child = self.Sizer.Children[groupid]
        return not any(cc.IsShown() for cc in child.Sizer.Children)
    
    def fold(self, groupid, p=True):
        """fold/unfold the boxed group"""
        child = self.Sizer.Children[groupid]
        if isinstance(child.Sizer, wx.StaticBoxSizer) and child.IsShown():
            for cc in child.Sizer.Children: # child of child <wx._core.SizerItem>
                cc.Show(not p)
            self.Sizer.Fit(self) # do Fit(self.Parent) if needed
            self.Layout()
            self.Parent.SendSizeEvent() # let parent redraw the child panel
    
    def layout(self, title, objs,
        row=1, expand=0, border=2, hspacing=1, vspacing=1,
        show=True, visible=True, align=wx.ALIGN_LEFT, **kwargs):
        """Do layout (cf. Layout) using mwx.pack
        title : box header string
         objs : list of Params, wx.Objects, tuple of sizing, or None
          row : number of row to arange widgets
         show : fold or unfold the boxed group
       expand : (0) fixed size
                (1) to expand horizontally
                (2) to exapnd horizontally and vertically
       border : size of outline border
  [hv]spacing : spacing among packed objs inside the group
        align : alignment flag (wx.ALIGN_*) default is ALIGN_LEFT
     **kwargs : extra keyword arguments given for Knob
        """
        ## assert all((key in inspect.getargspec(Knob)[0]) for key in kwargs)
        
        objs = [ (c, 0, wx.EXPAND) if isinstance(c, wx.StatusBar)
            else (c, 1, wx.EXPAND|wx.ALL, 1) if isinstance(c, wx.StaticLine)
            else c if c is None
            else c if isinstance(c, tuple)
            else c if isinstance(c, wx.Object)
            else Knob(self, c, **kwargs) for c in objs ]
        
        self.__groups.append([c for c in objs if isinstance(c, wx.Object)])
        
        def isvar(c):
            return c.param if isinstance(c, Knob)\
              else c if hasattr(c, 'reset') and hasattr(c, 'value') else None
        
        self.__params.append(list(filter(None, (isvar(c) for c in objs))))
        
        ## do layout in row
        p = wx.EXPAND if expand > 0 else wx.ALIGN_CENTER
        if row > 1:
            objs = [mwx.pack(self, *objs[i:i+row], orient=wx.HORIZONTAL,
                        style=(expand>0, p|wx.LEFT|wx.RIGHT, hspacing))
                            for i in range(0, len(objs), row)]
        
        p = wx.EXPAND if expand > 0 else align
        sizer = mwx.pack(self, *objs, label=title, orient=wx.VERTICAL,
                    style=(expand>1, p|wx.BOTTOM|wx.TOP, vspacing))
        
        self.Sizer.Add(sizer, expand>1, p|wx.ALL, border)
        self.Sizer.Fit(self)
        self.show(-1, visible)
        self.fold(-1, not show)
    
    ## --------------------------------
    ## 外部入出力／クリップボード通信
    ## --------------------------------
    parameters = property(
        lambda self: [p.value for p in chain(*self.__params)])
    
    def reset_params(self, argv=None, groupid=None, **kwargs):
        if groupid is not None:
            params = [self.__params[groupid]]
        else:
            params = self.__params
        
        if not argv:
            for p in chain(*params):
                p.reset(**kwargs)
        else:
            for p,v in zip(chain(*params), argv):
                p.reset(v, **kwargs)
    
    def copy_to_clipboard(self):
        text = '\t'.join(str(p.value) for p in chain(*self.__params))
        Clipboard.write(text)
    
    def paste_from_clipboard(self):
        text = Clipboard.read()
        self.reset_params(text.split())


class Clipboard:
    """Clipboard interface of text
    
    This does not work unless wx.App instance exists.
    The clipboard data cannot be transfered unless wx.Frame exists.
    """
    @staticmethod
    def read():
        do = wx.TextDataObject()
        wx.TheClipboard.Open() or print("Unable to open the clipboard")
        wx.TheClipboard.GetData(do)
        wx.TheClipboard.Close()
        return do.GetText()
    
    @staticmethod
    def write(text):
        do = wx.TextDataObject(str(text))
        wx.TheClipboard.Open() or print("Unable to open the clipboard")
        wx.TheClipboard.SetData(do)
        wx.TheClipboard.Close()


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

def getBmp(key, size=None):
    if key:
        try:
            bmp = getattr(images, key).GetBitmap()
            if size:
                img = bmp.ConvertToImage()
                img = img.Scale(*size)
                bmp = img.ConvertToBitmap()
            return bmp
        except Exception:
            return wx.ArtProvider.GetBitmap(
                provided_arts.get(key) or key, size=size or (14,14)) #<wx._core.Bitmap> IsOk ?
    
    return wx.NullBitmap # The standard wx control seems to accept this,
    ## return wx.Bitmap(0,0) # but some wx.lib.controls require this.

Icon = getBmp

getBmp.provided_arts = provided_arts

getBmp.custom_images = dict((k,v) for (k,v) in images.__dict__.items()
                            if isinstance(v, wx.lib.embeddedimage.PyEmbeddedImage))


class Button(pb.PlateButton):
    """Flat button
    """
    def __init__(self, parent, label='', handler=None, icon=None, tip=None, **kwargs):
        pb.PlateButton.__init__(self, parent, -1, label,
            style=pb.PB_STYLE_DEFAULT|pb.PB_STYLE_SQUARE, **kwargs)
        if handler:
            self.Bind(wx.EVT_BUTTON, handler)
            tip = tip or handler.__doc__
        tip = (tip or '').strip()
        self.SetToolTip(tip)
        try:
            if icon:
                self.SetBitmap(Icon(icon))
        except Exception:
            pass


class ToggleButton(wx.ToggleButton):
    """Togglable button
    check `Value property to get the status
    """
    def __init__(self, parent, label='', handler=None, icon=None, tip=None, **kwargs):
        wx.ToggleButton.__init__(self, parent, -1, label, **kwargs)
        if handler:
            self.Bind(wx.EVT_TOGGLEBUTTON, handler)
            tip = tip or handler.__doc__
        tip = (tip or '').strip()
        self.SetToolTip(tip)
        self.SetBitmap(Icon(icon))


## class TextLabel(wx.Panel):
##     """Label (widget complex of bitmap and label) readonly.
##     """
##     def __init__(self, parent, label, icon=None, tip=None, **kwargs):
##         wx.Panel.__init__(self, parent, **kwargs)
##         txt = wx.StaticText(self, label=label)
##         bmp = wx.StaticBitmap(self, bitmap=Icon(icon)) if icon else (0,0)
##         self.SetSizer(
##             mwx.pack(self,
##                 (bmp, 0, wx.ALIGN_CENTER|wx.ALL, 0),
##                 (txt, 0, wx.ALIGN_CENTER|wx.ALL, 0),
##                 orient=wx.HORIZONTAL,
##             )
##         )
##         txt.SetToolTip(tip)


class TextCtrl(wx.Panel):
    """Text control panel
    widget complex of bitmap, label, and textctrl
    """
    Value = property(
        lambda self: self.ctrl.GetValue(),
        lambda self,v: self.ctrl.SetValue(v))
    value = Value
    
    def reset(self, v=''):
        self.value = v
    
    def __init__(self, parent, label='',
        handler=None, updater=None, icon=None, tip=None, readonly=0, **kwargs):
        wx.Panel.__init__(self, parent, size=kwargs.get('size') or (-1,-1))
        
        self.btn = Button(self, label, icon=icon, tip=tip,
                                size=(-1,-1) if label or icon else (0,0))
        
        kwargs['style'] = kwargs.get('style', 0)
        kwargs['style'] |= wx.TE_PROCESS_ENTER|(wx.TE_READONLY if readonly else 0)
        self.ctrl = wx.TextCtrl(self, **kwargs)
        ## self.ctrl.SetFont(
        ##     wx.Font(9, wx.MODERN, wx.NORMAL, wx.NORMAL, False, u'MS Gothic'))
        
        self.SetSizer(
            mwx.pack(self,
                (self.btn, 0, wx.ALIGN_CENTER|wx.LEFT|wx.RIGHT, 0),
                (self.ctrl, 1, wx.EXPAND|wx.RIGHT, 0),
                orient=wx.HORIZONTAL,
            )
        )
        if handler:
            self.ctrl.Bind(wx.EVT_TEXT_ENTER, handler) # use style=wx.TE_PROCESS_ENTER
        if updater:
            self.btn.Bind(wx.EVT_BUTTON, lambda v: updater(self))


class Choice(wx.Panel):
    """Editable Choice (ComboBox) control panel
    If input item is not found, appends to `choices (only if `readonly=0)
    """
    Value = property(
        lambda self: self.ctrl.GetValue(),
        lambda self,v: self.ctrl.SetValue(v))
    value = Value
    
    Selection = property(
        lambda self: self.ctrl.GetSelection(),
        lambda self,v: self.ctrl.SetSelection(v))
    index = Selection
    
    def reset(self, v=None):
        if v is not None:
            self.value = v
    
    ## def __getattr__(self, attr): #! to be deprecated (Note: Panel interface is prior)
    ##     return getattr(self.ctrl, attr)
    
    def __init__(self, parent, label='',
        handler=None, updater=None, icon=None, tip=None, readonly=0, selection=None, **kwargs):
        wx.Panel.__init__(self, parent, size=kwargs.get('size') or (-1,-1))
        
        self.btn = Button(self, label, icon=icon, tip=tip,
                                size=(-1,-1) if label or icon else (0,0))
        
        kwargs['style'] = kwargs.get('style', 0)
        kwargs['style'] |= wx.TE_PROCESS_ENTER|(wx.CB_READONLY if readonly else 0)
        self.ctrl = wx.ComboBox(self, **kwargs)
        
        self.SetSizer(
            mwx.pack(self,
                (self.btn, 0, wx.ALIGN_CENTER|wx.LEFT|wx.RIGHT, 0),
                (self.ctrl, 1, wx.EXPAND|wx.RIGHT, 0),
                orient=wx.HORIZONTAL,
            )
        )
        if handler:
            self.ctrl.Bind(wx.EVT_COMBOBOX, handler)
            self.ctrl.Bind(wx.EVT_TEXT_ENTER, handler) # use style=wx.TE_PROCESS_ENTER
        self.ctrl.Bind(wx.EVT_TEXT_ENTER, self.OnEnter)
        if updater:
            self.btn.Bind(wx.EVT_BUTTON, lambda v: updater(self))
        if selection is not None:
            self.index = selection
    
    def OnEnter(self, evt):
        s = evt.String.strip()
        if not s:
            self.ctrl.SetSelection(-1)
        elif s not in self.ctrl.Items:
            self.ctrl.Append(s)
            self.ctrl.SetStringSelection(s)
        evt.Skip()


class Gauge(wx.Panel):
    """Rainbow gauge panel
    """
    @property
    def Value(self):
        return self.__value
    
    @Value.setter
    def Value(self, v):
        self.__value = v
        self.Draw()
    
    value = Value
    
    def __init__(self, parent, range=24, **kwargs):
        wx.Panel.__init__(self, parent, **kwargs)
        
        self.__range = range
        self.__value = 1
        self.canvas = wx.Bitmap(self.GetClientSize())
        
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
    
    def OnSize(self, evt):
        self.canvas = wx.Bitmap(self.GetClientSize())
        self.Draw()
    
    def OnPaint(self, evt):
        dc = wx.BufferedPaintDC(self, self.canvas)
    
    def Draw(self):
        dc = wx.BufferedDC(wx.ClientDC(self), self.canvas)
        ## dc = wx.ClientDC(self)
        dc.Clear()
        dc.SetDeviceOrigin(2, 2)
        dc.SetPen(wx.TRANSPARENT_PEN)
        
        def color(x):
            y = 4*x
            if   x < 0.25: rgb = (0, y, 1)
            elif x < 0.50: rgb = (0, 1, 2-y)
            elif x < 0.75: rgb = (y-2, 1, 0)
            else:          rgb = (1, 4-y, 0)
            return [255 * x for x in rgb]
        
        w, h = self.Size - (4,6)
        N = self.__range
        for i in range(N):
            if i < self.value:
                dc.SetBrush(wx.Brush(wx.Colour(color(i/N))))
            else:
                dc.SetBrush(wx.Brush('white'))
            dc.DrawRectangle(i*w/N, 0, w/N-1, h)


if __name__ == '__main__':
    
    class TestPanel(ControlPanel, mwx.CtrlInterface):
        def __init__(self, *args, **kwargs):
            ControlPanel.__init__(self, *args, **kwargs)
            mwx.CtrlInterface.__init__(self)
            
            self.A =  Param('HHH', np.arange(-1, 1, 1e-3), 0.5, doc='amplitude')
            self.K = LParam('k', (0,1,1e-4))
            self.P = LParam('φ', (-pi, pi, pi/100), 0)
            self.Q =  Param('universe', (1,2,3,inf), inf, handler=print, updater=print)
            self.R =  LParam('lens', (1,0xffff,1), 0x8000, handler=print, updater=print, dtype=hex)
            self.params = (
                self.A,
                self.K,
                self.P,
                self.Q,
                self.R,
            )
            for lp in self.params:
                lp.callback.update({
                    'control' : [lambda p: print('control', p.name, p.value)],
                      'check' : [lambda p: print('check', p.check)],
                   'overflow' : [lambda p: print("overflow", p)],
                  'underflow' : [lambda p: print("underflow", p)],
                })
            
            @self.K.bind
            @self.A.bind
            def p(item):
                print(item)
            
            self.layout("V1",
                self.params,
                row=1, expand=1, hspacing=1, vspacing=1, show=1, visible=1,
                type='slider', style='chk', lw=-1, tw=-1, cw=-1, h=22, editable=1
            )
            self.layout("V2",
                self.params,
                row=2, expand=1, hspacing=1, vspacing=2, show=1, visible=1,
                type='spin', style='btn', lw=-1, tw=60, cw=-1,
            )
            self.layout("types", (
                Knob(self, self.A, type, lw=32, tw=60, cw=-1, h=20)
                for type in (
                    'vspin',
                    'hspin',
                    'choice',
                    'slider',
                    )
                ),
                row=2, expand=0, hspacing=1, vspacing=2, show=0, visible=1,
            )
            
            for win in self.groups[1]:
                print(win)
            
            self.groups[1][1].Disable()
    
    app = wx.App()
    frm = mwx.Frame(None)
    frm.panel = TestPanel(frm)
    frm.Fit()
    frm.Show()
    frm.SetFocus()
    app.MainLoop()
