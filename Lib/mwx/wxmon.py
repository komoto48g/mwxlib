#! python3
"""Widget monitor.

*** Inspired by wx.lib.eventwatcher ***
"""
import wx
import wx.lib.eventwatcher as ew
from wx.lib.mixins.listctrl import ListCtrlAutoWidthMixin

from .utilus import where, ignore
from .controls import Icon, Clipboard
from .framework import CtrlInterface, Menu


class EventMonitor(wx.ListCtrl, ListCtrlAutoWidthMixin, CtrlInterface):
    """Event monitor.
    
    Attributes:
        parent: shellframe
        target: widget to monitor
    """
    def __init__(self, parent, **kwargs):
        wx.ListCtrl.__init__(self, parent,
                             style=wx.LC_REPORT|wx.LC_HRULES, **kwargs)
        ListCtrlAutoWidthMixin.__init__(self)
        CtrlInterface.__init__(self)
        
        self.EnableCheckBoxes()
        
        self.parent = parent
        self.target = None
        self._target = None  # previous target
        
        self.Font = wx.Font(9, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        
        self.__dir = True  # sort direction
        self.__items = []
        
        _alist = (
            ("typeId",    62),
            ("typeName", 200),
            ("stamp",     40),
            ("source",     0),
        )
        for k, (header, w) in enumerate(_alist):
            self.InsertColumn(k, header, width=w)
        
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnSortItems)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnItemActivated)
        self.Bind(wx.EVT_CONTEXT_MENU, self.OnContextMenu)
        self.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        
        from wx import adv, aui, stc, media
        for module in (adv, aui, stc, media):
            ew.addModuleEvents(module)
        
        @self.handler.bind('*button* pressed')
        @self.handler.bind('*button* released')
        def dispatch(evt):
            """Fork events to the parent."""
            self.parent.handler(self.handler.current_event, evt)
            evt.Skip()
        
        @self.handler.bind('C-c pressed')
        def copy(evt):
            self.copy()

    def OnDestroy(self, evt):
        if evt.EventObject is self:
            try:
                self.unwatch()
            except Exception as e:
                print(e)
        evt.Skip()

    def OnSetFocus(self, evt):
        title = "{} target: {}".format(self.__class__.__name__, self.target)
        self.parent.handler('title_window', title)
        evt.Skip()

    ## --------------------------------
    ## EventWatcher wrapper interface.
    ## --------------------------------
    ew.buildWxEventMap()  # build ew._eventBinders and ew._eventIdMap

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

    def watch(self, widget=None):
        """Begin watching the widget."""
        self.unwatch()
        self.clear()
        if widget is None:
            widget = self._target  # Resume watching the previous target.
        if not widget:
            return
        if not isinstance(widget, wx.Object):
            wx.MessageBox("Cannot watch the widget.\n\n"
                          "- {!r} is not a wx.Object.".format(widget),
                          self.__module__)
            return
        self._target = widget
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
                print("- Failed to unbind {}: {}".format(binder.typeId, widget))
        self.parent.handler('monitor_end', widget)
        self.target = None

    def onWatchedEvent(self, evt):
        if self:
            self.update(evt)
        evt.Skip()

    def dump(self, widget, verbose=True):
        """Dump all event handlers bound to the widget."""
        ## Note: This will not work unless [Monkey-patch for wx.core] is applied.
        ##       This is currently deprecated (see below).
        exclusions = [x.typeId for x in ew._noWatchList]
        ssmap = {}
        try:
            for event, handlers in sorted(widget.__event_handler__.items()):
                actions = [v for k, v in handlers if v.__name__ != 'onWatchedEvent']
                if actions and event not in exclusions:
                    ssmap[event] = actions
                    if verbose:
                        name = self.get_name(event)
                        print("{:8d}:{}".format(event, name))
                        for v in actions:
                            print(' '*8, "> {}".format(where(v)))
        except AttributeError:
            pass
        return ssmap

    ## --------------------------------
    ## Actions on list items.
    ## --------------------------------

    def clear(self):
        self.DeleteAllItems()
        del self.__items[:]

    def update(self, evt):
        event = evt.EventType
        obj = evt.EventObject
        name = self.get_name(event)
        source = ew._makeSourceString(obj) + " id=0x{:X}".format(id(evt))
        stamp = 1
        try:
            with ignore(DeprecationWarning):
                attribs = ew._makeAttribString(evt)
        except Exception:
            attribs = ''  # Failed to get event attributes; possibly <BdbQuit>.
        data = self.__items
        for item in data:
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
            
            def _reset_color():
                if self and i < self.ItemCount:
                    self.SetItemBackgroundColour(i, 'white')
            wx.CallAfter(wx.CallLater, 1000, _reset_color)

    def copy(self):
        if not self.SelectedItemCount:
            return
        text = ''
        for i in range(self.ItemCount):
            if self.IsSelected(i):
                event, name, *_, attribs = self.__items[i]
                text += "{}\t{}\n{}\n\n".format(event, name, attribs)
        Clipboard.write(text[:-1])

    def OnSortItems(self, evt):  # <wx._core.ListEvent>
        n = self.ItemCount
        if n < 2:
            return
        
        data = self.__items
        fi = data[self.FocusedItem]
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
            self.SetItemTextColour(i, 'black')  # reset font
            if item in lb:
                self.SetItemTextColour(i, 'blue')
            if item == fi:
                self.Focus(i)

    def OnItemActivated(self, evt):  # <wx._core.ListEvent>
        item = self.__items[evt.Index]
        wx.CallAfter(wx.TipWindow, self, item[-1], 512)  # attribs

    def OnContextMenu(self, evt):
        obj = self.target
        wnd = self._target
        Menu.Popup(self, [
            (1, "Copy data", Icon('copy'),
                lambda v: self.copy(),
                lambda v: v.Enable(self.SelectedItemCount)),
            (),
            (11, "Restart watching {}".format(wnd.__class__.__name__), Icon('ghost'),
                 lambda v: self.watch(wnd),
                 lambda v: v.Enable(wnd is not None)),
             
            (12, "Stop watching {}".format(obj.__class__.__name__), Icon('exit'),
                 lambda v: self.unwatch(),
                 lambda v: v.Enable(obj is not None)),
        ])


def monit(widget=None, **kwargs):
    """Wx.py tool for watching events of the widget.
    """
    from wx.lib.eventwatcher import EventWatcher
    ew = EventWatcher(None, **kwargs)
    ew.watch(widget)
    ew.Show()
    return ew


## Monkey-patch for wx.core (deprecated).
if 0:
    from wx import core  # PY3

    def _EvtHandler_Bind(self, event, handler=None, source=None, id=wx.ID_ANY, id2=wx.ID_ANY):
        """
        Bind an event to an event handler.
        (override) Record the handler in the list and return the handler.
        """
        if handler is None:
            return lambda f: _EvtHandler_Bind(self, event, f, source, id, id2)
        
        assert isinstance(event, wx.PyEventBinder)
        assert callable(handler) or handler is None
        assert source is None or hasattr(source, 'GetId')
        if source is not None:
            id  = source.GetId()
        event.Bind(self, id, id2, handler)
        
        ## Record all handlers.
        try:
            vmap = self.__event_handler__
        except AttributeError:
            vmap = self.__event_handler__ = {}
        try:
            vmap[event.typeId].insert(0, (id, handler))
        except KeyError:
            vmap[event.typeId] = [(id, handler)]
        return handler

    core.EvtHandler.Bind = _EvtHandler_Bind
    ## del _EvtHandler_Bind

    def _EvtHandler_Unbind(self, event, source=None, id=wx.ID_ANY, id2=wx.ID_ANY, handler=None):
        """
        Disconnects the event handler binding for event from `self`.
        Returns ``True`` if successful.
        (override) Delete the handler from the list.
        """
        if source is not None:
            id  = source.GetId()
        retval = event.Unbind(self, id, id2, handler)
        
        ## Remove the specified handler or all handlers.
        if retval:
            try:
                vmap = self.__event_handler__
            except AttributeError:
                return retval
            try:
                handlers = vmap[event.typeId]
                if handler or id != wx.ID_ANY:
                    for v in handlers.copy():
                        if v[0] == id or v[1] == handler:
                            handlers.remove(v)
                else:
                    handlers.pop(0)  # No optional arguments are specified.
                if not handlers:
                    del vmap[event.typeId]
            except KeyError:
                pass  # Note: vmap is actually inconsistent, but ignored.
        return retval

    core.EvtHandler.Unbind = _EvtHandler_Unbind
    ## del _EvtHandler_Unbind

    del core
