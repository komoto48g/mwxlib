#! python3
"""Widget inspection tool.

*** Inspired by wx.lib.inspection ***
"""
import wx
import wx.lib.inspection as it

from .controls import Icon
from .utilus import typename
from .framework import CtrlInterface, Menu, filling


class Inspector(it.InspectionTree, CtrlInterface):
    """Widget inspection tool
    
    Attributes:
        parent : shellframe
        target : widget to inspect
    """
    def __init__(self, parent, *args, **kwargs):
        it.InspectionTree.__init__(self, parent, *args, **kwargs)
        CtrlInterface.__init__(self)
        
        self.parent = parent
        self.target = None
        
        self.Font = wx.Font(9, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        self.timer = wx.Timer(self)
        self.toolFrame = self
        
        self._noWatchList = [self,
                             self.TopLevelParent]
        
        self.Bind(wx.EVT_TREE_ITEM_GETTOOLTIP, self.OnItemTooltip)
        self.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)
        self.Bind(wx.EVT_SHOW, self.OnShow)
        self.Bind(wx.EVT_TIMER, self.OnTimer)
        self.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        
        self.highlighter = it._InspectionHighlighter()
        self.highlighter.highlightTime = 2000
        
        @self.handler.bind('*button* pressed')
        @self.handler.bind('*button* released')
        def dispatch(evt):
            """Fork events to the parent."""
            self.parent.handler(self.handler.current_event, evt)
            evt.Skip()
        
        @self.handler.bind('f3 pressed')
        def _watchit(evt):
            if self.target:
                watchit(self.target)
        
        @self.handler.bind('f4 pressed')
        def _highlight(evt):
            self.highlighter.HighlightCurrentItem(self)
        
        @self.handler.bind('f5 pressed')
        def _refresh(evt):
            self.BuildTree(self.target)
    
    def OnDestroy(self, evt):
        if evt.EventObject is self:
            self.timer.Stop()
        evt.Skip()
    
    def OnSetFocus(self, evt):
        title = self.__class__.__name__
        self.parent.handler('title_window', title)
        evt.Skip()
    
    ## --------------------------------
    ## InspectionTree wrapper interface
    ## --------------------------------
    
    def SetObj(self, obj):
        """Called from tree.toolFrame -> SetObj.
        
        (override) Set target object.
        """
        if self.target is obj:
            return
        self.target = obj
        item = self.FindWidgetItem(obj)
        if item:
            self.EnsureVisible(item)
            self.SelectItem(item)
        elif obj:
            self.BuildTree(obj)
    
    def GetTextForWidget(self, obj):
        """Return the string to be used in the tree for a widget.
        
        (override) Make better object name and Id.
        """
        clsname = obj.__class__.__name__
        if hasattr(obj, 'Name'):
            return "{} ({!r} {})".format(clsname, obj.Name, obj.Id)
        return clsname
    
    def highlight(self, obj, msec=2000):
        self.highlighter.highlightTime = msec
        if isinstance(obj, wx.Window):
            self.highlighter.HighlightWindow(obj)
        elif isinstance(obj, wx.Sizer):
            self.highlighter.HighlightSizer(obj)
        elif isinstance(obj, wx.SizerItem):
            self.highlighter.HighlightSizer(obj.Sizer)
    
    def set_colour(self, obj, col):
        item = self.FindWidgetItem(obj)
        if item:
            self.SetItemTextColour(item, col)
    
    def watch(self, obj=None):
        if obj is None:
            item = self.Selection
            if item:
                obj = self.GetItemData(item) # Restart
        self.BuildTree(obj)
        if not isinstance(obj, wx.Window):
            wx.MessageBox("Cannot watch the widget.\n\n"
                          "- {!r} is not a wx.Object.".format(obj))
            return
        self.SetObj(obj)
        self.timer.Start(500)
    
    def unwatch(self):
        self.target = None
        self.timer.Stop()
    
    ## --------------------------------
    ## Actions on tree items
    ## --------------------------------
    
    def OnTimer(self, evt):
        ## wnd, pt = wx.FindWindowAtPointer() # as HitTest
        wnd = wx.Window.FindFocus()
        if (wnd and wnd is not self.target
                and wnd not in self._noWatchList):
            self.SetObj(wnd)
        evt.Skip()
    
    def OnShow(self, evt):
        if evt.IsShown():
            if not self.built:
                self.BuildTree(self.target)
        self._noWatchList = [w for w in self._noWatchList if w]
        evt.Skip()
    
    def OnItemTooltip(self, evt):
        item = evt.GetItem()
        if item:
            obj = self.GetItemData(item)
            evt.SetToolTip("id=0x{:X}".format(id(obj)))
        evt.Skip()
    
    def OnRightDown(self, evt):
        item, flags = self.HitTest(evt.Position)
        if item: # and flags & (0x10 | 0x20 | 0x40 | 0x80):
            self.SelectItem(item)
            self.SetFocus()
        obj = self.target
        Menu.Popup(self, [
            (1, "&Dive into {!r}".format(typename(obj)), Icon('core'),
                lambda v: dive(obj),
                lambda v: v.Enable(obj is not None)),
                
            (2, "&Watch event", Icon('tv'),
                lambda v: watch(obj),
                lambda v: v.Enable(obj is not None)),
            (),
            (10, "&Inspection Tool\tf3", Icon('inspect'),
                lambda v: watchit(obj),
                lambda v: v.Enable(obj is not None)),
            (),
            (11, "Highlight\tf4", miniIcon('HighlightItem'),
                lambda v: self.highlighter.HighlightCurrentItem(self),
                lambda v: v.Enable(obj is not None)),
                
            (12, "Refresh\tf5", miniIcon('Refresh'),
                lambda v: self.BuildTree(obj)),
        ])


def miniIcon(key, size=(16,16)):
    if key == 'ShowFilling':
        return wx.py.filling.images.getPyImage().Scale(16,16).ConvertToBitmap()
    art = getattr(it, key)
    return art.GetImage().Scale(*size).ConvertToBitmap()


def dumptree(self):
    def _dump(parent):
        item, cookie = self.GetFirstChild(parent)
        while item:
            obj = self.GetItemData(item)
            lc = list(_dump(item))
            yield [obj, lc] if lc else obj
            item, cookie = self.GetNextChild(parent, cookie)
    return list(_dump(self.RootItem))


def dump(widget=None):
    if not widget:
        return [dump(w) for w in wx.GetTopLevelWindows()]
    def _dump(w):
        for obj in w.Children:
            lc = list(_dump(obj))
            yield [obj, lc] if lc else obj
    return [widget, list(_dump(widget))]


def watchit(widget=None, **kwargs):
    """Wx.py tool for watching widget tree structure and events."""
    from wx.lib.inspection import InspectionTool
    it = InspectionTool()
    it.Init(**kwargs)
    it.Show(widget)
    return it._frame
