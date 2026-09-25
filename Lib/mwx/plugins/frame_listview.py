#! python3
"""Property list of buffers.
"""
from pprint import pformat
import time
import wx
from wx import aui
from wx.lib.mixins.listctrl import ListCtrlAutoWidthMixin

from mwx.framework import CtrlInterface, AuiNotebook, Menu, StatusBar, pack
from mwx.controls import Icon
from mwx.graphman import Layer


class InfoDialog(wx.Dialog, CtrlInterface):
    """Modal dialog for displaying text information.
    """
    Value = property(
        lambda self: self._ctrl.GetValue(),
        lambda self, v: self._ctrl.SetValue(v))

    def __init__(self, *args, **kwargs):
        wx.Dialog.__init__(self, *args, **kwargs)
        CtrlInterface.__init__(self)
        
        self._ctrl = wx.TextCtrl(self, style=wx.TE_MULTILINE|wx.BORDER_NONE)
        
        self.handler.bind('enter pressed', lambda v: self.EndModal(wx.ID_OK))
        self.handler.bind('escape pressed', lambda v: self.EndModal(wx.ID_CANCEL))


class CheckList(wx.ListCtrl, ListCtrlAutoWidthMixin, CtrlInterface):
    """CheckList of Graph buffers.
    
    Note:
        list item order = buffer order.
        (リストアイテムとバッファの並び順 0..n は常に一致します)
    """
    @property
    def selected_items(self):
        return filter(self.IsSelected, range(self.ItemCount))

    @property
    def checked_items(self):
        return filter(self.IsItemChecked, range(self.ItemCount))

    @property
    def focused_item(self):
        return self.FocusedItem

    @property
    def all_items(self):
        rows = range(self.ItemCount)
        cols = range(self.ColumnCount)
        return [[self.GetItemText(j, k) for k in cols] for j in rows]

    def __init__(self, parent, target, **kwargs):
        wx.ListCtrl.__init__(self, parent, size=(400,130),
                             style=wx.LC_REPORT|wx.LC_HRULES, **kwargs)
        ListCtrlAutoWidthMixin.__init__(self)
        CtrlInterface.__init__(self)
        
        self.EnableCheckBoxes()
        
        self.parent = parent
        self.target = target
        self._dir = True
        self._alist = (
            ("id", 45),
            ("name", 160),
            ("shape", 90),
            ("dtype", 60),
            ("Mb",   40),
            ("unit", 60),
            ("timestamp", 120),
            ("annotation", 240),
        )
        for col, (name, w) in enumerate(self._alist):
            self.InsertColumn(col, name, width=w)
        
        for j, frame in enumerate(self.target.get_all_frames()):
            self.InsertItem(j, str(j))
            self.UpdateInfo(frame)  # update all --> 計算が入ると時間がかかる
        
        self.handler.update({  # DNA<frame_listview>
            0 : {
                'enter pressed' : (0, self.OnShowItems),  # -> frame_shown
               'delete pressed' : (0, self.OnRemoveItems),  # -> frame_removed/shown
                  'C-a pressed' : (0, self.OnSelectAllItems),
                  'M-a pressed' : (0, self.OnEditAnnotation),
                 'M-up pressed' : (0, self.target.OnPageUp),
               'M-down pressed' : (0, self.target.OnPageDown),
              'M-enter pressed' : (0, self.OnShowAttributes),
             'Lbutton dblclick' : (0, self.OnLeftDClick),
            },
        })
        self.handler.clear(0)
        
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnSortItems)
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected)
        
        self.context = {  # DNA<GraphPlot>
            None: {
                  'frame_shown' : [None, self.on_frame_shown],
                 'frame_hidden' : [None, self.on_frame_hidden],
                 'frame_loaded' : [None, self.on_frame_loaded],
                'frame_removed' : [None, self.on_frames_removed],
               'frame_modified' : [None, self.UpdateInfo],
                'frame_updated' : [None, self.UpdateInfo],
            }
        }
        self.target.handler.append(self.context)
        
        self.menu = [
            (wx.ID_ANY, "Edit annotation\tM-a", Icon('pencil'),
                self.OnEditAnnotation,
                lambda v: v.Enable(self.focused_item != -1)),
            (),
            (wx.ID_ANY, "Show attributes\tM-enter", Icon('copy'),
                self.OnShowAttributes,
                lambda v: v.Enable(len(list(self.selected_items)))),
        ]
        self.Bind(wx.EVT_CONTEXT_MENU,
                  lambda v: Menu.Popup(self, self.menu))
        
        self.info_dlg = InfoDialog(self,
                            title="Attributes", size=(480, -1),
                            style=wx.DEFAULT_DIALOG_STYLE|wx.RESIZE_BORDER)

    def Destroy(self):
        self.target.handler.remove(self.context)
        return wx.ListCtrl.Destroy(self)

    def UpdateInfo(self, frame):
        info = {
            "id"    : frame.index,
            "name"  : frame.name,
            "shape" : frame.buffer.shape,
            "dtype" : frame.buffer.dtype,
            "Mb"    : "{:.1f}".format(frame.buffer.nbytes / 1e6),
            "unit"  : "{:g}{}".format(frame.unit, '*' if frame.localunit else ''),
            "timestamp": time.strftime("%y/%m/%d %H:%M:%S", time.localtime(frame.timestamp)),
            "annotation": frame.annotation,
        }
        j = frame.index
        for k, v in enumerate(info.values()):
            self.SetItem(j, k, str(v))
        self.CheckItem(j, frame.pathname is not None)

    def OnShowItems(self, evt):
        self.target.select(self.focused_item)

    def OnRemoveItems(self, evt):
        # del self.target[self.selected_items]
        self.target.kill_buffers(list(self.selected_items))
        self.SetFocus()

    def OnSortItems(self, evt):  # <wx._core.ListEvent>
        col = evt.Column
        if col == 0:  # reverse the first column
            self._dir = False
        self._dir = not self._dir  # toggle 0:ascend/1:descend
        
        frame = self.target.frame
        if frame:
            def _eval(x):
                try:
                    return eval(x[col].replace('*', ''))  # localunit* とか
                except Exception:
                    return x[col]
            items = sorted(self.all_items, reverse=self._dir, key=_eval)
            self.target.sort_frames(int(c[0]) for c in items)
            
            lc = list(self.checked_items)
            for j, c in enumerate(items):
                self.Select(j, False)
                self.CheckItem(j, int(c[0]) in lc)
                for k, v in enumerate(c[1:]):  # update data except for id(0)
                    self.SetItem(j, k+1, v)
            self.target.select(frame)  # invokes [frame_shown] to select the item

    def OnItemSelected(self, evt):
        frame = self.target.frames[evt.Index]
        self.parent.message(frame.pathname)
        evt.Skip()

    def OnSelectAllItems(self, evt):
        for j in range(self.ItemCount):
            self.Select(j)

    def OnLeftDClick(self, evt):
        pos = evt.Position
        row, flags = self.HitTest(pos)
        if row < 0:
            evt.Skip()
            return
        col = 0
        x = 0
        while 1:
            x += self.GetColumnWidth(col)
            if x > pos.x:
                break
            col += 1
        if col == 7:
            self.OnEditAnnotation(evt)
        else:
            self.OnShowAttributes(evt)

    def OnShowAttributes(self, evt):
        def _pf(frame):
            return f"# {frame.name}\n" + pformat(frame.attributes, sort_dicts=0)
        
        selected_frames = [self.target.frames[j] for j in self.selected_items]
        if selected_frames:
            self.info_dlg.Value = '\n\n'.join(_pf(frame) for frame in selected_frames)
            self.info_dlg.ShowModal()
        self.SetFocus()

    def OnEditAnnotation(self, evt):
        frame = self.target.frames[self.focused_item]
        with wx.TextEntryDialog(self, frame.name,
                "Enter an annotation", frame.annotation,
                style=wx.TextEntryDialogStyle | wx.TE_MULTILINE) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                frame.annotation = dlg.Value
        self.SetFocus()

    ## --------------------------------
    ## Actions of frame-handler.
    ## --------------------------------

    def on_frame_loaded(self, frame):
        j = frame.index
        self.InsertItem(j, str(j))
        for k in range(j+1, self.ItemCount):  # id(0) を更新する
            self.SetItem(k, 0, str(k))
        self.UpdateInfo(frame)

    def on_frame_shown(self, frame):
        j = frame.index
        self.SetItemFont(j, self.Font.Bold())
        self.Select(j)
        self.Focus(j)

    def on_frame_hidden(self, frame):
        j = frame.index
        self.SetItemFont(j, self.Font)
        self.Select(j, False)

    def on_frames_removed(self, indices):
        with wx.FrozenWindow(self):
            for j in reversed(indices):
                self.DeleteItem(j)
            for k in range(self.ItemCount):  # id(0) を更新する
                self.SetItem(k, 0, str(k))


class Plugin(Layer):
    """Property list of Graph buffers.
    """
    menukey = "Plugins/Extensions/&Buffer listbox\tAlt+b"
    caption = "Property list"
    dockable = False

    @property
    def all_pages(self):
        return [self.nb.GetPage(i) for i in range(self.nb.PageCount)]

    @property
    def message(self):  # Overrides default message.
        return self.statusline

    def Init(self):
        self.nb = AuiNotebook(self, size=(400,150),
                    style=(aui.AUI_NB_DEFAULT_STYLE|aui.AUI_NB_RIGHT)
                        &~(aui.AUI_NB_CLOSE_ON_ACTIVE_TAB|aui.AUI_NB_MIDDLE_CLICK_CLOSE)
        )
        self.attach(self.graph)
        self.attach(self.output)
        
        self.statusline = StatusBar(self)
        self.layout((
                self.nb,
                (self.statusline, 0, wx.EXPAND),
            ),
            expand=2, border=0, vspacing=0,
        )
        
        def on_focus_set(evt):
            self.parent.select_view(self.nb.CurrentPage.target)
            evt.Skip()
        self.nb.Bind(wx.EVT_CHILD_FOCUS, on_focus_set)

    def attach(self, target):
        if target not in [lc.target for lc in self.all_pages]:
            lc = CheckList(self, target)
            self.nb.AddPage(lc, target.Name)

    def detach(self, target):
        for k, lc in enumerate(self.all_pages):
            if target is lc.target:
                self.nb.DeletePage(k)
