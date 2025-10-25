#! python3
"""Property list of buffers.
"""
from pprint import pformat
import wx
from wx import aui
from wx.lib.mixins.listctrl import ListCtrlAutoWidthMixin

from mwx.framework import CtrlInterface, Menu, StatusBar
from mwx.controls import Icon, Clipboard
from mwx.graphman import Layer


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
        ## return [[self.GetItemText(j, k) for k in cols] for j in rows]
        for j in rows:
            yield [self.GetItemText(j, k) for k in cols]

    def __init__(self, parent, target, **kwargs):
        wx.ListCtrl.__init__(self, parent, size=(400,130),
                             style=wx.LC_REPORT|wx.LC_HRULES, **kwargs)
        ListCtrlAutoWidthMixin.__init__(self)
        CtrlInterface.__init__(self)
        
        self.EnableCheckBoxes()
        
        self.parent = parent
        self.Target = target
        
        self.__dir = True
        
        _alist = ( # assoc-list of column names
            ("id", 45),
            ("name", 160),
            ("shape", 90),
            ("dtype", 60),
            ("Mb",   40),
            ("unit", 60),
            ("annotation", 240),
        )
        for k, (name, w) in enumerate(_alist):
            self.InsertColumn(k, name, width=w)
        
        for j, frame in enumerate(self.Target.all_frames):
            self.InsertItem(j, str(j))
            self.UpdateInfo(frame) # update all --> 計算が入ると時間がかかる
        
        self.handler.update({ # DNA<frame_listview>
            0 : {
             'Lbutton dblclick' : (0, self.OnShowItems), # -> frame_shown
                'enter pressed' : (0, self.OnShowItems), # -> frame_shown
               'delete pressed' : (0, self.OnRemoveItems), # -> frame_removed/shown
                  'C-a pressed' : (0, self.OnSelectAllItems),
                  'C-o pressed' : (0, self.OnLoadItems),
                  'C-s pressed' : (0, self.OnSaveItems),
                'C-S-s pressed' : (0, self.OnSaveItems),
                  'C-c pressed' : (0, self.OnCopyInfo),
                  'C-l pressed' : (0, self.OnEditLocalUnit),
                   'f2 pressed' : (0, self.OnEditAnnotation),
                 'M-up pressed' : (0, self.Target.OnPageUp),
               'M-down pressed' : (0, self.Target.OnPageDown),
            },
        })
        self.handler.clear(0)
        
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnSortItems)
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected)
        
        self.context = { # DNA<GraphPlot>
            None: {
                  'frame_shown' : [ None, self.on_frame_shown ],
                 'frame_hidden' : [ None, self.on_frame_hidden ],
                 'frame_loaded' : [ None, self.on_frame_loaded ],
                'frame_removed' : [ None, self.on_frames_removed ],
               'frame_modified' : [ None, self.UpdateInfo ],
                'frame_updated' : [ None, self.UpdateInfo ],
            }
        }
        self.Target.handler.append(self.context)
        
        self.menu = [
            (100, "Edit localunit", Icon('image'),
                self.OnEditLocalUnit,
                lambda v: v.Enable(self.focused_item != -1)),
                
            (101, "Edit annotation", Icon('pencil'),
                self.OnEditAnnotation,
                lambda v: v.Enable(self.focused_item != -1)),
            (),
            (102, "Copy info", Icon('copy'),
                self.OnCopyInfo,
                lambda v: v.Enable(len(list(self.selected_items)))),
        ]
        self.Bind(wx.EVT_CONTEXT_MENU,
                  lambda v: Menu.Popup(self, self.menu))

    def Destroy(self):
        self.Target.handler.remove(self.context)
        return wx.ListCtrl.Destroy(self)

    def UpdateInfo(self, frame):
        ls = ("{}".format(frame.index),
              "{}".format(frame.name),
              "{}".format(frame.buffer.shape),
              "{}".format(frame.buffer.dtype),
          "{:.1f}".format(frame.buffer.nbytes/1e6),
          "{:g}{}".format(frame.unit, '*' if frame.localunit else ''),
              "{}".format(frame.annotation),
        )
        j = frame.index
        for k, v in enumerate(ls):
            self.SetItem(j, k, v)
        if frame.pathname:
            self.CheckItem(j)

    def OnShowItems(self, evt):
        self.Target.select(self.focused_item)

    def OnRemoveItems(self, evt):
        del self.Target[self.selected_items]

    def OnSortItems(self, evt): #<wx._controls.ListEvent>
        col = evt.Column
        if col == 0: # reverse the first column
            self.__dir = False
        self.__dir = not self.__dir # toggle 0:ascend/1:descend
        
        frames = self.Target.all_frames
        if frames:
            def _eval(x):
                try:
                    return eval(x[col].replace('*', '')) # localunit* とか
                except Exception:
                    return x[col]
            frame = self.Target.frame
            items = sorted(self.all_items, reverse=self.__dir, key=_eval)
            frames[:] = [frames[int(c[0])] for c in items] # sort by new Id of items
            
            lc = list(self.checked_items)
            
            for j, c in enumerate(items):
                self.Select(j, False)
                self.CheckItem(j, int(c[0]) in lc)
                for k, v in enumerate(c[1:]): # update data except for id(0)
                    self.SetItem(j, k+1, v)
            self.Target.select(frame) # invokes [frame_shown] to select the item

    def OnSelectAllItems(self, evt):
        for j in range(self.ItemCount):
            self.Select(j)

    def OnLoadItems(self, evt):
        self.parent.parent.load_index(view=self.Target)

    def OnSaveItems(self, evt):
        selected_frames = [self.Target.all_frames[j] for j in self.selected_items]
        if selected_frames:
            self.parent.message("Exporting {} frames.".format(len(selected_frames)))
            self.parent.parent.save_index(frames=selected_frames)
        else:
            self.parent.message("No frame selected.")

    def OnCopyInfo(self, evt):
        selected_frames = [self.Target.all_frames[j] for j in self.selected_items]
        if selected_frames:
            text = []
            for frame in selected_frames:
                text += [pformat(frame.attributes, sort_dicts=0)]  # ALL attributes
            Clipboard.write('\n'.join(text))
        else:
            self.parent.message("No frame selected.")

    def OnEditLocalUnit(self, evt):
        frame = self.Target.all_frames[self.focused_item]
        with wx.TextEntryDialog(self, frame.name,
                'Enter localunit', repr(frame.localunit)) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                frame.unit = eval(dlg.Value or 'None')
        self.SetFocus()

    def OnEditAnnotation(self, evt):
        frame = self.Target.all_frames[self.focused_item]
        with wx.TextEntryDialog(self, frame.name,
                'Enter an annotation', frame.annotation) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                frame.annotation = dlg.Value
        self.SetFocus()

    def OnItemSelected(self, evt):
        frame = self.Target.all_frames[evt.Index]
        self.parent.message(frame.pathname)
        evt.Skip()

    ## --------------------------------
    ## Actions of frame-handler
    ## --------------------------------

    def on_frame_loaded(self, frame):
        j = frame.index
        self.InsertItem(j, str(j))
        for k in range(j+1, self.ItemCount): # id(0) を更新する
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
            for k in range(self.ItemCount): # id(0) を更新する
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
    def message(self):
        return self.statusline

    def Init(self):
        self.nb = aui.AuiNotebook(self, size=(400,150),
            style = (aui.AUI_NB_DEFAULT_STYLE|aui.AUI_NB_RIGHT)
                  &~(aui.AUI_NB_CLOSE_ON_ACTIVE_TAB|aui.AUI_NB_MIDDLE_CLICK_CLOSE)
        )
        self.attach(self.graph, "graph")
        self.attach(self.output, "output")
        
        self.statusline = StatusBar(self)
        self.layout((
                self.nb,
                (self.statusline, 0, wx.EXPAND),
            ),
            expand=2, border=0, vspacing=0,
        )
        
        def on_focus_set(evt):
            self.parent.select_view(self.nb.CurrentPage.Target)
            evt.Skip()
        self.nb.Bind(wx.EVT_CHILD_FOCUS, on_focus_set)

    def attach(self, target, caption):
        if target not in [lc.Target for lc in self.all_pages]:
            lc = CheckList(self, target)
            self.nb.AddPage(lc, caption)

    def detach(self, target):
        for k, lc in enumerate(self.all_pages):
            if target is lc.Target:
                self.nb.DeletePage(k)
