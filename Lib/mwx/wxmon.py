#! python3
# -*- coding: utf-8 -*-
"""Widget minitor
*** Inspired by wx.lib.eventwatcher ***

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
import warnings
import wx
import wx.lib.eventwatcher as ew
try:
    from framework import where
    from controls import CheckList
except ImportError:
    from .framework import where
    from .controls import CheckList


class EventMonitor(CheckList):
    """Event monitor

Args:
    parent : shellframe
    """
    parent = property(lambda self: self.__shellframe)
    target = property(lambda self: self.__watchedWidget)
    
    def __init__(self, parent, **kwargs):
        CheckList.__init__(self, parent,
                           style=wx.LC_REPORT|wx.LC_HRULES, **kwargs)
        
        self.Font = wx.Font(9, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        
        self.__shellframe = parent
        self.__watchedWidget = None
        
        self.__dir = True # sort direction
        self.__items = []
        
        self.alist = ( # assoc list of column names
            ("typeId",    62),
            ("typeName", 200),
            ("source",   200),
        )
        for k, (header, w) in enumerate(self.alist):
            self.InsertColumn(k, header, width=w)
        
        self.Bind(wx.EVT_LIST_ITEM_FOCUSED, self.OnItemFocused)
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnSortItems)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnItemDClick)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        
        self.add_module = ew.addModuleEvents
        
        from wx import adv, aui, stc, media
        for module in (adv, aui, stc, media):
            self.add_module(module)
    
    def OnDestroy(self, evt):
        if evt.EventObject is self:
            self.unwatch()
        evt.Skip()
    
    ## --------------------------------
    ## EventWatcher wrapper interfaces 
    ## --------------------------------
    
    ew.buildWxEventMap() # build ew._eventBinders and ew._eventIdMap
    
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
        if widget and hasattr(widget, '__event_handler__'):
            try:
                handlers = widget.__event_handler__[event]
                ## Exclude ew:onWatchedEvent by comparing names instead of objects
                ## return [a for a in handlers if a != self.onWatchedEvent]
                return [a for a in handlers if a.__name__ != 'onWatchedEvent']
            except KeyError:
                print("- No such event: {}".format(event))
    
    def watch(self, widget):
        """Begin watching"""
        if not widget:
            self.unwatch()
            return
        if not isinstance(widget, wx.Object):
            wx.MessageBox("Cannot watch the widget.\n\n"
                          "- {!r} is not a wx.Object.".format(widget))
            return
        self.unwatch()
        self.clear()
        self.__watchedWidget = widget
        ssmap = self.dump(widget, verbose=1)
        for binder in self.get_watchlist():
            widget.Bind(binder, self.onWatchedEvent)
            if binder.typeId in ssmap:
                self.append(binder.typeId)
        self.parent.handler("show_page", self)
        self.parent.handler("monitor_begin", self.target)
    
    def unwatch(self):
        """End watching"""
        if not self.target:
            return
        for binder in self.get_watchlist():
            if not self.target.Unbind(binder, handler=self.onWatchedEvent):
                print("- Failed to unbind {}:{}".format(binder.typeId, binder))
        self.parent.handler("monitor_end", self.target)
        self.__watchedWidget = None
    
    def onWatchedEvent(self, evt):
        if self:
            self.update(evt)
        evt.Skip()
    
    def dump(self, widget, verbose=True):
        """Dump all event handlers bound to the widget"""
        exclusions = [x.typeId for x in ew._noWatchList]
        ssmap = {}
        if not hasattr(widget, '__event_handler__'):
            return ssmap
        for event in sorted(widget.__event_handler__):
            actions = self.get_actions(event)
            if actions and event not in exclusions:
                ssmap[event] = actions
                if verbose:
                    name = self.get_name(event)
                    values = ('\n'+' '*41).join(where(a) for a in actions)
                    print("{:8d}:{:32s}{!s}".format(event, name, values))
        return ssmap
    
    ## --------------------------------
    ## Actions for event-logger items
    ## --------------------------------
    
    def clear(self):
        self.DeleteAllItems()
        del self.__items[:]
    
    def update(self, evt):
        event = evt.EventType
        obj = evt.EventObject
        name = self.get_name(event)
        source = ew._makeSourceString(obj)
        
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            attribs = ew._makeAttribString(evt)
        
        if wx.VERSION < (4,1,0): # ignore self insert
            if event == wx.EVT_LIST_INSERT_ITEM.typeId\
              and obj is self:
                return
        
        data = self.__items
        for i, item in enumerate(data):
            if item[0] == event:
                item[1:] = [name, source, attribs]
                break
        else:
            i = len(data)
            item = [event, name, source, attribs]
            data.append(item)
            self.InsertItem(i, event)
        
        for j, v in enumerate(item[:-1]):
            self.SetItem(i, j, str(v))
        
        if i == self.FocusedItem:
            self.parent.handler("put_scratch", attribs)
        
        if self.IsItemChecked(i):
            actions = self.get_actions(evt.EventType)
            if actions:
                self.CheckItem(i, False)
                for f in actions:
                    self.parent.debugger.trace(f, evt)
        self.blink(i)
    
    def append(self, event, bold=True):
        data = self.__items
        if event in (item[0] for item in data):
            return
        
        i = len(data)
        name = self.get_name(event)
        item = [event, name, '-', 'no data']
        data.append(item)
        self.InsertItem(i, event)
        for j, v in enumerate(item[:-1]):
            self.SetItem(i, j, str(v))
        if bold:
            self.SetItemFont(i, self.Font.Bold())
        self.blink(i)
    
    def OnSortItems(self, evt): #<wx._controls.ListEvent>
        n = self.ItemCount
        if n < 2:
            return
        
        def _getitem(key):
            return [data[i] for i in range(n) if key(i)]
        
        data = self.__items
        ls = _getitem(self.IsSelected)
        lc = _getitem(self.IsItemChecked)
        lb = _getitem(lambda i: self.GetItemFont(i) == self.Font.Bold())
        f = data[self.FocusedItem]
        
        col = evt.Column
        self.__dir = not self.__dir
        data.sort(key=lambda v: v[col], reverse=self.__dir)
        
        for i, item in enumerate(data):
            for j, v in enumerate(item[:-1]):
                self.SetItem(i, j, str(v))
            self.Select(i, item in ls)
            self.CheckItem(i, item in lc)
            self.SetItemFont(i, self.Font) # reset font
            if item in lb:
                self.SetItemFont(i, self.Font.Bold())
            if item == f:
                self.Focus(i)
    
    def OnItemFocused(self, evt): #<wx._controls.ListEvent>
        i = evt.Index
        item = self.__items[i]
        self.parent.handler("put_scratch", item[-1]) # attribs
        evt.Skip()
    
    def OnItemDClick(self, evt): #<wx._core.MouseEvent>
        i, flag = self.HitTest(evt.Position)
        if i >= 0:
            item = self.__items[i]
            wx.CallAfter(wx.TipWindow, self, item[-1], 512) # attribs
        evt.Skip()


if __name__ == "__main__":
    import mwx
    app = wx.App()
    frm = mwx.Frame(None)
    if 1:
        self = frm.shellframe
        self.mon = EventMonitor(self)
        self.Show()
        self.add_page(self.mon)
        self.rootshell.write("self.shellframe.mon.watch(self.shellframe.mon)")
    frm.Show()
    app.MainLoop()
