#! python3
"""Widget monitor.

*** Inspired by wx.lib.eventwatcher ***
"""
import wx
import wx.lib.eventwatcher as ew
from wx.lib.mixins.listctrl import ListCtrlAutoWidthMixin

from .utilus import where, ignore
from .controls import Icon, Clipboard
from .framework import CtrlInterface, Menu, ignore_wxlog


class EventMonitor(wx.ListCtrl, ListCtrlAutoWidthMixin, CtrlInterface):
    """Event monitor.
    
    Attributes:
        parent: shellframe
        target: widget to monitor
    """
    @property
    def selected_items(self):
        return filter(self.IsSelected, range(self.ItemCount))

    @property
    def checked_items(self):
        return filter(self.IsItemChecked, range(self.ItemCount))

    def __init__(self, parent, **kwargs):
        wx.ListCtrl.__init__(self, parent, style=wx.LC_REPORT|wx.LC_HRULES, **kwargs)
        ListCtrlAutoWidthMixin.__init__(self)
        CtrlInterface.__init__(self)
        
        self.EnableCheckBoxes()
        self.Font = wx.Font(9, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        
        self.parent = parent
        self.target = None
        self._target = None  # previous target
        self._dir = True  # sort direction
        self._items = []
        self._attribs = {}
        self._alist = (
            ("typeId",    62),
            ("typeName", 200),
            ("stamp",     40),
            ("source",     0),
        )
        for k, (header, w) in enumerate(self._alist):
            self.InsertColumn(k, header, width=w)
        
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnSortItems)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnItemActivated)
        self.Bind(wx.EVT_CONTEXT_MENU, self.OnContextMenu)
        self.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        
        with ignore_wxlog():
            from wx import adv, aui, stc, media
            for module in (adv, aui, stc, media):
                ew.addModuleEvents(module)

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
        ssmap = self._dump(widget, verbose=0)  # Currently deprecated.
        for binder in self.get_watchlist():
            event = binder.typeId
            try:
                widget.Bind(binder, self.onWatchedEvent)
                if event in ssmap:
                    self._append(event)  # Currently deprecated.
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

    def _dump(self, widget, verbose=True):
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
        self._items.clear()
        self._attribs.clear()

    def update(self, evt):
        event = evt.EventType
        obj = evt.EventObject
        name = self.get_name(event)
        source = ew._makeSourceString(obj) + " id=0x{:X}".format(id(evt))
        try:
            with ignore(DeprecationWarning):
                attribs = ew._makeAttribString(evt)
        except Exception:
            attribs = ''  # Failed to get event attributes; possibly <BdbQuit>.
        self._attribs[event] = attribs
        
        for i, item in enumerate(self._items):  # noqa # i used as a counter
            if item[0] == event:
                stamp = item[2] + 1
                item[1:] = [name, stamp, source]
                break
        else:
            stamp = 1
            i = len(self._items)
            item = [event, name, stamp, source]
            self._items.append(item)
            self.InsertItem(i, event)
        
        for j, v in enumerate(item):
            self.SetItem(i, j, str(v))
        
        if self.IsItemChecked(i):
            self.CheckItem(i, False)
            self.parent.debugger.set_trace()
            return
        self.blink(i)

    def _append(self, event):
        if event in (item[0] for item in self._items):
            return
        
        i = len(self._items)
        name = self.get_name(event)
        item = [event, name, 0, '-', 'no data']
        self._items.append(item)
        self.InsertItem(i, event)
        for j, v in enumerate(item):
            self.SetItem(i, j, str(v))
        self.SetItemTextColour(i, 'blue')
        self.blink(i)

    def blink(self, i):
        if self.GetItemBackgroundColour(i) != wx.Colour('yellow'):
            self.SetItemBackgroundColour(i, "yellow")
            
            def _reset():
                if self and i < self.ItemCount:
                    self.SetItemBackgroundColour(i, 'white')
            wx.CallAfter(wx.CallLater, 1000, _reset)

    def copy_items(self):
        if not self.SelectedItemCount:
            return
        lines = []
        for i in self.selected_items:
            event, name, *_ = self._items[i]
            attribs = self._attribs[event]
            lines.append(f"{event}\t{name}\n{attribs}")
        Clipboard.write("\n\n".join(lines))

    def sort_items(self, col):
        self._dir = not self._dir
        rows = [(item, self.IsSelected(i),
                       self.IsItemChecked(i),
                       self.GetItemTextColour(i),
                       self.FocusedItem == i) for i, item in enumerate(self._items)]
        rows.sort(key=lambda r: r[0][col], reverse=self._dir)
        self._items[:] = [r[0] for r in rows]
        
        for i, (item, sel, chk, color, focused) in enumerate(rows):
            for j, v in enumerate(item):
                self.SetItem(i, j, str(v))
            self.Select(i, sel)
            self.CheckItem(i, chk)
            self.SetItemTextColour(i,
                    color if color.IsOk() else
                    wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT))
            if focused:
                self.Focus(i)

    def OnSortItems(self, evt):  # <wx._core.ListEvent>
        if self.ItemCount > 1:
            self.sort_items(evt.Column)

    def OnItemActivated(self, evt):  # <wx._core.ListEvent>
        item = self._items[evt.Index]
        wx.CallAfter(wx.TipWindow, self, self._attribs[item[0]], 512)

    def OnContextMenu(self, evt):
        obj = self.target
        wnd = self._target
        Menu.Popup(self, [
            (1, "Copy data", Icon('copy'),
                lambda v: self.copy_items(),
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
            id = source.GetId()
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
            id = source.GetId()
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
