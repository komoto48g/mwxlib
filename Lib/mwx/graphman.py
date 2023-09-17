#! python3
# -*- coding: utf-8 -*-
"""Graph manager

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
from importlib import reload, import_module
from pprint import pprint, pformat
from functools import wraps
from bdb import BdbQuit
import subprocess
import threading
import traceback
import warnings
import inspect
import sys
import os
import platform
import re
import wx
from wx import aui

from matplotlib import cm
from matplotlib import colors
## from matplotlib import pyplot as plt
import numpy as np
from PIL import Image
from PIL.TiffImagePlugin import TiffImageFile

from . import framework as mwx
from .utilus import funcall as _F
from .controls import ControlPanel, Icon
from .framework import CtrlInterface, AuiNotebook
from .matplot2g import GraphPlot
from .matplot2lg import Histogram


class Thread(object):
    """Thread for graphman.Layer
    
    The worker:thread runs the given target:f of owner:object.
    
    Attributes:
        target  : A target method of the Layer.
        result  : A variable that retains the last retval of f.
        worker  : Reference of the worker thread.
        owner   : Reference of the handler owner (was typ. f.__self__).
                  If None, the thread_event is handled by its own handler.
        event   : A common event flag to interrupt the process.
    
    There are two flags to check the thread status:
    
     - active   : A flag of being kept going.
                  Check this to see the worker is running and intended being kept going.
     - running  : A flag of being running now.
                  Watch this to verify the worker is alive after it has been inactivated.
    
    The event object can be used to suspend/resume the thread:
    
        1. event.clear -> clear flag:False so that the thread suspends when wait is called.
        2. event.wait -> wait until the chequer flag to be set True.
        3. event.set -> set flag:True to resume the thread.
        
        The event.wait blocks until the internal flag is True when it is False,
        and returns immediately when it is True.
    """
    class ThreadInterrupt(Exception):
        pass
    
    @property
    def running(self):
        if self.worker:
            return self.worker.is_alive()
        return False
    
    def __init__(self, owner=None):
        self.owner = owner
        self.worker = None
        self.target = None
        self.result = None
        self.active = 0
        self.event = threading.Event()
        self.event.set()
        try:
            self.handler = self.owner.handler
        except AttributeError:
            self.handler = mwx.FSM({ # DNA<Thread>
                None : {
                 'thread_begin' : [ None ], # begin processing
                   'thread_end' : [ None ], # end processing
                  'thread_quit' : [ None ], # terminated by user
                 'thread_error' : [ None ], # failed in error
                      '*:enter' : [ None ], # enter module:co_name
                       '*:exit' : [ None ], # exit module:co_name
                      '*:error' : [ None ], # error
                },
            })
    
    def __del__(self):
        if self.active:
            self.Stop()
    
    def __enter__(self):
        frame = inspect.currentframe().f_back
        module = inspect.getmodule(frame)
        name = frame.f_code.co_name
        
        assert self.active, "cannot enter {!r}".format(name)
        
        event = "{}:{}:enter".format(module.__name__, name)
        self.handler(event, self)
    
    def __exit__(self, t, v, tb):
        frame = inspect.currentframe().f_back
        module = inspect.getmodule(frame)
        name = frame.f_code.co_name
        if t:
            event = "{}:{}:error".format(module.__name__, name)
            self.handler(event, self)
        
        event = "{}:{}:exit".format(module.__name__, name)
        self.handler(event, self)
    
    def __call__(self, f, *args, **kwargs):
        """Decorator of thread starter function."""
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
            except BdbQuit:
                pass
            except (KeyboardInterrupt, Thread.ThreadInterrupt) as e:
                print("- Thread:execution stopped: {}".format(e))
            except AssertionError as e:
                print("- Thread:execution failed: {}".format(e))
            except Exception as e:
                traceback.print_exc()
                print("- Thread:exception: {}".format(e))
                self.handler('thread_error', self)
            finally:
                self.active = 0
                self.handler('thread_end', self)
        
        if self.running:
            wx.MessageBox("The thread is running (Press [C-g] to quit).",
                          style=wx.ICON_WARNING)
            return
        
        self.target = f
        self.result = None
        self.active = 1
        self.worker = threading.Thread(target=_f,
                                args=args, kwargs=kwargs, daemon=True)
        self.worker.start()
        self.event.set()
    
    def Stop(self):
        def _Stop():
            self.active = 0
            if self.running:
                try:
                    busy = wx.BusyInfo("One moment please, "
                                       "waiting for threads to die...")
                    self.handler('thread_quit', self)
                    self.worker.join(1)
                finally:
                    del busy
        wx.CallAfter(_Stop)


def _isLayer(obj):
    """Check if obj is an instance of Layer."""
    ## If this script file is executed i.e., `this` module is __main__,
    ## this.Layer <class '__main__.Layer'> is not <mwx.graphman.Layer>.
    ## So, we check it in two ways:
    return isinstance(obj, LayerInterface)\
        or isinstance(obj, CtrlInterface) and hasattr(obj, 'category')


class LayerInterface(CtrlInterface):
    """Graphman.Layer interface mixin
    
    The layer properties can be switched by the following classvars::
    
        menukey     : menu item key:str in parent menubar
        category    : title of notebook holder, otherwise None for single pane
        caption     : flag to set the pane caption to be visible
                      a string can also be specified (default is __module__)
        dockable    : flag to set the pane to be dockable
                      type: bool or dock:int (1:t, 2:r, 3:b, 4:l, 5:c)
        reloadable  : flag to set the Layer to be reloadable
        unloadable  : flag to set the Layer to be unloadable
    
    Note:
        parent <Frame> is not always equal to Parent when floating.
        Parent type can be <Frame>, <AuiFloatingFrame>, or <AuiNotebook>.
    """
    MENU = "Plugins" # default menu for Plugins
    menukey = "Plugins/"
    caption = True
    category = None
    dockable = True
    editable = True # to be deprecated
    reloadable = True
    unloadable = True
    
    graph = property(lambda self: self.parent.graph)
    output = property(lambda self: self.parent.output)
    histogram = property(lambda self: self.parent.histogram)
    selected_view = property(lambda self: self.parent.selected_view)
    
    message = property(lambda self: self.parent.message)
    
    ## thread_type = Thread
    thread = None
    
    ## layout helper function
    pack = mwx.pack
    
    ## funcall = interactive_call
    funcall = staticmethod(_F)
    
    ## for debug (internal use only)
    pane = property(lambda self: self.parent.get_pane(self))
    
    @property
    def Arts(self):
        """List of arts <matplotlib.artist.Artist>."""
        return self.__artists
    
    @Arts.setter
    def Arts(self, arts):
        for art in self.__artists[:]:
            if art not in arts:
                art.remove()
                self.__artists.remove(art)
        self.__artists = arts
    
    @Arts.deleter
    def Arts(self):
        for art in self.__artists:
            art.remove()
        self.__artists = []
    
    def attach_artists(self, axes, *artists):
        """Attach artists (e.g., patches) to the given axes.
        If axes is None, they will be removed from the axes.
        """
        if not artists:
            artists = self.Arts[:]
        if axes:
            for art in artists:
                if art.axes and art.axes is not axes:
                    art.remove()
                    art._transformSet = False
                axes.add_artist(art)
                if art not in self.Arts:
                    self.Arts.append(art)
        else:
            for art in artists:
                if art.axes:
                    art.remove()
                    art._transformSet = False
                self.Arts.remove(art)
    
    def __init__(self, parent, session=None):
        CtrlInterface.__init__(self)
        
        self.parent = parent
        self.__artists = []
        self.parameters = None # => reset
        
        def copy_params(**kwargs):
            if self.parameters:
                return self.copy_to_clipboard(**kwargs)
        
        def paste_params(**kwargs):
            if self.parameters:
                return self.paste_from_clipboard(**kwargs)
        
        def reset_params(**kwargs):
            self.Draw(None)
            if self.parameters:
                return self.reset_params(**kwargs)
        
        self.handler.append({ # DNA<Layer>
            None : {
                 'thread_begin' : [ None ], # begin processing
                   'thread_end' : [ None ], # end processing
                  'thread_quit' : [ None ], # terminated by user
                 'thread_error' : [ None ], # failed in error
                   'page_shown' : [ None, _F(self.Draw, True)  ],
                  'page_closed' : [ None, _F(self.Draw, False) ],
                  'page_hidden' : [ None, _F(self.Draw, False) ],
            },
            0 : {
                  'C-c pressed' : (0, _F(copy_params)),
                'C-S-c pressed' : (0, _F(copy_params, checked_only=1)),
                  'C-v pressed' : (0, _F(paste_params)),
                'C-S-v pressed' : (0, _F(paste_params, checked_only=1)),
                  'C-n pressed' : (0, _F(reset_params)),
                'C-S-n pressed' : (0, _F(reset_params, checked_only=1)),
            },
        })
        self.menu = [
            (wx.ID_COPY, "&Copy params\t(C-c)", "Copy params",
                lambda v: copy_params(checked_only=wx.GetKeyState(wx.WXK_SHIFT)),
                lambda v: v.Enable(bool(self.parameters))),
                
            (wx.ID_PASTE, "&Paste params\t(C-v)", "Read params",
                lambda v: paste_params(checked_only=wx.GetKeyState(wx.WXK_SHIFT)),
                lambda v: v.Enable(bool(self.parameters))),
            (),
            (wx.ID_RESET, "&Reset params\t(C-n)", "Reset params", Icon('-'),
                lambda v: reset_params(checked_only=wx.GetKeyState(wx.WXK_SHIFT)),
                lambda v: v.Enable(bool(self.parameters))),
            (),
            (wx.ID_EDIT, "&Edit module", "Edit module src", Icon('pen'),
                lambda v: self.parent.edit_plug(self.__module__),
                lambda v: v.Enable(self.editable)),
                
            (mwx.ID_(201), "&Reload module", "Reload module", Icon('load'),
                lambda v: self.parent.reload_plug(self.__module__),
                lambda v: v.Enable(self.reloadable
                            and not (self.thread and self.thread.active))),
                
            (mwx.ID_(202), "&Unload module", "Unload module", Icon('delete'),
                lambda v: self.parent.unload_plug(self.__module__),
                lambda v: v.Enable(self.unloadable
                            and not (self.thread and self.thread.active))),
            (),
            (mwx.ID_(203), "&Dive into {!r}".format(self.__module__), "dive", Icon('core'),
                lambda v: self.parent.inspect_plug(self.__module__)),
        ]
        self.Bind(wx.EVT_CONTEXT_MENU,
                  lambda v: mwx.Menu.Popup(self, self.menu))
        
        def destroy(v):
            if v.EventObject is self:
                if self.thread and self.thread.active:
                    self.thread.active = 0
                    self.thread.Stop()
                del self.Arts
            v.Skip()
        self.Bind(wx.EVT_WINDOW_DESTROY, destroy)
        
        def on_show(v):
            if v.IsShown():
                self.handler('page_shown', self)
            elif self and isinstance(self.Parent, aui.AuiNotebook):
                self.handler('page_hidden', self) # -> notebook
            v.Skip()
        self.Bind(wx.EVT_SHOW, on_show)
        
        try:
            self.Init()
            if session:
                self.load_session(session)
        except Exception as e:
            traceback.print_exc()
            if parent:
                bmp = wx.StaticBitmap(self, bitmap=Icon('!!!'))
                txt = wx.StaticText(self, label="Exception")
                txt.SetToolTip(repr(e))
                self.layout((bmp, txt), row=2)
    
    def Init(self):
        """Initialize me safely (to be overridden)."""
        pass
    
    def load_session(self, session):
        """Restore settings from a session file (to be overridden)."""
        if 'params' in session:
            self.parameters = session['params']
    
    def save_session(self, session):
        """Save settings in a session file (to be overridden)."""
        if self.parameters:
            session['params'] = self.parameters
    
    Shown = property(
        lambda self: self.IsShown(),
        lambda self,v: self.Show(v))
    
    def IsShown(self):
        return self.parent.get_pane(self).IsShown()
    
    def Show(self, show=True):
        """Show associated pane (override) window."""
        ## Note: This might be called from a thread.
        wx.CallAfter(self.parent.show_pane, self, show)
    
    Drawn = property(
        lambda self: self.IsDrawn(),
        lambda self,v: self.Draw(v))
    
    def IsDrawn(self):
        return any(art.get_visible() for art in self.Arts)
    
    def Draw(self, show=None):
        """Draw artists.
        If show is None:default, draw only when the pane is visible.
        """
        if not self.Arts:
            return
        if show is None:
            show = self.IsShown()
        try:
            ## Arts may be belonging to graph, output, and any other windows.
            for art in self.Arts:
                art.set_visible(show)
            ## EVT_SHOW [page_hidden] is called when the page is destroyed.
            ## To avoid RuntimeError, check if canvas object has been deleted.
            canvas = art.axes.figure.canvas
            if canvas:
                canvas.draw_idle()
        except Exception as e:
            print("- Failed to draw Arts of {!r}: {}".format(self.__module__, e))
            del self.Arts


class Layer(ControlPanel, LayerInterface):
    """Graphman.Layer
    """
    def __init__(self, parent, session=None, **kwargs):
        ControlPanel.__init__(self, parent, **kwargs)
        LayerInterface.__init__(self, parent, session)
    
    ## Explicit (override) precedence
    message = LayerInterface.message
    IsShown = LayerInterface.IsShown
    Shown = LayerInterface.Shown
    Show = LayerInterface.Show


class Graph(GraphPlot):
    """GraphPlot (override) to better make use for graph manager
    
    Attributes:
        parent : Parent window (usually mainframe)
        loader : mainframe
    """
    def __init__(self, parent, loader=None, **kwargs):
        GraphPlot.__init__(self, parent, **kwargs)
        
        self.parent = parent
        self.loader = loader or parent
        
        self.handler.append({ # DNA<Graph>
            None : {
                    'focus_set' : [ None, _F(self.loader.select_view, view=self) ],
                   'page_shown' : [ None, ],
                  'page_closed' : [ None, ],
                  'frame_shown' : [ None, _F(self.update_infobar) ],
                  'S-a pressed' : [ None, _F(self.toggle_infobar) ],
                   'f5 pressed' : [ None, _F(self.refresh) ],
            },
        })
        ## ドロップターゲットを許可する
        self.SetDropTarget(MyFileDropLoader(self, self.loader))
    
    def refresh(self):
        if self.frame:
            self.frame.update_buffer()
            self.draw()
    
    def toggle_infobar(self):
        """Toggle infobar (frame.annotation)."""
        if self.infobar.IsShown():
            self.infobar.Dismiss()
        elif self.frame:
            self.infobar.ShowMessage(str(self.frame.annotation))
    
    def update_infobar(self, frame):
        """Show infobar (frame.annotation)."""
        if self.infobar.IsShown():
            self.infobar.ShowMessage(str(frame.annotation))
    
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
        self.selected.set_visible(v)
        self.marked.set_visible(v)
        self.rected.set_visible(v)
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
    
    Args:
        loader : mainframe
        target : target window to drop in, e.g. frame, graph, pane, etc.
    """
    def __init__(self, target, loader):
        wx.FileDropTarget.__init__(self)
        
        self.target = target
        self.loader = loader
    
    def OnDropFiles(self, x, y, filenames):
        pos = self.target.ScreenPosition + (x,y)
        paths = []
        for f in filenames:
            name, ext = os.path.splitext(f)
            if ext == '.py' or os.path.isdir(f):
                self.loader.load_plug(f, show=1, floating_pos=pos,
                                      force=wx.GetKeyState(wx.WXK_ALT))
            elif ext == '.jssn':
                self.loader.load_session(f)
            elif ext == '.index':
                self.loader.import_index(f, self.target)
            else:
                paths.append(f) # image file just stacks to be loaded
        if paths:
            self.loader.load_frame(paths, self.target)
        return True


class Frame(mwx.Frame):
    """Graph and Plug manager frame
    
    Interfaces:
        1. pane window interface
        2. plugins interface
        3. load/save images
        4. open/close session
    """
    graph = property(lambda self: self.__graph)
    output = property(lambda self: self.__output)
    histogram = property(lambda self: self.__histgrm)
    
    selected_view = property(lambda self: self.__view)
    
    def select_view(self, view):
        self.__view = view
        self.set_title(view.frame)
    
    @property
    def graphic_windows(self):
        """Graphic windows list.
        [0] graph [1] output [2:] others(user-defined)
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
        
        self.__plugins = {} # modules in the order of load/save
        
        self.__graph = Graph(self, log=self.statusbar, margin=None, size=(600,600))
        self.__output = Graph(self, log=self.statusbar, margin=None, size=(600,600))
        
        self.__histgrm = Histogram(self, log=self.statusbar, margin=None, size=(130,65))
        self.__histgrm.attach(self.graph)
        self.__histgrm.attach(self.output)
        
        self.__graphic_windows = [
            self.__graph,
            self.__output,
        ]
        self.select_view(self.graph)
        
        ## Set winow.Name for inspection.
        self.graph.Name = "graph"
        self.output.Name = "output"
        self.histogram.Name = "histogram"
        
        self._mgr.AddPane(self.graph,
                          aui.AuiPaneInfo().CenterPane().CloseButton(1)
                             .Name("graph").Caption("graph").CaptionVisible(1))
        
        size = (200, 200)
        self._mgr.AddPane(self.output,
                          aui.AuiPaneInfo().Name("output").Caption("output")
                             .FloatingSize(size).MinSize(size).Right().Show(0))
        
        size = self.histogram.GetSize()
        self._mgr.AddPane(self.histogram,
                          aui.AuiPaneInfo().Name("histogram").Caption("histogram")
                             .FloatingSize(size).MinSize(size).Left().Show(0))
        
        self._mgr.Update()
        
        self.menubar["File"][0:0] = [
            (wx.ID_OPEN, "&Open\tCtrl-o", "Open file", Icon('book'),
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
                
            (wx.ID_SAVEAS, "&Save as TIFFs", "Save buffers as a statck-tiff", Icon('saveall'),
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
                    
                (mwx.ID_(16), "&Save session", "Save session file",
                    lambda v: self.save_session()),
                    
                (mwx.ID_(17), "&Save session as", "Save session file as",
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
                
            (mwx.ID_(21), "Toggle &Markers", "Show/Hide markups", wx.ITEM_CHECK, Icon('+'),
                lambda v: self.__view.set_markups_visible(v.IsChecked()),
                lambda v: v.Check(self.__view.get_markups_visible())),
                
            (mwx.ID_(22), "&Remove Markers", "Remove markups", Icon('-'),
                lambda v: self.__view.remove_markups()),
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
        
        def _cmenu(i, name):
            return (mwx.ID_(30 + i), "&" + name, name, wx.ITEM_CHECK,
                lambda v: self.__view.set_cmap(name),
                lambda v: v.Check(self.__view.get_cmap() == name
                               or self.__view.get_cmap() == name+"_r"),
            )
        colours = [c for c in dir(cm) if c[-2:] != "_r"
                    and isinstance(getattr(cm, c), colors.LinearSegmentedColormap)]
        
        self.menubar["Edit"] += [
            (),
            ## (mwx.ID_(26), "Default Color", "gray", wx.ITEM_CHECK,
            ##     lambda v: self.__view.set_cmap('gray'),
            ##     lambda v: v.Check(self.__view.get_cmap()[:4] == "gray")),
            ##     
            ("Standard Colors",
                [_cmenu(i, c) for i, c in enumerate(colours) if c.islower()]),
                
            ("Other Colors",
                [_cmenu(i, c) for i, c in enumerate(colours) if not c.islower()]),
        ]
        
        self.menubar[Layer.MENU] = [
            (mwx.ID_(100), "&Load Plugs", "Load plugins", Icon('plugin'),
                self.OnLoadPlugins),
            
            (mwx.ID_(101), "&Quit Plugs\tCtrl-g", "Stop all plugin threads", Icon('exit'),
                self.Quit),
            (),
        ]
        self.menubar.reset()
        
        def show_graph(frame):
            wx.CallAfter(self.show_pane, frame.parent) # Show graph / output
        
        self.graph.handler.append({ # DNA<Graph:Frame>
            None : {
                  'frame_shown' : [ None, self.set_title ],
                 'frame_loaded' : [ None, show_graph ],
               'frame_modified' : [ None, show_graph ],
               'frame_selected' : [ None, self.set_title ],
                  'canvas_draw' : [ None, lambda v: self.sync(self.graph, self.output) ],
            },
        })
        self.output.handler.append({ # DNA<Graph:Frame>
            None : {
                  'frame_shown' : [ None, self.set_title ],
                 'frame_loaded' : [ None, show_graph ],
               'frame_modified' : [ None, show_graph ],
               'frame_selected' : [ None, self.set_title ],
                  'canvas_draw' : [ None, lambda v: self.sync(self.output, self.graph) ],
            },
        })
        
        ## Add main-menu to context-menu
        self.graph.menu += self.menubar["Edit"][2:8]
        self.output.menu += self.menubar["Edit"][2:8]
        
        self._mgr.Bind(aui.EVT_AUI_PANE_CLOSE, self.OnPaneClose)
        
        self.Bind(wx.EVT_ACTIVATE, self.OnActivate)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        
        ## Custom Key Bindings
        self.define_key('C-g', self.Quit)
        
        ## Accepts DnD
        self.SetDropTarget(MyFileDropLoader(self, self))
    
    sync_switch = True
    
    def sync(self, a, b):
        """Synchronize b to a."""
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
            name,_ = os.path.splitext(f.__file__)
            f = name + '.py'
        cmd = '{} "{}"'.format(self.Editor, f)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            subprocess.Popen(cmd)
            self.statusbar(cmd)
    
    def set_title(self, frame):
        ssn = os.path.basename(self.session_file or '--')
        ssn,_ = os.path.splitext(ssn)
        name = (frame.pathname or frame.name) if frame else ''
        self.SetTitle("{}@{} - [{}] {}".format(self.Name, platform.node(), ssn, name))
    
    def OnActivate(self, evt): #<wx._core.ActivateEvent>
        if self and evt.Active:
            self.set_title(self.selected_view.frame)
    
    def OnClose(self, evt): #<wx._core.CloseEvent>
        ssn = os.path.basename(self.session_file or '--')
        with wx.MessageDialog(None,
                "Do you want to save session before closing program?",
                "{}@{} - [{}]".format(self.Name, platform.node(), ssn),
                style=wx.YES_NO|wx.CANCEL|wx.ICON_INFORMATION) as dlg:
            ret = dlg.ShowModal()
            if ret == wx.ID_YES:
                self.save_session()
            elif ret == wx.ID_CANCEL:
                evt.Veto()
                return
        for frame in self.graph.all_frames:
            if frame.pathname is None:
                if wx.MessageBox( # Confirm close.
                        "You are closing unsaved frame.\n\n"
                        "Continue closing?",
                        "Close {!r}".format(frame.name),
                        style=wx.YES_NO|wx.ICON_INFORMATION) != wx.YES:
                    self.message("The close has been canceled.")
                    evt.Veto()
                    return
                break
        evt.Skip()
    
    def Destroy(self):
        self._mgr.UnInit()
        return mwx.Frame.Destroy(self)
    
    ## --------------------------------
    ## pane window interface
    ## --------------------------------
    
    def get_pane(self, name):
        """Get the named pane or notebook pane.
        
        Args:
            name : str or plug object.
        """
        if name in self.plugins:
            plug = self.plugins[name].__plug__
            name = plug.category or name
        elif name and _isLayer(name):
            ## Also check if wrapped C/C++ object of Layer has been deleted.
            name = name.category or name
        return self._mgr.GetPane(name)
    
    def show_pane(self, name, show=True, interactive=False):
        """Show named pane or notebook pane."""
        pane = self.get_pane(name)
        if not pane.IsOk():
            return
        
        ## Set the graph and output window sizes to half & half.
        if name == "output" or name is self.output:
            w, h = self.graph.GetClientSize()
            pane.best_size = (w//2, h) # ドッキング時に再計算される
        
        ## Force Layer windows to show.
        if interactive:
            ## [M-S-menu] Reload plugin
            if wx.GetKeyState(wx.WXK_ALT) and wx.GetKeyState(wx.WXK_SHIFT):
                self.reload_plug(name)
                pane = self.get_pane(name)
                show = True
            
            ## [S-menu] Reset floating position of a stray window.
            if wx.GetKeyState(wx.WXK_SHIFT):
                pane.floating_pos = wx.GetMousePosition()
                pane.Float()
                show = True
        
        plug = self.get_plug(name) # -> None if pane.window is a Graph
        win = pane.window # -> Window (plug / notebook / Graph)
        if show:
            if isinstance(win, aui.AuiNotebook):
                j = win.GetPageIndex(plug)
                if j != win.Selection:
                    win.Selection = j # the focus is moved => [page_shown]
                else:
                    plug.handler('page_shown', plug)
            elif not pane.IsShown():
                if not plug or win.Parent is not self: # otherwise Layer.on_show
                    win.handler('page_shown', win)
        else:
            if isinstance(win, aui.AuiNotebook):
                for plug in win.all_pages: # => [page_closed] to all pages
                    plug.handler('page_closed', plug)
            elif pane.IsShown():
                win.handler('page_closed', win)
        
        ## Modify the floating position of the pane when displayed.
        ## Note: This is a known bug in wxWidgets 3.17 -- 3.20,
        ##       and will be fixed in wxPython 4.2.1.
        if wx.Display.GetFromWindow(pane.window) == -1:
            pane.floating_pos = wx.GetMousePosition()
        pane.Show(show)
        self._mgr.Update()
    
    def update_pane(self, name, show=False, **kwargs):
        """Update the layout of the pane.
        
        Note:
            This is called automatically from load_plug,
            and should not be called directly from user.
        """
        pane = self.get_pane(name)
        
        pane.dock_layer = kwargs.get('layer', 0)
        pane.dock_pos = kwargs.get('pos', 0)
        pane.dock_row = kwargs.get('row', 0)
        pane.dock_proportion = kwargs.get('prop') or pane.dock_proportion
        pane.floating_pos = kwargs.get('floating_pos') or pane.floating_pos
        pane.floating_size = kwargs.get('floating_size') or pane.floating_size
        
        plug = self.get_plug(name)
        if plug:
            dock = plug.dockable
            if not isinstance(dock, bool): # prior to kwargs
                kwargs.update(dock=dock)
            if not plug.caption:
                pane.CaptionVisible(False)       # no caption bar
                pane.Gripper(dock not in (0, 5)) # show a grip when docked
            pane.Dockable(dock)
        
        dock = kwargs.get('dock')
        pane.dock_direction = dock or 0
        if dock:
            pane.Dock()
        else:
            pane.Float()
        self.show_pane(name, show)
        self._mgr.Update()
    
    def OnPaneClose(self, evt): #<wx.aui.AuiManagerEvent>
        pane = evt.GetPane()
        win = pane.window
        if isinstance(win, aui.AuiNotebook):
            for plug in win.all_pages:
                plug.handler('page_closed', plug)
        else:
            win.handler('page_closed', win)
        pane.Show(0)
        self._mgr.Update()
        evt.Veto() # Don't skip. Just hide it.
    
    ## --------------------------------
    ## Plugin (Layer) interface
    ## --------------------------------
    plugins = property(lambda self: self.__plugins)
    
    def require(self, name):
        """Get named plug window.
        If not found, try to load it once.
        
        Note:
            When called in thread, the display of AuiPane might be broken.
            Reload this from menu with [C-M-S] key after the thread exits.
        """
        plug = self.get_plug(name)
        if not plug:
            if self.load_plug(name) is not False:
                return self.get_plug(name)
        return plug
    
    def get_plug(self, name):
        """Find the named plug window in registered plugins.
        
        Args:
            name : str or plug object.
        """
        if isinstance(name, str):
            if name.endswith(".py") or name.endswith(".pyc"):
                name,_ = os.path.splitext(os.path.basename(name))
            if name in self.plugins:
                return self.plugins[name].__plug__
        elif name and _isLayer(name):
            ## Also check if wrapped C/C++ object of Layer has been deleted.
            return name
    
    @staticmethod
    def register(cls, module=None):
        """Register dummy plug; Add module.Plugin(Layer).
        """
        if not module:
            module = inspect.getmodule(cls) # rebase module or __main__
        
        if issubclass(cls, LayerInterface):
            warnings.warn("Duplicate iniheritance of LayerInterface by {!r}."
                          .format(cls.__name__), stacklevel=2)
            cls.__module__ = module.__name__ # __main__ to module
            module.Plugin = cls
            return cls
        
        class _Plugin(cls, LayerInterface):
            def __init__(self, parent, session=None, **kwargs):
                cls.__init__(self, parent, **kwargs)
                LayerInterface.__init__(self, parent, session)
            
            ## Explicit (override) precedence
            message = LayerInterface.message
            IsShown = LayerInterface.IsShown
            Shown = LayerInterface.Shown
            Show = LayerInterface.Show
            
            ## Implicit (override) precedence
            ## cls.Init / cls.save_session / cls.load_session
        
        _Plugin.__module__ = cls.__module__ = module.__name__
        _Plugin.__name__ = cls.__name__ + str("~")
        _Plugin.__doc__ = cls.__doc__
        module.Plugin = _Plugin
        return _Plugin
    
    def load_module(self, root, force, session, **props):
        """Load module of plugin (internal use only).
        
        Note:
            This is called automatically from load_plug,
            and should not be called directly from user.
        """
        if hasattr(root, '__file__'): #<class 'module'>
            rootpath = root.__file__
        elif isinstance(root, type): #<class 'type'>
            rootpath = inspect.getsourcefile(root)
        else:
            rootpath = root
        
        assert isinstance(rootpath, str)
        
        name = os.path.basename(rootpath)
        if name.endswith(".py"):
            name,_ = os.path.splitext(name)
        
        plug = self.get_plug(name)
        if plug: # <plug:name> is already registered
            if not force:
                self.update_pane(name, **props)
                if session:
                    plug.load_session(session)
                return None
        
        ## Update the include-path to load the module correctly.
        dirname_ = os.path.dirname(rootpath)
        if os.path.isdir(dirname_):
            if dirname_ in sys.path:
                sys.path.remove(dirname_)
            sys.path.insert(0, dirname_)
        elif dirname_:
            print("- No such directory {!r}".format(dirname_))
            return False
        try:
            if name in sys.modules:
                module = reload(sys.modules[name])
            else:
                module = import_module(name)
        except Exception as e:
            ## traceback.print_exc()
            print("- Unable to load {!r}: {}".format(root, e))
            return False
        
        ## the module must have a class `Plugin`.
        if not hasattr(module, 'Plugin'):
            if isinstance(root, type):
                warnings.warn("Use dummy plug mode for debugging.", stacklevel=3)
                module.__dummy_plug__ = root
                self.register(root, module)
        else:
            if hasattr(module, '__dummy_plug__'):
                root = module.__dummy_plug__         # old class (imported)
                cls = getattr(module, root.__name__) # new class (reloaded)
                self.register(cls, module)
        return module
    
    def load_plug(self, root, show=False,
                  dock=False, layer=0, pos=0, row=0, prop=10000,
                  floating_pos=None, floating_size=None,
                  force=False, session=None, **kwargs):
        """Load plugin.
        
        Args:
            root    : Layer module, or name of the module.
                      Any wx.Window object can be specified (as dummy-plug).
                      However, do not use this mode in release versions.
            show    : the pane is shown after loaded
            force   : force loading even if it is already loaded
            session : Conditions for initializing the plug and starting session
            dock    : dock_direction (1:top, 2:right, 3:bottom, 4:left, 5:center)
            layer   : dock_layer
            pos     : dock_pos
            row     : dock_row position
            prop    : dock_proportion < 1e6 ?
            floating_pos : posision of floating window
            floating_size : size of floating window
        
        Returns:
            None if succeeded else False
        
        Note:
            The root module must have a class `Plugin` <mwx.graphman.Layer>
        """
        props = dict(show=show,
                     dock=dock, layer=layer, pos=pos, row=row, prop=prop,
                     floating_pos=floating_pos, floating_size=floating_size)
        
        module = self.load_module(root, force, session, **props)
        if not module:
            return module # None (if not force) or False (failed to import)
        
        try:
            name = module.Plugin.__module__
            title = module.Plugin.category
            
            pane = self._mgr.GetPane(title)
            
            if pane.IsOk(): # <pane:title> is already registered
                nb = pane.window
                if not isinstance(nb, aui.AuiNotebook):
                    raise NameError("Notebook name must not be the same as any other plugins")
            
            pane = self.get_pane(name)
            
            if pane.IsOk(): # <pane:name> is already registered
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
        except (AttributeError, NameError) as e:
            traceback.print_exc()
            wx.CallAfter(wx.MessageBox,
                         "{}\n\n{}".format(e, traceback.format_exc()),
                         "Error in loading {!r}".format(module.__name__),
                         style=wx.ICON_ERROR)
            return False
        
        ## --------------------------------
        ## Create and register the plugin
        ## --------------------------------
        if pane.IsOk():
            self.unload_plug(name) # unload once right here
        
        try:
            plug = module.Plugin(self, session, **kwargs)
            
        except Exception as e:
            traceback.print_exc()
            wx.CallAfter(wx.MessageBox,
                         "{}\n\n{}".format(e, traceback.format_exc()),
                         "Error in loading {!r}".format(name),
                         style=wx.ICON_ERROR)
            return False
        
        ## Add to the list after the plug is created successfully.
        self.plugins[name] = module
        
        ## set reference of a plug (one module, one plugin)
        module.__plug__ = plug
        
        ## Create pane or notebook pane
        caption = plug.caption
        if not isinstance(caption, str):
            caption = name
        
        title = plug.category
        if title:
            pane = self._mgr.GetPane(title)
            if pane.IsOk():
                nb = pane.window
                nb.AddPage(plug, caption)
            else:
                size = plug.GetSize() + (2,30) # padding for notebook
                nb = AuiNotebook(self)
                nb.Name = title
                nb.AddPage(plug, caption)
                self._mgr.AddPane(nb, aui.AuiPaneInfo()
                                         .Name(title).Caption(title)
                                         .FloatingSize(size).MinSize(size).Show(0))
            j = nb.GetPageIndex(plug)
            nb.SetPageToolTip(j, "[{}]\n{}".format(plug.__module__, plug.__doc__))
        else:
            nb = None
            size = plug.GetSize()
            self._mgr.AddPane(plug, aui.AuiPaneInfo()
                                       .Name(name).Caption(caption)
                                       .FloatingSize(size).MinSize(size).Show(0))
        
        ## Set winow.Name for inspection.
        plug.Name = name
        
        self.update_pane(name, **props)
        
        ## Create a menu
        plug.__Menu_item = None
        
        if not hasattr(module, 'ID_'): # give a unique index to the module
            global __plug_ID__ # cache ID *not* in [ID_LOWEST(4999):ID_HIGHEST(5999)]
            try:
                __plug_ID__
            except NameError:
                __plug_ID__ = 10000
            __plug_ID__ += 1
            module.ID_ = __plug_ID__
        
        if plug.menukey:
            menu, sep, tail = plug.menukey.rpartition('/')
            menu = menu or Layer.MENU
            text = tail or plug.__module__
            hint = (plug.__doc__ or name).strip().splitlines()[0]
            plug.__Menu_item = (
                module.ID_, text, hint, wx.ITEM_CHECK,
                lambda v: self.show_pane(name, v.IsChecked(), interactive=1),
                lambda v: v.Check(self.get_pane(name).IsShown()),
            )
            if menu not in self.menubar:
                self.menubar[menu] = []
            self.menubar[menu] += [plug.__Menu_item]
            self.menubar.update(menu)
        return None
    
    def unload_plug(self, name):
        """Unload plugin and detach the pane from UI manager."""
        try:
            plug = self.get_plug(name)
            if not plug:
                return False
            
            name = plug.__module__
            if name not in self.plugins:
                return False
            
            del self.plugins[name]
            
            if plug.__Menu_item:
                menu, sep, tail = plug.menukey.rpartition('/')
                menu = menu or Layer.MENU
                self.menubar[menu].remove(plug.__Menu_item)
                self.menubar.update(menu)
            
            if isinstance(plug.Parent, aui.AuiNotebook):
                nb = plug.Parent
                j = nb.GetPageIndex(plug)
                nb.RemovePage(j) # just remove page
                ## nb.DeletePage(j) # cf. destroy plug object too
            else:
                nb = None
                self._mgr.DetachPane(plug)
                self._mgr.Update()
            
            plug.handler('page_closed', plug) # (even if not shown)
            plug.Destroy()
            
            if nb and not nb.PageCount:
                self._mgr.DetachPane(nb) # detach notebook pane
                self._mgr.Update()
                nb.Destroy()
            
        except Exception as e:
            traceback.print_exc()
            wx.CallAfter(wx.MessageBox,
                         "{}\n\n{}".format(e, traceback.format_exc()),
                         "Error in unloading {!r}".format(name),
                         style=wx.ICON_ERROR)
            return False
    
    def reload_plug(self, name):
        plug = self.get_plug(name)
        if not plug:
            return
        if plug.reloadable:
            session = {}
            try:
                print("Reloading {}...".format(plug))
                plug.save_session(session)
            except Exception:
                traceback.print_exc()
                print("- Failed to save session: {}".format(plug))
            return self.load_plug(plug.__module__, force=1, session=session)
        return False
    
    def edit_plug(self, name):
        plug = self.get_plug(name)
        if not plug:
            return
        self.edit(self.plugins[plug.__module__])
    
    def inspect_plug(self, name):
        """Dive into the process to inspect plugs in the shell.
        """
        plug = self.get_plug(name)
        if not plug:
            return
        
        shell = self.shellframe.clone_shell(plug)
        
        @shell.handler.bind("shell_activated")
        def init(shell):
            nonlocal plug
            _plug = self.get_plug(name)
            if _plug is not plug:
                shell.target = _plug or self # reset for loaded/unloaded plug
            plug = _plug
        init(shell)
        self.shellframe.Show()
        self.shellframe.load(plug)
    
    def OnLoadPlugins(self, evt):
        with wx.FileDialog(self, "Load a plugin file",
                wildcard="Python file (*.py)|*.py",
                style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST
                                |wx.FD_MULTIPLE) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                for path in dlg.Paths:
                    self.load_plug(path)
    
    def Quit(self, evt=None):
        """Stop all Layer.thread."""
        for name in self.plugins:
            plug = self.get_plug(name)
            try:
                if plug.thread and plug.thread.active:
                    plug.thread.active = 0 # worker-thread から直接切り替える
                    plug.thread.Stop()     # main-thread で終了させる
            except AttributeError:
                pass
    
    ## --------------------------------
    ## load/save index file
    ## --------------------------------
    ATTRIBUTESFILE = "results.index"
    
    def import_index(self, file=None, view=None):
        """Load frames :ref to the Index file.
        """
        if not view:
            view = self.selected_view
        
        if not file:
            with wx.FileDialog(self, "Select index file to import",
                    defaultFile=self.ATTRIBUTESFILE,
                    wildcard="Index (*.index)|*.index|"
                             "ALL files (*.*)|*.*",
                    style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                file = dlg.Path
        
        res, mis = self.read_attributes(file)
        
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
        print(self.statusbar.read())
        return frames
    
    def export_index(self, file=None, frames=None):
        """Save frames :ref to the Index file.
        """
        if not frames:
            frames = self.selected_view.all_frames
            if not frames:
                return
        
        if not file:
            f = next((x.pathname for x in frames if x.pathname), '')
            with wx.FileDialog(self, "Select index file to export",
                    defaultDir=os.path.dirname(f),
                    defaultFile=self.ATTRIBUTESFILE,
                    wildcard="Index (*.index)|*.index",
                    style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                file = dlg.Path
        
        savedir = os.path.dirname(file)
        output_frames = []
        for frame in frames:
            try:
                self.statusbar("Export index of {!r}...".format(frame.name))
                f = frame.pathname
                if not f:
                    f = os.path.join(savedir, frame.name) # new file
                if not os.path.exists(f):
                    if not f.endswith('.tif'):
                        f += '.tif'
                    self.write_buffer(f, frame.buffer)
                    frame.pathname = f
                    frame.name = os.path.basename(f) # new name and pathname
                output_frames.append(frame)
                print(" ", self.statusbar("\b done."))
            except (PermissionError, OSError):
                print("-", self.statusbar("\b failed. pass."))
        
        frames = output_frames
        res, mis = self.write_attributes(file, frames)
        n = len(frames)
        self.statusbar(
            "{} frames were exported, "
            "{} files were skipped, "
            "{} files are missing.".format(n, len(res)-n, len(mis)))
        print(self.statusbar.read())
        return frames
    
    ## --------------------------------
    ## load/save frames and attributes 
    ## --------------------------------
    
    @classmethod
    def read_attributes(self, file):
        """Read attributes file."""
        try:
            res = {}
            mis = {}
            savedir = os.path.dirname(file)
            
            with open(file) as i:
                from numpy import nan, inf  # noqa: necessary to eval
                import datetime             # noqa: necessary to eval
                
                res.update(eval(i.read()))  # read res <dict>
            
            for name, attr in tuple(res.items()):
                f = os.path.join(savedir, name)
                if not os.path.exists(f): # search by relpath (dir+name)
                    f = attr.get('pathname')
                if not os.path.exists(f): # check & pop missing files
                    res.pop(name)
                    mis.update({name:attr})
                else:
                    attr.update(pathname=f)
        except FileNotFoundError:
            pass
        except Exception as e:
            print("- Failed to read attributes: {}".format(e))
            wx.MessageBox(str(e), style=wx.ICON_ERROR)
        finally:
            return res, mis # finally raises no exception
    
    @classmethod
    def write_attributes(self, file, frames):
        """Write attributes file."""
        try:
            res, mis = self.read_attributes(file)
            new = dict((x.name, x.attributes) for x in frames)
            
            ## `res` order may differ from that of given frames,
            ## so we take a few steps to merge `new` to be exported.
            
            res.update(new) # res updates to new info,
            new.update(res) # copy res back keeping new order.
            
            with open(file, 'w') as o:
                try:
                    pprint(new, stream=o, sort_dicts=False) # write new <dict> PY38
                except Exception:
                    pprint(tuple(new.items()), stream=o) # PY37 or less
            
        except Exception as e:
            print("- Failed to write attributes: {}".format(e))
            wx.MessageBox(str(e), style=wx.ICON_ERROR)
        finally:
            return new, mis # finally raises no exception
    
    def load_frame(self, paths=None, view=None):
        """Load frames from files to the view window.
        
        Load buffer and the attributes of the frame.
        If the file names duplicate, the latter takes priority.
        """
        frames = self.load_buffer(paths, view)
        if frames:
            savedirs = {}
            for frame in frames:
                savedir = os.path.dirname(frame.pathname)
                if savedir not in savedirs:
                    f = os.path.join(savedir, self.ATTRIBUTESFILE)
                    res, mis = self.read_attributes(f)
                    savedirs[savedir] = res
                results = savedirs[savedir]
                frame.update_attributes(results.get(frame.name))
        return frames
    
    def save_frame(self, path=None, frame=None):
        """Save frame to a file.
        
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
         "ALL files (*.*)|*.*",
    ]
    
    @staticmethod
    def read_buffer(path):
        """Read buffer from a file (to be overridden)."""
        buf = Image.open(path)
        info = {}
        if buf.mode[:3] == 'RGB':  # 今のところカラー画像には対応する気はない▼
            buf = buf.convert('L') # ここでグレースケールに変換する
        ## return np.asarray(buf), info # ref
        ## return np.array(buf), info # copy
        return buf, info
    
    @staticmethod
    def write_buffer(path, buf):
        """Write buffer to a file (to be overridden)."""
        try:
            img = Image.fromarray(buf)
            img.save(path) # PIL saves as L, I, F, and RGB.
        except PermissionError:
            raise
        except OSError: # cannot write mode L, I, F as BMP, etc.
            if os.path.exists(path):
                os.remove(path)
            raise
    
    def load_buffer(self, paths=None, view=None):
        """Load buffers from paths to the view window.
        
        If no view given, the currently selected view is chosen.
        """
        if not view:
            view = self.selected_view
        
        if isinstance(paths, str): # for single frame
            paths = [paths]
        
        if paths is None:
            with wx.FileDialog(self, "Open image files",
                    wildcard='|'.join(self.wildcards),
                    style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST
                                    |wx.FD_MULTIPLE) as dlg:
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
                
                if isinstance(buf, TiffImageFile) and buf.n_frames > 1: # multi-page tiff
                    n = buf.n_frames
                    d = len(str(n))
                    for j in range(n):
                        self.statusbar("Loading {!r} [{} of {} pages]...".format(f, j+1, n))
                        buf.seek(j)
                        frame = view.load(buf, f"{j:0{d}}-{f}", show=0)
                else:
                    frame = view.load(buf, f, show=0, pathname=path, **info)
                    frames.append(frame)
            
            self.statusbar("\b done.")
            view.select(frame)
            return frames
        
        except Exception as e:
            print("-", self.statusbar("\b failed."))
            wx.MessageBox(str(e), style=wx.ICON_ERROR)
        
        view.select(frame)
        return frames
    
    def save_buffer(self, path=None, frame=None):
        """Save buffer of the frame to a file.
        
        If no view given, the currently selected view is chosen.
        """
        if not frame:
            frame = self.selected_view.frame
            if not frame:
                return
        
        if not path:
            with wx.FileDialog(self, "Save buffer as",
                    defaultFile=re.sub(r'[\/:*?"<>|]', '_', frame.name),
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
        except ValueError:
            ## ValueError('unknown file extension')
            if not path.endswith('.tif'):
                return self.save_buffer(path + '.tif', frame)
            raise
        except Exception as e:
            print("-", self.statusbar("\b failed."))
            wx.MessageBox(str(e), style=wx.ICON_ERROR)
    
    def save_buffers_as_tiffs(self, path=None, frames=None):
        """Export buffers to a file as a multi-page tiff."""
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
            busy = wx.BusyInfo("One moment please, "
                               "now saving {!r}...".format(name))
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
        finally:
            del busy
    
    ## --------------------------------
    ## load/save session
    ## --------------------------------
    session_file = None
    
    def load_session(self, file=None, flush=True):
        """Load session from file."""
        if not file:
            with wx.FileDialog(self, 'Load session',
                    wildcard="Session file (*.jssn)|*.jssn",
                    style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST
                                    |wx.FD_CHANGE_DIR) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                file = dlg.Path
        
        if flush:
            for name in list(self.plugins): # plugins:dict mutates during iteration
                self.unload_plug(name)
            del self.graph[:]
            del self.output[:]
        
        self.session_file = os.path.abspath(file)
        
        ## Load the session in the shell.
        self.statusbar("Loading session from {!r}...".format(self.session_file))
        
        shell = self.shellframe.rootshell
        shell.locals.update(
            nan = np.nan,
            inf = np.inf,
        )
        with open(self.session_file) as i:
            shell.Execute(i.read())
        self._mgr.Update()
        self.menubar.reset()
        
        dirname_ = os.path.dirname(i.name)
        if dirname_:
            os.chdir(dirname_)
        
        ## Reposition the window if it is not on the desktop.
        if wx.Display.GetFromWindow(self) == -1:
            self.Position = (0, 0)
        
        self.statusbar("\b done.")
    
    def save_session_as(self):
        """Save session as a new file."""
        with wx.FileDialog(self, "Save session as",
                defaultDir=os.path.dirname(self.session_file or ''),
                defaultFile=os.path.basename(self.session_file or ''),
                wildcard="Session file (*.jssn)|*.jssn",
                style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT
                                |wx.FD_CHANGE_DIR) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.session_file = dlg.Path
                self.save_session()
    
    def save_session(self):
        """Save session to file."""
        if not self.session_file:
            return self.save_session_as()
        
        self.statusbar("Saving session to {!r}...".format(self.session_file))
        
        with open(self.session_file, 'w') as o,\
          np.printoptions(threshold=np.inf): # printing all(inf) elements
            o.write("#! Session file (This file is generated automatically)\n")
            o.write("self.SetSize({})\n".format(self.Size))
            o.write("self.SetPosition({})\n".format(self.Position))
            
            for name, module in self.plugins.items():
                plug = self.get_plug(name)
                path = os.path.abspath(module.__file__)
                basename = os.path.basename(path)
                if basename == "__init__.py": # is module package?
                    path = path[:-12]
                session = {}
                try:
                    plug.save_session(session)
                except Exception:
                    traceback.print_exc()
                    print("- Failed to save session: {}".format(plug))
                o.write("self.load_plug({!r}, session={})\n".format(path, session or None))
            o.write("self._mgr.LoadPerspective({!r})\n".format(self._mgr.SavePerspective()))
            
            ## set-global-unit
            o.write("self.graph.unit = {:g}\n".format(self.graph.unit))
            o.write("self.output.unit = {:g}\n".format(self.output.unit))
            
            ## stack-frame
            paths = [x.pathname for x in self.graph.all_frames if x.pathname]
            if paths:
                o.write("self.load_frame(\n{}, self.graph)\n".format(
                        pformat(paths, width=160)))
            if len(paths) > 1:
                frame = self.graph.frame # restore currently selected frame
                if frame and frame.pathname:
                    o.write("self.graph.select({!r})\n".format(frame.name))
        
        self.statusbar("\b done.")


if __name__ == "__main__":
    import glob
    
    app = wx.App()
    frm = Frame(None)
    
    frm.handler.debug = 0
    frm.graph.handler.debug = 0
    frm.output.handler.debug = 0
    
    ## frm.load_frame([r"C:\usr\home\lib\python\demo\sample.bmp",
    ##                 r"C:\usr\home\lib\python\demo\sample2.tif",
    ##                 ])
    frm.load_frame(glob.glob(r"C:\usr\home\lib\python\demo\*.bmp"))
    frm.load_frame(glob.glob(r"C:\usr\home\workspace\images\*.bmp"))
    frm.graph.load(np.random.randn(1024,1024))
    
    ## Note: 次の二つは別モジュール扱い
    ## frm.load_plug("demo.template.py", show=1, force=1)
    ## frm.load_plug("demo/template.py", show=1, force=1)
    
    frm.Show()
    app.MainLoop()
