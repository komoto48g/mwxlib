#! python3
import re
import wx

from .framework import CtrlInterface


class MyDropTarget(wx.DropTarget):
    """DnD loader for files and URL text.
    """
    def __init__(self, tree):
        wx.DropTarget.__init__(self)
        
        self.tree = tree
        self.datado = wx.CustomDataObject("TreeItem")
        self.textdo = wx.TextDataObject()
        self.filedo = wx.FileDataObject()
        self.do = wx.DataObjectComposite()
        self.do.Add(self.datado)
        self.do.Add(self.textdo)
        self.do.Add(self.filedo)
        self.SetDataObject(self.do)
    
    def OnDragOver(self, x, y, result):
        item, flags = self.tree.HitTest((x, y))
        items = list(self.tree._gen_items(self.tree.RootItem)) # first level items
        if not item:
            item = items[0]
        elif item not in items:
            item = self.tree.GetItemParent(item) # Select the parent item
        if item != self.tree.Selection:
            self.tree.SelectItem(item)
        return result
    
    def OnData(self, x, y, result):
        item = self.tree.Selection
        name = self.tree.GetItemText(item)
        editor = self.tree.Parent.FindWindow(name) # window.Name
        self.GetData()
        if self.datado.Data:
            fn = self.datado.Data.tobytes().decode()
            if result == wx.DragMove:
                try:
                    buf = self.tree._buffer  # only for the same process buffer DnD
                    buf.parent.kill_buffer(buf) # the focus moves
                    wx.CallAfter(self.tree.SetFocus)
                except AttributeError:
                    pass
            editor.load_file(fn)
            self.datado.SetData(b"")
        elif self.textdo.Text:
            fn = self.textdo.Text.strip()
            res = editor.parent.handler("text_dropped", fn)
            if res is None or not any(res):
                editor.load_file(fn)
            result = wx.DragCopy
            self.textdo.SetText("")
        else:
            for fn in self.filedo.Filenames:
                editor.load_file(fn)
            self.filedo.SetData(wx.DF_FILENAME, None)
        return result


class EditorTreeCtrl(wx.TreeCtrl, CtrlInterface):
    """TreeList/Ctrl
    
    Note:
        This only works with single selection mode.
    """
    def __init__(self, parent, *args, **kwargs):
        wx.TreeCtrl.__init__(self, parent, *args, **kwargs)
        CtrlInterface.__init__(self)
        
        self.Font = wx.Font(9, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        
        self.parent = parent
        
        ## self.Bind(wx.EVT_TREE_ITEM_GETTOOLTIP, self.OnItemTooltip)
        self.Bind(wx.EVT_TREE_SEL_CHANGED, self.OnSelChanged)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        
        self.SetDropTarget(MyDropTarget(self))
        
        self.Bind(wx.EVT_TREE_BEGIN_DRAG, self.OnBeginDrag)
        
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
               'delete pressed' : (0, self.on_delete_buffer),
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
                for editor in self.parent.get_all_editors():
                    editor.handler.append(self.context)
                self.build_tree()
        wx.CallAfter(_attach)
        wx.CallAfter(self.ExpandAll)
    
    def OnDestroy(self, evt):
        if self and self.parent:
            for editor in self.parent.get_all_editors():
                editor.handler.remove(self.context)
        evt.Skip()
    
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
        for editor in self.parent.get_all_editors():
            self._set_item(self.RootItem, editor.Name, editor.get_all_buffers())
        self.Refresh()
    
    def _gen_items(self, root, key=None):
        """Generates the [root/key] items."""
        item, cookie = self.GetFirstChild(root)
        while item:
            if not key:
                yield item
            else:
                ## キャプション先頭の識別子 %* を除外して比較する
                caption = self.GetItemText(item)
                if key == re.sub(r"^\W+\s+(.*)", r"\1", caption):
                    yield item
            item, cookie = self.GetNextChild(root, cookie)
    
    def _get_item(self, root, key):
        """Get the first [root/key] item found."""
        return next(self._gen_items(root, key), None)
    
    def _set_item(self, root, key, data):
        """Set the [root/key] item with data recursively."""
        for item in self._gen_items(root, key):
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
    def on_buffer_selected(self, buf):
        if self and buf:
            wx.CallAfter(lambda: self.SelectItem(buf.__itemId))
    
    def on_buffer_filename(self, buf):
        if self and buf:
            self.SetItemText(buf.__itemId, buf.caption_prefix + buf.name)
    
    def on_delete_buffer(self, evt):
        item = self.Selection
        if item:
            data = self.GetItemData(item)
            if data:
                data.parent.kill_buffer(data)  # the focus moves
                wx.CallAfter(self.SetFocus)
    
    def OnSelChanged(self, evt):
        if self and self.HasFocus():
            data = self.GetItemData(evt.Item)
            if data:
                data.SetFocus()
            else:
                name = self.GetItemText(evt.Item)
                editor = self.Parent.FindWindow(name) # window.Name (not page.caption)
                if not editor.IsShown():
                    self.Parent.Selection = self.Parent.FindPage(editor)
            wx.CallAfter(self.SetFocus)
        evt.Skip()
    
    def OnBeginDrag(self, evt):
        data = self.GetItemData(evt.Item)
        if data:
            self._buffer = data
            dd = wx.CustomDataObject("TreeItem")
            dd.SetData(data.filename.encode())
            dropSource = wx.DropSource()
            dropSource.SetData(dd)
            dropSource.DoDragDrop(wx.Drag_AllowMove) # -> wx.DragResult
            del self._buffer
