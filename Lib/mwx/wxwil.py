#! python3
"""Watcher of namespace info.
"""
from collections.abc import Mapping
import wx
from wx.py import dispatcher
from wx.lib.mixins.listctrl import ListCtrlAutoWidthMixin

from .controls import Icon, Clipboard
from .framework import CtrlInterface, Menu


def _repr(value):
    try:
        return repr(value)
    except Exception as e:
        return f"- {e!r}"


class LocalsWatcher(wx.ListCtrl, ListCtrlAutoWidthMixin, CtrlInterface):
    """Locals info watcher.
    
    Attributes:
        parent: shellframe
        target: namespace to watch
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
        
        self.Font = wx.Font(9, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        
        self.parent = parent
        self.target = None
        self._dir = True  # sort direction
        self._items = []
        self._alist = {
            "key"   : 140,
            "value" : 0,
        }
        for col, (header, w) in enumerate(self._alist.items()):
            self.InsertColumn(col, header, width=w)
        
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnSortItems)
        self.Bind(wx.EVT_CONTEXT_MENU, self.OnContextMenu)
        
        dispatcher.connect(receiver=self._update, signal='Interpreter.push')

    def _update(self, *args, **kwargs):
        if not self:
            dispatcher.disconnect(receiver=self._update, signal='Interpreter.push')
            return
        self.update()

    def watch(self, namespace):
        self.clear()
        if isinstance(namespace, (dict, Mapping)):  # for f_locals:Mapping type (>= PY313)
            self.target = namespace
        elif hasattr(namespace, '__dict__'):
            self.target = vars(namespace)
        else:
            self.unwatch()
            return
        try:
            self.Freeze()
            self.DeleteAllItems()
            for key, value in self.target.items():
                vstr = _repr(value)
                i = len(self._items)
                item = [key, vstr]
                self._items.append(item)
                self.InsertItem(i, key)
                self.SetItem(i, 1, vstr)
                self.blink(i)
        finally:
            self.Thaw()

    def unwatch(self):
        self.target = None

    ## --------------------------------
    ## Actions on list items.
    ## --------------------------------

    def clear(self):
        self.DeleteAllItems()
        self._items.clear()

    def update(self):
        if not self.target:
            return
        n = len(self._items)
        for i, item in enumerate(self._items[::-1]):
            if item[0] not in self.target:
                j = n-i-1
                self.DeleteItem(j)
                del self._items[j]
        
        for key, value in self.target.items():
            vstr = _repr(value)
            i = next((i for i, item in enumerate(self._items) if item[0] == key), None)
            if i is not None:
                if self._items[i][1] == vstr:
                    continue
                self._items[i][1] = vstr
            else:
                i = len(self._items)
                item = [key, vstr]
                self._items.append(item)
                self.InsertItem(i, key)
            self.SetItem(i, 1, vstr)
            self.blink(i)
            self.EnsureVisible(i)

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
            key, vstr = self._items[i]
            lines.append(f"{key} = {vstr}")
        Clipboard.write('\n'.join(lines))

    def sort_items(self, col):
        self._dir = not self._dir
        rows = [(item, self.IsSelected(i),
                       self.FocusedItem == i) for i, item in enumerate(self._items)]
        rows.sort(key=lambda r: r[0][col], reverse=self._dir)
        self._items[:] = [r[0] for r in rows]
        
        for i, (item, sel, focused) in enumerate(rows):
            for j, v in enumerate(item):
                self.SetItem(i, j, v)
            self.Select(i, sel)
            if focused:
                self.Focus(i)

    def OnSortItems(self, evt):  # <wx._core.ListEvent>
        if self.ItemCount > 1:
            self.sort_items(evt.Column)

    def OnContextMenu(self, evt):
        Menu.Popup(self, [
            (1, "Copy data", Icon('copy'),
                lambda v: self.copy_items(),
                lambda v: v.Enable(self.SelectedItemCount)),
        ])
