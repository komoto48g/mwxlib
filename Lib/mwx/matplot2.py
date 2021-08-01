#! python
# -*- coding: utf-8 -*-
"""mwxlib base plotter

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
from __future__ import division, print_function
from __future__ import unicode_literals
from __future__ import absolute_import
import numpy as np
import wx
from . import framework as mwx
import matplotlib
matplotlib.use('wxagg')
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg as Toolbar
#from matplotlib.backends.backend_wx import NavigationToolbar2Wx as Toolbar
#from matplotlib.backends.backend_wxagg import Toolbar
#from matplotlib.backend_bases import Cursors
from matplotlib.widgets import Cursor
from matplotlib.figure import Figure
from matplotlib import cm

## state constants
NORMAL = 'Normal'
DRAGGING = '-dragging'
PAN, ZOOM = 'Pan', 'Zoom'
XAXIS, YAXIS = 'Xaxis', 'Yaxis'
MARK, LINE, REGION = 'Mark', 'Line', 'Region'


def wx_hotkey(evt):
    """mpl が取りこぼすイベントを捕まえるとそのキーを CMS-修飾付きで返す
    特殊キー (speckeys) のみ対応する．mpl_hotkey 形式に変換する．
    cf. mwx.hotkey
    """
    key = evt.GetKeyCode()
    speckeys = {
        wx.WXK_CANCEL           : 'break',
        wx.WXK_UP               : 'up',
        wx.WXK_DOWN             : 'down',
        wx.WXK_LEFT             : 'left',
        wx.WXK_RIGHT            : 'right',
        wx.WXK_RETURN           : 'enter',
        wx.WXK_TAB              : 'tab',
        wx.WXK_NUMPAD_UP        : 'up',
        wx.WXK_NUMPAD_DOWN      : 'down',
        wx.WXK_NUMPAD_LEFT      : 'left',
        wx.WXK_NUMPAD_RIGHT     : 'right',
        wx.WXK_NUMPAD_ENTER     : 'enter',
        wx.WXK_WINDOWS_LEFT     : 'Lwin',
        wx.WXK_WINDOWS_RIGHT    : 'Rwin',
    }
    if key in speckeys:
        mod = ""
        for k,v in ((wx.WXK_WINDOWS_LEFT, 'Lwin-'),
                     (wx.WXK_WINDOWS_RIGHT, 'Rwin-'),
                     (wx.WXK_CONTROL, 'ctrl+'),
                     (wx.WXK_ALT,     'alt+'),
                     (wx.WXK_SHIFT,   'shift+')):
            if key != k and wx.GetKeyState(k):
                mod += v
        if mod.startswith("alt+"): # skip to mpl
            return
        evt.key = mod + speckeys[key]
        return mpl_hotkey(evt)


def mpl_hotkey(evt):
    """key = A+B+C+K where A,B,C prefix and K the last pressed/released key
    The modifier key is in [LR]win+C-M-S order (matplotlib)
        *pressed*           *released*          *mod*
        -------------------------------------------------------
    C   ctrl+control        control         ->  ctrl
    M   alt+alt             alt             ->  alt
    S   shift               shift           ->  shift
  C-M   ctrl+alt+alt        ctrl+alt        ->  ctrl+alt
  M-C   ctrl+alt+control    alt+control     ->  alt+ctrl
  C-S   ctrl+shift          ctrl+shift      ->  ctrl+shift
  M-S   alt+shift           alt+shift       ->  alt+shift
C-M-S   ctrl+alt+shift      ctrl+alt+shift  ->  ctrl+alt+shift
        -------------------------------------------------------
    Note: key = shift+M (M:modifier) => M
    Note: matplotlib (>= 3.4.x) changed the mod order to S-M-C.
    """
    key = evt.key
    
    if key is not None:
        ## matplot 3.2.x --> 3.4.x 対応
        if key.startswith('shift+'):
            key = key[6:]
        if key == 'alt+ctrl+alt':   key = 'ctrl+alt'
    if   key == 'control':          key = 'ctrl'
    elif key == 'ctrl+control':     key = 'ctrl'
    elif key == 'alt+alt':          key = 'alt'
    elif key == 'ctrl+alt+alt':     key = 'ctrl+alt'
    elif key == 'ctrl+alt+control': key = 'alt+ctrl'
    elif key == 'alt+control':      key = 'alt+ctrl'
    
    if key is not None:
        if key[-1:] == '\0': return None
        if key[-1:] == '\t': key = key[:-1] + 'tab'
        if key[-1:] == ' ' : key = key[:-1] + 'space'
        
        if key[-4:] in ('none', 'None'): # when alt+ win, appskey, etc.
            key = key[:-4] + '?'
        
        ## shift キーが押されている場合 `shift+(小文字)` に変換する
        if wx.GetKeyState(wx.WXK_SHIFT) and 'shift' not in key:
            if key and key[-1] == '+':
                key = key[:-1] + 'shift++'
            else:
                j = key.rfind('+') + 1
                key = key[:j] + 'shift+' + key[j:].lower()
        
        if wx.GetKeyState(wx.WXK_WINDOWS_RIGHT) and 'Rwin' not in key:
            key = 'Rwin-' + key
        
        if wx.GetKeyState(wx.WXK_WINDOWS_LEFT) and 'Lwin' not in key:
            key = 'Lwin-' + key
        
        ## matplot 3.2.x --> 3.4.x 対応
        key = key.replace("alt+ctrl+", "ctrl+alt+")
        
    if key:
        head, sep, tail = key.rpartition('+')
        evt.rawkey = tail or sep
    else:
        evt.rawkey = key
    evt.key = key
    return key


def mpl_mousekey(evt):
    if evt.button in (1,2,3):
        btn = "LMR"[evt.button-1] #{1:L,2:M,3:R}
        key = mpl_hotkey(evt)
        if key:
            return key + '+' + btn
        return btn


class MatplotPanel(wx.Panel):
    """MPL panel for general graph
    
      axes : <matplotlib.axes.Axes>
    figure : <matplotlib.figure.Figure>
    cursor : <matplotlib.widgets.Cursor>
  selected : selected points <matplotlib.lines.Line2D>
  Selector : selected points arrays (xx, yy)
    """
    handler = property(lambda self: self.__handler)
    
    def __init__(self, parent, log=None, margin=(.1,.1,.9,.9), **kwargs):
        wx.Panel.__init__(self, parent, **kwargs)
        
        self.message = log or (lambda s: s)
        
        #<matplotlib.figure.Figure>
        self.figure = Figure(facecolor='white', figsize=(1,1))
        
        #<matplotlib.backends.backend_wxagg.FigureCanvasWxAgg>
        self.canvas = FigureCanvas(self, -1, self.figure)
        
        ## To avoid AssertionError('self._cachedRenderer is not None')
        ## To avoid AttributeError("draw_artist can only be used after an "
        ##                         "initial draw which caches the renderer")
        self.canvas.draw()
        
        #<matplotlib.backends.backend_wxagg.NavigationToolbar2WxAgg>
        self.toolbar = Toolbar(self.canvas)
        self.toolbar.Show(0)
        
        ## modeline bar
        self.modeline = wx.StaticText(self, label="", style=wx.ST_NO_AUTORESIZE)
        self.modeline.write = self.modeline.SetLabel
        self.modeline.read = self.modeline.GetLabel
        self.modeline.SetToolTip("")
        self.modeline.ToolTip.SetDelay(250)
        
        self.modeline.Bind(wx.EVT_MOTION, self.on_modeline_tip)
        self.modeline.Bind(wx.EVT_LEFT_DOWN, lambda v: self.canvas.SetFocus())
        
        self.infobar = wx.InfoBar(self)
        
        self.SetSizer(
            mwx.pack(self,
                (self.canvas, 1, wx.EXPAND|wx.ALL, 0),
                (self.infobar, 0, wx.EXPAND|wx.ALL, 0),
                (self.modeline, 0, wx.EXPAND|wx.ALL, 2),
                (self.toolbar, 0, wx.EXPAND|wx.ALL, 2),
                orient = wx.VERTICAL,
            )
        )
        self.modeline.Show(0)
        self.Layout()
        
        self.__isMenu = None
        self.__isPressed = None
        self.__isDragging = False # True if dragging. (None if dblclicked)
        
        self.set_margin(margin or (0,0,1,1))
        self.clear()
        
        ## mpl event handler
        ## 後方優先でイベントハンドラが呼び出される
        self.canvas.mpl_connect('pick_event', self.on_pick)
        self.canvas.mpl_connect('scroll_event', self.on_scroll)
        self.canvas.mpl_connect('key_press_event', self.on_key_press)
        self.canvas.mpl_connect('key_release_event', self.on_key_release)
        self.canvas.mpl_connect('button_press_event', self.on_button_press)
        self.canvas.mpl_connect('button_release_event', self.on_button_release)
        self.canvas.mpl_connect('motion_notify_event', self.on_motion_notify)
        
        self.canvas.mpl_connect('figure_enter_event', lambda v: self.handler('figure enter', v))
        self.canvas.mpl_connect('figure_leave_event', lambda v: self.handler('figure leave', v))
        self.canvas.mpl_connect('axes_enter_event', lambda v: self.handler('axes enter', v))
        self.canvas.mpl_connect('axes_leave_event', lambda v: self.handler('axes leave', v))
        self.canvas.mpl_connect('resize_event', lambda v: self.handler('canvas_resized', v))
        ## self.canvas.mpl_connect('draw_event', lambda v: self.handler('canvas_drawn', v))
        
        ## mpl が取りこぼすイベントを捕まえる
        self.canvas.Bind(wx.EVT_CHAR_HOOK, self.on_hotkey_press)
        
        self.canvas.Bind(wx.EVT_MOUSE_AUX1_DOWN, lambda v: self.handler('Xbutton1 pressed', v))
        self.canvas.Bind(wx.EVT_MOUSE_AUX2_DOWN, lambda v: self.handler('Xbutton2 pressed', v))
        self.canvas.Bind(wx.EVT_MOUSE_AUX1_UP, lambda v: self.handler('Xbutton1 released', v))
        self.canvas.Bind(wx.EVT_MOUSE_AUX2_UP, lambda v: self.handler('Xbutton2 released', v))
        
        self.canvas.Bind(wx.EVT_SET_FOCUS, self.on_focus_set)     # => 'canvas_focus_set'
        self.canvas.Bind(wx.EVT_KILL_FOCUS, self.on_focus_killed) # => 'canvas_focus_killed'
        
        ## `Rbutton pressed` on_menu is enabled for Normal mode only.
        ## The context menus is disabled and never skip to the next handler.
        self.canvas.Bind(wx.EVT_CONTEXT_MENU, lambda v: self.handler('context_menu', v))
        
        def fork(v):
            self.handler.fork(v)
        
        self.__handler = mwx.FSM({
                None : {
                  'canvas_draw' : [ None, self.OnDraw ], # before canvas.draw
                #'canvas_drawn' : [ None, ],             # after canvas.draw :deprecated
               'canvas_resized' : [ None, ],
             'canvas_focus_set' : [ None, self.escape ],
          'canvas_focus_killed' : [ None, self.escape ],
                 'figure enter' : [ None, self.on_figure_enter ],
                 'figure leave' : [ None, self.on_figure_leave ],
                   'axes enter' : [ None, ],
                   'axes leave' : [ None, ],
                 'home pressed' : [ None, self.OnHomePosition ],
            'backspace pressed' : [ None, self.OnBackPosition ],
        'alt+backspace pressed' : [ None, self.OnForwardPosition ],
             'Xbutton1 pressed' : [ None, self.OnBackPosition ],
             'Xbutton2 pressed' : [ None, self.OnForwardPosition ],
                'alt+p pressed' : [ None, self.OnBackPosition ],
                'alt+n pressed' : [ None, self.OnForwardPosition ],
                },
                NORMAL : {
                   'art_picked' : (NORMAL, ),
                  'axes motion' : (NORMAL, self.OnMotion),
               'escape pressed' : (NORMAL, self.OnEscapeSelection),
              'Rbutton pressed' : (NORMAL, self.on_menu_lock),
             'Rbutton released' : (NORMAL, self.on_menu),
                'space pressed' : (PAN, self.OnPanBegin),
                 'ctrl pressed' : (PAN, self.OnPanBegin),
                    'z pressed' : (ZOOM, self.OnZoomBegin),
                 'figure leave' : (NORMAL, self.clear_cursor),
                 'xaxis motion' : (XAXIS, self.OnAxisEnter),
                 'yaxis motion' : (YAXIS, self.OnAxisEnter),
                'y2axis motion' : (YAXIS, self.OnAxisEnter),
                },
                PAN : {
          'ctrl+wheel* pressed' : (PAN, self.OnScrollZoom),
              ## 'ctrl+up pressed' : (PAN, self.OnShiftLimit),
            ## 'ctrl+down pressed' : (PAN, self.OnShiftLimit),
            ## 'ctrl+left pressed' : (PAN, self.OnShiftLimit),
           ## 'ctrl+right pressed' : (PAN, self.OnShiftLimit),
           'ctrl+[+;-] pressed' : (PAN, self.OnZoom),
     'ctrl+shift+[+;-] pressed' : (PAN, self.OnZoom),
     'ctrl+*[LR]button pressed' : (PAN+DRAGGING, ),
     'space+[LR]button pressed' : (PAN+DRAGGING, ),
              '*[LR]drag begin' : (PAN+DRAGGING, ),
                'ctrl released' : (NORMAL, self.OnPanEnd),
               'space released' : (NORMAL, self.OnPanEnd),
          'canvas_focus_killed' : (NORMAL, self.OnPanEnd),
                 'figure leave' : (NORMAL, self.OnPanEnd),
                   'axes leave' : (NORMAL, self.OnPanEnd),
               'ctrl+* pressed' : (NORMAL, fork, self.OnPanEnd),
           'ctrl+shift pressed' : (PAN, ),
                },
                PAN+DRAGGING : {
                '*[LR]drag end' : (NORMAL, self.OnPanEnd),
         '*[LR]button released' : (NORMAL, self.OnPanEnd),
                },
                ZOOM : {
              '*[LR]drag begin' : (ZOOM+DRAGGING, ),
          '*[LR]button pressed' : (ZOOM+DRAGGING, ),
               'escape pressed' : (NORMAL, self.OnZoomEnd),
                    'z pressed' : (NORMAL, self.OnZoomEnd),
                },
                ZOOM+DRAGGING : {
                '*[LR]drag end' : (NORMAL, self.OnZoomEnd),
         '*[LR]button released' : (NORMAL, self.OnZoomEnd),
                },
                XAXIS : {
                   'axes enter' : (NORMAL, self.OnAxisLeave),
                  'Ldrag begin' : (XAXIS+DRAGGING, self.OnAxisDragBegin),
                 '*Ldrag begin' : (XAXIS+ZOOM+DRAGGING, self.OnAxisDragBegin),
                 '*Rdrag begin' : (XAXIS+ZOOM+DRAGGING, self.OnAxisDragBegin),
                 'yaxis motion' : (YAXIS, ),
                'y2axis motion' : (YAXIS, ),
              '*Lbutton dclick' : (XAXIS, self.OnHomeXPosition),
                },
                XAXIS+DRAGGING : {
                   'Ldrag move' : (XAXIS+DRAGGING, self.OnXAxisPanMove),
                  '*Rdrag move' : (XAXIS+ZOOM+DRAGGING, self.OnXAxisPanZoom),
              'ctrl+Ldrag move' : (XAXIS+ZOOM+DRAGGING, self.OnXAxisPanZoom),
        'ctrl+shift+Ldrag move' : (XAXIS+ZOOM+DRAGGING, self.OnXAxisPanZoomOrig),
                 'ctrl pressed' : (XAXIS+ZOOM+DRAGGING, self.OnAxisDragBegin),
                   '*Ldrag end' : (XAXIS, self.OnAxisDragEnd),
                   '*Rdrag end' : (XAXIS, self.OnAxisDragEnd),
                },
                XAXIS+ZOOM+DRAGGING : {
                   'Ldrag move' : (XAXIS+DRAGGING, self.OnXAxisPanMove),
                  '*Rdrag move' : (XAXIS+ZOOM+DRAGGING, self.OnXAxisPanZoom),
              'ctrl+Ldrag move' : (XAXIS+ZOOM+DRAGGING, self.OnXAxisPanZoom),
        'ctrl+shift+Ldrag move' : (XAXIS+ZOOM+DRAGGING, self.OnXAxisPanZoomOrig),
                'ctrl released' : (XAXIS+DRAGGING, self.OnAxisDragBegin),
                   '*Ldrag end' : (XAXIS, self.OnAxisDragEnd),
                   '*Rdrag end' : (XAXIS, self.OnAxisDragEnd),
                },
                YAXIS : {
                   'axes enter' : (NORMAL, self.OnAxisLeave),
                  'Ldrag begin' : (YAXIS+DRAGGING, self.OnAxisDragBegin),
                 '*Ldrag begin' : (YAXIS+ZOOM+DRAGGING, self.OnAxisDragBegin),
                 '*Rdrag begin' : (YAXIS+ZOOM+DRAGGING, self.OnAxisDragBegin),
                 'xaxis motion' : (XAXIS, ),
              '*Lbutton dclick' : (YAXIS, self.OnHomeYPosition),
                },
                YAXIS+DRAGGING : {
                   'Ldrag move' : (YAXIS+DRAGGING, self.OnYAxisPanMove),
                  '*Rdrag move' : (YAXIS+ZOOM+DRAGGING, self.OnYAxisPanZoom),
              'ctrl+Ldrag move' : (YAXIS+ZOOM+DRAGGING, self.OnYAxisPanZoom),
        'ctrl+shift+Ldrag move' : (YAXIS+ZOOM+DRAGGING, self.OnYAxisPanZoomOrig),
                 'ctrl pressed' : (YAXIS+ZOOM+DRAGGING, self.OnAxisDragBegin),
                   '*Ldrag end' : (YAXIS, self.OnAxisDragEnd),
                   '*Rdrag end' : (YAXIS, self.OnAxisDragEnd),
                },
                YAXIS+ZOOM+DRAGGING : {
                   'Ldrag move' : (YAXIS+DRAGGING, self.OnYAxisPanMove),
                  '*Rdrag move' : (YAXIS+ZOOM+DRAGGING, self.OnYAxisPanZoom),
              'ctrl+Ldrag move' : (YAXIS+ZOOM+DRAGGING, self.OnYAxisPanZoom),
        'ctrl+shift+Ldrag move' : (YAXIS+ZOOM+DRAGGING, self.OnYAxisPanZoomOrig),
                'ctrl released' : (YAXIS+DRAGGING, self.OnAxisDragBegin),
                   '*Ldrag end' : (YAXIS, self.OnAxisDragEnd),
                   '*Rdrag end' : (YAXIS, self.OnAxisDragEnd),
                },
            },
            default = NORMAL
        )
        
        self.Menu = [
            (mwx.ID_(501), "&Copy image", "Copy canvas image to clipboard",
                lambda v: self.copy_to_clipboard()),
                
            ## (mwx.ID_(502), "&Export image", "Save canvas image",
            ##     lambda v: self.save_to_file()),
        ]
    
    def clear(self):
        """Initialize the plot figure"""
        #<matplotlib.axes.Axes>
        self.figure.clear()
        self.figure.add_subplot(111) # cf. add_axes(margin=(l,b,w,t))
        
        #<matplotlib.lines.Line2D>
        (self.selected,) = self.axes.plot([], [], "yo-", ms=6, lw=2, alpha=0.75,
                                          markeredgecolor='y', visible=0)
        self.selected.set_data([], [])
        
        #<matplotlib.widgets.Cursor>
        self.cursor = Cursor(self.axes, useblit=True, color='grey', linewidth=1)
        self.cursor.visible = 1
    
    def draw(self, art=None):
        """Draw the plot
        Called every time the drawing is updated.
        """
        ## 描画全体をアップデートするたびに呼び出す
        if isinstance(art, matplotlib.artist.Artist):
            ## bg = self.canvas.copy_from_bbox(self.axes.bbox)
            ## self.canvas.restore_region(bg)
            self.axes.draw_artist(art)
            self.canvas.blit(art.get_clip_box())
            ## self.canvas.draw_idle()
        elif art is None:
            self.handler('canvas_draw', self.frame)
            self.canvas.draw()
    
    ## --------------------------------
    ## Property of current frame
    ## --------------------------------
    
    frame = property(lambda self: self) # to be overrided (handler process `frame` in draw)
    
    axes = property(lambda self: self.figure.axes[0])
    
    xbound = property(
        lambda self: np.array(self.axes.get_xbound()),
        lambda self,v: self.axes.set_xbound(v),
        doc = "x-axis numerical bounds where lowerBound < upperBound)")
    
    ybound = property(
        lambda self: np.array(self.axes.get_ybound()),
        lambda self,v: self.axes.set_ybound(v),
        doc = "y-axis numerical bounds where lowerBound < upperBound)")
    
    xlim = property(
        lambda self: np.array(self.axes.get_xlim()),
        lambda self,v: self.axes.set_xlim(v),
        doc = "x-axis range [left, right]")
    
    ylim = property(
        lambda self: np.array(self.axes.get_ylim()),
        lambda self,v: self.axes.set_ylim(v),
        doc = "y-axis range [bottom, top]")
    
    @property
    def ddpu(self):
        """x, y display-dot resolution [dots per arb.unit]"""
        ## return self.mapxy2disp(1,1) - self.mapxy2disp(0,0)
        a, b = self.mapxy2disp([0,1],[0,1])
        return b - a
    
    def mapxy2disp(self, x, y):
        """xydata --> display dot pixel-coordinates"""
        v = np.array((x, y)).T
        return self.axes.transData.transform(v)
    
    def mapdisp2xy(self, px, py):
        """display dot pixel-coordinates --> xydata"""
        v = np.array((px, py)).T
        return self.axes.transData.inverted().transform(v)
    
    def set_wxcursor(self, c):
        self.canvas.SetCursor(wx.Cursor(c))
    
    def set_margin(self, lbwt):
        self.figure.subplots_adjust(*lbwt)
    
    def on_modeline_tip(self, evt):
        pos = self.modeline.ScreenToClient(wx.GetMousePosition())
        flag = self.modeline.HitTest(pos)
        tip = self.modeline.ToolTip
        if flag == wx.HT_WINDOW_INSIDE:
            tip.SetTip(self.modeline.read())
        evt.Skip()
    
    def on_focus_set(self, evt):
        if self.modeline.IsShown():
            self.modeline.SetBackgroundColour('#000000')
            self.modeline.SetForegroundColour('#f0f0f0')
            self.Refresh()
        self.handler('canvas_focus_set', self.frame)
    
    def on_focus_killed(self, evt):
        if self.modeline.IsShown():
            self.modeline.SetBackgroundColour('')
            self.modeline.SetForegroundColour('#000000')
            self.Refresh()
        self.handler('canvas_focus_killed', self.frame)
    
    def escape(self, evt=None):
        """{escape} を押した気持ちになる"""
        wx.UIActionSimulator().KeyUp(wx.WXK_ESCAPE)
    
    def clear_cursor(self, evt=None): #<matplotlib.backend_bases.MouseEvent>
        self.cursor.clear(evt)
        self.canvas.draw()
    
    ## --------------------------------
    ## 外部入出力／複合インターフェース
    ## --------------------------------
    
    ## def save_to_file(self, path=None):
    ##     """Save canvas image to file"""
    ##     if not path:
    ##         with wx.FileDialog(self, 'Save Figure as',
    ##             style = wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT) as dlg:
    ##             if dlg.ShowModal() != wx.ID_OK:
    ##                 return
    ##             path = dlg.Path
    ##     self.message("Save image to {!r}'".format(path))
    ##     try:
    ##         b = self.selected.get_visible()
    ##         self.selected.set_visible(0)
    ##         self.cursor.visible = 0
    ##         self.canvas.draw()
    ##         self.canvas.print_figure(path, dpi=300) # canvas figure to image
    ##     finally:
    ##         self.selected.set_visible(b)
    ##         self.cursor.visible = 1
    ##         self.canvas.draw()
    
    def copy_to_clipboard(self):
        """Copy canvas image to clipboard"""
        self.message("Copy image to clipboard")
        try:
            b = self.selected.get_visible()
            self.selected.set_visible(0)
            self.cursor.visible = 0
            self.canvas.draw()
            self.canvas.Copy_to_Clipboard()
        finally:
            self.selected.set_visible(b)
            self.cursor.visible = 1
            self.canvas.draw()
    
    ## --------------------------------
    ## Selector interface
    ## --------------------------------
    
    def trace_point(self, x, y):
        if hasattr(x, '__iter__'):
            if not len(x):
                return
            x, y = x[0], y[0]
        self.message("({:g}, {:g})".format(x, y))
    
    def on_figure_enter(self, evt):
        if self.Selector.size:
            self.trace_point(*self.Selector)
    
    def on_figure_leave(self, evt):
        pass
    
    @property
    def Selector(self):
        return np.array(self.selected.get_data(orig=0))
    
    @Selector.setter
    def Selector(self, v):
        self.selected.set_visible(1)
        self.selected.set_data(*v)
        self.draw(self.selected)
        self.trace_point(*v)
    
    @Selector.deleter
    def Selector(self):
        self.selected.set_visible(0)
        self.selected.set_data([], [])
        self.draw(self.selected)
    
    ## --------------------------------
    ## matplotlib interfaces
    ## --------------------------------
    
    @property
    def p_event(self):
        """the last `pressed` event <matplotlib.backend_bases.MouseEvent>"""
        return self.__isPressed
    
    @p_event.setter
    def p_event(self, v):
        self.__isPressed = v
    
    def on_menu_lock(self, evt): #<matplotlib.backend_bases.MouseEvent>
        self.__isMenu = 1
    
    def on_menu(self, evt): #<matplotlib.backend_bases.MouseEvent>
        if self.__isMenu:
            self.canvas.SetFocus()
            mwx.Menu.Popup(self, self.Menu)
        self.__isMenu = 0
    
    def on_pick(self, evt): #<matplotlib.backend_bases.PickEvent>
        """Find index near (x,y) and set the Selector
        Called (maybe) after mouse button pressed.
        
      * Data reference method (get_xdata/ydata) should be added
      * scatter はデータ参照メソッドを持たないので，マニュアルで追加する
      o axes.plot <matplotlib.lines.Line2D>
      x axes.scatter <matplotlib.collections.PathCollection>
        """
        if evt.mouseevent.button != 1 or not evt.artist.get_visible():
            return
        
        if not evt.mouseevent.inaxes:
            return
        
        if isinstance(evt.artist, (matplotlib.lines.Line2D,
                                   matplotlib.collections.PathCollection)):
            indices = evt.ind
            x = evt.mouseevent.xdata
            y = evt.mouseevent.ydata
            xs = evt.artist.get_xdata()
            ys = evt.artist.get_ydata()
            distances = np.hypot(x-xs[indices], y-ys[indices])
            evt.index = k = indices[distances.argmin()] # index of the nearest point
            evt.xdata = x = xs[k]
            evt.ydata = y = ys[k]
            self.Selector = (x, y)
            self.canvas.draw_idle()
            self.handler('art_picked', evt)
            self.message("({:g}, {:g}) index {}".format(x, y, evt.index))
    
    def on_hotkey_press(self, evt): #<wx._core.KeyEvent>
        """Catch the event that mpl misses by wx"""
        key = wx_hotkey(evt)
        if key:
            self.handler('{} pressed'.format(key), evt)
        else:
            evt.Skip() # skip to mpl:on_key_press
    
    def on_hotkey_release(self, evt): #<wx._core.KeyEvent>
        """Catch the event that mpl misses by wx"""
        key = wx_hotkey(evt)
        if key:
            self.handler('{} released'.format(key), evt)
        else:
            evt.Skip() # skip to mpl:on_key_release
    
    def on_key_press(self, evt): #<matplotlib.backend_bases.KeyEvent>
        """mpl key_press_event"""
        key = mpl_hotkey(evt)
        if key:
            self.handler('{} pressed'.format(key), evt)
    
    def on_key_release(self, evt): #<matplotlib.backend_bases.KeyEvent>
        """mpl key_release_event"""
        key = mpl_hotkey(evt)
        if key:
            self.handler('{} released'.format(key), evt)
    
    def on_button_press(self, evt): #<matplotlib.backend_bases.MouseEvent>
        self.p_event = evt
        if not evt.inaxes or evt.inaxes is not self.axes:
            (evt.xdata, evt.ydata) = self.mapdisp2xy(evt.x, evt.y)
        
        key = mpl_mousekey(evt)
        if evt.dblclick:
            self.__isDragging = None
            self.handler('{}button dclick'.format(key), evt)
        else:
            self.__isDragging = False
            self.handler('{}button pressed'.format(key), evt)
    
    def on_button_release(self, evt): #<matplotlib.backend_bases.MouseEvent>
        if not evt.inaxes or evt.inaxes is not self.axes:
            (evt.xdata, evt.ydata) = self.mapdisp2xy(evt.x, evt.y)
        
        key = mpl_mousekey(evt)
        if self.__isDragging:
            self.__isDragging = False
            self.handler('{}drag end'.format(key), evt)
            self.handler('{}button released'.format(key), evt)
        else:
            if self.__isDragging is None: # dclick end
                return
            self.handler('{}button released'.format(key), evt)
        self.p_event = None
    
    def on_motion_notify(self, evt): #<matplotlib.backend_bases.MouseEvent>
        if not evt.inaxes or evt.inaxes is not self.axes:
            (evt.xdata, evt.ydata) = self.mapdisp2xy(evt.x, evt.y)
        
        if evt.button in (1,2,3):
            key = mpl_mousekey(evt)
            if self.__isDragging:
                self.handler('{}drag move'.format(key), evt)
            else:
                self.__isDragging = True
                self.handler('{}drag begin'.format(key), evt)
            
        elif evt.inaxes is self.axes:
            self.handler('axes motion', evt)
            
        else:
            lx,ly = self.xlim, self.ylim
            if   evt.xdata < lx[0]: event = 'yaxis'
            elif evt.xdata > lx[1]: event = 'y2axis'
            elif evt.ydata < ly[0]: event = 'xaxis'
            elif evt.ydata > ly[1]: event = 'x2axis'
            else:
                return
            self.handler("{} motion".format(event), evt)
    
    def on_scroll(self, evt): #<matplotlib.backend_bases.MouseEvent>
        self.p_event = evt
        if not evt.inaxes or evt.inaxes is not self.axes:
            (evt.xdata, evt.ydata) = self.mapdisp2xy(evt.x, evt.y)
        
        key = mpl_hotkey(evt)
        key = '{}wheel{}'.format((key + '+') if key else '', evt.button) # up/down
        self.handler('{} pressed'.format(key), evt)
        self.p_event = None
    
    ## --------------------------------
    ## Pan/Zoom actions 
    ## --------------------------------
    
    ZOOM_RATIO = 10**0.2
    
    def update_position(self):
        self.toolbar.update()
        self.toolbar.push_current()
    
    def OnDraw(self, evt):
        """Called before canvas.draw"""
        pass
    
    def OnMotion(self, evt):
        """Called when mouse moves in axes"""
        if not self.Selector.size:
            self.trace_point(evt.xdata, evt.ydata)
    
    def OnForwardPosition(self, evt):
        """Go forward view position"""
        self.toolbar.forward()
        self.draw()
    
    def OnBackPosition(self, evt):
        """Go backward view position"""
        self.toolbar.back()
        self.draw()
    
    def OnHomePosition(self, evt):
        """Go back to home position"""
        self.toolbar.home()
        self.update_position()
        self.draw()
    
    def OnEscapeSelection(self, evt):
        """Escape from selection"""
        del self.Selector
    
    def OnShiftLimit(self, evt, r=0.1):
        w = self.xlim[1] - self.xlim[0]
        h = self.ylim[1] - self.ylim[0]
        if 'up' in evt.key: self.ylim += h * r
        elif 'down' in evt.key: self.ylim -= h * r
        elif 'left' in evt.key: self.xlim -= w * r
        elif 'right' in evt.key: self.xlim += w * r
        if 1:
            self.toolbar.push_current()
            self.draw()
    
    def zoomlim(self, lim, M, c=None):
        ## 拡大しすぎると処理速度が遅くなるため表示幅を制限する (None を返す)
        if c is None:
            c = (lim[1] + lim[0]) / 2
        y = c - M * (c - lim)
        if abs(y[1] - y[0]) > 0.1 or M > 1:
            return y
    
    def OnZoom(self, evt):
        M = 1/self.ZOOM_RATIO if evt.key[-1] in '+;' else self.ZOOM_RATIO
        self.xlim = x = self.zoomlim(self.xlim, M)
        self.ylim = y = self.zoomlim(self.ylim, M)
        
        if x is not None or y is not None:
            self.toolbar.push_current()
            self.draw()
    
    def OnScrollZoom(self, evt):
        M = 1/self.ZOOM_RATIO if evt.button == 'up' else self.ZOOM_RATIO
        self.xlim = x = self.zoomlim(self.xlim, M, evt.xdata if evt.inaxes else None)
        self.ylim = y = self.zoomlim(self.ylim, M, evt.ydata if evt.inaxes else None)
        
        if x is not None or y is not None:
            self.toolbar.push_current()
            self.draw()
    
    def OnPanBegin(self, evt):
        """Toolbar pan - While panning, press x/y to constrain the direction"""
        self.toolbar.set_cursor(0)
        self.toolbar.pan()
        self.__prev = self.handler.previous_state # PAN 前の状態を記録する
    
    def OnPanEnd(self, evt):
        self.toolbar.set_cursor(1)
        self.toolbar.pan()
        self.draw()
        self.handler.current_state = self.__prev  # PAN 前の状態に戻す
        del self.__prev
    
    def OnZoomBegin(self, evt):
        """Toolbar zoom - While zooming, press x/y to constrain the direction"""
        self.toolbar.set_cursor(2)
        self.toolbar.zoom()
        self.__prev = self.handler.previous_state # ZOOM 前状態を記録する
    
    def OnZoomEnd(self, evt):
        self.toolbar.set_cursor(1)
        self.toolbar.zoom()
        self.draw()
        self.handler.current_state = self.__prev  # ZOOM 前の状態に戻す
        del self.__prev
    
    ## def OnZoomMove(self, evt):
    ##     """Zoom
    ##     apted from http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/189744
    ##     matplotlib.backends.backend_wx - NavigationToolbar2Wx.draw_rubberband
    ##     """
    ##     dc = wx.ClientDC(self.canvas)
    ##     
    ##     ## Set logical function to XOR for rubberbanding
    ##     dc.SetLogicalFunction(wx.XOR)
    ##     
    ##     ## Set dc brush and pen
    ##     wbrush = wx.Brush(wx.Colour(255,255,255), wx.TRANSPARENT)
    ##     wpen = wx.Pen(wx.Colour(255,255,255), 1, wx.SOLID)
    ##     dc.SetBrush(wbrush)
    ##     dc.SetPen(wpen)
    ##     dc.ResetBoundingBox()
    ##     dc.BeginDrawing()
    ##     
    ##     height = self.canvas.figure.bbox.height
    ##     org = self.p_event
    ##     x0, y0 = org.x, org.y
    ##     x1, y1 = evt.x, evt.y
    ##     y0 = height - y0
    ##     y1 = height - y1
    ##     if y1 < y0: y0, y1 = y1, y0
    ##     if x1 < y0: x0, x1 = x1, x0
    ##     w = x1 - x0
    ##     h = y1 - y0
    ##     rect = int(x0), int(y0), int(w), int(h)
    ##     try:
    ##         dc.DrawRectangle(*self.__lastrect)  #erase last
    ##     except AttributeError:
    ##         pass
    ##     
    ##     self.__lastrect = rect
    ##     dc.DrawRectangle(*rect)
    ##     dc.EndDrawing()
    ## 
    ## def OnZoomEnd(self, evt):
    ##     try:
    ##         del self.__lastrect
    ##         self.xbound = (self.p_event.xdata, evt.xdata)
    ##         self.ybound = (self.p_event.ydata, evt.ydata)
    ##     except AttributeError:
    ##         pass
    ##     self.toolbar.set_cursor(1)
    ##     self.draw()
    
    ## --------------------------------
    ## Axis actions
    ## --------------------------------
    
    def OnHomeXPosition(self, evt):
        self.OnHomePosition(evt)
    
    def OnHomeYPosition(self, evt):
        self.OnHomePosition(evt)
    
    def OnAxisEnter(self, evt):
        self.set_wxcursor(wx.CURSOR_HAND)
    
    def OnAxisLeave(self, evt):
        self.set_wxcursor(wx.CURSOR_ARROW)
    
    def OnAxisDragBegin(self, evt):
        org = self.p_event
        w, h = self.canvas.Size
        p = self.canvas.ScreenToClient(wx.GetMousePosition())
        org.x, org.y = (p[0], h-p[1])
        org.xdata, org.ydata = self.mapdisp2xy(org.x, org.y) # p_event overwrites
    
    def OnAxisDragEnd(self, evt):
        self.toolbar.push_current()
        if evt.inaxes:
            self.handler('axes enter', evt)
    
    def OnXAxisPanMove(self, evt):
        self.xlim -= (evt.xdata - self.p_event.xdata)
        self.draw()
    
    def OnXAxisPanZoom(self, evt, c=None):
        org = self.p_event
        M = np.exp(-(evt.x - org.x)/100)
        if c is None:
            c = org.xdata
        self.xlim = self.zoomlim(self.xlim, M, c)
        org.x, org.y = evt.x, evt.y
        self.draw()
    
    def OnXAxisPanZoomOrig(self, evt):
        self.OnXAxisPanZoom(evt, c=self.xlim[0])
    
    def OnYAxisPanMove(self, evt):
        self.ylim -= (evt.ydata - self.p_event.ydata)
        self.draw()
    
    def OnYAxisPanZoom(self, evt, c=None):
        org = self.p_event
        M = np.exp(-(evt.y - org.y)/100)
        if c is None:
            c = org.ydata
        self.ylim = self.zoomlim(self.ylim, M, c)
        org.x, org.y = evt.x, evt.y
        self.draw()
    
    def OnYAxisPanZoomOrig(self, evt):
        self.OnYAxisPanZoom(evt, c=self.ylim[0])
    
    def OnYAxisPanZoomEdge(self, evt):
        self.OnYAxisPanZoom(evt, c=self.ylim[1])


if __name__ == '__main__':
    from matplotlib import pyplot as plt
    from matplotlib import patches
    from numpy import pi
    
    def _plot(axes):
        t = np.arange(0,1,0.01)*2*pi
        x = np.cos(t*1.5)
        y = np.sin(t)
        
        #<matplotlib.lines.Line2D>
        art, = axes.plot(x, y, 'y--', lw=1, mec='b', mfc='r', picker=True, pickradius=2)
        
    def _scatter1(axes):
        t = np.arange(0,1,0.02)*2*pi
        x = np.cos(t*1.5)
        y = np.sin(t)
        
        #<matplotlib.collections.Collection>
        art = axes.scatter(x, y, c=t, s=t*10, marker='o',
            alpha=0.5, cmap=cm.Reds, edgecolors='none', picker=True, pickradius=2)
        
        ## set_array -> z color value
        ## set_offsets -> x & y locations
        
        ## scatter は データ参照メソッドを追加する必要がある see on_pick
        ## art.get_data = lambda: x, y
        art.get_xdata = lambda: x
        art.get_ydata = lambda: y
        art.get_zdata = art.get_array
    
    def _scatter2(axes):
        N = 50
        x = 4 * (np.random.rand(N) -1/2)
        y = 4 * (np.random.rand(N) -1/2)
        c = np.random.rand(N)
        r = 100 * np.random.rand(N)
        
        #<matplotlib.collections.Collection>
        art = axes.scatter(x, y, c=c, s=r, marker='o',
            alpha=0.5, cmap=cm.rainbow, edgecolors='blue', picker=True, pickradius=4)
        art.get_xdata = lambda: x
        art.get_ydata = lambda: y
        art.get_zdata = art.get_array
        
    app = wx.App()
    frm = mwx.Frame(None)
    frm.graph = MatplotPanel(frm, log=frm.statusbar, size=(300,240))
    frm.graph.handler.debug = 2
    
    axes = frm.graph.axes
    if 1:
        #<matplotlib.patches.Circle>
        ## axes.add_artist(plt.Circle((0, 0), np.sqrt(2), color='r', ls='dashed', fill=0))
        
        ## axes.add_artist(patches.Circle((0, 0), 2.5, color='r', ls='dashed', fill=0, alpha=0.5))
        axes.add_patch(patches.Circle((0, 0), 2.5, color='r', ls='dashed', fill=0, alpha=0.5))
        
        #<matplotlib.patches.Rectangle>
        axes.add_patch(patches.Rectangle((-1/2,-1/2),1,1, color='r', ls='solid', alpha=0.1))
        
        #<matplotlib.patches.Polygon>
        axes.add_patch(patches.Polygon([(-1,-1),(1,-1),(1,1)], alpha=0.1))
        
    axes.set_title("the title")
    axes.set_xlabel("x")
    axes.set_ylabel("y")
    axes.grid(True)
    axes.axis((-2, 2, -2, 2))
    
    _plot(frm.graph.axes)
    _scatter1(frm.graph.axes)
    _scatter2(frm.graph.axes)
    
    frm.graph.update_position()
    frm.Fit()
    frm.Show()
    app.MainLoop()
