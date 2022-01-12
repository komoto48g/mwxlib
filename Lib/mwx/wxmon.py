#! python3
# -*- coding: utf-8 -*-
from pprint import pformat
import inspect
import wx
from wx import aui
from wx import stc
import wx.lib.eventwatcher as ew
from mwx.framework import FSM

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


class EventMonitor(wx.SplitterWindow):
    """Event monitor of the inspector
    
Args:
    parent : inspector of the shell
    """
    handler = property(lambda self: self.__handler)
    shell = property(lambda self: self.__inspector.rootshell)
    
    def __init__(self, parent, *args, **kwargs):
        wx.SplitterWindow.__init__(self, parent, *args, **kwargs)
        
        self.__inspector = parent
        
        self.lctr = EventLogger(self, size=(512,-1))
        self.text = wx.TextCtrl(self, size=(200,-1),
                                style=wx.TE_MULTILINE|wx.TE_PROCESS_ENTER)
        self.SplitVertically(self.lctr, self.text,
                             self.lctr.MinWidth) # no scrollbar padding +20
        
        self.__handler = FSM({ #<EventMonitor.handler>
            0 : {
                   'event_hook' : [ 0, self.on_event_hook ],
                 'item_updated' : [ 0, self.on_item_updated ],
                'item_selected' : [ 0, self.on_item_selected ],
               'item_activated' : [ 0, self.on_item_activated ],
            },
        })
        self.handler.clear(0)
        
        self.__watchedWidget = None
        
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
    
    def OnDestroy(self, evt):
        self.unwatch()
        evt.Skip()
    
    ## --------------------------------
    ## event-watcher interface
    ## Inspired by wx.lib.eventwatcher.
    ## --------------------------------
    
    ew.buildWxEventMap() # build ew._eventBinders and ew._eventIdMap
    ew.addModuleEvents(aui) # + some additives
    ew.addModuleEvents(stc)
    
    ## Events that should not be watched by default
    _noWatchList = [
        wx.EVT_PAINT,
        wx.EVT_NC_PAINT,
        wx.EVT_ERASE_BACKGROUND,
        wx.EVT_IDLE,
        wx.EVT_UPDATE_UI,
        wx.EVT_UPDATE_UI_RANGE,
        wx.EVT_TOOL,
        wx.EVT_TOOL_RANGE, # menu items (typeId=10018)
        wx.EVT_MENU,
        10018, # other command menu?
    ]
    
    target = property(lambda self: self.__watchedWidget)
    
    def get_watched_events(self):
        """All watched events except noWatchList"""
        def watch_only(v):
            return (v not in self._noWatchList
                and v.typeId not in self._noWatchList)
        return filter(watch_only, ew._eventBinders)
    
    def get_bound_handlers(self, event, widget=None):
        """Wx.PyEventBinder and the handlers"""
        widget = widget or self.target
        if widget:
            try:
                actions = widget.__event_handler__[event]
                handlers = [a for a in actions if a != self.onWatchedEvent]
                ## handlers = [a for a in actions if a.__name__ != 'onWatchedEvent']
                binder = next(x for x in ew._eventBinders if x.typeId == event)
                return binder, handlers
            except KeyError:
                print("- No such event: {}".format(event))
        return None, []
    
    def watch(self, widget):
        """Begin watching"""
        if not isinstance(widget, wx.Object):
            return
        self.unwatch()
        self.lctr.clear()
        self.__watchedWidget = widget
        ssmap = self.dump(widget, verbose=1)
        for binder in self.get_watched_events():
            widget.Bind(binder, self.onWatchedEvent)
            if binder.typeId in ssmap:
                self.lctr.add_event(binder.typeId)
        self.__inspector.handler("add_page", self)
        self.shell.handler("monitor_begin", self.target)
    
    def unwatch(self):
        """End watching"""
        if not self.target:
            return
        ## self.__inspector.handler("remove_page", self)
        self.shell.handler("monitor_end", self.target)
        for binder in self.get_watched_events():
            if not self.target.Unbind(binder, handler=self.onWatchedEvent):
                print("- Failed to unbind {}:{}".format(binder.typeId, binder))
        self.__watchedWidget = None
    
    def onWatchedEvent(self, evt):
        if self:
            self.lctr.update(evt)
        evt.Skip()
    
    def dump(self, widget, verbose=True):
        """Dump all event handlers bound to the widget"""
        if not isinstance(widget, wx.Object):
            return
        def _where(obj):
            try:
                filename = inspect.getsourcefile(obj)
                src, lineno = inspect.getsourcelines(obj)
                return "{!s}:{}:{!s}".format(filename, lineno, src[0].rstrip())
            except TypeError:
                return repr(obj)
        ssmap = {}
        for event, actions in sorted(widget.__event_handler__.items()):
            la = [a for a in actions if a != self.onWatchedEvent]
            if la:
                ssmap[event] = la
                if verbose:
                    name = ew._eventIdMap.get(event, 'Unknown')
                    values = ('\n'+' '*41).join(_where(a) for a in la)
                    print("{:8d}:{:32s}{!s}".format(event, name, values))
        return ssmap
    
    def hook(self, event, widget):
        """Add hook for the event bound to the widget"""
        binder, actions = self.get_bound_handlers(event, widget)
        for f in actions:
            def _hook(v):
                if not widget.Unbind(binder, handler=_hook):
                    print("- Failed to unbind hook for {}".format(event))
                self.__inspector.debugger.trace(f, v)
            widget.Bind(binder, _hook)
        return actions
    
    def unhook(self, event, widget):
        """Remove hook from the events bound to the widget"""
        binder, actions = self.get_bound_handlers(event, widget)
        for f in actions[::-1]:
            if f.__name__ == '_hook':
                if not widget.Unbind(binder, handler=f):
                    print("- Failed to unbind hook for {}".format(event))
    
    ## --------------------------------
    ## Actions for event-logger
    ## --------------------------------
    
    def on_event_hook(self, evt):
        event = evt.EventType
        binder, actions = self.get_bound_handlers(event)
        for f in actions:
            self.__inspector.debugger.trace(f, evt)
    
    def on_item_activated(self, item):
        event = item[0]
        binder, actions = self.get_bound_handlers(event)
        tip = pformat(actions or None)
        wx.CallAfter(wx.TipWindow, self, tip, 512)
    
    def on_item_updated(self, item):
        event = item[0]
        binder, actions = self.get_bound_handlers(event)
        if actions:
            i = self.lctr.keys.index(event)
            self.lctr.SetItemFont(i, self.lctr.Font.Bold())
    
    def on_item_selected(self, item):
        self.text.SetValue(item[-1]) # => attribs


class EventLogger(_ListCtrl):
    """Event notify logger
    """
    data = property(lambda self: self.__items)
    keys = property(lambda self: [item[0] for item in self.__items])
    
    def __init__(self, parent, **kwargs):
        _ListCtrl.__init__(self, parent,
                           style=wx.LC_REPORT|wx.LC_HRULES, **kwargs)
        
        self.parent = parent
        
        self.Font = wx.Font(9, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        
        self.alist = ( # assoc list of column names
            ("typeId",    62),
            ("typeName", 200),
            ("stats",     50),
            ("source",   200),
            # item[-1]: attributes,
        )
        for k, (header, w) in enumerate(self.alist):
            self.InsertColumn(k, header, width=w)
        
        self.__dir = True # sort direction
        self.__items = [] # data holder
        
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnSortItems)
        
        def dispatch(binder, signal):
            def _dispatch(evt): #<wx._core.ListEvent>
                i = evt.Index
                item = self.__items[i]
                self.parent.handler(signal, item)
            self.Bind(binder, _dispatch)
        
        dispatch(wx.EVT_LIST_ITEM_SELECTED, 'item_selected')
        dispatch(wx.EVT_LIST_ITEM_DESELECTED, 'item_deselected')
        dispatch(wx.EVT_LIST_ITEM_RIGHT_CLICK, 'item_right_clicked')
        dispatch(wx.EVT_LIST_ITEM_MIDDLE_CLICK, 'item_middle_clicked')
        dispatch(wx.EVT_LIST_ITEM_ACTIVATED, 'item_activated')
    
    def update(self, evt):
        event = evt.EventType
        obj = evt.EventObject
        name = ew._eventIdMap.get(event, 'Unknown')
        source = "{} {!r}".format(obj.__class__.__name__,
                                  obj.Name if hasattr(obj, 'Name') else '')
        ## source = ew._makeSourceString(obj)
        attribs = ew._makeAttribString(evt)
        
        if wx.VERSION < (4,1,0): # ignore self insert
            if event == wx.EVT_LIST_INSERT_ITEM.typeId\
              and obj is self:
                return
        
        for i, item in enumerate(self.__items):
            if item[0] == event:
                item[1:] = [name, item[2]+1, source, attribs]
                break
        else:
            i = len(self.__items)
            item = [event, name, 1, source, attribs] # new data:list
            self.__items.append(item)
            self.InsertItem(i, event)
        
        for j, v in enumerate(item[:-1]):
            self.SetItem(i, j, str(v))
        self.parent.handler('item_updated', item)
        
        if self.IsItemChecked(i):
            self.CheckItem(i, False)
            self.parent.handler('event_hook', evt)
        
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
    
    def add_event(self, event):
        if event in self.keys: # no need to add
            return
        i = len(self.__items)
        name = ew._eventIdMap.get(event, 'Unknown')
        item = [event, name, 0, '', '']
        self.__items.append(item)
        self.InsertItem(i, event)
        for j, v in enumerate(item[:-1]):
            self.SetItem(i, j, str(v))
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
            self.parent.handler('item_updated', item)
        self.Focus(self.__items.index(f))  # focus (one)
    
    def OnMotion(self, evt): #<wx._core.MouseEvent>
        i, flag = self.HitTest(evt.GetPosition())
        if i >= 0:
            item = self.__items[i]
            self.parent.handler('item_motion', item)
        evt.Skip()


if __name__ == "__main__":
    import mwx
    app = wx.App()
    frm = mwx.Frame(None)
    if 1:
        self = frm.inspector
        frm.mon = EventMonitor(self)
        frm.mon.handler.debug = 0
        self.rootshell.write("self.mon.watch(self)")
        self.Show()
    frm.Show()
    app.MainLoop()
