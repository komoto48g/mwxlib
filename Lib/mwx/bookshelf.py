#! python3
import re
import wx

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
        
        ## self.Bind(wx.EVT_TREE_ITEM_GETTOOLTIP, self.OnItemTooltip)
        self.Bind(wx.EVT_TREE_SEL_CHANGED, self.OnSelChanged)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        
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
               'delete pressed' : (0, self._delete),
                   'f5 pressed' : (0, self._refresh),
            },
        })
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
        def _attach():
            if self and self.parent:
                for editor in self.parent.all_editors:
                    editor.handler.append(self.context)
                self.build_tree()
        wx.CallAfter(_attach)
    
    def OnDestroy(self, evt):
        if self and self.parent:
            for editor in self.parent.all_editors:
                editor.handler.remove(self.context)
        evt.Skip()
    
    def _refresh(self, evt):
        def _item(editor):
            return self._get_item(self.RootItem, editor.Name)
        ls = []
        for editor in self.parent.all_editors:
            if self.IsExpanded(_item(editor)):
                ls.append(editor)
        data = None
        if self.Selection.IsOk():
            data = self.GetItemData(self.Selection)
            if data:
                wx.CallAfter(data.SetFocus)
                wx.CallAfter(self.SetFocus)
        self.build_tree()
        for editor in ls:
            self.Expand(_item(editor))
    
    def _delete(self, evt):
        if self.Selection.IsOk():
            data = self.GetItemData(self.Selection)
            if data:
                data.parent.kill_buffer(data) # the focus moves
                wx.CallAfter(self.SetFocus)
    
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
        for editor in self.parent.all_editors:
            self._set_item(self.RootItem, editor.Name, editor.all_buffers)
        self.Refresh()
    
    def _gen_item(self, root, key):
        """Generates the [root/key] items."""
        item, cookie = self.GetFirstChild(root)
        while item:
            caption = self.GetItemText(item)
            if key == re.sub(r"^\W+\s+(.*)", r"\1", caption):
                yield item
            item, cookie = self.GetNextChild(root, cookie)
    
    def _get_item(self, root, key):
        """Get the first [root/key] item found."""
        return next(self._gen_item(root, key), None)
    
    def _set_item(self, root, key, data):
        """Set the [root/key] item with data recursively."""
        for item in self._gen_item(root, key):
            buf = self.GetItemData(item)
            if not buf or buf is data:
                break
        else:
            item = self.AppendItem(root, key)
        try:
            for buf in data:
                self._set_item(item, buf.name, buf)
        except Exception:
            data.__itemId = item
            self.SetItemData(item, data)
            self.SetItemText(item, data.caption_prefix + data.name)
        return item
    
    ## --------------------------------
    ## Actions for bookshelf interfaces
    ## --------------------------------
    
    def on_buffer_new(self, buf):
        self.build_tree(clear=0)
    
    def on_buffer_deleted(self, buf):
        self.Delete(buf.__itemId)
    
    ## Note: [buffer_activated][EVT_SET_FOCUS] > [buffer_new] の順で呼ばれる
    ##       buf.__itemId がない場合がある (delete_buffer 直後など)
    @postcall
    def on_buffer_selected(self, buf):
        if self and buf:
            self.SelectItem(buf.__itemId)
    
    def on_buffer_filename(self, buf):
        if self and buf:
            self.SetItemText(buf.__itemId, buf.caption_prefix + buf.name)
    
    def OnSelChanged(self, evt):
        if self and self.HasFocus():
            data = self.GetItemData(evt.Item)
            if data:
                data.SetFocus()
            else:
                name = self.GetItemText(evt.Item)
                editor = self.Parent.FindWindow(name) # window.Name (not page.caption)
                if not editor.IsShown():
                    ## editor.SetFocus()
                    self.Parent.Selection = self.Parent.FindPage(editor)
            self.SetFocus()
        evt.Skip()
