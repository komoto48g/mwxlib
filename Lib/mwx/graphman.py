#! python3
# -*- coding: utf-8 -*-
"""Graph manager

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
from collections import OrderedDict
from functools import partial
from functools import wraps
import subprocess
import threading
import traceback
import inspect
import codecs
import sys
import os
import platform
import re
import wx
from wx import aui
## import wx.lib.agw.aui as aui
try:
    import framework as mwx
    from controls import Icon
    from controls import ControlPanel
    from matplot2g import GraphPlot
    from matplot2lg import Histogram
except ImportError:
    from . import framework as mwx
    from .controls import Icon
    from .controls import ControlPanel
    from .matplot2g import GraphPlot
    from .matplot2lg import Histogram
import matplotlib
from matplotlib import cm
from matplotlib import colors
## from matplotlib import pyplot as plt
import numpy as np
from numpy import nan, inf
from PIL import Image
from PIL import ImageFile
from PIL.TiffImagePlugin import TiffImageFile
from pprint import pprint, pformat
from importlib import reload
from six import string_types

## if sys.version_info < (3,0):
##     FileNotFoundError = IOError

_F = mwx.funcall


class Thread(object):
    """Thread for graphman.Layer
    
    The worker:thread runs the given target:f of owner:object.
    
Attributes:
     target : A method bound to an instance of Layer.
     result : A variable that retains the last retval of f.

     worker : reference of the worker thread
      owner : reference of the handler owner (was typ. f.__self__)
              if None, the thread_event is handled by its own handler
Note:
    is_active : flag of being kept going
                Check this to see the worker is running and intended being kept going
    is_running : flag of being running now
                 Watch this to verify the worker is alive after it has been inactivated
    """
    is_active = property(lambda self: self.__keepGoing)
    is_running = property(lambda self: self.__isRunning)
    
    flag = property(lambda self: self.__flag)
    
    def wait(self, timeout=None):
        """Wait flag or interrupt the process
        1. flag.clear   -> clear flag:False so that the thread suspends when wait is called
        2. flag.wait    -> wait until the chequer flag to be set True
        3. flag.set     -> set flag:True to resume the thread
        """
        if not self.is_running:
            return False
        
        ## The event.wait returns immediately when it is True (:set)
        ## and blocks until the internal flag is True when it is False (:clear)
        try:
            if not self.__flag.wait(timeout):
                raise KeyboardInterrupt("timeout")
            if not self.is_active:
                raise KeyboardInterrupt("terminated by user")
            return True
        finally:
            self.__flag.set()
    
    check = wait
    
    def pause(self, msg=""):
        """Pause the process where called
        The caller should check the retval and decide whether to stop the thread.
        """
        if not self.is_running:
            return False
        try:
            self.__flag.clear()
            if wx.MessageBox(msg + "\n\n"
                    "Press [OK] to continue.\n"
                    "Press [CANCEL] to terminate the process.",
                    style=wx.OK|wx.CANCEL|wx.ICON_WARNING) != wx.OK:
                ## self.Stop() # caller should stop if necessary
                return False
            return True
        finally:
            self.__flag.set()
    
    def __init__(self, owner=None):
        self.owner = owner
        self.worker = None
        self.target = None
        self.result = None
        self.__keepGoing = 0
        self.__isRunning = 0
        self.__flag = threading.Event()
        self.__flag.set()
        try:
            self.handler = self.owner.handler
        except AttributeError:
            self.handler = mwx.FSM({})
    
    def __del__(self):
        if self.is_active:
            self.Stop()
    
    def __enter__(self):
        frame = inspect.currentframe().f_back
        module = inspect.getmodule(frame)
        if not self.is_active:
            raise AssertionError("cannot enter {} "
                "unless the thread is running".format(frame.f_code.co_name))
        
        event = "{}:{}:enter".format(module.__name__, frame.f_code.co_name)
        self.handler(event, self)
    
    def __exit__(self, t, v, tb):
        frame = inspect.currentframe().f_back
        module = inspect.getmodule(frame)
        if t:
            event = "{}:{}:error".format(module.__name__, frame.f_code.co_name)
            self.handler(event, self)
        
        event = "{}:{}:exit".format(module.__name__, frame.f_code.co_name)
        self.handler(event, self)
    
    def __call__(self, f, *args, **kwargs):
        """Decorator of thread starter function"""
        @wraps(f)
        def _f(*v):
            return self.Start(f, *v+args, **kwargs)
        return _f
    
    def Start(self, f, *args, **kwargs):
        @wraps(f)
        def _f(*args, **kwargs):
            try:
                self.handler('thread_begin', self)
                self.result = f(*args, **kwargs)
            except KeyboardInterrupt as e:
                print("- Thread:execution stopped: {}".format(e))
            except AssertionError as e:
                print("- Thread:execution failed: {}".format(e))
            except Exception as e:
                traceback.print_exc()
                print("- Thread:exception: {}".format(e))
                self.handler('thread_error', self)
            finally:
                self.__keepGoing = self.__isRunning = 0
                self.handler('thread_end', self)
        
        if self.__isRunning:
            wx.MessageBox("The thread is running (Press C-g to quit).",
                          style=wx.ICON_WARNING)
            return
        
        self.target = f
        self.result = None
        self.__keepGoing = self.__isRunning = 1
        self.worker = threading.Thread(target=_f, args=args, kwargs=kwargs)
        ## self.worker.setDaemon(True)
        self.worker.start()
    
    @mwx.postcall
    def Stop(self):
        self.__keepGoing = 0
        if self.__isRunning:
            busy = wx.BusyInfo("One moment please, now waiting for threads to die...")
            self.handler('thread_quit', self)
            self.worker.join(1)
            ## sys.exit(1)


class Layer(ControlPanel, mwx.CtrlInterface):
    """Graphman.Layer
    
      menu : menu string in parent menubar
   menustr : menu-item string in parent menubar
  category : title of notebook holder, otherwise None for single pane
   caption : flag to set the pane caption to be visible (default caption is __module__)
             a string can also be specified
  dockable : flag to set the pane to be dockable
             type: bool or dock:int (1:t, 2:r, 3:b, 4:l, 5:c)
reloadable : flag to set the Layer to be reloadable
unloadable : flag to set the Layer to be unloadable
    parent : parent <Frame> (not always equals `Parent' especially when floating)
     graph : parent.graph window
    otuput : parent.output window
    """
    menu = "Plugins"
    menustr = property(lambda self: "&"+self.__module__)
    menuicon = None
    caption = True
    category = None
    dockable = True
    editable = True # to be deprecated
    reloadable = True
    unloadable = True
    
    parent = property(lambda self: self.__parent)
    message = property(lambda self: self.__parent.statusbar)
    
    graph = property(lambda self: self.__parent.graph)
    output = property(lambda self: self.__parent.output)
    histogram = property(lambda self: self.__parent.histogram)
    selected_view = property(lambda self: self.__parent.selected_view)
    
    pane = property(lambda self: self.__parent.get_pane(self))
    
    thread_type = Thread
    thread = None # worker <Thread>
    
    @property
    def Arts(self):
        """List of arts <matplotlib.artist.Artist>"""
        return self.__artists
    
    @Arts.setter
    def Arts(self, arts):
        self.__artists = arts
    
    @Arts.deleter
    def Arts(self):
        for art in self.__artists:
            art.remove()
        self.__artists = []
    
    def attach_artists(self, axes, *args):
        """Attach unbound artists (e.g., patches) to the given axes
        If axes is None, the arts will be removed from their axes.
        """
        if axes:
            self._add_artists(axes, *args)
        else:
            self._remove_artists(*args)
    
    ## def set_artists(self, target, *args): # to be deprecated
    ##     self.attach_artists(target.axes, *args)
    
    def _add_artists(self, axes, *args): # to be deprecated
        for art in args:
            if art.axes:
                art.remove()
            axes.add_artist(art)
            self.__artists.append(art)
    
    def _remove_artists(self, *args): # to be deprecated
        for art in args or self.__artists[:]:
            if art.axes:
                art.remove()
            self.__artists.remove(art)
    
    def __init__(self, parent, **kwargs):
        ControlPanel.__init__(self, parent, size=(130,24)) # keep minimum size
        mwx.CtrlInterface.__init__(self)
        
        self.__parent = parent #= self.Parent, but not always if whose son is floating
        self.__artists = []
        
        self.handler.append({ #<Layer.handler>
            None : {
                 'thread_begin' : [ None ], # begin processing
                   'thread_end' : [ None ], # end processing
                  'thread_quit' : [ None ], # terminated by user
                 'thread_error' : [ None ], # failed in error
                  'pane_loaded' : [ None ], # Called after Init
                'pane_unloaded' : [ None ], # Called before Destroy
                   'pane_shown' : [ None, _F(self.Draw, show=True)  ], # when active
                  'pane_closed' : [ None, _F(self.Draw, show=False) ], # when inactive
                  'pane_hidden' : [ None, _F(self.Draw, show=False) ], # when hidden (not closed)
            },
            0 : {
                  'C-c pressed' : (0, _F(self.copy_to_clipboard)),
                  'C-v pressed' : (0, _F(self.paste_from_clipboard)),
                  'C-n pressed' : (0, _F(self.Draw, show=False), _F(self.reset_params)),
                'C-S-c pressed' : (0, _F(self.copy_to_clipboard, checked_only=1)),
                'C-S-v pressed' : (0, _F(self.paste_from_clipboard, checked_only=1)),
                'C-S-n pressed' : (0, _F(self.reset_params, checked_only=1)),
            }
        })
        self.handler.clear(0)
        
        ## Menu (override)
        self.Menu = [
            (wx.ID_COPY, "&Copy params\t(C-c)", "Copy params",
                lambda v: self.copy_to_clipboard()),
                
            (wx.ID_PASTE, "&Paste params\t(C-v)", "Read params",
                lambda v: self.paste_from_clipboard()),
            (),
            (wx.ID_RESET, "&Reset params\t(C-n)", "Reset params", Icon('-'),
                lambda v: (self.Draw(False), self.reset_params())),
            (),
            (wx.ID_EDIT, "&Edit module", "Edit module src", Icon('pen'),
                lambda v: self.parent.edit_plug(self.__module__),
                lambda v: v.Enable(self.editable)),
                
            (mwx.ID_(201), "&Reload module", "Reload module", Icon('load'),
                lambda v: self.parent.reload_plug(self.__module__),
                lambda v: v.Enable(self.reloadable
                            and not (self.thread and self.thread.is_active))),
                
            (mwx.ID_(202), "&Unload module", "Unload module", Icon('delete'),
                lambda v: self.parent.unload_plug(self.__module__),
                lambda v: v.Enable(self.unloadable
                            and not (self.thread and self.thread.is_active))),
            (),
            (mwx.ID_(203), "&Dive into {!r}".format(self.__module__), "deb", Icon('core'),
                lambda v: self.parent.inspect_plug(self.__module__)),
        ]
        
        def destroy(evt):
            if self.thread and self.thread.is_active:
                self.thread.Stop()
            del self.Arts
            evt.Skip()
        self.Bind(wx.EVT_WINDOW_DESTROY, destroy)
        
        try:
            self.Init()
            
            session = kwargs.get('session')
            if session:
                wx.CallAfter(self.init_session, session)
        except RuntimeError:
            if parent: # unless stand-alone Layer <wx.Window> object is intended ?
                raise
        except Exception as e:
            traceback.print_exc()
            if parent:
                bmp = wx.StaticBitmap(self, bitmap=Icon('!!!'))
                txt = wx.StaticText(self, label="Exception")
                txt.SetToolTip(repr(e))
                self.layout((bmp, txt), row=2)
    
    def Init(self):
        """Initialize me safely (to be overridden)"""
        pass
    
    ## def Destroy(self):
    ##     """Called from parent (to be overridden) -> destroy"""
    ##     return Layer.Destroy(self)
    
    def init_session(self, session):
        """Restore settings from a session file (to be overridden)"""
        pass
    
    def save_session(self, session):
        """Save settings in a session file (to be overridden)"""
        pass
    
    Shown = property(
        lambda self: self.IsShown(),
        lambda self,v: self.Show(v))
    
    def IsShown(self):
        return self.parent.get_pane(self).IsShown()
    
    def Show(self, show=True):
        ## self.parent.show_pane(self, show)
        wx.CallAfter(self.parent.show_pane, self, show)
    
    Drawn = property(
        lambda self: self.IsDrawn(),
        lambda self,v: self.Draw(v))
    
    def IsDrawn(self):
        return any(art.get_visible() for art in self.Arts)
    
    def Draw(self, show=True):
        if not self.Arts:
            return
        try:
            ## Arts may be belonging to either graph, output, and any other windows.
            for art in self.Arts:
                art.set_visible(show)
            art.axes.figure.canvas.draw_idle()
        except RuntimeError as e:
            print("- {}: Artists failed to draw: {}".format(self.__module__, e))
            del self.Arts


class Graph(GraphPlot):
    """GraphPlot (override) to better make use for graph manager
    """
    parent = property(lambda self: self.__parent)
    loader = property(lambda self: self.__loader)
    
    def __init__(self, parent, loader=None, **kwargs):
        GraphPlot.__init__(self, parent, **kwargs)
        
        self.__parent = parent
        self.__loader = loader or parent
        
        self.handler.append({ #<Graph.handler>
            None : {
                    'focus_set' : [ None, _F(self.loader.select_view, view=self) ],
                  'frame_shown' : [ None, _F(self.update_infobar) ],
                  'S-a pressed' : [ None, _F(self.toggle_infobar) ],
                   'f5 pressed' : [ None, _F(self.refresh) ],
            },
        })
        ## ドロップターゲットを許可する
        self.SetDropTarget(MyFileDropLoader(self, loader=self.loader))
    
    def refresh(self):
        if self.frame:
            self.frame.update_buffer()
            self.draw()
    
    def toggle_infobar(self):
        """Toggle infobar (frame.annotation)"""
        if self.infobar.IsShown():
            self.infobar.Dismiss()
        elif self.frame:
            self.infobar.ShowMessage(str(self.frame.annotation))
    
    def update_infobar(self, frame):
        """Show infobar (frame.annotation)"""
        if self.infobar.IsShown():
            self.infobar.ShowMessage(str(frame.annotation))
    
    def get_frame(self, j):
        if isinstance(j, string_types):
            return next((art for art in self.all_frames if art.name == j), None)
        return self.all_frames[j]
    
    def get_frame_visible(self):
        if self.frame:
            return self.frame.get_visible()
        return False
    
    def set_frame_visible(self, v):
        if self.frame:
            self.frame.set_visible(v)
            self.draw()
    
    def get_markups_visible(self):
        return self.marked.get_visible()
    
    def set_markups_visible(self, v):
        self.marked.set_visible(v)
        self.update_art_of_mark()
    
    def remove_markups(self):
        del self.Selector
        del self.Markers
        del self.Region
    
    def hide_layers(self):
        for name in self.parent.plugins:
            plug = self.parent.get_plug(name)
            for art in plug.Arts:
                art.set_visible(0)
        self.remove_markups()
        self.draw()


class MyFileDropLoader(wx.FileDropTarget):
    """File Drop interface
    
    window : target window to drop in, e.g. frame, graph, pane, etc.
    loader : the main frame
    """
    def __init__(self, target, loader):
        wx.FileDropTarget.__init__(self)
        self.target = target
        self.loader = loader
    
    def OnDropFiles(self, x, y, filenames):
        pos = self.target.ScreenPosition + (x,y)
        paths = []
        for path in filenames:
            name, ext = os.path.splitext(path)
            if ext == '.py' or os.path.isdir(path):
                self.loader.load_plug(path, show=1, floating_pos=pos,
                                        force=wx.GetKeyState(wx.WXK_ALT))
            elif ext == '.jssn':
                self.loader.load_session(path)
            elif ext == '.results':
                self.loader.import_index(path, self.target)
            else:
                paths.append(path) # image file just stacks to be loaded
        if paths:
            self.loader.load_frame(paths, self.target)
        return True


class AuiNotebook(aui.AuiNotebook):
    def __init__(self, *args, **kwargs):
        aui.AuiNotebook.__init__(self, *args, **kwargs)
        
        self.Bind(aui.EVT_AUINOTEBOOK_TAB_RIGHT_DOWN, self.on_show_menu)
        self.Bind(aui.EVT_AUINOTEBOOK_PAGE_CHANGED, self.on_page_changed)
        self.Bind(aui.EVT_AUINOTEBOOK_PAGE_CHANGING, self.on_page_changing)
    
    def on_show_menu(self, evt): #<wx._aui.AuiNotebookEvent>
        plug = self.GetPage(evt.Selection)
        mwx.Menu.Popup(self, plug.Menu)
        evt.Skip()
    
    def on_page_changed(self, evt): #<wx._aui.AuiNotebookEvent>
        self.CurrentPage.handler('pane_shown')
        evt.Skip()
    
    def on_page_changing(self, evt): #<wx._aui.AuiNotebookEvent>
        plug = self.GetPage(evt.Selection) # <-- CurrentPage
        if self.CurrentPage:
            if self.CurrentPage is not plug:
                self.CurrentPage.handler('pane_hidden')
        evt.Skip() # skip to the next handler
                   # but called twice when click?


class Frame(mwx.Frame):
    """Graph and Plug manager frame
    
  Interfaces
    1. pane window interface
    2. plugins interface
    3. load/save images
    4. open/close session
    """
    graph = property(lambda self: self.__graph)
    output = property(lambda self: self.__output)
    histogram = property(lambda self: self.__histogram)
    
    selected_view = property(lambda self: self.__view)
    
    def select_view(self, view):
        self.__view = view
        self.OnShowFrame(view.frame)
    
    @property
    def graphic_windows(self):
        """graphic windows list
        including [0] graph [1] output [2:] others(user-defined)
        """
        return self.__graphic_windows
    
    ## @property
    ## def graphic_windows_on_screen(self):
    ##     return [w for w in self.__graphic_windows if w.IsShownOnScreen()]
    
    def __init__(self, *args, **kwargs):
        mwx.Frame.__init__(self, *args, **kwargs)
        
        #<wx.aui.AuiManager>
        self._mgr = aui.AuiManager()
        self._mgr.SetManagedWindow(self)
        self._mgr.SetDockSizeConstraint(0.5, 0.5)
        
        ## self._mgr.SetAutoNotebookStyle(
        ##     agwStyle=(aui.AUI_NB_SMART_TABS
        ##             | aui.AUI_NB_TAB_MOVE
        ##             | aui.AUI_NB_TAB_SPLIT
        ##             | aui.AUI_NB_TAB_FLOAT
        ##             | aui.AUI_NB_TAB_EXTERNAL_MOVE
        ##             | aui.AUI_NB_SCROLL_BUTTONS)
        ##             &~(aui.AUI_NB_CLOSE_ON_ACTIVE_TAB
        ##              | aui.AUI_NB_CLOSE_BUTTON
        ##              | aui.AUI_NB_SUB_NOTEBOOK)
        ## )
        
        self.__plugins = OrderedDict() # modules in the order of load/save
        
        self.__graph = Graph(self, log=self.statusbar, margin=None, size=(200,200))
        self.__output = Graph(self, log=self.statusbar, margin=None, size=(200,200))
        
        self.__graphic_windows = [
            self.__graph,
            self.__output,
        ]
        self.select_view(self.__graph)
        
        self.__histogram = Histogram(self, log=self.statusbar, margin=None, size=(130,65))
        self.__histogram.attach(self.graph)
        self.__histogram.attach(self.output)
        
        self._mgr.AddPane(self.graph, aui.AuiPaneInfo().CenterPane().CloseButton(1)
            .Name("graph").Caption("graph").CaptionVisible(1))
        
        size = self.output.GetSize()
        self._mgr.AddPane(self.output, aui.AuiPaneInfo()
            .Name("output").Caption("output").FloatingSize(size).MinSize(size).Right().Show(0))
        
        size = self.histogram.GetSize()
        self._mgr.AddPane(self.histogram, aui.AuiPaneInfo()
            .Name("histogram").Caption("histogram").FloatingSize(size).MinSize(size).Left().Show(0))
        
        self.menubar["File"][0:0] = [
            (wx.ID_OPEN, "&Open\tCtrl-o", "Open file", Icon('book_open'),
                lambda v: self.load_frame()),
                
            (wx.ID_CLOSE, "&Close\t(C-k)", "Kill buffer", Icon('book_blue'),
                lambda v: self.__view.kill_buffer(),
                lambda v: v.Enable(self.__view.frame is not None)),
                
            (wx.ID_CLOSE_ALL, "&Close all\t(C-S-k)", "Kill all buffers", Icon('book_red'),
                lambda v: self.__view.kill_buffer_all(),
                lambda v: v.Enable(self.__view.frame is not None)),
                
            (wx.ID_SAVE, "&Save as\tCtrl-s", "Save buffer as", Icon('save'),
                lambda v: self.save_frame(),
                lambda v: v.Enable(self.__view.frame is not None)),
                
            (wx.ID_SAVEAS, "&Save as TIFFs", "Save buffers as a statck-tiff", Icon('saveas'),
                lambda v: self.save_buffers_as_tiffs(),
                lambda v: v.Enable(self.__view.frame is not None)),
            (),
            ("Index", (
                (mwx.ID_(11), "&Import index\tCtrl+Shift+o", "Import index file", Icon('open'),
                    lambda v: self.import_index()),
                    
                (mwx.ID_(12), "&Export index\tCtrl+Shift+s", "Export index file", Icon('saveas'),
                    lambda v: self.export_index(),
                    lambda v: v.Enable(self.__view.frame is not None)),
                )),
            ## (),
            ("Session", (
                (mwx.ID_(15), "&Open session", "Open session file",
                    lambda v: self.load_session()),
                    
                (mwx.ID_(16), "&Ssave session", "Save session file",
                    lambda v: self.save_session()),
                    
                (mwx.ID_(17), "&Ssave session as", "Save session file as",
                    lambda v: self.save_session_as()),
                )),
            ## (),
            ("Options", []), # reserved for optional app settings
            (),
            (mwx.ID_(13), "&Graph window\tF9", "Show graph window", wx.ITEM_CHECK,
                lambda v: self.show_pane("graph", v.IsChecked()),
                lambda v: v.Check(self.get_pane("graph").IsShown())),
                
            (mwx.ID_(14), "&Output window\tF10", "Show Output window", wx.ITEM_CHECK,
                lambda v: self.show_pane("output", v.IsChecked()),
                lambda v: v.Check(self.get_pane("output").IsShown())),
            (),
        ]
        self.menubar["Edit"] = [
            (wx.ID_COPY, "&Copy\t(C-c)", "Copy buffer to clipboard", Icon('copy'),
                lambda v: self.__view.write_buffer_to_clipboard()),
                
            (wx.ID_PASTE, "&Paste\t(C-v)", "Paste buffer from clipboard", Icon('paste'),
                lambda v: self.__view.read_buffer_from_clipboard()),
            (),
            (mwx.ID_(20), "Show &Image", "Show/Hide image", wx.ITEM_CHECK, Icon('image'),
                lambda v: self.__view.set_frame_visible(v.IsChecked()),
                lambda v: v.Check(self.__view.get_frame_visible())),
                
            (mwx.ID_(21), "Show &Markers", "Show/Hide markups", wx.ITEM_CHECK, Icon('+'),
                lambda v: self.__view.set_markups_visible(v.IsChecked()),
                lambda v: v.Check(self.__view.get_markups_visible())),
                
            (mwx.ID_(22), "&Remove Markers", "Remove markups", wx.ITEM_CHECK, Icon('-'),
                lambda v: self.__view.remove_markups(),
                lambda v: v.Check(self.__view.Markers.size)),
            (),
            (mwx.ID_(23), "Hide all &Layers", "Hide all layers", Icon('xr'),
                lambda v: self.__view.hide_layers()),
            (),
            (mwx.ID_(24), "&Histogram\tCtrl-h", "Show Histogram window", wx.ITEM_CHECK,
                lambda v: self.show_pane("histogram", v.IsChecked()),
                lambda v: v.Check(self.get_pane("histogram").IsShown())),
                
            (mwx.ID_(25), "&Invert Color\t(C-i)", "Invert colormap", wx.ITEM_CHECK,
                lambda v: self.__view.invert_cmap(),
                lambda v: v.Check(self.__view.get_cmap()[-2:] == "_r")),
        ]
        
        def cmenu(i, name):
            return (mwx.ID_(30 + i), "&" + name, name, wx.ITEM_CHECK,
                lambda v: self.__view.set_cmap(name),
                lambda v: v.Check(self.__view.get_cmap() == name
                               or self.__view.get_cmap() == name+"_r"),
            )
        colours = [c for c in dir(cm) if c[-2:] != "_r"
                    and isinstance(getattr(cm,c), colors.LinearSegmentedColormap)]
        
        self.menubar["Edit"] += [
            (),
            ## (mwx.ID_(26), "Default Color", "gray", wx.ITEM_CHECK,
            ##     lambda v: self.__view.set_cmap('gray'),
            ##     lambda v: v.Check(self.__view.get_cmap()[:4] == "gray")),
            ##     
            ("Standard Color",
                [cmenu(i,c) for i,c in enumerate(colours) if c.islower()]),
                
            ("Another Color",
                [cmenu(i,c) for i,c in enumerate(colours) if not c.islower()]),
        ]
        
        self.menubar[Layer.menu] = [ # Plugins menu
            (mwx.ID_(100), "&Load Plugs", "Load plugins", Icon('load'),
                self.OnLoadPlugins),
            
            (mwx.ID_(101), "&Quit Plugs\tCtrl-g", "Stop all plugin threads", Icon('exit'),
                self.Quit),
            (),
        ]
        self.menubar.reset()
        
        ## フレーム変更時の描画設定
        self.graph.handler.append({ #<Graph.handler>
            None : {
                  'frame_shown' : [ None, self.OnShowFrame ],
                 'frame_loaded' : [ None, lambda v: self.show_pane("graph") ],
               'frame_modified' : [ None, lambda v: self.show_pane("graph") ],
               'frame_selected' : [ None, self.OnShowFrame ],
                  'canvas_draw' : [ None, lambda v: self.sync(self.graph, self.output) ],
            },
        })
        self.output.handler.append({ #<Graph.handler>
            None : {
                  'frame_shown' : [ None, self.OnShowFrame ],
                 'frame_loaded' : [ None, lambda v: self.show_pane("output") ],
               'frame_modified' : [ None, lambda v: self.show_pane("output") ],
               'frame_selected' : [ None, self.OnShowFrame ],
                  'canvas_draw' : [ None, lambda v: self.sync(self.output, self.graph) ],
            },
        })
        
        ## コンテキストメニューに追加
        ## self.graph.Menu += self.menubar["File"][3:5]
        self.graph.Menu += self.menubar["Edit"][2:8]
        
        ## self.output.Menu += self.menubar["File"][3:5]
        self.output.Menu += self.menubar["Edit"][2:8]
        
        ## その他
        self._mgr.Bind(aui.EVT_AUI_PANE_CLOSE, self.OnPaneClose)
        
        self.Bind(wx.EVT_CLOSE, self.OnCloseFrame)
        
        ## self.Bind(wx.EVT_ACTIVATE,
        ##           lambda v: self.OnShowFrame(self.selected_view.frame))
        
        ## Custom Key Bindings:
        self.define_key('C-g', self.Quit)
        
        ## ドロップターゲットを許可する
        self.SetDropTarget(MyFileDropLoader(self, loader=self))
        
        self._mgr.Update()
    
    sync_switch = True
    
    def sync(self, a, b):
        """synchronize b to a"""
        if (self.sync_switch
            and a.frame and b.frame
            and a.frame.unit == b.frame.unit
            and a.buffer.shape == b.buffer.shape):
                b.xlim = a.xlim
                b.ylim = a.ylim
                b.OnDraw(None)
                b.canvas.draw_idle()
    
    Editor = "notepad"
    
    def edit(self, f):
        if hasattr(f, '__file__'):
            name,_ext = os.path.splitext(f.__file__)
            f = name + '.py'
        subprocess.Popen('{} "{}"'.format(self.Editor, f))
    
    def OnShowFrame(self, frame):
        ssn = os.path.basename(self.session_file or '--')
        session_name,_ext = os.path.splitext(ssn)
        self.SetTitle("{}@{} - [{}] {}".format(
            self.__class__.__name__, platform.node(), session_name,
            (frame.pathname or frame.name) if frame else '',
        ))
    
    def OnCloseFrame(self, evt): #<wx._core.CloseEvent>
        ssn = os.path.basename(self.session_file or '--')
        with wx.MessageDialog(None,
                "Do you want to save session before closing program?",
                "{}@{} - [{}]".format(self.__class__.__name__, platform.node(), ssn),
                style=wx.YES_NO|wx.CANCEL|wx.ICON_INFORMATION) as dlg:
            ret = dlg.ShowModal()
            if ret == wx.ID_YES:
                if not self.save_session():
                    return
            elif ret == wx.ID_CANCEL:
                return
            evt.Skip()
    
    def Destroy(self):
        try:
            for pane in self._mgr.GetAllPanes():
                pane.window.Destroy()
        finally:
            self._mgr.UnInit()
            return mwx.Frame.Destroy(self)
    
    ## --------------------------------
    ## pane window interface
    ## --------------------------------
    
    def get_pane(self, name):
        """Get named pane or notebook pane"""
        if name in self.plugins:
            plug = self.plugins[name].__plug__
            name = plug.category or name
        elif hasattr(name, 'category'): # isinstance(name, Layer):<type 'Layer'>
            plug = name
            name = plug.category or name
        return self._mgr.GetPane(name)
    
    def show_pane(self, name, show=True):
        """Show named pane or notebook pane"""
        pane = self.get_pane(name)
        
        if not pane.IsOk():
            return False
        
        if name == "output": # set graph and output size be as half & half
            w, h = self.graph.GetClientSize()
            pane.best_size = (w//2, h) # サイズはドッキング時に再計算される
        
        if wx.GetKeyState(wx.WXK_SHIFT):
            ## (alt + shift + menu) reload plugin
            if wx.GetKeyState(wx.WXK_ALT):
                if hasattr(name, 'category'): # isinstance(name, Layer):<type 'Layer'>
                    self.reload_plug(name)
                    pane = self.get_pane(name)
            ## (ctrl + shift + menu) reset floating position of a stray window
            if wx.GetKeyState(wx.WXK_CONTROL):
                pane.floating_pos = wx.GetMousePosition()
            show = True
        
        plug = self.get_plug(name)
        
        try:
            ## for Layers only (has notebook property)
            nb = plug.__notebook
            if nb and show:
                nb.SetSelection(nb.GetPageIndex(plug))
        except AttributeError:
            pass
        
        if plug:
            if show:
                if not pane.IsShown():
                    plug.handler('pane_shown')
            else:
                if pane.IsShown():
                    plug.handler('pane_closed')
        pane.Show(show)
        self._mgr.Update()
    
    def update_pane(self, name, show=False, **kwargs):
        """Update the layout of pane
        
        Note: This is called automatically from load_plug,
              and should not be called directly from user.
        """
        pane = self.get_pane(name)
        
        pane.dock_layer = kwargs.get('layer', 0)
        pane.dock_pos = kwargs.get('pos', 0)
        pane.dock_row = kwargs.get('row', 0)
        pane.dock_proportion = kwargs.get('prop') or pane.dock_proportion
        pane.floating_pos = kwargs.get('floating_pos') or pane.floating_pos
        pane.floating_size = kwargs.get('floating_size') or pane.floating_size
        
        dock = kwargs.get('dock')
        if dock:
            pane.dock_direction = dock
            pane.Dock()
        else:
            pane.Float()
        
        plug = self.get_plug(name)
        
        try:
            ## for Layers only (has some special constants)
            pane.CaptionVisible(bool(plug.caption))
            pane.Gripper(not plug.caption and dock != 5)
            pane.Dockable(plug.dockable)
            nb = plug.__notebook
            if nb and show:
                nb.SetSelection(nb.GetPageIndex(plug))
        except AttributeError:
            pass
        
        if plug:
            if show:
                if not pane.IsShown():
                    plug.handler('pane_shown')
            else:
                if pane.IsShown():
                    plug.handler('pane_closed')
        pane.Show(show)
        self._mgr.Update()
    
    def OnPaneClose(self, evt): #<wx.aui.AuiManagerEvent>
        pane = evt.GetPane()
        win = pane.window
        if isinstance(win, aui.AuiNotebook):
            for j in range(win.PageCount):
                plug = win.GetPage(j)
                plug.handler('pane_closed')
        else:
            win.handler('pane_closed')
        ## evt.Skip() # cause the same event call twice?
    
    ## --------------------------------
    ## Plugin (Layer) interface
    ## --------------------------------
    plugins = property(lambda self: self.__plugins)
    
    @property
    def plugs(self):
        return OrderedDict((k, v.__plug__) for k,v in self.plugins.items())
    
    __new_ID_ = 10001 # use ID_ *not* in [ID_LOWEST(4999):ID_HIGHEST(5999)]
    
    def require(self, name):
        """Get named plug window
        If not found, try to load it once.
        
        Note: When called in thread, the display of AuiPane might be broken.
              Reload this from menu with [C-M-S] key after the thread exits.
        """
        if isinstance(name, string_types):
            if name.endswith(".py") or name.endswith(".pyc"):
                name,_ext = os.path.splitext(os.path.basename(name))
        plug = self.get_plug(name)
        if plug is None:
            if self.load_plug(name) is not False:
                return self.get_plug(name)
        return plug
    
    def get_plug(self, name):
        """Find named plug window in registered plugins"""
        if name in self.plugins:
            return self.plugins[name].__plug__
        elif hasattr(name, 'category'): # isinstance(name, Layer):<type 'Layer'>
            return name
    
    def load_plug(self, root, show=False,
            docking=None, dock=False, layer=0, pos=0, row=0, prop=10000,
            floating_pos=None, floating_size=None, force=False, **kwargs):
        """Load plugin module
        The module `root must have 'class Plugin' derived from <mwx.graphman.Layer>
        
        root : Layer object, module, or `name of module
        show : the pane is to be shown when loaded
       force : force loading even when it were already loaded
        dock : dock_direction (1:top, 2:right, 3:bottom, 4:left, 5:center)
       layer : dock_layer
         pos : dock_pos
         row : dock_row position
        prop : dock_proportion < 1e6 ?
   floating_ : pos/size of floating window
        
        retval-> None if succeeded else False
        """
        if hasattr(root, '__file__'): #<type 'module'>
            root = root.__file__
            
        elif hasattr(root, '__module__'): # isinstance(root, Layer):<type 'Layer'>
            root = root.__module__
            
            ## If the name of root has been loaded,
            ## we reload it referring to the file-name, not module-name
            if root in self.plugins:
                root = self.plugins[root].__file__
        
        name = os.path.basename(root)
        if name.endswith(".py") or name.endswith(".pyc"):
            name,_ext = os.path.splitext(name)
        
        ## 正しくロードできるようにインクルードパスを更新する
        root = os.path.normpath(root)
        dirname = os.path.dirname(root)
        if dirname:
            if os.path.isdir(dirname):
                if dirname in sys.path:
                    sys.path.remove(dirname) # インクルードパスの先頭に移動するため削除
                sys.path.insert(0, dirname) # インクルードパスの先頭に追加する
            else:
                print("- No such directory {!r}".format(dirname))
                return False
        
        ## --------------------------------
        ## 0. Check if already plugged in
        ## --------------------------------
        if docking is not None:
            dock = docking # to be deprecated
        
        props = dict(show=show,
                     dock=dock, layer=layer, pos=pos, row=row, prop=prop,
                     floating_pos=floating_pos, floating_size=floating_size)
        
        plug = self.get_plug(name)
        
        ## [name] がすでに登録されている (OK)
        if plug:
            if not force:
                if not isinstance(plug.dockable, bool):
                    props.update(dock = plug.dockable)
                self.update_pane(name, **props)
                
                session = kwargs.get('session') # session が指定されていれば優先
                if session:
                    plug.init_session(session)
                return #<plug>
        
        ## --------------------------------
        ## 1. import the module
        ## --------------------------------
        try:
            self.statusbar("Loading plugin {!r}...".format(name))
            if name in sys.modules:
                module = reload(sys.modules[name])
            else:
                module = __import__(name, fromlist=[''])
            
        except ImportError as e:
            print("-", self.statusbar("\b failed to import: {}".format(e)))
            return False
        
        try:
            title = module.Plugin.category
            pane = self._mgr.GetPane(title)
            
            ## [category] がすでに登録されている
            if pane.IsOk():
                nb = pane.window
                if not isinstance(nb, aui.AuiNotebook):
                    ## AuiManager:Name をダブって登録することはできない
                    ## Notebook.title (category) はどのプラグインとも別名にすること
                    raise NameError("Notebook name must not be the same as any other plugins")
            
            name = module.Plugin.__module__ # rename as module plugin name
            pane = self.get_pane(name)
            
            ## [name] がすでに登録されている
            if pane.IsOk():
                if name not in self.plugins:
                    raise NameError("Plugin name must not be the same as any other panes")
                
                props.update(
                    show = show or pane.IsShown(),
                    dock = pane.IsDocked() and pane.dock_direction,
                    layer = pane.dock_layer,
                    pos = pane.dock_pos,
                    row = pane.dock_row,
                    prop = pane.dock_proportion,
                    floating_pos = floating_pos or pane.floating_pos[:], # copy (pane unloaded)
                    floating_size = floating_size or pane.floating_size[:], # copy
                )
        except NameError as e:
            wx.CallAfter(wx.MessageBox,
                         "{}\n\n{}".format(e, traceback.format_exc()),
                         "Error in loading {!r}".format(name),
                         style=wx.ICON_ERROR)
            return False
        
        ## --------------------------------
        ## 2. register the plugin
        ## --------------------------------
        try:
            if pane.IsOk():
                self.unload_plug(name) # unload once right here
            
            ## Add to the list in advance to refer the module in Plugin.Init.
            ## However, it's uncertain that the Init will end successfully.
            ## self.plugins[name] = module
            
            ## Create a plug and register to plugins list プラグインのロード開始
            ## The module must have a class Plugin
            plug = module.Plugin(self, **kwargs)
            plug.__notebook = None
            plug.__Menu_item = None
            
            ## set reference of a plug (one module, one plugin)
            module.__plug__ = plug
            
            ## Add to the list after the plug is created successfully.
            self.plugins[name] = module
            plug.handler('pane_loaded')
            
        except Exception as e:
            wx.CallAfter(wx.MessageBox,
                         "{}\n\n{}".format(e, traceback.format_exc()),
                         "Error in loading {!r}".format(name),
                         style=wx.ICON_ERROR)
            return False
        
        ## --------------------------------
        ## 3. create pane or notebook pane
        ## --------------------------------
        try:
            title = plug.category
            caption = plug.caption
            if not isinstance(caption, string_types):
                caption = name
            
            if not isinstance(plug.dockable, bool):
                props.update(dock = plug.dockable)
            
            if title:
                pane = self._mgr.GetPane(title)
                if pane.IsOk():
                    nb = pane.window
                    nb.AddPage(plug, caption)
                    props.update(show = show or pane.IsShown())
                else:
                    size = plug.GetSize() + (2,30)
                    nb = AuiNotebook(self,
                        style=(aui.AUI_NB_DEFAULT_STYLE | aui.AUI_NB_BOTTOM)
                            &~(aui.AUI_NB_CLOSE_ON_ACTIVE_TAB | aui.AUI_NB_MIDDLE_CLICK_CLOSE))
                    nb.AddPage(plug, caption)
                    self._mgr.AddPane(nb, aui.AuiPaneInfo()
                        .Name(title).Caption(title).FloatingSize(size).MinSize(size).Show(0))
                j = nb.GetPageIndex(plug)
                nb.SetPageToolTip(j, "[{}]\n{}".format(plug.__module__, plug.__doc__))
            else:
                nb = None
                size = plug.GetSize() + (2,2)
                self._mgr.AddPane(plug, aui.AuiPaneInfo()
                    .Name(name).Caption(caption).FloatingSize(size).MinSize(size).Show(0))
            
            ## set reference of notebook (optional)
            plug.__notebook = nb
            
            self.update_pane(name, **props)
            
            ## register menu item
            if not hasattr(module, 'ID_'): # give a unique index to the module
                module.ID_ = Frame.__new_ID_
                Frame.__new_ID_ += 1
            
            if plug.menu:
                doc = (plug.__doc__ or name).strip().splitlines()[0]
                plug.__Menu_item = (
                    module.ID_, plug.menustr, doc, wx.ITEM_CHECK, Icon(plug.menuicon),
                    lambda v: self.show_pane(name, v.IsChecked()),
                    lambda v: v.Check(self.get_pane(name).IsShown()),
                )
                menu = self.menubar[plug.menu] or []
                self.menubar[plug.menu] = menu + [plug.__Menu_item]
                self.menubar.update(plug.menu)
            
            self.statusbar("\b done.")
            return #<plug>
        
        except Exception as e:
            wx.CallAfter(wx.MessageBox,
                         "{}\n\n{}".format(e, traceback.format_exc()),
                         "Error in loading {!r}".format(name),
                         style=wx.ICON_ERROR)
            return False
    
    def unload_plug(self, name):
        """Unload plugin module and detach the pane from UI manager"""
        try:
            ## self.statusbar("Unloading plugin {!r}...".format(name))
            plug = self.get_plug(name)
            if not plug:
                return False
            
            name = plug.__module__
            if name not in self.plugins:
                return False
            
            del self.plugins[name]
            
            if plug.__Menu_item:
                self.menubar[plug.menu].remove(plug.__Menu_item)
                self.menubar.update(plug.menu)
            
            nb = plug.__notebook
            if nb:
                j = nb.GetPageIndex(plug)
                nb.RemovePage(j) # just remove page
                ## nb.DeletePage(j) # cf. destroy plug object too
            else:
                self._mgr.DetachPane(plug)
                self._mgr.Update()
            
            plug.handler('pane_closed')
            plug.handler('pane_unloaded')
            plug.Destroy()
            
            if nb and not nb.PageCount:
                self._mgr.DetachPane(nb) # detach notebook pane
                self._mgr.Update()
                nb.Destroy()
            
        except Exception as e:
            wx.CallAfter(wx.MessageBox,
                         "{}\n\n{}".format(e, traceback.format_exc()),
                         "Error in unloading {!r}".format(name),
                         style=wx.ICON_ERROR)
            return False
    
    def reload_plug(self, name):
        plug = self.get_plug(name)
        if plug.reloadable:
            current_session = {}
            plug.save_session(current_session)
            return self.load_plug(plug.__module__, force=1, session=current_session)
        return False
    
    def edit_plug(self, name):
        plug = self.get_plug(name)
        self.edit(self.plugins[plug.__module__])
    
    def inspect_plug(self, name):
        """Dive into the process to inspect plugs in the shell
        
        The plugins and modules are to be reloaded and lost, so we accessed as property.
        l: plugin  (cf. lm.__plug__)
        lm: module (cf. l.__module__ @sys.modules.get)
        """
        self.__class__.l = property(lambda self: self.get_plug(name))
        self.__class__.lm = property(lambda self: self.plugins.get(name))
        
        rootshell = self.shellframe.rootshell
        rootshell.clearCommand()
        rootshell.write(
            "#include plug {!r} as propperty:\n"
            "<-- self.l : {!r}\n"
            "<-- self.lm : {!r}\n".format(name, self.l, self.lm))
        rootshell.prompt()
        
        shell = rootshell.clone(self.l)
        shell.SetFocus()
        
        @shell.handler.bind("shell_activated")
        def init(shell):
            shell.target = self.l or self # reset when unloaded
        init(shell)
        self.shellframe.Show()
    
    def OnLoadPlugins(self, evt):
        with wx.FileDialog(self, "Load a plugin file",
            wildcard="Python file (*.py)|*.py",
            style=wx.FD_OPEN|wx.FD_MULTIPLE|wx.FD_FILE_MUST_EXIST) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                for path in dlg.Paths:
                    self.load_plug(path)
    
    def Quit(self, evt):
        """Stop all Layer.thread"""
        for name in self.plugins:
            plug = self.get_plug(name)
            if plug.thread and plug.thread.is_active:
                plug.thread._Thread__keepGoing = 0 # is_active=False 直接切り替える
                plug.thread.Stop() # すぐに止まるわけではない
    
    ## --------------------------------
    ## load/save index file
    ## --------------------------------
    
    def import_index(self, f=None, view=None):
        """Load frames :ref to the Index file
        """
        if view not in self.graphic_windows:
            view = self.selected_view
        
        if not f:
            with wx.FileDialog(self, "Select path to import",
                defaultFile=self.ATTRIBUTESFILE,
                wildcard="Index (*.results)|*.results",
                style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                f = dlg.Path
        
        res, mis = self.read_attributes(f)
        
        paths = [attr['pathname'] for attr in res.values()]
        frames = self.load_buffer(paths, view)
        if frames:
            for frame in frames:
                frame.update_attributes(res.get(frame.name))
        
        n = len(frames)
        self.statusbar(
            "{} frames were imported, "
            "{} files were skipped, "
            "{} files are missing.".format(n, len(res)-n, len(mis)))
        return frames
    
    def export_index(self, f=None, frames=None):
        """Save frames :ref to the Index file
        """
        if not frames:
            frames = self.selected_view.all_frames
            if not frames:
                return
        
        if not f:
            ls = filter(None, (x.pathname for x in frames))
            with wx.FileDialog(self, "Select path to export",
                defaultDir=os.path.dirname(next(ls, '')),
                defaultFile=self.ATTRIBUTESFILE,
                wildcard="Index (*.results)|*.results",
                style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                f = dlg.Path
        
        savedir = os.path.dirname(f)
        for frame in frames:
            try:
                path = os.path.join(savedir, frame.name)
                if not os.path.exists(path):
                    if not path.endswith('.tif'):
                        path += '.tif'
                    self.write_buffer(path, frame.buffer)
            except (PermissionError, OSError) as e:
                print("- Failed to save {!r}".format(path))
                print("  {!r}".format((e)))
                pass
        
        res, mis = self.write_attributes(f, frames)
        n = len(frames)
        self.statusbar(
            "{} frames were exported, "
            "{} files were skipped, "
            "{} files are missing.".format(n, len(res)-n, len(mis)))
        return frames
    
    ## --------------------------------
    ## load/save frames and attributes 
    ## --------------------------------
    ATTRIBUTESFILE = "index.results"
    
    @classmethod
    def read_attributes(self, f):
        """Read attributes file"""
        try:
            res = OrderedDict()
            mis = OrderedDict()
            savedir = os.path.dirname(f)
            
            with codecs.open(f, encoding='utf-8') as i:
                ## evaluation of attributes:tuple in locals
                from numpy import nan, inf
                import datetime
                res.update(eval(i.read()))
            
            for name, attr in tuple(res.items()):
                path = os.path.join(savedir, name)
                if not os.path.exists(path): # check & pop missing files
                    res.pop(name)
                    mis.update({name:attr})
                else:
                    attr.update(pathname=path)
        except FileNotFoundError:
            pass
        except Exception as e:
            print("- Failed to read attributes: {}".format(e))
            wx.MessageBox(str(e), style=wx.ICON_ERROR)
        finally:
            return res, mis # finally raises no exception
    
    @classmethod
    def write_attributes(self, f, frames):
        """Write attributes file"""
        try:
            res, mis = self.read_attributes(f)
            new = OrderedDict((x.name, x.attributes) for x in frames)
            
            ## res order may differ from that of given new frames.
            ## OrderedDict does not change the order even when updated,
            ## so we take a few steps to update results to be exported.
            
            res.update(new) # res updates to new info,
            new.update(res) # copy res back keeping new order.
            
            with codecs.open(f, 'w', encoding='utf-8') as o:
                pprint(tuple(new.items()), stream=o) # save all attributes
            
        except Exception as e:
            print("- Failed to write attributes: {}".format(e))
            wx.MessageBox(str(e), style=wx.ICON_ERROR)
        finally:
            return new, mis # finally raises no exception
    
    def load_frame(self, paths=None, view=None):
        """Load frame(s) from paths to the view window
        
        Load buffer and the attributes of the frame.
        If the file names duplicate, the latter takes priority.
        """
        frames = self.load_buffer(paths, view)
        if frames:
            ls = [os.path.dirname(x.pathname) for x in frames]
            savedirs = sorted(set(ls), key=ls.index) # keep order but no duplication
            results = {}
            for savedir in savedirs:
                f = os.path.join(savedir, self.ATTRIBUTESFILE)
                res, mis = self.read_attributes(f)
                results.update(res)
            for frame in frames:
                frame.update_attributes(results.get(frame.name))
        return frames
    
    def save_frame(self, path=None, frame=None):
        """Save frame to the path
        
        Save buffer and the attributes of the frame.
        """
        frame = self.save_buffer(path, frame)
        if frame:
            savedir = os.path.dirname(frame.pathname)
            f = os.path.join(savedir, self.ATTRIBUTESFILE)
            res, mis = self.write_attributes(f, [frame])
        return frame
    
    ## --------------------------------
    ## load/save images
    ## --------------------------------
    wildcards = [
        "TIF file (*.tif)|*.tif",
        "BMP file (*.bmp)|*.bmp",
         "ALL files (*.*)|*.*",
    ]
    
    @staticmethod
    def read_buffer(path):
        """Read buffer from `path file (to be overridden)"""
        if sys.version_info < (3,0):
            path = path.encode('shift-jis') # using Windows file encoding
        
        buf = Image.open(path)
        info = {}
        if isinstance(buf, TiffImageFile): # tiff はそのまま返して後処理に回す
            return buf, info
        
        if buf.mode[:3] == 'RGB':  # 今のところカラー画像には対応する気はない▼
            buf = buf.convert('L') # ここでグレースケールに変換する
        
        ## return np.asarray(buf), info # ref
        return np.array(buf), info # copy
    
    @staticmethod
    def write_buffer(path, buf):
        """Write buffer to `path file (to be overridden)"""
        try:
            img = Image.fromarray(buf)
            img.save(path) # PIL saves as L,I,F,RGB.
        except PermissionError:
            raise
        except OSError: # e.g., cannot write mode L; 16 as BMP
            os.remove(path)
            raise
    
    def load_buffer(self, paths=None, view=None):
        """Load buffers from paths to the view window
        
        If no view given, the currently selected view is chosen.
        """
        if view not in self.graphic_windows:
            view = self.selected_view
        
        if isinstance(paths, string_types): # for single frame:backward compatibility
            paths = [paths]
        
        if paths is None:
            with wx.FileDialog(self, "Open image files",
                wildcard='|'.join(self.wildcards),
                style=wx.FD_OPEN|wx.FD_MULTIPLE|wx.FD_FILE_MUST_EXIST) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                paths = dlg.Paths
        try:
            frames = []
            frame = None
            for i, path in enumerate(paths):
                f = os.path.basename(path)
                self.statusbar("Loading {!r} ({} of {})...".format(f, i+1, len(paths)))
                try:
                    buf, info = self.read_buffer(path)
                    
                except Image.UnidentifiedImageError:
                    retvals = self.handler('unknown_format', path)
                    if retvals and any(retvals):
                        continue
                    raise # no contexts or handlers
                
                frame = view.load(buf, f, show=0, # do not show while loading
                                    pathname=path, **info)
                frames.append(frame)
                
                if isinstance(buf, TiffImageFile) and buf.n_frames > 1: # multi-page tiff
                    n = buf.n_frames
                    dg = int(np.log10(n)) + 1
                    fmt = "{{:0>{}}}-{}".format(dg, f) # zero padding for numerical sort
                    for j in range(1,n):
                        self.statusbar("Loading {!r} [{} of {} pages]...".format(f, j+1, n))
                        buf.seek(j)
                        frame = view.load(buf, name=fmt.format(j), show=0)
            
            self.statusbar("\b done.")
            view.select(frame)
            return frames
        
        except Exception as e:
            print("-", self.statusbar("\b failed."))
            wx.MessageBox(str(e), style=wx.ICON_ERROR)
        
        view.select(frame)
        return frames
    
    def save_buffer(self, path=None, frame=None):
        """Save a buffer of the frame to the path
        
        If no view given, the currently selected view is chosen.
        """
        if not frame:
            frame = self.selected_view.frame
            if not frame:
                return
        
        if not path:
            name = re.sub("[\\/:*?\"<>|]", '_', frame.name)
            with wx.FileDialog(self, "Save buffer as",
                defaultFile=name,
                wildcard='|'.join(self.wildcards),
                style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                path = dlg.Path
        try:
            name = os.path.basename(path)
            self.statusbar("Saving {!r}...".format(name))
            
            self.write_buffer(path, frame.buffer)
            frame.name = name
            frame.pathname = path
            
            self.statusbar("\b done.")
            return frame
        
        except Exception as e:
            print("-", self.statusbar("\b failed."))
            wx.MessageBox(str(e), style=wx.ICON_ERROR)
    
    def save_buffers_as_tiffs(self, path=None, frames=None):
        """Export buffers to the path as multi-page tiff"""
        if not frames:
            frames = self.selected_view.all_frames
            if not frames:
                return
        
        if not path:
            with wx.FileDialog(self, "Save frames as stack-tiff",
                defaultFile="Stack-image",
                wildcard="TIF file (*.tif)|*.tif",
                style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                path = dlg.Path
        try:
            name = os.path.basename(path)
            self.statusbar("Saving {!r}...".format(name))
            busy = wx.BusyInfo("One moment please, now saving {!r}...".format(name))
            
            stack = [Image.fromarray(x.buffer.astype(int)) for x in frames]
            stack[0].save(path,
                    save_all=True,
                    compression="tiff_deflate", # cf. tiff_lzw
                    append_images=stack[1:])
            
            self.statusbar("\b done.")
            return True
        
        except Exception as e:
            print("-", self.statusbar("\b failed."))
            wx.MessageBox(str(e), style=wx.ICON_ERROR)
    
    ## --------------------------------
    ## open/close session
    ## --------------------------------
    session_file = None
    
    def load_session(self, f=None, flush=True):
        """Load session from file"""
        if not f:
            with wx.FileDialog(self, 'Load session',
                wildcard="Session file (*.jssn)|*.jssn",
                style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return False
                f = dlg.Path
        
        if flush:
            del self.graph[:]
            del self.output[:]
            for name in list(self.plugins): # OrderedDict mutated during iteration
                self.unload_plug(name)
        
        self.session_file = os.path.abspath(f)
        self.statusbar("Loading session from {!r}...".format(f))
        
        with open(f) as i:
            ## evaluation of session in the shell
            self.shellframe.rootshell.locals.update(
                nan = np.nan,
                inf = np.inf,
            )
            self.shellframe.rootshell.Execute(i.read())
            self.menubar.reset()
            dirname = os.path.dirname(f)
            if dirname:
                os.chdir(dirname)
        
        self.statusbar("\b done.")
        return True
    
    def save_session_as(self):
        """Save session as (new file)"""
        with wx.FileDialog(self, "Save session as",
            defaultFile=self.session_file or '',
            wildcard="Session file (*.jssn)|*.jssn",
            style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                return self.save_session(dlg.Path)
            return False
    
    def save_session(self, f=None):
        """Save session to file"""
        f = f or self.session_file
        if not f:
            return self.save_session_as()
        
        self.session_file = os.path.abspath(f)
        self.statusbar("Saving session to {!r}...".format(f))
        
        options = np.get_printoptions()
        np.set_printoptions(linewidth=256, threshold=np.inf) # inf:all elements
        
        with open(f, 'w') as o:
            o.write('\n'.join((
                "#! wxpyJemacs session file (This file is generated automatically)",
                "self.SetSize({})".format(self.Size),
                "self.shellframe.SetSize({})".format(self.shellframe.Size),
                "self.shellframe.Show({})".format(self.shellframe.IsShown()),
                ""
            )))
            for name in ('output', 'histogram'): # save built-in window layout
                pane = self.get_pane(name)
                o.write("self.update_pane('{name}', show={show}, dock={dock}, "
                        "layer={layer}, pos={pos}, row={row}, prop={prop}, "
                        "floating_pos={fpos}, floating_size={fsize})\n".format(
                    name = name,
                    show = pane.IsShown(),
                    dock = pane.IsDocked() and pane.dock_direction,
                   layer = pane.dock_layer,
                     pos = pane.dock_pos,
                     row = pane.dock_row,
                    prop = pane.dock_proportion,
                    fpos = pane.floating_pos,
                   fsize = pane.floating_size,
                ))
            for name, module in self.plugins.items(): # save plugins layout
                pane = self.get_pane(name)
                plug = self.get_plug(name)
                path = os.path.abspath(module.__file__).replace('\\','/')
                if path.endswith('.pyc'): # PY2 may return '*.pyc'
                    path = path[:-1]
                if path.endswith("/__init__.py"): # when root:module is a package
                    path = path[:-12]
                current_session = {}
                plug.save_session(current_session)
                o.write("self.load_plug('{name}', show={show}, dock={dock}, "
                        "layer={layer}, pos={pos}, row={row}, prop={prop}, "
                        "floating_pos={fpos}, floating_size={fsize}, "
                        "force=0, session={session!r})\n".format(
                    name = path,
                    show = pane.IsShown(),
                    dock = pane.IsDocked() and pane.dock_direction,
                   layer = pane.dock_layer,
                     pos = pane.dock_pos,
                     row = pane.dock_row,
                    prop = pane.dock_proportion,
                    fpos = pane.floating_pos,
                   fsize = pane.floating_size,
                 session = current_session or None,
                ))
            paths = [x.pathname for x in self.graph.all_frames if x.pathname]
            if paths:
                o.write("self.load_frame(\n{})\n".format(pformat(paths, width=160)))
            
            ## set-global-unit
            o.write("self.graph.unit = {}\n".format(self.graph.unit))
            o.write("self.output.unit = {}\n".format(self.output.unit))
            
            ## set-local-unit
            for frame in self.graph.all_frames:
                if frame.localunit and frame.pathname: # localunit:need-buffer-save-?
                    o.write("self.graph.get_frame({!r}).unit = {}\n".format(
                            frame.name, frame.localunit))
            ## select-page
            if self.graph.frame:
                o.write("self.graph.select({!r})\n".format(self.graph.frame.name))
            o.write('# end of session\n')
            
        np.set_printoptions(**options)
        self.statusbar("\b done.")
        return True


if __name__ == '__main__':
    print("Python {}".format(sys.version))
    print("wxPython {}".format(wx.version()))
    print("matplotlib {}".format(matplotlib.__version__))
    
    app = wx.App()
    frm = Frame(None)
    
    frm.handler.debug = 4
    frm.graph.handler.debug = 0
    frm.output.handler.debug = 0
    
    frm.load_buffer(u"demo/sample.bmp")
    frm.load_buffer(u"demo/sample2.tif")
    frm.graph.load(np.random.randn(1024,1024))
    
    ## 次の二つは別モジュール
    ## frm.load_plug('demo.template.py', show=1, force=1)
    frm.load_plug('demo/template.py', show=1, force=1)
    
    ## frm.load_plug('C:/usr/home/workspace/tem13/gdk/plugins/viewframe.py')
    ## frm.load_plug('C:/usr/home/workspace/tem13/gdk/plugins/lineprofile.py')
    ## frm.load_plug('C:/usr/home/workspace/tem13/gdk/templates/template.py', show=1)
    ## frm.load_plug('C:/usr/home/workspace/tem13/gdk/templates/template2.py', show=1)
    
    frm.Show()
    app.MainLoop()
