#! python3
# -*- coding: utf-8 -*-
import inspect
import wx
from wx import aui
from wx import stc
import wx.lib.eventwatcher as ew

if wx.VERSION < (4,1,0):
    from wx.lib.mixins.listctrl import CheckListCtrlMixin
    
    class _ListCtrl(wx.ListCtrl, CheckListCtrlMixin):
        def __init__(self, *args, **kwargs):
            wx.ListCtrl.__init__(self, *args, **kwargs)
            CheckListCtrlMixin.__init__(self)
            
            self.IsItemChecked = self.IsChecked # for wx 4.1 compatibility
else:
    class _ListCtrl(wx.ListCtrl):
        def __init__(self, *args, **kwargs):
            wx.ListCtrl.__init__(self, *args, **kwargs)
            self.EnableCheckBoxes()


def where(obj):
    try:
        filename = inspect.getsourcefile(obj)
        src, lineno = inspect.getsourcelines(obj)
        return "{!s}:{}:{!s}".format(filename, lineno, src[0].rstrip())
    except Exception:
        return repr(obj)


class EventMonitor(_ListCtrl):
    """Event monitor of the inspector
*** Inspired by wx.lib.eventwatcher ***

Args:
    parent : inspector of the shell
    """
    target = property(lambda self: self.__watchedWidget)
    data = property(lambda self: self.__items)
    
    def __init__(self, parent, **kwargs):
        _ListCtrl.__init__(self, parent,
                           style=wx.LC_REPORT|wx.LC_HRULES, **kwargs)
        
        self.__inspector = parent
        self.__watchedWidget = None
        
        self.__dir = True # sort direction
        self.__items = []
        
        self.Font = wx.Font(9, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        
        self.alist = ( # assoc list of column names
            ("typeId",    62),
            ("typeName", 200),
            ("source",   200),
        )
        for k, (header, w) in enumerate(self.alist):
            self.InsertColumn(k, header, width=w)
        
        ## self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnSortItems)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnItemActivated) # left-dclick
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
    
    def OnDestroy(self, evt):
        self.unwatch()
        evt.Skip()
    
    ## --------------------------------
    ## Event-watcher wrapper interface 
    ## --------------------------------
    
    ew.buildWxEventMap() # build ew._eventBinders and ew._eventIdMap
    ew.addModuleEvents(aui) # + some additives
    ew.addModuleEvents(stc)
    
    ## Events that should not be watched by default
    ew._noWatchList = [
        wx.EVT_PAINT,
        wx.EVT_NC_PAINT,
        wx.EVT_ERASE_BACKGROUND,
        wx.EVT_IDLE,
        wx.EVT_UPDATE_UI,
        wx.EVT_UPDATE_UI_RANGE,
        wx.EVT_TOOL,
        wx.EVT_TOOL_RANGE, # menu items (typeId=10018)
        wx.EVT_MENU,
    ]
    
    @staticmethod
    def get_name(event):
        return ew._eventIdMap.get(event, 'Unknown')
    
    @staticmethod
    def get_binder(event):
        return next(x for x in ew._eventBinders if x.typeId == event)
    
    @staticmethod
    def get_watchlist():
        """All watched event binders except noWatchList"""
        return filter(lambda v: v not in ew._noWatchList,
                      ew._eventBinders)
    
    def get_actions(self, event, widget=None):
        """Wx.PyEventBinder and the handlers"""
        widget = widget or self.target
        if widget:
            try:
                handlers = widget.__event_handler__[event]
                return [a for a in handlers if a != self.onWatchedEvent]
            except KeyError:
                print("- No such event: {}".format(event))
    
    def watch(self, widget):
        """Begin watching"""
        if not isinstance(widget, wx.Object):
            return
        self.unwatch()
        self.clear()
        self.__watchedWidget = widget
        ssmap = self.dump(widget, verbose=1)
        for binder in self.get_watchlist():
            widget.Bind(binder, self.onWatchedEvent)
            if binder.typeId in ssmap:
                self.append(binder.typeId)
        self.__inspector.handler("add_page", self)
        self.__inspector.handler("monitor_begin", self.target)
    
    def unwatch(self):
        """End watching"""
        if not self.target:
            return
        for binder in self.get_watchlist():
            if not self.target.Unbind(binder, handler=self.onWatchedEvent):
                print("- Failed to unbind {}:{}".format(binder.typeId, binder))
        self.__inspector.handler("monitor_end", self.target)
        self.__watchedWidget = None
    
    def onWatchedEvent(self, evt):
        if self:
            self.update(evt)
        evt.Skip()
    
    def dump(self, widget, verbose=True):
        """Dump all event handlers bound to the widget"""
        exclusions = [x.typeId for x in ew._noWatchList]
        ssmap = {}
        for event in sorted(widget.__event_handler__):
            actions = self.get_actions(event)
            if event not in exclusions and actions:
                ssmap[event] = actions
                if verbose:
                    name = self.get_name(event)
                    values = ('\n'+' '*41).join(where(a) for a in actions)
                    print("{:8d}:{:32s}{!s}".format(event, name, values))
        return ssmap
    
    ## --------------------------------
    ## Actions for event-logger items
    ## --------------------------------
    
    def OnItemActivated(self, evt):
        item = self.__items[evt.Index]
        attribs = item[-1]
        wx.CallAfter(wx.TipWindow, self, attribs, 512)
        self.__inspector.handler("put_scratch", attribs)
    
    def update(self, evt):
        event = evt.EventType
        obj = evt.EventObject
        name = self.get_name(event)
        source = ew._makeSourceString(obj)
        attribs = ew._makeAttribString(evt)
        
        if wx.VERSION < (4,1,0): # ignore self insert
            if event == wx.EVT_LIST_INSERT_ITEM.typeId\
              and obj is self:
                return
        
        for i, item in enumerate(self.__items):
            if item[0] == event:
                item[1:] = [name, source, attribs]
                break
        else:
            i = len(self.__items)
            item = [event, name, source, attribs]
            self.__items.append(item)
            self.InsertItem(i, event)
        
        for j, v in enumerate(item[:-1]):
            self.SetItem(i, j, str(v))
        
        if i == self.FocusedItem:
            self.__inspector.handler("put_scratch", attribs)
        
        if self.IsItemChecked(i):
            actions = self.get_actions(evt.EventType)
            if actions:
                self.CheckItem(i, False)
                for f in actions:
                    self.__inspector.debugger.trace(f, evt)
        
        if self.GetItemBackgroundColour(i) != wx.Colour('yellow'):
            ## Don't run out of all timers and get warnings
            self.SetItemBackgroundColour(i, "yellow")
            def reset_color():
                if self:
                    self.SetItemBackgroundColour(i, 'white')
            wx.CallLater(1000, reset_color)
    
    def clear(self):
        self.DeleteAllItems()
        self.__items = []
    
    def append(self, event, bold=True):
        if event in (item[0] for item in self.__items):
            return
        
        i = len(self.__items)
        name = self.get_name(event)
        item = [event, name, '-', 'no data']
        self.__items.append(item)
        self.InsertItem(i, event)
        for j, v in enumerate(item[:-1]):
            self.SetItem(i, j, str(v))
        if bold:
            self.SetItemFont(i, self.Font.Bold())
    
    def OnSortItems(self, evt): #<wx._controls.ListEvent>
        n = self.ItemCount
        lc = [self.__items[j] for j in range(n) if self.IsItemChecked(j)]
        ls = [self.__items[j] for j in range(n) if self.IsSelected(j)]
        f = self.__items[self.FocusedItem]
        
        col = evt.GetColumn()
        self.__dir = not self.__dir
        self.__items.sort(key=lambda v: v[col], reverse=self.__dir) # sort data
        
        for i, item in enumerate(self.__items):
            for j, v in enumerate(item[:-1]):
                self.SetItem(i, j, str(v))
            self.CheckItem(i, item in lc)  # check
            self.Select(i, item in ls)     # seleciton
            if self.get_actions(item[0]):
                self.SetItemFont(i, self.Font.Bold())
            else:
                self.SetItemFont(i, self.Font)
        self.Focus(self.__items.index(f))  # focus (one)
    
    ## def OnMotion(self, evt): #<wx._core.MouseEvent>
    ##     i, flag = self.HitTest(evt.Position)
    ##     if i >= 0:
    ##         item = self.__items[i]
    ##     evt.Skip()


if __name__ == "__main__":
    import mwx
    app = wx.App()
    frm = mwx.Frame(None)
    if 1:
        self = frm.inspector
        frm.mon = EventMonitor(self)
        frm.mon.Show(0)
        self.rootshell.write("self.mon.watch(self.mon)")
        self.Show()
    frm.Show()
    app.MainLoop()
