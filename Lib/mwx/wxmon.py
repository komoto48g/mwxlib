#! python3
# -*- coding: utf-8 -*-
"""Widget minitor
*** Inspired by wx.lib.eventwatcher ***

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
import warnings
import wx
import wx.lib.eventwatcher as ew
from wx.lib.mixins.listctrl import ListCtrlAutoWidthMixin

from .utilus import where
from .controls import Icon, Clipboard
from .framework import CtrlInterface, Menu


if wx.VERSION < (4,1,0):
    from wx.lib.mixins.listctrl import CheckListCtrlMixin

    class CheckList(wx.ListCtrl, CheckListCtrlMixin):
        def __init__(self, *args, **kwargs):
            wx.ListCtrl.__init__(self, *args, **kwargs)
            CheckListCtrlMixin.__init__(self)
            
            ## self.ToolTip = ''
            self.IsItemChecked = self.IsChecked # for wx 4.1.0 compatibility

else:
    class CheckList(wx.ListCtrl):
        def __init__(self, *args, **kwargs):
            wx.ListCtrl.__init__(self, *args, **kwargs)
            
            ## If we use a custom ToolTip, chkbox will disappear.
            ## To avoid this *BUG* (4.1.1), set a blank string.
            ## Note: the default Tooltip will disappear too.
            ## self.ToolTip = ''
            self.EnableCheckBoxes()


class EventMonitor(CheckList, ListCtrlAutoWidthMixin, CtrlInterface):
    """Event monitor
    
    Attributes:
        parent : shellframe
        target : widget to monitor
    """
    _alist = (
        ("typeId",    62),
        ("typeName", 200),
        ("stamp",     40),
        ("source",     0),
    )
    def __init__(self, parent, **kwargs):
        CheckList.__init__(self, parent,
                           style=wx.LC_REPORT|wx.LC_HRULES, **kwargs)
        ListCtrlAutoWidthMixin.__init__(self)
        CtrlInterface.__init__(self)
        
        self.parent = parent
        self.target = None
        self.Font = wx.Font(9, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        
        self.__prev = None
        self.__dir = True # sort direction
        self.__items = []
        
        for k, (header, w) in enumerate(self._alist):
            self.InsertColumn(k, header, width=w)
        
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnSortItems)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnItemDClick)
        self.Bind(wx.EVT_CONTEXT_MENU, self.OnContextMenu)
        self.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        
        from wx import adv, aui, stc, media
        for module in (adv, aui, stc, media):
            ew.addModuleEvents(module)
        
        @self.handler.bind('*button* pressed')
        @self.handler.bind('*button* released')
        def dispatch(v):
            """Fork mouse events to the parent."""
            self.parent.handler(self.handler.event, v)
            v.Skip()
    
    def OnDestroy(self, evt):
        if evt.EventObject is self:
            self.unwatch()
        evt.Skip()
    
    def OnSetFocus(self, evt):
        self.parent.handler('title_window', self.__class__.__name__)
        evt.Skip()
    
    ## --------------------------------
    ## EventWatcher wrapper interfaces 
    ## --------------------------------
    ew.buildWxEventMap() # build ew._eventBinders and ew._eventIdMap
    
    @staticmethod
    def get_name(event):
        return ew._eventIdMap.get(event, 'Unknown')
    
    @staticmethod
    def get_binder(event):
        return next(x for x in ew._eventBinders if x.typeId == event)
    
    @staticmethod
    def get_watchlist():
        """All watched event binders except noWatchList."""
        return (x for x in ew._eventBinders if x not in ew._noWatchList)
    
    @staticmethod
    def get_actions(event, widget):
        """Wx.PyEventBinder and the handlers."""
        try:
            handlers = widget.__event_handler__[event]
            ## Exclude ew:onWatchedEvent by comparing names instead of objects
            ## cf. [a for a in handlers if a != self.onWatchedEvent]
            return [a for a in handlers if a.__name__ != 'onWatchedEvent']
        except AttributeError:
            pass
        except KeyError:
            print("- No such event: {}".format(event))
    
    def watch(self, widget=None):
        """Begin watching the widget."""
        if widget is None:
            widget = self.__prev # Restart
        if not widget:
            self.unwatch()
            return
        if not isinstance(widget, wx.Object):
            wx.MessageBox("Cannot watch the widget.\n\n"
                          "- {!r} is not a wx.Object.".format(widget))
            return
        self.unwatch()
        self.clear()
        self.target = widget
        ssmap = self.dump(widget, verbose=0)
        for binder in self.get_watchlist():
            event = binder.typeId
            try:
                widget.Bind(binder, self.onWatchedEvent)
                if event in ssmap:
                    self.append(event)
            except Exception as e:
                name = self.get_name(event)
                print(" #{:6d}:{:32s}{!s}".format(event, name, e))
                continue
        self.parent.handler('monitor_begin', widget)
    
    def unwatch(self):
        """End watching the widget."""
        widget = self.target
        if not widget:
            return
        for binder in self.get_watchlist():
            if not widget.Unbind(binder, handler=self.onWatchedEvent):
                print("- Failed to unbind {}:{}".format(binder.typeId, binder))
        self.parent.handler('monitor_end', widget)
        self.__prev = widget
        self.target = None
    
    def onWatchedEvent(self, evt):
        if self:
            self.update(evt)
        evt.Skip()
    
    def dump(self, widget, verbose=True):
        """Dump all event handlers bound to the widget."""
        exclusions = [x.typeId for x in ew._noWatchList]
        ssmap = {}
        try:
            for event in sorted(widget.__event_handler__):
                actions = self.get_actions(event, widget)
                if actions and event not in exclusions:
                    ssmap[event] = actions
                    if verbose:
                        name = self.get_name(event)
                        values = ('\n'+' '*41).join(str(where(a)) for a in actions)
                        print("{:8d}:{:32s}{!s}".format(event, name, values))
        except AttributeError:
            pass
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
        source = ew._makeSourceString(obj) + " id=0x{:X}".format(id(evt))
        ## timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-4]
        stamp = 1
        
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            attribs = ew._makeAttribString(evt)
        
        if wx.VERSION < (4,1,0): # ignore self insert event
            if event == wx.EVT_LIST_INSERT_ITEM.typeId\
              and obj is self:
                return
        
        data = self.__items
        for i, item in enumerate(data):
            if item[0] == event:
                stamp = item[2] + 1
                item[1:] = [name, stamp, source, attribs]
                break
        else:
            i = len(data)
            item = [event, name, stamp, source, attribs]
            data.append(item)
            self.InsertItem(i, event)
        
        for j, v in enumerate(item[:-1]):
            self.SetItem(i, j, str(v))
        
        if self.IsItemChecked(i):
            self.CheckItem(i, False)
            ## if self.get_actions(event, obj):
            ##     self.parent.debugger.set_trace()
            wx.CallAfter(self.parent.debugger.set_trace)
            return
        self.blink(i)
    
    def append(self, event):
        data = self.__items
        if event in (item[0] for item in data):
            return
        
        i = len(data)
        name = self.get_name(event)
        item = [event, name, 0, '-', 'no data']
        data.append(item)
        self.InsertItem(i, event)
        for j, v in enumerate(item[:-1]):
            self.SetItem(i, j, str(v))
        self.SetItemTextColour(i, 'blue')
        self.blink(i)
    
    def blink(self, i):
        if self.GetItemBackgroundColour(i) != wx.Colour('yellow'):
            self.SetItemBackgroundColour(i, "yellow")
            def reset_color():
                if self and i < self.ItemCount:
                    self.SetItemBackgroundColour(i, 'white')
            wx.CallAfter(wx.CallLater, 1000, reset_color)
    
    def OnSortItems(self, evt): #<wx._controls.ListEvent>
        n = self.ItemCount
        if n < 2:
            return
        
        data = self.__items
        f = data[self.FocusedItem]
        ls = [data[i] for i in range(n) if self.IsSelected(i)]
        lc = [data[i] for i in range(n) if self.IsItemChecked(i)]
        lb = [data[i] for i in range(n) if self.GetItemTextColour(i) == 'blue']
        
        col = evt.Column
        self.__dir = not self.__dir
        data.sort(key=lambda v: v[col], reverse=self.__dir)
        
        for i, item in enumerate(data):
            for j, v in enumerate(item[:-1]):
                self.SetItem(i, j, str(v))
            self.Select(i, item in ls)
            self.CheckItem(i, item in lc)
            self.SetItemTextColour(i, 'black') # reset font
            if item in lb:
                self.SetItemTextColour(i, 'blue')
            if item == f:
                self.Focus(i)
    
    def OnItemDClick(self, evt): #<wx._core.MouseEvent>
        i, flag = self.HitTest(evt.Position)
        if i >= 0:
            item = self.__items[i]
            wx.CallAfter(wx.TipWindow, self, item[-1], 512) # attribs
        evt.Skip()
    
    def OnContextMenu(self, evt):
        i = self.FocusedItem
        item = self.__items[i] if i != -1 else []
        obj = self.target
        wnd = self.__prev
        menu = [
            ('No Item selected', item) if not item
        else
            (item[1], Icon('copy'), (
                (1, "Copy typeName",
                    lambda v: Clipboard.write(item[1]),
                    lambda v: v.Enable(item is not None)),
                    
                (2, "Copy typeInfo",
                    lambda v: Clipboard.write('\n'.join(str(x) for x in item)),
                    lambda v: v.Enable(item is not None)),
            )),
            (),
            (11, "Restart watching {}".format(wnd.__class__.__name__), Icon('ghost'),
                 lambda v: self.watch(wnd),
                 lambda v: v.Enable(wnd is not None)),
             
            (12, "Stop watching {}".format(obj.__class__.__name__), Icon('exit'),
                 lambda v: self.unwatch(),
                 lambda v: v.Enable(obj is not None)),
        ]
        Menu.Popup(self, menu)
