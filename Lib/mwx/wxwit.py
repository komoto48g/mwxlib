#! python3
# -*- coding: utf-8 -*-
"""Widget inspection tool
*** Inspired by wx.lib.inspection ***

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
import warnings
import re
import wx
from wx.lib import inspection as it
try:
    from framework import Menu, watch
    from controls import Icon
except ImportError:
    from .framework import Menu, watch
    from .controls import Icon


def atomvars(obj):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)
        p = re.compile('[a-zA-Z]+')
        keys = sorted(filter(p.match, dir(obj)), key=lambda s:s.upper())
        attr = {}
        for key in keys:
            try:
                value = getattr(obj, key)
                if hasattr(value, '__name__'): #<atom>
                    continue
            except Exception as e:
                value = e
            attr[key] = repr(value)
        return attr


class InfoList(wx.ListCtrl):
    def __init__(self, parent, **kwargs):
        wx.ListCtrl.__init__(self, parent,
                             style=wx.LC_REPORT|wx.LC_HRULES, **kwargs)
        
        ## self.Font = wx.Font(9, wx.FONTFAMILY_MODERN, wx.NORMAL, wx.NORMAL)
        self.Font = wx.Font(9, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        self.attr = {}
        self.alist = ( # assoc list of column names
            ("key",   140),
            ("value", 160),
        )
        for k, (header, w) in enumerate(self.alist):
            self.InsertColumn(k, header, width=w)
        try:
            self.SetHeaderAttr(
                wx.ItemAttr('black', '', self.Font.Bold()))
        except AttributeError:
            pass
    
    def clear(self):
        self.DeleteAllItems()
        self.attr = {}
    
    def UpdateInfo(self, obj):
        if not obj:
            return
        self.clear()
        attr = atomvars(obj)
        for key, vstr in attr.items():
            if key == 'ContainingSizer':
                sizer = obj.ContainingSizer
                if sizer:
                    _attr = atomvars(sizer.GetItem(obj)) #<wx.SizerItem>
                    self.attr[key] = vstr
                    self.attr.update(("-> SizerItem.{}".format(k), v)
                                      for k,v in _attr.items())
                    continue
            if re.match(r"<(.+) object at \w+>", vstr): #<instance>
                continue
            self.attr[key] = vstr
        
        for i, (k, v) in enumerate(self.attr.items()):
            self.InsertItem(i, k)
            self.SetItem(i, 1, v)


class Inspector(wx.SplitterWindow):
    """Widget inspection tool with check-list

Args:
    parent : shellframe
    """
    parent = property(lambda self: self.__shellframe)
    target = property(lambda self: self.__watchedWidget)
    
    def __init__(self, parent, *args, **kwargs):
        wx.SplitterWindow.__init__(self, parent, *args, **kwargs)
        
        self.__shellframe = parent
        self.__watchedWidget = None
        
        self.tree = it.InspectionTree(self, size=(300,-1))
        self.tree.toolFrame = self # override tree
        self.tree.Font = wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.NORMAL, wx.NORMAL)
        
        ## self.info = it.InspectionInfoPanel(self, size=(200,-1))
        ## self.info.DropTarget = None # to prevent filling from crash
        self.info = InfoList(self, size=(200,-1))
        
        self.SplitVertically(
            self.tree, self.info, self.tree.MinWidth)
        
        self.tree.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)
        
        self.timer = wx.Timer(self)
        
        self.Bind(wx.EVT_TIMER, self.OnTimer)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        
        self.highlighter = it._InspectionHighlighter()
        self.highlighter.highlightTime = 2000
        
        ## wx.CallAfter(self.SetObj, None)
    
    def OnDestroy(self, evt):
        if evt.EventObject is self:
            self.unwatch()
        evt.Skip()
    
    ## --------------------------------
    ## InspectionTool wrapper methods
    ## --------------------------------
    
    it.INCLUDE_INSPECTOR = True
    it.USE_CUSTOMTREECTRL = False
    
    includeSizers = False
    expandFrame = False
    
    def RefreshTree(self):
        self.tree.BuildTree(self.__watchedWidget,
                            self.includeSizers,
                            self.expandFrame)
    
    def SetObj(self, obj):
        """Called from tree.toolFrame -> SetObj"""
        if self.__watchedWidget is not obj:
            self.__watchedWidget = obj
            self.info.UpdateInfo(obj)
        if not self.tree.built:
            self.RefreshTree()
        else:
            self.tree.SelectObj(obj)
    
    def watch(self, widget):
        if widget:
            self.RefreshTree()
            self.SetObj(widget)
            self.timer.Start(500)
            self.parent.handler("show_page", self)
        else:
            self.unwatch()
    
    def unwatch(self):
        self.timer.Stop()
    
    def OnTimer(self, evt):
        ## wnd, pt = wx.FindWindowAtPointer() # as HitTest
        wnd = wx.Window.FindFocus()
        if wnd not in self.Children:
            self.SetObj(wnd)
    
    def OnRightDown(self, evt):
        item, flags = self.tree.HitTest(evt.Position)
        if item.IsOk():
            # and flags & (0x10 | 0x20 | 0x40 | 0x80):
            self.tree.SelectItem(item)
            Menu.Popup(self, (
                (1, "&Dive into the shell", Icon('core'),
                    lambda v: self.parent.clone_shell(self.target)),
                    
                (2, "&Watch the event", Icon('proc'),
                    lambda v: self.parent.monitor.watch(self.target)),
                (),
                (10, "&Inspection Tool", Icon('inspect'),
                     lambda v: watch(self.target)),
                
                (11, "Refresh", miniIcon('Refresh'),
                     lambda v: self.RefreshTree()),
                
                (12, "Highlight", miniIcon('HighlightItem'),
                     lambda v: self.highlighter.HighlightCurrentItem(self.tree)),
            ))
        evt.Skip()


def miniIcon(key, size=(16,16)):
    art = getattr(it, key)
    return art.GetImage().Scale(*size).ConvertToBitmap()


if __name__ == "__main__":
    import mwx
    app = wx.App()
    frm = mwx.Frame(None)
    if 1:
        self = frm.shellframe
        frm.wit = Inspector(self)
        frm.wit.Show(0)
        self.Show()
        self.rootshell.write("self.wit.watch(self.wit)")
    frm.Show()
    app.MainLoop()
