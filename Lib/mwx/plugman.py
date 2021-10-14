#! python3
# -*- coding: utf-8 -*-
"""Plug manager

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
import copy
import wx
from . import framework as mwx
from .framework import CtrlInterface, TreeList
from .controls import Icon


class ItemData(object):
    """Item data for TreeCtrl
    
Attributes:
       tree : owner tree object
       plug : owner plugin object
   callback : a function which is called from menu
     status : status of the plugin (default -1)
     symbol : map of status:icons idx
    """
    def __init__(self, tree, plug=None, callback=None, tip=None):
        self.tree = tree
        self.plug = plug
        self.callback = callback
        self.__doc__ = plug.__doc__ if plug else (tip or '')
        self.symbol = {-3:6, -2:2, -1:1, False:3, True:4, None:5,}
        self.status = -1
    
    def __deepcopy__(self, memo):
        """Called from deepcopy to export status"""
        return self.status
    
    def update_status(self, status):
        self.status = status
        self.tree.SetItemImage(self.ItemId, self.symbol.get(status))
    
    def get_children(self):
        """Generate items in the branch associated with this data:item"""
        item, cookie = self.tree.GetFirstChild(self.ItemId)
        while item.IsOk():
            yield self.tree.GetItemData(item)
            item, cookie = self.tree.GetNextChild(self.ItemId, cookie)


class TreeCtrl(wx.TreeCtrl, CtrlInterface, TreeList):
    icons = (
        'folder',   # 0: 
        'file',     # 1: (default)
        '->',       # 2: (busy) in process
        'w',        # 3: (false) 0=failure
        'v',        # 4: (true) 1=success
        '!!',       # 5: (nan) error
        '!!!',      # 6: (nil) exception
    )
    def __init__(self, parent, **kwargs):
        wx.TreeCtrl.__init__(self, parent, **kwargs)
        CtrlInterface.__init__(self)
        TreeList.__init__(self)
        
        self.li = wx.ImageList(16,16)
        for icon in self.icons:
            self.li.Add(Icon(icon, (16,16)))
        self.SetImageList(self.li)
        
        self._root = None
        
        self.handler.update({
            0 : {
             '*Rbutton pressed' : (0, self.OnRightDown),
               'Lbutton dclick' : (0, self.OnLeftDclick),
                       'motion' : (0, self.OnMotion),
            },
        })
        self.Bind(wx.EVT_MOTION, lambda v: self.handler('motion', v))
    
    def reset(self):
        self.DeleteAllItems()
        self._root = self.AddRoot("Root")
        for branch in self:
            self.set_item(self._root, *branch)
    
    def append(self, key, value):
        self[key] = value
        if not self._root:
            return self.reset()
        rootkey = key.partition('/')[0]
        self.set_item(self._root, rootkey, self[rootkey])
        self.Refresh()
    
    def remove(self, key):
        del self[key]
        self.reset()
    
    def get_item(self, parent, key):
        if '/' in key:
            a, b = key.split('/', 1)
            child = self.get_item(parent, a)
            return self.get_item(child, b)
        
        item, cookie = self.GetFirstChild(parent)
        while item.IsOk():
            if key == self.GetItemText(item):
                return item
            item, cookie = self.GetNextChild(parent, cookie)
    
    def set_item(self, parent, key, *values):
        if '/' in key:
            a, b = key.split('/', 1)
            child = self.get_item(parent, a)
            return self.set_item(child, b, *values)
        
        item = self.get_item(parent, key) or self.AppendItem(parent, key)
        data = values[0]
        if isinstance(data, ItemData):
            self.SetItemData(item, data)
            data.ItemId = item # set reference to the own item
            
            if len(values) == 1: # => (key, data)
                data.update_status(data.status) # resotre session
                return
            
            data.symbol[-1] = 0 # set default icon as 'folder'
        
        for branch in values[-1]: # => (key, data, branches)
            self.set_item(item, *branch)
        self.SetItemImage(item, image=0)
    
    def get_flags(self):
        """Get all flags in the branches"""
        return copy.deepcopy(list(self)) # => ItemData.__deepcopy__
    
    def set_flags(self, temp, tree=None):
        """Set temp flags to the tree (or self) as most as possible
        temp : TreeList template of flags to copy to the tree
        """
        for org, branch in zip(temp, tree or self):
            tag, flags = org[0], org[-1]
            key, data = branch[0], branch[-1]
            if key != tag:
                raise KeyError("Failed to restore status: "
                               "got inconsistent keys {!r}, {!r})".format(tag, key))
            if isinstance(data, ItemData):
                data.update_status(flags)
            else:
                self.set_flags(flags, data)
    
    ## --------------------------------
    ## Interface for event handler
    ## --------------------------------
    
    def OnMotion(self, evt):
        item, flag = self.HitTest(evt.GetPosition())
        if item.IsOk():
            try:
                data = self.GetItemData(item)
                self.SetToolTip(data.__doc__)
            except AttributeError:
                self.SetToolTip("")
        evt.Skip()
    
    def OnLeftDclick(self, evt):
        item, flags = self.HitTest(evt.GetPosition())
        if item.IsOk(): # and flags & (0x10|0x20|0x40|0x80):
            try:
                data = self.GetItemData(item)
                data.plug.Show()
            except AttributeError:
                wx.MessageBox("The selected item has no control panel")
                pass
        evt.Skip()
    
    def OnRightDown(self, evt):
        item, flags = self.HitTest(evt.GetPosition())
        if item.IsOk(): # and flags & (0x10|0x20|0x40|0x80):
            self.SelectItem(item)
            try:
                data = self.GetItemData(item)
                name = data.plug and data.plug.__module__
                mwx.Menu.Popup(self.Parent, (
                    (1, "clear", Icon(''),
                        lambda v: data.update_status(-1)),
                    
                    (2, "execute", Icon('->'),
                        lambda v: data.callback(data),
                        lambda v: v.Enable(data.callback is not None
                                       and data.status is not True)),
                    (),
                    (3, "pass", Icon('v'),
                        lambda v: data.update_status(True)),
                    
                    (4, "fail", Icon('w'),
                        lambda v: data.update_status(False)),
                    
                    (5, "nil", Icon('x'),
                        lambda v: data.update_status(None)),
                    (),
                    (6, "Maintenance for {!r}".format(name), Icon('proc'),
                        lambda v: data.plug.Show(),
                        lambda v: v.Enable(name is not None)),
                ))
            except AttributeError:
                pass
        evt.Skip()
