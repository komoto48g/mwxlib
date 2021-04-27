#! python
# -*- coding: utf-8 -*-
"""Wx my custom controls

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
from __future__ import division, print_function
from __future__ import unicode_literals
from __future__ import absolute_import
import wx
import wx.lib.platebtn as pb
from .framework import pack
from .graphman import Icon


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
##             pack(self,
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
            pack(self,
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
    
    def __getattr__(self, attr): #! to be deprecated (Note: Panel interface is prior)
        return getattr(self.ctrl, attr)
    
    def __init__(self, parent, label='',
        handler=None, updater=None, icon=None, tip=None, readonly=0, selection=None, **kwargs):
        wx.Panel.__init__(self, parent, size=kwargs.get('size') or (-1,-1))
        
        self.btn = Button(self, label, icon=icon, tip=tip,
                                size=(-1,-1) if label or icon else (0,0))
        
        kwargs['style'] = kwargs.get('style', 0)
        kwargs['style'] |= wx.TE_PROCESS_ENTER|(wx.CB_READONLY if readonly else 0)
        self.ctrl = wx.ComboBox(self, **kwargs)
        
        self.SetSizer(
            pack(self,
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
