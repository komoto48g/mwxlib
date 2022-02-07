#! python3
# -*- coding: utf-8 -*-
"""Local info list tool

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
import wx
from wx.py import dispatcher
try:
    from controls import ListCtrl
except ImportError:
    from .controls import ListCtrl


class LocalsWatcher(ListCtrl):
    """Locals info watcher
    """
    def __init__(self, parent, **kwargs):
        ListCtrl.__init__(self, parent,
                          style=wx.LC_REPORT|wx.LC_HRULES, **kwargs)
        
        self.Font = wx.Font(9, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        
        self.__dir = True # sort direction
        self.__items = []
        self.__locals = {}
        
        self.alist = (
            ("key",   140),
            ("value", 280),
        )
        for k, (header, w) in enumerate(self.alist):
            self.InsertColumn(k, header, width=w)
        
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnSortItems)
        
        dispatcher.connect(receiver=self.push, signal='Interpreter.push')
    
    def push(self, command, more):
        """Receiver for Interpreter.push signal."""
        if not self:
            dispatcher.disconnect(receiver=self.push, signal='Interpreter.push')
            return
        self.update(self.__locals)
    
    def watch(self, locals):
        if not locals:
            self.unwatch()
            return
        if not isinstance(locals, dict):
            wx.MessageBox("Cannot watch the locals.\n\n"
                          "- {!r} is not a dict object.".format(locals))
            return
        self.__locals = locals
        self.update(self.__locals)
    
    def unwatch(self):
        self.__locals = None
    
    def clear(self):
        self.DeleteAllItems()
        del self.__items[:]
    
    def update(self, attr):
        if not attr:
            return
        data = self.__items
        n = len(data)
        for i, (k, v) in enumerate(data[::-1]):
            if k not in attr:
                j = n-i-1
                self.DeleteItem(j)
                del data[j]
        
        for key, value in attr.items():
            vstr = str(value)
            i = next((i for i, item in enumerate(data)
                                    if item[0] == key), None)
            if i is not None:
                if data[i][1] == vstr:
                    continue
                data[i][1] = vstr # Update data to locals
            else:
                i = len(data)
                item = [key, vstr]
                data.append(item)
                self.InsertItem(i, key)
            self.SetItem(i, 1, vstr)
            self.blink(i)
            ## self.EnsureVisible(i)
    
    def OnSortItems(self, evt): #<wx._controls.ListEvent>
        n = self.ItemCount
        if n < 2:
            return
        
        def _getitem(key):
            return [data[i] for i in range(n) if key(i)]
        
        data = self.__items
        ls = _getitem(self.IsSelected)
        f = data[self.FocusedItem]
        
        col = evt.Column
        self.__dir = not self.__dir
        data.sort(key=lambda v: v[col].upper(), reverse=self.__dir)
        
        for i, item in enumerate(data):
            for j, v in enumerate(item):
                self.SetItem(i, j, v)
            self.Select(i, item in ls)
            if item == f:
                self.Focus(i)
