#! python3
# -*- coding: utf-8 -*-
import re
import wx
from wx.lib import inspection as it


def atomvars(obj):
    p = re.compile('[a-zA-Z]+')
    keys = sorted(filter(p.match, dir(obj)), key=lambda s:s.upper())
    attr = {}
    for key in keys:
        try:
            value = getattr(obj, key)
            if hasattr(value, '__name__'): #<atom>
                continue
        except Exception as e:
            value = e
        attr[key] = repr(value)
    return attr


class InfoList(wx.ListCtrl):
    def __init__(self, parent, **kwargs):
        wx.ListCtrl.__init__(self, parent,
                             style=wx.LC_REPORT|wx.LC_HRULES, **kwargs)
        
        ## self.Font = wx.Font(9, wx.FONTFAMILY_MODERN, wx.NORMAL, wx.NORMAL)
        self.Font = wx.Font(9, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        
        self.attr = {}
        
        self.alist = ( # assoc list of column names
            ("key",   200),
            ("value", 400),
        )
        for k, (header, w) in enumerate(self.alist):
            self.InsertColumn(k, header, width=w)
        
        self.SetHeaderAttr(
            wx.ItemAttr('black', 'none', self.Font.Bold()))
    
    def clear(self):
        self.DeleteAllItems()
        self.attr = {}
    
    def UpdateInfo(self, obj):
        if not obj:
            return
        self.clear()
        attr = atomvars(obj)
        for key, vstr in attr.items():
            if key == 'ContainingSizer':
                sizer = obj.ContainingSizer
                if sizer:
                    _attr = atomvars(sizer.GetItem(obj)) #<wx.SizerItem>
                    self.attr[key] = vstr
                    self.attr.update(("-> SizerItem.{}".format(k), v)
                                      for k,v in _attr.items())
                    continue
            if re.match(r"<(.+) object at \w+>", vstr): #<instance>
                continue
            self.attr[key] = vstr
        
        for i, (k, v) in enumerate(self.attr.items()):
            self.InsertItem(i, k)
            self.SetItem(i, 1, v)


class Inspector(wx.SplitterWindow):
    """Widget inspection tool with check-list
*** Inspired by wx.lib.inspection ***

Args:
    parent : shellframe
    """
    parent = property(lambda self: self.__inspector)
    target = property(lambda self: self.__watchedWidget)
    
    def __init__(self, parent, *args, **kwargs):
        wx.SplitterWindow.__init__(self, parent, *args, **kwargs)
        
        self.__inspector = parent
        self.__watchedWidget = None
        
        self.tree = it.InspectionTree(self, size=(300,-1))
        ## self.info = it.InspectionInfoPanel(self, size=(200,-1))
        ## self.info.DropTarget = None
        self.info = InfoList(self, size=(200,-1))
        
        self.SplitVertically(
            self.tree, self.info, self.tree.MinWidth)
        
        self.tree.toolFrame = self # override tree
    
    ## --------------------------------
    ## InspectionTool wrapper methods
    ## --------------------------------
    
    it.INCLUDE_INSPECTOR = True
    it.USE_CUSTOMTREECTRL = False
    
    includeSizers = False
    
    def SetObj(self, obj):
        """Called from tree.OnSelectionChanged"""
        ## self.parent.rootshell.locals['obj'] = obj
        if self.__watchedWidget is not obj:
            self.__watchedWidget = obj
            self.info.UpdateInfo(obj)
        if not self.tree.built:
            self.tree.BuildTree(obj, self.includeSizers)
        else:
            self.tree.SelectObj(obj)
        self.parent.handler('title_window', obj)
    
    def watch(self, obj):
        self.SetObj(obj)
        self.parent.handler("add_page", self, show=1)


if __name__ == "__main__":
    import mwx
    app = wx.App()
    frm = mwx.Frame(None)
    if 1:
        self = frm.shellframe
        frm.wit = Inspector(self)
        frm.wit.Show(0)
        self.Show()
        self.rootshell.write("self.wit.watch(self.wit)")
    frm.Show()
    app.MainLoop()
