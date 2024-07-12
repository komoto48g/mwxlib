#! python3
import re
import wx

from .utilus import funcall as _F
from .framework import CtrlInterface, postcall


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
        
        self.context = { # DNA<EditorBook>
            None : {
                   'buffer_new' : [ None, self.on_buffer_new ],
                 'buffer_saved' : [ None, ],
                'buffer_loaded' : [ None, ],
               'buffer_deleted' : [ None, self.on_buffer_deleted ],
             'buffer_activated' : [ None, self.on_buffer_selected ],
           'buffer_inactivated' : [ None, ],
       'buffer_caption_updated' : [ None, self.on_buffer_filename ],
            },
        }
        
        ## self.Bind(wx.EVT_TREE_ITEM_GETTOOLTIP, self.OnItemTooltip)
        self.Bind(wx.EVT_TREE_SEL_CHANGED, self.OnSelChanged)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        
        def enter(evt):
            data = self.GetItemData(self.Selection)
            if data:
                data.SetFocus()
        
        def refresh(evt, clear=False):
            self.build_tree(clear)
            if self.target:
                self.target.current_editor.SetFocus()
                wx.CallAfter(self.SetFocus)
        
        def delete(evt):
            data = self.GetItemData(self.Selection)
            if data:
                if data.mtdelta or data.Text:
                    data.parent.kill_buffer(data) # -> focus moves
                wx.CallAfter(self.SetFocus)
        
        def dispatch(evt):
            """Fork events to the parent."""
            self.parent.handler(self.handler.current_event, evt)
            evt.Skip()
        
        self.handler.update({ # DNA<EditorTreeCtrl>
            None : {
             '*button* pressed' : [ None, dispatch ],
            '*button* released' : [ None, dispatch ],
            },
            0 : {
                'enter pressed' : (0, enter),
               'delete pressed' : (0, delete),
                   'f5 pressed' : (0, refresh),
                 'S-f5 pressed' : (0, _F(refresh, clear=1)),
            },
        })
    
    def OnDestroy(self, evt):
        if evt.EventObject is self:
            self.detach()
        evt.Skip()
    
    def attach(self, target):
        self.detach()
        self.target = target
        for editor in self.target.all_editors:
            editor.handler.append(self.context)
        self.build_tree()
    
    def detach(self):
        if not self.target:
            return
        for editor in self.target.all_editors:
            editor.handler.remove(self.context)
        self.target = None
        self.build_tree()
    
    ## --------------------------------
    ## TreeList/Ctrl wrapper interface 
    ## --------------------------------
    
    def build_tree(self, clear=True):
        """Build tree control.
        All items will be cleared if specified.
        """
        if clear:
            self.DeleteAllItems()
            self.AddRoot(self.Name)
        if self.target:
            for editor in self.target.all_editors:
                self._set_item(self.RootItem, editor.Name, editor.all_buffers)
        self.Refresh()
    
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
        if isinstance(data, list):
            for buf in data:
                self._set_item(item, buf.name, buf)
        else:
            data.__itemId = item
            self.SetItemData(item, data)
            self.SetItemText(item, data.caption_prefix + data.name)
    
    ## --------------------------------
    ## Actions for bookshelf interfaces
    ## --------------------------------
    
    ## @postcall
    def on_buffer_new(self, buf):
        self.build_tree(clear=0)
    
    ## @postcall
    def on_buffer_deleted(self, buf):
        self.Delete(buf.__itemId)
    
    @postcall
    def on_buffer_selected(self, buf):
        self.SelectItem(buf.__itemId)
    
    @postcall
    def on_buffer_filename(self, buf):
        self.SetItemText(buf.__itemId, buf.caption_prefix + buf.name)
    
    def OnSelChanged(self, evt):
        if self and self.HasFocus():
            data = self.GetItemData(evt.Item)
            if data:
                data.SetFocus()
            self.SetFocus()
        evt.Skip()
