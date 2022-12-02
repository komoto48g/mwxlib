#! python3
# -*- coding: utf-8 -*-
"""Widget inspection tool
*** Inspired by wx.lib.inspection ***

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
import wx
import wx.lib.inspection as it
try:
    from mwx.framework import CtrlInterface, Menu, watchit
    from mwx.controls import Icon
except ImportError:
    from .framework import CtrlInterface, Menu, watchit
    from .controls import Icon


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
        self.toolFrame = self
        self.Font = wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.NORMAL, wx.NORMAL)
        self.timer = wx.Timer(self)
        
        try:
            from mwx.nutshell import Nautilus
        except ImportError:
            from .nutshell import Nautilus
        
        self._noWatchList = [self, self.GetTopLevelParent()]
        self._noWatchClsList = (Nautilus,)
        
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
            """Fork mouse events to the parent."""
            self.parent.handler(self.handler.event, v)
            v.Skip()
        
        @self.handler.bind('focus_set')
        def activate(v):
            self.parent.handler('title_window', self.__class__.__name__)
            v.Skip()
        
        @self.handler.bind('f4 pressed')
        def highlight(v):
            if self.target:
                self.highlighter.HighlightCurrentItem(self)
        
        @self.handler.bind('f5 pressed')
        def refresh(v):
            self.BuildTree(self.target)
    
    def OnDestroy(self, evt):
        if evt.EventObject is self:
            self.timer.Stop()
        evt.Skip()
    
    def SetObj(self, obj):
        """Called from tree.toolFrame -> SetObj."""
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
        """Returns the string to be used in the tree for a widget.
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
    
    def watch(self, obj=None):
        if obj is None:
            item = self.Selection
            if item:
                obj = self.GetItemData(item) # Restart
        if not obj:
            self.unwatch()
            return
        if not isinstance(obj, wx.Window):
            wx.MessageBox("Cannot watch the widget.\n\n"
                          "- {!r} is not a wx.Object.".format(obj))
            return
        self.SetObj(obj)
        self.timer.Start(500)
    
    def unwatch(self):
        self.target = None
        self.timer.Stop()
    
    def addref(self, obj, ref='obj'):
        shell = self.parent.current_shell
        if shell is not obj:
            shell.locals[ref] = obj
            ## shell.write(ref)
            self.parent.message("self.{} -> {!r}".format(ref, obj))
        shell.SetFocus()
        return shell
    
    def highlight(self, obj):
        if isinstance(obj, wx.Window):
            self.highlighter.HighlightWindow(obj)
        elif isinstance(obj, wx.Sizer):
            self.highlighter.HighlightSizer(obj)
        elif isinstance(obj, wx.SizerItem):
            self.highlighter.HighlightSizer(obj.Sizer)
    
    def OnTimer(self, evt):
        ## wnd, pt = wx.FindWindowAtPointer() # as HitTest
        wnd = wx.Window.FindFocus()
        if (wnd and wnd is not self.target\
                and wnd not in self._noWatchList\
                and not isinstance(wnd, self._noWatchClsList)):
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
        valid = (obj is not None)
        menu = [
            (1, "&Dive into the shell", Icon('core'),
                lambda v: self.parent.clone_shell(obj),
                lambda v: v.Enable(valid)),
                
            (2, "&Watch the event", Icon('ghost'),
                lambda v: self.parent.debug(obj),
                lambda v: v.Enable(valid)),
                
            (3, "&Add reference", Icon('tag'),
                lambda v: self.addref(obj),
                lambda v: v.Enable(valid)),
            (),
            (10, "&Inspection Tool", Icon('inspect'),
                lambda v: watchit(obj),
                lambda v: v.Enable(valid)),
            (),
            (11, "Highlight\tf4", miniIcon('HighlightItem'),
                lambda v: self.highlighter.HighlightCurrentItem(self),
                lambda v: v.Enable(valid)),
                
            (12, "Refresh\tf5", miniIcon('Refresh'),
                lambda v: self.BuildTree(obj)),
        ]
        Menu.Popup(self, menu)
        evt.Skip()


def miniIcon(key, size=(16,16)):
    art = getattr(it, key)
    return art.GetImage().Scale(*size).ConvertToBitmap()


def dumptree(self):
    def _dump(parent):
        item, cookie = self.GetFirstChild(parent)
        while item:
            obj = self.GetItemData(item)
            yield obj
            data = list(_dump(item))
            if data:
                yield data
            item, cookie = self.GetNextChild(parent, cookie)
    return list(_dump(self.RootItem))


if __name__ == "__main__":
    from mwx.framework import Frame
    
    app = wx.App()
    frm = Frame(None)
    frm.plug = Inspector(frm)
    frm.plug.watch(frm)
    pp(dumptree(frm.plug))
    frm.Show()
    app.MainLoop()
