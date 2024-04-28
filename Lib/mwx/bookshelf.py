#! python3
import re
import wx

from .framework import CtrlInterface


class ItemData:
    """Item data for TreeList/Ctrl
    """
    def __init__(self, tree, buffer):
        self.tree = tree
        self.buffer = buffer
        self._itemId = None #: reference <TreeItemId>


class EditorTreeCtrl(wx.TreeCtrl, CtrlInterface):
    """TreeList/Ctrl
    
    Construct treectrl in the order of tree:list.
    """
    def __init__(self, parent, *args, **kwargs):
        wx.TreeCtrl.__init__(self, parent, *args, **kwargs)
        CtrlInterface.__init__(self)
        
        self.Font = wx.Font(9, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        
        self.parent = parent
        self.target = None
        self.__items = {}
        
        self.context = { # DNA<EditorTreeCtrl>
            None : {
                   'buffer_new' : [ None, self.on_buffer_new ],
                 'buffer_saved' : [ None, ],
                'buffer_loaded' : [ None, ],
               'buffer_deleted' : [ None, self.on_buffer_deleted ],
             'buffer_activated' : [ None, self.on_buffer_selected ],
           'buffer_inactivated' : [ None, ],
         'buffer_caption_reset' : [ None, self.on_buffer_caption ],
        'buffer_filename_reset' : [ None, self.on_buffer_filename ],
            },
        }
        
        ## self.Bind(wx.EVT_TREE_ITEM_GETTOOLTIP, self.OnItemTooltip)
        self.Bind(wx.EVT_TREE_SEL_CHANGED, self.OnSelChanged)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        
        @self.handler.bind('enter pressed')
        def enter(v):
            data = self.GetItemData(self.Selection)
            if data:
                data.buffer.SetFocus()
        
        @self.handler.bind('f5 pressed')
        def refresh(v):
            self.reset()
        
        @self.handler.bind('delete pressed')
        def delete(v):
            data = self.GetItemData(self.Selection)
            if data:
                buf = data.buffer
                buf.parent.kill_buffer(buf) # -> focus moves
                wx.CallAfter(self.SetFocus)
        
        @self.handler.bind('*button* pressed')
        @self.handler.bind('*button* released')
        def dispatch(v):
            """Fork mouse events to the parent."""
            self.parent.handler(self.handler.current_event, v)
            v.Skip()
    
    def OnDestroy(self, evt):
        if evt.EventObject is self:
            self.detach()
        evt.Skip()
    
    def reset_tree(self, editor):
        """Reset a branch for Editor/Buffer."""
        self.__items[editor.Name] = {
            buf.name : ItemData(self, buf) for buf in editor.all_buffers
        }
    
    def attach(self, target):
        self.detach()
        self.target = target
        if self.target:
            for editor in self.target.all_editors:
                editor.handler.append(self.context)
                self.reset_tree(editor)
            self.reset()
    
    def detach(self):
        self.__items.clear()
        if self.target:
            for editor in self.target.all_editors:
                editor.handler.remove(self.context)
            self.reset()
        self.target = None
    
    ## --------------------------------
    ## TreeList/Ctrl wrapper interface 
    ## --------------------------------
    
    def reset(self, clear=True):
        """Build tree control.
        All items will be reset after clear if specified.
        """
        try:
            self.Freeze()
            wnd = wx.Window.FindFocus() # original focus
            if clear:
                self.DeleteAllItems()
                self.AddRoot(self.Name)
            for key, values in self.__items.items():
                self._set_item(self.RootItem, key, values)
        finally:
            if wnd:
                wnd.SetFocus() # restore focus
            self.Thaw()
    
    def _get_item(self, root, key):
        """Returns the first item [root/key] found.
        Note: Items with the same name are not supported.
        """
        item, cookie = self.GetFirstChild(root)
        while item:
            caption = self.GetItemText(item)
            if key == re.sub(r"^\W+\s+(.*)", r"\1", caption):
                return item
            item, cookie = self.GetNextChild(root, cookie)
    
    def _set_item(self, root, key, data):
        """Set the item [root/key] with data recursively.
        """
        item = self._get_item(root, key) or self.AppendItem(root, key)
        if isinstance(data, dict):
            for k, v in data.items():
                self._set_item(item, k, v)
        else:
            data._itemId = item
            self.SetItemData(item, data)
            buf = data.buffer
            self.SetItemText(item, buf.caption_prefix + buf.name)
    
    ## --------------------------------
    ## Actions for bookshelf interfaces
    ## --------------------------------
    
    def on_buffer_new(self, buf):
        self.__items[buf.parent.Name][buf.name] = ItemData(self, buf)
        self.reset(clear=0)
    
    def on_buffer_deleted(self, buf):
        del self.__items[buf.parent.Name][buf.name]
        self.reset()
    
    def on_buffer_selected(self, buf):
        data = self.__items[buf.parent.Name][buf.name]
        self.SelectItem(data._itemId)
    
    def on_buffer_caption(self, buf):
        data = self.__items[buf.parent.Name][buf.name]
        self.SetItemText(data._itemId, buf.caption_prefix + buf.name)
    
    def on_buffer_filename(self, buf):
        self.reset_tree(buf.parent)
        self.reset()
    
    def OnSelChanged(self, evt):
        if self and self.HasFocus():
            data = self.GetItemData(evt.Item)
            if data and data.buffer:
                data.buffer.SetFocus()
            self.SetFocus()
        evt.Skip()
    
    ## def OnItemTooltip(self, evt):
    ##     data = self.GetItemData(evt.Item)
    ##     if data and data.buffer:
    ##         evt.SetToolTip(data.buffer.filename)
    ##     evt.Skip()
