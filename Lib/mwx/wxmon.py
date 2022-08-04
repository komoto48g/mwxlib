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
try:
    from utilus import where
    from framework import CtrlInterface, Menu
    from controls import Icon, Clipboard
except ImportError:
    from .utilus import where
    from .framework import CtrlInterface, Menu
    from .controls import Icon, Clipboard

if wx.VERSION < (4,1,0):
    from wx.lib.mixins.listctrl import CheckListCtrlMixin
    
    class CheckList(wx.ListCtrl, CheckListCtrlMixin):
        def __init__(self, *args, **kwargs):
            wx.ListCtrl.__init__(self, *args, **kwargs)
            CheckListCtrlMixin.__init__(self)
            
            ## self.ToolTip = ''
            self.IsItemChecked = self.IsChecked # for wx 4.1 compatibility

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
    """
    parent = property(lambda self: self.__shellframe)
    target = property(lambda self: self.__widget)
    
    def __init__(self, parent, **kwargs):
        CheckList.__init__(self, parent,
                           style=wx.LC_REPORT|wx.LC_HRULES, **kwargs)
        ListCtrlAutoWidthMixin.__init__(self)
        CtrlInterface.__init__(self)
        
        self.Font = wx.Font(9, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        
        self.__shellframe = parent
        self.__widget = None
        self.__prev = None
        self.__dir = True # sort direction
        self.__items = []
        
        self.alist = (
            ("typeId",    62),
            ("typeName", 200),
            ("stamp",     40),
            ("source",     0),
        )
        for k, (header, w) in enumerate(self.alist):
            self.InsertColumn(k, header, width=w)
        
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnSortItems)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnItemDClick)
        self.Bind(wx.EVT_CONTEXT_MENU, self.OnContextMenu)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        
        self.add_module = ew.addModuleEvents
        
        from wx import adv, aui, stc, media
        for module in (adv, aui, stc, media):
            self.add_module(module)
        
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
        return (x for x in ew._eventBinders if x not in ew._noWatchList)
    
    @staticmethod
    def get_actions(event, widget):
        """Wx.PyEventBinder and the handlers"""
        if widget and hasattr(widget, '__event_handler__'):
            try:
                handlers = widget.__event_handler__[event]
                ## Exclude ew:onWatchedEvent by comparing names instead of objects
                ## cf. [a for a in handlers if a != self.onWatchedEvent]
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
        self.__widget = widget
        ssmap = self.dump(widget, verbose=1)
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
        """End watching"""
        widget = self.__widget
        if not widget:
            return
        for binder in self.get_watchlist():
            if not widget.Unbind(binder, handler=self.onWatchedEvent):
                print("- Failed to unbind {}:{}".format(binder.typeId, binder))
        self.parent.handler('monitor_end', widget)
        self.__prev = widget
        self.__widget = None
    
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
            actions = self.get_actions(event, widget)
            if actions and event not in exclusions:
                ssmap[event] = actions
                if verbose:
                    name = self.get_name(event)
                    values = ('\n'+' '*41).join(str(where(a)) for a in actions)
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
            self.parent.debugger.set_trace()
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
        
        def _getitem(key):
            return [data[i] for i in range(n) if key(i)]
        
        data = self.__items
        ls = _getitem(self.IsSelected)
        lc = _getitem(self.IsItemChecked)
        lb = _getitem(lambda i: self.GetItemTextColour(i) == 'blue')
        f = data[self.FocusedItem]
        
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
    
    ## @property
    ## def SelectedItems(self):
    ##     return filter(self.IsSelected, range(self.ItemCount))
    
    def OnContextMenu(self, evt):
        i = self.FocusedItem
        item = self.__items[i] if i != -1 else []
        obj = self.__widget
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


if __name__ == "__main__":
    from graphman import Frame
    
    app = wx.App()
    frm = Frame(None)
    frm.load_plug(EventMonitor, show=1) #>>> self.plug.watch(self.plug)
    frm.get_plug("wxmon").plug.watch(frm.shellframe.ghost)
    frm.Show()
    app.MainLoop()
