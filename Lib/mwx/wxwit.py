#! python3
# -*- coding: utf-8 -*-
"""Widget inspection tool
*** Inspired by wx.lib.inspection ***

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
import wx
import wx.lib.inspection as it
try:
    from framework import CtrlInterface, Menu, watchit
    from controls import Icon
except ImportError:
    from .framework import CtrlInterface, Menu, watchit
    from .controls import Icon


class Inspector(it.InspectionTree, CtrlInterface):
    """Widget inspection tool
    
    Attributes:
        parent : shellframe
        target : widget to inspect
    """
    parent = property(lambda self: self.__shellframe)
    target = property(lambda self: self.__widget)
    
    def __init__(self, parent, *args, **kwargs):
        it.InspectionTree.__init__(self, parent, *args, **kwargs)
        CtrlInterface.__init__(self)
        
        self.__shellframe = parent
        self.__widget = None
        self._noWatchList = [self]
        self.toolFrame = self
        self.Font = wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.NORMAL, wx.NORMAL)
        self.timer = wx.Timer(self)
        
        self.Bind(wx.EVT_TREE_ITEM_GETTOOLTIP, self.OnItemTooltip)
        self.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)
        self.Bind(wx.EVT_SHOW, self.OnShow)
        self.Bind(wx.EVT_TIMER, self.OnTimer)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        
        self.highlighter = it._InspectionHighlighter()
        self.highlighter.highlightTime = 2000
        
        @self.handler.bind('*button* pressed')
        @self.handler.bind('*button* released')
        def dispatch(v):
            """Fork mouse events to the parent"""
            self.parent.handler(self.handler.event, v)
            v.Skip()
        
        @self.handler.bind('focus_set')
        def activate(v):
            self.parent.handler('title_window', self.__class__.__name__)
            v.Skip()
    
    def OnDestroy(self, evt):
        if evt.EventObject is self:
            self.timer.Stop()
        evt.Skip()
    
    def SetObj(self, obj):
        """Called from tree.toolFrame -> SetObj"""
        if self.__widget is obj:
            return
        self.__widget = obj
        item = self.FindWidgetItem(obj)
        if item:
            self.EnsureVisible(item)
            self.SelectItem(item)
        elif obj:
            self.BuildTree(obj)
    
    def GetTextForWidget(self, obj):
        """Returns the string to be used in the tree for a widget
        (override) make better object name and Id
        """
        clsname = obj.__class__.__name__
        if hasattr(obj, 'Name'):
            return "{} ({!r} {})".format(clsname, obj.Name, obj.Id)
        return clsname
    
    def set_colour(self, obj, col):
        self.SetObj(obj)
        item = self.FindWidgetItem(obj)
        if item:
            self.SetItemTextColour(item, col)
    
    def watch(self, obj):
        if not obj:
            self.unwatch()
            return
        self.SetObj(obj)
        self.timer.Start(500)
    
    def unwatch(self):
        self.__widget = None
        self.timer.Stop()
    
    def dive(self, obj):
        shell = self.parent.rootshell.clone(obj)
        self._noWatchList.append(shell)
        ## self.parent.load(obj)
        self.SetObj(obj)
        return shell
    
    def monitor(self, obj):
        self.parent.debug(obj)
    
    def OnTimer(self, evt):
        ## wnd, pt = wx.FindWindowAtPointer() # as HitTest
        wnd = wx.Window.FindFocus()
        if wnd:
            if (wnd is self.__widget
                or wnd in self._noWatchList
                or wnd in self.Parent.Children
                or wnd is self.GetTopLevelParent()):
                return
            self.SetObj(wnd)
        evt.Skip()
    
    def OnShow(self, evt):
        if evt.IsShown():
            if not self.built:
                self.BuildTree(self.__widget)
        self._noWatchList = [w for w in self._noWatchList if w]
        evt.Skip()
    
    def OnItemTooltip(self, evt):
        item = evt.GetItem()
        if item:
            obj = self.GetItemData(item)
            evt.SetToolTip("id={:#x}".format(id(obj)))
        evt.Skip()
    
    def OnRightDown(self, evt):
        item, flags = self.HitTest(evt.Position)
        if item: # and flags & (0x10 | 0x20 | 0x40 | 0x80):
            self.SelectItem(item)
        obj = self.__widget
        
        Menu.Popup(self, (
            (1, "&Dive into the shell", Icon('core'),
                lambda v: self.dive(obj),
                lambda v: v.Enable(obj is not None)),
            (),
            (2, "&Watch the event", Icon('ghost'),
                lambda v: self.monitor(obj),
                lambda v: v.Enable(obj is not None)),
            (),
            (10, "&Inspection Tool", Icon('inspect'),
                lambda v: watchit(obj)),
            (),
            (11, "Refresh", miniIcon('Refresh'),
                lambda v: self.BuildTree(obj)),
                 
            (12, "Highlight", miniIcon('HighlightItem'),
                lambda v: self.highlighter.HighlightCurrentItem(self),
                lambda v: v.Enable(obj is not None)),
        ))
        evt.Skip()


def miniIcon(key, size=(16,16)):
    art = getattr(it, key)
    return art.GetImage().Scale(*size).ConvertToBitmap()


if __name__ == "__main__":
    from graphman import Frame
    
    app = wx.App()
    frm = Frame(None)
    frm.load_plug(Inspector, show=1) #>>> self.plug.watch(self.plug)
    frm.Show()
    app.MainLoop()
