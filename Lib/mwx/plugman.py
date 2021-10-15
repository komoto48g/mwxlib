#! python3
# -*- coding: utf-8 -*-
"""Plug manager

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
import copy
import wx
from .controls import Icon
from .framework import Menu, TreeList


class ItemData(object):
    """Item data for TreeCtrl
    
Attributes:
       tree : owner tree object
       plug : owner plugin object
   callback : a function which is called from menu
     status : status of the plugin (default -1)
    _ItemId : reference of the TreeItemId
    """
    ST_EXCEPTION = -3
    ST_PROCESS   = -2
    ST_NORMAL    = -1
    ST_FAILURE   = False
    ST_SUCCESS   = True
    ST_ERROR     = None
    
    def __init__(self, tree, plug=None, callback=None, tip=None):
        self.tree = tree
        self.plug = plug
        self.callback = callback
        self.__doc__ = plug.__doc__ if plug else (tip or '')
        self.__status = -1
        self.__symbols = {-3:6, -2:2, -1:1, False:3, True:4, None:5,} # status:icons
    
    def __deepcopy__(self, memo):
        """Called from deepcopy to export status"""
        return self.__status
    
    status = property(
        lambda self: self.__status,
        lambda self,v: self.set_status(v))
    
    def set_status(self, v):
        self.__status = v
        self.tree.SetItemImage(self._ItemId, self.__symbols.get(v))
    
    ## def setq(self, **kwargs):
    ##     for k,v in kwargs.items():
    ##         setattr(self, k, v)
    
    ## def get_icon(self) -> str:
    ##     j = self.tree.GetItemImage(self._ItemId)
    ##     return TreeCtrl.icons[j]
    ## 
    ## def set_icon(self, icon:str):
    ##     j = TreeCtrl.icons.index(icon)
    ##     self.tree.SetItemImage(self._ItemId, j)
    
    def set_default_icon(self, icon):
        self.__symbols[-1] = TreeCtrl.icons.index(icon)


class TreeCtrl(wx.TreeCtrl, TreeList):
    """TreeList Control 
    """
    icons = (
        'folder',   # 0: container
        'file',     # 1: (default) data
        '->',       # 2: (busy) in-process
        'w',        # 3: (false) 0=failure
        'v',        # 4: (true) 1=success
        '!!',       # 5: (none) error
        '!!!',      # 6: (nil) exception
    )
    
    def __init__(self, *args, **kwargs):
        wx.TreeCtrl.__init__(self, *args, **kwargs)
        TreeList.__init__(self)
        
        li = wx.ImageList(16,16)
        for icon in self.icons:
            li.Add(Icon(icon, (16,16)))
        self.SetImageList(li)
        
        self.__li = li # リストを保持する必要がある
        self.__root = None
        
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDclick)
    
    def reset(self):
        self.DeleteAllItems()
        self.__root = self.AddRoot("Root")
        for branch in self:
            self.set_item(self.__root, *branch)
    
    def append(self, key, value):
        self[key] = value
        if not self.__root:
            return self.reset()
        rootkey = key.partition('/')[0]
        self.set_item(self.__root, rootkey, self[rootkey])
        self.Refresh()
    
    def remove(self, key):
        del self[key]
        self.reset()
    
    def get_children(self, parent):
        """Generate items associated with the parent:item"""
        if isinstance(parent, ItemData):
            parent = parent._ItemId
        
        item, cookie = self.GetFirstChild(parent)
        while item.IsOk():
            yield self.GetItemData(item)
            item, cookie = self.GetNextChild(parent, cookie)
    
    def get_item(self, parent, key):
        """Get item from parent[key]"""
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
        """Set item values to parent[key]"""
        if '/' in key:
            a, b = key.split('/', 1)
            child = self.get_item(parent, a)
            return self.set_item(child, b, *values)
        
        item = self.get_item(parent, key) or self.AppendItem(parent, key)
        data = values[0]
        if isinstance(data, ItemData):
            self.SetItemData(item, data)
            data._ItemId = item # set reference to the own item <wx.TreeItemId>
            
            if len(values) == 1: # => (key, data) no more branches
                data.set_status(data.status) # set icon
                return
            else:
                data.set_default_icon('folder') # container
        
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
                raise KeyError("inconsistent keys {!r} for {!r})".format(tag, key))
            if isinstance(data, ItemData):
                data.set_status(flags)
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
                name = data.plug and data.plug.__module__ # None, otherwise
                
                Menu.Popup(self.Parent, (
                    (1, "clear", Icon(''),
                        lambda v: data.set_status(-1)),
                    
                    (2, "execute", Icon('->'),
                        lambda v: data.callback(data),
                        lambda v: v.Enable(data.callback is not None
                                       and data.status is not True)),
                    (),
                    (3, "pass", Icon('v'),
                        lambda v: data.set_status(True)),
                    
                    (4, "fail", Icon('w'),
                        lambda v: data.set_status(False)),
                    
                    (5, "nil", Icon('x'),
                        lambda v: data.set_status(None)),
                    (),
                    (6, "Maintenance for {!r}".format(name), Icon('proc'),
                        lambda v: data.plug.Show(),
                        lambda v: v.Enable(bool(name))),
                ))
            except AttributeError:
                pass
        evt.Skip()
