#! python3
"""mwxlib base plot.
"""
import wx

import matplotlib; matplotlib.use('wxagg')  # noqa
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg as Toolbar
from matplotlib.widgets import Cursor
from matplotlib.figure import Figure
import numpy as np

from . import framework as mwx
from .framework import hotkey, regulate_key, postcall, pack, Menu, FSM


## state constants
NORMAL = 'Normal'
DRAGGING = '-dragging'
PAN, ZOOM = 'Pan', 'Zoom'
XAXIS, YAXIS = 'Xaxis', 'Yaxis'
MARK, LINE, REGION = 'Mark', 'Line', 'Region'


## Monkey-patch for matplotlib 3.4/WXAgg
if matplotlib.parse_version(matplotlib.__version__).release < (3,8,0):
    from matplotlib.backend_bases import Event

    def __init__(self, name, canvas, guiEvent=None):
        self.name = name
        self.canvas = canvas
        self.guiEvent = None

    Event.__init__ = __init__
    del __init__

## (local) Monkey-patch for matplotlib 3.8/WXAgg
if 1:
    class Cursor(Cursor):
        def onmove(self, event):
            """Internal event handler to draw the cursor when the mouse moves.
            
            (override) If the cursor is off the axes, the xdata and ydata will
                       be None, and will simply be cleared rather than drawn.
            """
            if self.ignore(event):
                return
            if not self.canvas.widgetlock.available(self):
                return
            
            ## xdata, ydata = self._get_data_coords(event) # >= 3.8 only
            xdata, ydata = event.xdata, event.ydata
            self.linev.set_xdata((xdata, xdata))
            self.linev.set_visible(self.visible and self.vertOn)
            self.lineh.set_ydata((ydata, ydata))
            self.lineh.set_visible(self.visible and self.horizOn)
            if not (self.visible and (self.vertOn or self.horizOn)):
                return
            ## Redraw.
            if self.useblit:
                if self.background is not None:
                    self.canvas.restore_region(self.background)
                self.ax.draw_artist(self.linev)
                self.ax.draw_artist(self.lineh)
                self.canvas.blit(self.ax.bbox)
            else:
                self.canvas.draw_idle()


class MatplotPanel(wx.Panel):
    """MPL panel for general graph
    
    Attributes:
        figure      : <matplotlib.figure.Figure>
        canvas      : <matplotlib.backends.backend_wxagg.FigureCanvasWxAgg>
        toolbar     : <matplotlib.backends.backend_wx.NavigationToolbar2Wx>
        cursor      : <matplotlib.widgets.Cursor>
        selected    : Selected points <matplotlib.lines.Line2D>
    """
    handler = property(lambda self: self.__handler)
    
    def __init__(self, parent, log=None, margin=(.1,.1,.9,.9), **kwargs):
        wx.Panel.__init__(self, parent, **kwargs)
        
        self.message = log or (lambda s: s)
        
        #<matplotlib.figure.Figure>
        self.figure = Figure(facecolor='white', figsize=(.1,.1)) # inches
        
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
        self.modeline = wx.StaticText(self, style=wx.ST_NO_AUTORESIZE)
        
        self.modeline.Bind(wx.EVT_MOTION, self.on_modeline_tip)
        self.modeline.Bind(wx.EVT_LEFT_DOWN, lambda v: self.canvas.SetFocus())
        
        self.infobar = wx.InfoBar(self)
        self.infobar.Size = (0, 0) # workaround for incorrect wrap sizing
        
        self.SetSizer(
            pack(self, (
                (self.canvas,   1, wx.EXPAND | wx.ALL, 0),
                (self.infobar,  0, wx.EXPAND | wx.ALL, 0),
                (self.modeline, 0, wx.EXPAND | wx.ALL, 2),
                (self.toolbar,  0, wx.EXPAND | wx.ALL, 2),
                ),
                orient = wx.VERTICAL,
            )
        )
        self.modeline.Show(0)
        self.Layout()
        
        self.set_margin(margin or (0,0,1,1)) # if margin is None
        self.clear()
        
        ## mpl event handler
        self.canvas.mpl_connect('pick_event', self.on_pick)
        self.canvas.mpl_connect('scroll_event', self.on_scroll)
        ## self.canvas.mpl_connect('key_press_event', self.on_key_press)
        ## self.canvas.mpl_connect('key_release_event', self.on_key_release)
        self.canvas.mpl_connect('button_press_event', self.on_button_press)
        self.canvas.mpl_connect('button_release_event', self.on_button_release)
        self.canvas.mpl_connect('motion_notify_event', self.on_motion_notify)
        
        self.canvas.mpl_connect('figure_enter_event', lambda v: self.handler('figure_enter', v))
        self.canvas.mpl_connect('figure_leave_event', lambda v: self.handler('figure_leave', v))
        self.canvas.mpl_connect('axes_enter_event', lambda v: self.handler('axes_enter', v))
        self.canvas.mpl_connect('axes_leave_event', lambda v: self.handler('axes_leave', v))
        ## self.canvas.mpl_connect('resize_event', lambda v: self.handler('canvas_resized', v))
        ## self.canvas.mpl_connect('draw_event', lambda v: self.handler('canvas_drawn', v))
        
        self.canvas.Bind(wx.EVT_CHAR_HOOK, self.on_hotkey_press)
        self.canvas.Bind(wx.EVT_KEY_DOWN, self.on_hotkey_down)
        self.canvas.Bind(wx.EVT_KEY_UP, self.on_hotkey_up)
        
        self.canvas.Bind(wx.EVT_MOUSE_AUX1_DOWN, lambda v: self.handler('Xbutton1 pressed', v))
        self.canvas.Bind(wx.EVT_MOUSE_AUX2_DOWN, lambda v: self.handler('Xbutton2 pressed', v))
        self.canvas.Bind(wx.EVT_MOUSE_AUX1_UP, lambda v: self.handler('Xbutton1 released', v))
        self.canvas.Bind(wx.EVT_MOUSE_AUX2_UP, lambda v: self.handler('Xbutton2 released', v))
        
        self.canvas.Bind(wx.EVT_SET_FOCUS, lambda v: self.handler('focus_set', v))
        self.canvas.Bind(wx.EVT_KILL_FOCUS, lambda v: self.handler('focus_kill', v))
        
        ## `Rbutton pressed` on_menu is enabled for Normal mode only.
        ## The context menus is disabled and never skip to the next handler.
        self.canvas.Bind(wx.EVT_CONTEXT_MENU, lambda v: self.handler('context_menu', v))
        
        def fork(evt):
            if self.handler.fork(self.handler.current_event, evt) is None:
                evt.Skip()
        
        def skip(evt): #<wx._core.KeyEvent> #<matplotlib.backend_bases.MouseEvent>
            try:
                evt.Skip()
            except AttributeError:
                pass
        
        self.__handler = FSM({ # DNA<MatplotPanel>
                None : {
                  'canvas_draw' : [ None, self.OnDraw ], # before canvas.draw
                #'canvas_drawn' : [ None, ],             # after canvas.draw
              #'canvas_resized' : [ None, ],
                    'focus_set' : [ None, self.on_focus_set ],
                   'focus_kill' : [ None, self.on_focus_kill ],
                 'figure_enter' : [ None, self.on_figure_enter ],
                 'figure_leave' : [ None, self.on_figure_leave ],
                   'axes_enter' : [ None, ],
                   'axes_leave' : [ None, ],
                 'home pressed' : [ None, self.OnHomePosition ],
             'Xbutton1 pressed' : [ None, self.OnBackPosition ],
             'Xbutton2 pressed' : [ None, self.OnForwardPosition ],
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
                    '* pressed' : (NORMAL, skip),
                 'xaxis motion' : (XAXIS, self.OnAxisEnter),
                 'yaxis motion' : (YAXIS, self.OnAxisEnter),
                'y2axis motion' : (YAXIS, self.OnAxisEnter),
                },
                PAN : {
             '*wheelup pressed' : (PAN, self.OnScrollZoom),
           '*wheeldown pressed' : (PAN, self.OnScrollZoom),
              'C-[+;-] pressed' : (PAN, self.OnZoom),
            'C-S-[+;-] pressed' : (PAN, self.OnZoom),
        'C-*[LR]button pressed' : (PAN+DRAGGING, ),
     'space+[LR]button pressed' : (PAN+DRAGGING, ),
              '*[LR]drag begin' : (PAN+DRAGGING, ),
               '*ctrl released' : (NORMAL, self.OnPanEnd),
               'space released' : (NORMAL, self.OnPanEnd),
                 'figure_leave' : (NORMAL, self.OnPanEnd),
                   'axes_leave' : (NORMAL, self.OnPanEnd),
                   'focus_kill' : (NORMAL, self.OnPanEnd),
                  'C-* pressed' : (NORMAL, fork, self.OnPanEnd),
              'C-shift pressed' : (PAN, ),
                },
                PAN+DRAGGING : {
                '*[LR]drag end' : (NORMAL, self.OnPanEnd, self.draw),
         '*[LR]button released' : (NORMAL, self.OnPanEnd, self.draw),
                },
                ZOOM : {
              '*[LR]drag begin' : (ZOOM+DRAGGING, ),
          '*[LR]button pressed' : (ZOOM+DRAGGING, ),
               'escape pressed' : (NORMAL, self.OnZoomEnd),
                    'z pressed' : (NORMAL, self.OnZoomEnd),
                },
                ZOOM+DRAGGING : {
                '*[LR]drag end' : (NORMAL, self.OnZoomEnd, self.draw),
         '*[LR]button released' : (NORMAL, self.OnZoomEnd, self.draw),
                },
                XAXIS : {
                   'axes_enter' : (NORMAL, self.OnAxisLeave),
                 'figure_leave' : (NORMAL, ),
                  'Ldrag begin' : (XAXIS+DRAGGING, self.OnAxisDragBegin),
                 '*Ldrag begin' : (XAXIS+ZOOM+DRAGGING, self.OnAxisDragBegin),
                 '*Rdrag begin' : (XAXIS+ZOOM+DRAGGING, self.OnAxisDragBegin),
                 'yaxis motion' : (YAXIS, ),
                'y2axis motion' : (YAXIS, ),
            '*Lbutton dblclick' : (XAXIS, self.OnHomeXPosition),
                },
                XAXIS+DRAGGING : {
                   'Ldrag move' : (XAXIS+DRAGGING, self.OnXAxisPanMove),
                  '*Rdrag move' : (XAXIS+ZOOM+DRAGGING, self.OnXAxisPanZoom),
                 'C-Ldrag move' : (XAXIS+ZOOM+DRAGGING, self.OnXAxisPanZoom),
               'C-S-Ldrag move' : (XAXIS+ZOOM+DRAGGING, self.OnXAxisPanZoomOrig),
                 'ctrl pressed' : (XAXIS+ZOOM+DRAGGING, self.OnAxisDragBegin),
                   '*Ldrag end' : (XAXIS, self.OnAxisDragEnd),
                   '*Rdrag end' : (XAXIS, self.OnAxisDragEnd),
                },
                XAXIS+ZOOM+DRAGGING : {
                   'Ldrag move' : (XAXIS+DRAGGING, self.OnXAxisPanMove),
                  '*Rdrag move' : (XAXIS+ZOOM+DRAGGING, self.OnXAxisPanZoom),
                 'C-Ldrag move' : (XAXIS+ZOOM+DRAGGING, self.OnXAxisPanZoom),
               'C-S-Ldrag move' : (XAXIS+ZOOM+DRAGGING, self.OnXAxisPanZoomOrig),
                'ctrl released' : (XAXIS+DRAGGING, self.OnAxisDragBegin),
                   '*Ldrag end' : (XAXIS, self.OnAxisDragEnd),
                   '*Rdrag end' : (XAXIS, self.OnAxisDragEnd),
                },
                YAXIS : {
                   'axes_enter' : (NORMAL, self.OnAxisLeave),
                 'figure_leave' : (NORMAL, ),
                  'Ldrag begin' : (YAXIS+DRAGGING, self.OnAxisDragBegin),
                 '*Ldrag begin' : (YAXIS+ZOOM+DRAGGING, self.OnAxisDragBegin),
                 '*Rdrag begin' : (YAXIS+ZOOM+DRAGGING, self.OnAxisDragBegin),
                 'xaxis motion' : (XAXIS, ),
            '*Lbutton dblclick' : (YAXIS, self.OnHomeYPosition),
                },
                YAXIS+DRAGGING : {
                   'Ldrag move' : (YAXIS+DRAGGING, self.OnYAxisPanMove),
                  '*Rdrag move' : (YAXIS+ZOOM+DRAGGING, self.OnYAxisPanZoom),
                 'C-Ldrag move' : (YAXIS+ZOOM+DRAGGING, self.OnYAxisPanZoom),
               'C-S-Ldrag move' : (YAXIS+ZOOM+DRAGGING, self.OnYAxisPanZoomOrig),
                 'ctrl pressed' : (YAXIS+ZOOM+DRAGGING, self.OnAxisDragBegin),
                   '*Ldrag end' : (YAXIS, self.OnAxisDragEnd),
                   '*Rdrag end' : (YAXIS, self.OnAxisDragEnd),
                },
                YAXIS+ZOOM+DRAGGING : {
                   'Ldrag move' : (YAXIS+DRAGGING, self.OnYAxisPanMove),
                  '*Rdrag move' : (YAXIS+ZOOM+DRAGGING, self.OnYAxisPanZoom),
                 'C-Ldrag move' : (YAXIS+ZOOM+DRAGGING, self.OnYAxisPanZoom),
               'C-S-Ldrag move' : (YAXIS+ZOOM+DRAGGING, self.OnYAxisPanZoomOrig),
                'ctrl released' : (YAXIS+DRAGGING, self.OnAxisDragBegin),
                   '*Ldrag end' : (YAXIS, self.OnAxisDragEnd),
                   '*Rdrag end' : (YAXIS, self.OnAxisDragEnd),
                },
            },
            default = NORMAL
        )
        
        self.menu = [
            (mwx.ID_(501), "&Copy image", "Copy canvas image to clipboard",
                lambda v: self.copy_to_clipboard()),
                
            ## (mwx.ID_(502), "&Export image", "Save canvas image",
            ##     lambda v: self.save_to_file()),
        ]
        
        self.__key = ''
        self.__isMenu = None
        self.__isPressed = None
        self.__isDragging = False # True if dragging. (None if dblclicked)
    
    def clear(self):
        """Initialize the plot figure."""
        #<matplotlib.axes.Axes>
        self.figure.clear()
        self.figure.add_subplot(111) # cf. add_axes(rect=(l,b,w,h))
        
        #<matplotlib.lines.Line2D>
        (self.selected,) = self.axes.plot([], [], "yo-", ms=6, lw=2, alpha=0.75,
                                          markeredgecolor='y', visible=0)
        self.selected.set_data([], [])
        
        #<matplotlib.widgets.Cursor>
        self.cursor = Cursor(self.axes, useblit=True, color='grey', linewidth=1)
        self.cursor.visible = 1
    
    ## Note: To avoid a wxAssertionError when running in a thread.
    @postcall
    def draw(self, art=None):
        """Draw plots.
        Call each time the drawing should be updated.
        """
        if isinstance(art, matplotlib.artist.Artist):
            self.axes.draw_artist(art)
            self.canvas.blit(art.get_clip_box())
            ## self.canvas.draw_idle()
        else:
            self.handler('canvas_draw', self.frame)
            self.canvas.draw()
    
    def set_margin(self, lbrt):
        self.figure.subplots_adjust(*lbrt)
    
    def set_wxcursor(self, c):
        self.canvas.SetCursor(wx.Cursor(c))
    
    ## --------------------------------
    ## Property of the current frame
    ## --------------------------------
    
    ## to be overridden (referenced in draw).
    frame = property(lambda self: self)
    
    axes = property(
        lambda self: self.figure.axes[0],
        doc="The first figure axes <matplotlib.axes.Axes>")
    
    xbound = property(
        lambda self: np.array(self.axes.get_xbound()),
        lambda self, v: self.axes.set_xbound(v),
        doc="X-axis numerical bounds where lowerBound < upperBound)")
    
    ybound = property(
        lambda self: np.array(self.axes.get_ybound()),
        lambda self, v: self.axes.set_ybound(v),
        doc="Y-axis numerical bounds where lowerBound < upperBound)")
    
    xlim = property(
        lambda self: np.array(self.axes.get_xlim()),
        lambda self, v: self.axes.set_xlim(v),
        doc="X-axis range [left, right]")
    
    ylim = property(
        lambda self: np.array(self.axes.get_ylim()),
        lambda self, v: self.axes.set_ylim(v),
        doc="Y-axis range [bottom, top]")
    
    @property
    def ddpu(self):
        """Display-dot resolution (x, y) [dots per arb.unit]."""
        ## return self.mapxy2disp(1,1) - self.mapxy2disp(0,0)
        a, b = self.mapxy2disp([0,1],[0,1])
        return b - a
    
    def mapxy2disp(self, x, y):
        """Map xydata --> display dot pixel-coordinates."""
        v = np.array((x, y)).T
        return self.axes.transData.transform(v)
    
    def mapdisp2xy(self, px, py):
        """Map display dot pixel-coordinates --> xydata."""
        v = np.array((px, py)).T
        return self.axes.transData.inverted().transform(v)
    
    ## --------------------------------
    ## Property of the modeline
    ## --------------------------------
    
    selectedModeLineBg = '#000000'
    selectedModeLineFg = '#f0f0f0'
    unselectedModeLineBg = 'auto'
    unselectedModeLineFg = 'auto'
    
    def on_modeline_tip(self, evt): #<wx._core.MouseEvent>
        flag = self.modeline.HitTest(evt.Position)
        if flag == wx.HT_WINDOW_INSIDE:
            self.modeline.SetToolTip(self.modeline.Label)
        evt.Skip()
    
    def on_focus_set(self, evt): #<wx._core.FocusEvent>
        if self.modeline.IsShown():
            self.modeline.SetBackgroundColour(self.selectedModeLineBg)
            self.modeline.SetForegroundColour(self.selectedModeLineFg)
            self.modeline.Refresh()
        self.escape()
        evt.Skip()
    
    def on_focus_kill(self, evt): #<wx._core.FocusEvent>
        if self.modeline.IsShown():
            self.modeline.SetBackgroundColour(self.unselectedModeLineBg)
            self.modeline.SetForegroundColour(self.unselectedModeLineFg)
            self.modeline.Refresh()
        self.escape()
        evt.Skip()
    
    def escape(self, evt=None):
        """Feel like pressing {escape}.
        エスケープキーを押した気持ちになる
        """
        wx.UIActionSimulator().KeyUp(wx.WXK_ESCAPE)
    
    ## --------------------------------
    ## External I/O file and clipboard
    ## --------------------------------
    
    def copy_to_clipboard(self):
        """Copy canvas image to clipboard."""
        ## b = self.selected.get_visible()
        c = self.cursor.visible
        try:
            ## self.selected.set_visible(0)
            self.cursor.visible = 0
            self.canvas.draw()
            self.canvas.Copy_to_Clipboard()
            self.message("Copy image to clipboard.")
        finally:
            ## self.selected.set_visible(b)
            self.cursor.visible = c
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
    
    def on_figure_enter(self, evt): #<matplotlib.backend_bases.MouseEvent>
        pass
    
    def on_figure_leave(self, evt): #<matplotlib.backend_bases.MouseEvent>
        self.cursor.clear(evt)
        self.canvas.draw()
    
    @property
    def selector(self):
        """Selected points array [[x],[y]]."""
        return np.array(self.selected.get_data(orig=0))
    
    @selector.setter
    def selector(self, v):
        x, y = v
        if not hasattr(x, '__iter__'):
            x, y = [x], [y]
        self.selected.set_visible(1)
        self.selected.set_data(x, y)
        self.handler('selector_drawn', self.frame)
        self.draw(self.selected)
        self.trace_point(*v)
    
    @selector.deleter
    def selector(self):
        self.selected.set_visible(0)
        self.selected.set_data([], [])
        self.handler('selector_removed', self.frame)
        self.draw(self.selected)
    
    ## --------------------------------
    ## matplotlib interfaces
    ## --------------------------------
    
    @property
    def p_event(self):
        """Last `pressed` event <matplotlib.backend_bases.MouseEvent>."""
        return self.__isPressed
    
    @p_event.setter
    def p_event(self, v):
        self.__isPressed = v
    
    def on_menu_lock(self, evt): #<matplotlib.backend_bases.MouseEvent>
        self.__isMenu = 1
    
    def on_menu(self, evt): #<matplotlib.backend_bases.MouseEvent>
        if self.__isMenu:
            self.canvas.SetFocus()
            Menu.Popup(self, self.menu)
        self.__isMenu = 0
    
    def on_pick(self, evt): #<matplotlib.backend_bases.PickEvent>
        """Find index near (x,y) and set the selector.
        Called (maybe) after mouse button pressed.
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
            try:
                #<matplotlib.lines.Line2D>
                xs, ys = evt.artist.get_data()
            except AttributeError:
                #<matplotlib.collections.PathCollection>
                xs, ys = evt.artist.get_offsets().T
            
            distances = np.hypot(x-xs[indices], y-ys[indices])
            evt.index = k = indices[distances.argmin()] # index of the nearest point
            evt.xdata = x = xs[k]
            evt.ydata = y = ys[k]
            self.selector = ([x], [y])
            self.canvas.draw_idle()
            self.handler('art_picked', evt)
            self.message("({:g}, {:g}) index {}".format(x, y, evt.index))
    
    def on_hotkey_press(self, evt): #<wx._core.KeyEvent>
        """Called when a key is pressed."""
        key = hotkey(evt)
        self.__key = regulate_key(key + '-')
        if self.handler('{} pressed'.format(key), evt) is None:
            evt.Skip()
    
    def on_hotkey_down(self, evt): #<wx._core.KeyEvent>
        """Called when a key is pressed while dragging.
        Specifically called when the mouse is being captured.
        """
        if self.__isDragging:
            self.on_hotkey_press(evt)
        else:
            evt.Skip()
    
    def on_hotkey_up(self, evt): #<wx._core.KeyEvent>
        """Called when a key is released."""
        key = hotkey(evt)
        self.__key = ''
        if self.handler('{} released'.format(key), evt) is None:
            evt.Skip()
    
    def _on_mouse_event(self, evt): #<matplotlib.backend_bases.MouseEvent>
        """Called in mouse event handlers."""
        if not evt.inaxes or evt.inaxes is not self.axes:
            (evt.xdata, evt.ydata) = self.mapdisp2xy(evt.x, evt.y)
        
        ## Overwrite evt.key with modifiers.
        key = self.__key
        if evt.button in (1,2,3):
            key += 'LMR'[evt.button-1] # {1:L, 2:M, 3:R}
            evt.key = key + 'button'
        elif evt.button in ('up', 'down'):
            key += 'wheel{}'.format(evt.button) # wheel[up|down]
            evt.key = key
        return key
    
    def on_button_press(self, evt): #<matplotlib.backend_bases.MouseEvent>
        """Called when the mouse button is pressed."""
        self.p_event = evt
        key = self._on_mouse_event(evt)
        if evt.dblclick:
            self.__isDragging = None
            self.handler('{}button dblclick'.format(key), evt)
        else:
            self.__isDragging = False
            self.handler('{}button pressed'.format(key), evt)
    
    def on_button_release(self, evt): #<matplotlib.backend_bases.MouseEvent>
        """Called when the mouse button is released."""
        key = self._on_mouse_event(evt)
        if self.__isDragging:
            self.__isDragging = False
            self.handler('{}drag end'.format(key), evt)
            self.handler('{}button released'.format(key), evt)
        else:
            if self.__isDragging is None: # dblclick end
                return
            self.handler('{}button released'.format(key), evt)
        self.p_event = None
    
    def on_motion_notify(self, evt): #<matplotlib.backend_bases.MouseEvent>
        """Called when the mouse is moved."""
        key = self._on_mouse_event(evt)
        if evt.button in (1,2,3):
            if not self.__isDragging:
                self.__isDragging = True
                self.handler('{}drag begin'.format(key), evt)
            else:
                self.handler('{}drag move'.format(key), evt)
        elif evt.inaxes is self.axes:
            self.handler('axes motion', evt)
        else:
            lx, ly = self.xlim, self.ylim
            if   evt.xdata < lx[0]: event = 'yaxis'
            elif evt.xdata > lx[1]: event = 'y2axis'
            elif evt.ydata < ly[0]: event = 'xaxis'
            elif evt.ydata > ly[1]: event = 'x2axis'
            else:
                return
            self.handler('{} motion'.format(event), evt)
    
    def on_scroll(self, evt): #<matplotlib.backend_bases.MouseEvent>
        """Called when scrolling the mouse wheel."""
        self.p_event = evt
        key = self._on_mouse_event(evt)
        self.handler('{} pressed'.format(key), evt)
        self.p_event = None
    
    ## --------------------------------
    ## Pan/Zoom actions
    ## --------------------------------
    
    ZOOM_RATIO = 10 ** 0.2
    ZOOM_LIMIT = 0.1  # logical limit <= epsilon
    
    def OnDraw(self, evt):
        """Called before canvas.draw."""
        pass
    
    def OnMotion(self, evt):
        """Called when mouse moves in axes."""
        if not self.selector.size:
            self.trace_point(evt.xdata, evt.ydata)
    
    def OnForwardPosition(self, evt):
        """Go forward view position."""
        self.toolbar.forward()
        self.draw()
    
    def OnBackPosition(self, evt):
        """Go backward view position."""
        self.toolbar.back()
        self.draw()
    
    def OnHomePosition(self, evt):
        """Go back to home position."""
        self.toolbar.home()
        self.toolbar.update()
        self.toolbar.push_current()
        self.draw()
    
    def OnEscapeSelection(self, evt):
        """Escape from selection."""
        del self.selector
        self.canvas.draw_idle()
    
    def zoomlim(self, lim, M, c=None):
        ## The limitation of zoom is necessary; If the axes is enlarged too much,
        ## the processing speed will significantly slow down.
        if c is None:
            c = (lim[1] + lim[0]) / 2
        y = c - M * (c - lim)
        if abs(y[1] - y[0]) > self.ZOOM_LIMIT:
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
        """Toolbar pan - While panning, press x/y to constrain the direction."""
        ## self.toolbar.set_cursor(2)
        self.set_wxcursor(wx.CURSOR_HAND)
        self.toolbar.pan()
        self.__prev = self.handler.previous_state # save previous state of PAN
    
    def OnPanEnd(self, evt):
        ## self.toolbar.set_cursor(1)
        self.set_wxcursor(wx.CURSOR_ARROW)
        self.toolbar.pan()
        self.handler.current_state = self.__prev  # --> previous state of PAN
        del self.__prev
    
    def OnZoomBegin(self, evt):
        """Toolbar zoom - While zooming, press x/y to constrain the direction."""
        ## self.toolbar.set_cursor(3)
        self.set_wxcursor(wx.CURSOR_CROSS)
        self.toolbar.zoom()
        self.__prev = self.handler.previous_state # save previous state of ZOOM
    
    def OnZoomEnd(self, evt):
        ## self.toolbar.set_cursor(1)
        self.set_wxcursor(wx.CURSOR_ARROW)
        self.toolbar.zoom()
        self.handler.current_state = self.__prev  # --> previous state of ZOOM
        del self.__prev
    
    ## def OnZoomMove(self, evt):
    ##     """Zoom."""
    ##     ## http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/189744
    ##     ## matplotlib.backends.backend_wx - NavigationToolbar2Wx.draw_rubberband
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
            self.handler('axes_enter', evt)
    
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
