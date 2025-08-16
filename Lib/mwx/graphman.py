#! python3
"""Graph manager.
"""
from contextlib import contextmanager
from functools import wraps
from importlib import reload, import_module
from bdb import BdbQuit
from pprint import pformat
import threading
import traceback
import inspect
import sys
import os
import platform
import re
import wx
from wx import aui
from wx import stc

from matplotlib import cm
from matplotlib import colors
## from matplotlib import pyplot as plt
import numpy as np
from PIL import Image
from PIL.TiffImagePlugin import TiffImageFile

from . import framework as mwx
from .utilus import ignore, warn
from .utilus import funcall as _F
from .controls import KnobCtrlPanel, Icon
from .framework import CtrlInterface, AuiNotebook, Menu, FSM

from .matplot2 import MatplotPanel  # noqa
from .matplot2g import GraphPlot
from .matplot2lg import LinePlot  # noqa
from .matplot2lg import LineProfile  # noqa
from .matplot2lg import Histogram


class Thread:
    """Thread manager for graphman.Layer
    
    The worker:thread runs the given target.
    
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
    
        1. event.clear -> clear flag so that the thread suspends when wait is called.
        2. event.wait -> wait until the chequer flag to be set True.
        3. event.set -> set flag to resume the thread.
        
        The event.wait blocks until the internal flag is True when it is False,
        and returns immediately when it is True.
    """
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
            self.handler = FSM({ # DNA<Thread>
                None : {
                 'thread_begin' : [ None ], # begin processing
                   'thread_end' : [ None ], # end processing
                },
            })
    
    def __del__(self):
        if self.active:
            self.Stop()
    
    @contextmanager
    def entry(self):
        """Exclusive reentrant lock manager.
        Allows only this worker (but no other thread) to enter.
        """
        frame = inspect.currentframe().f_back.f_back
        name = frame.f_code.co_name
        
        ## Other threads are not allowed to enter.
        ct = threading.current_thread()
        assert self.worker is ct, f"{ct.name} are not allowed to enter {name!r}."
        
        ## The thread must be activated to enter.
        ## assert self.active, f"{self!r} must be activated to enter {name!r}."
        yield self
    
    def enters(self, f):
        """Decorator to add a one-time handler for the enter event.
        The specified function will be called from the main thread.
        """
        return self.handler.binds('thread_begin', _F(f))
    
    def exits(self, f):
        """Decorator to add a one-time handler for the exit event.
        The specified function will be called from the main thread.
        """
        return self.handler.binds('thread_end', _F(f))
    
    def wraps(self, f, *args, **kwargs):
        """Decorator for a function that starts a new thread."""
        @wraps(f)
        def _f(*v, **kw):
            return self.Start(f, *v, *args, **kw, **kwargs)
        return _f
    
    def check(self, timeout=None):
        """Check the thread event flags."""
        if not self.running:
            return None
        if not self.event.wait(timeout): # wait until set in time
            raise KeyboardInterrupt("timeout")
        if not self.active:
            raise KeyboardInterrupt("terminated by user")
        return True
    
    def pause(self, msg=None, caption=wx.MessageBoxCaptionStr):
        """Pause the thread.
        Confirm whether to terminate the thread.
        
        Returns:
            True  : [OK] if terminating.
            False : [CANCEL] otherwise.
        
        Note:
            Use ``check`` method where you want to pause.
            Even after the message dialog is displayed, the thread
            does not suspend until check (or event.wait) is called.
        """
        if not self.running:
            return None
        if not msg:
            msg = ("The thread is running.\n\n"
                   "Do you want to terminate the thread?")
        try:
            self.event.clear() # suspend
            if wx.MessageBox(  # Confirm closing the thread.
                    msg, caption,
                    style=wx.OK|wx.CANCEL|wx.ICON_WARNING) == wx.OK:
                self.Stop()
                return True
            return False
        finally:
            self.event.set() # resume
    
    def Start(self, f, *args, **kwargs):
        """Start the thread to run the specified function.
        """
        @wraps(f)
        def _f(*v, **kw):
            try:
                wx.CallAfter(self.handler, 'thread_begin', self)
                self.result = f(*v, **kw)
            except BdbQuit:
                pass
            except KeyboardInterrupt as e:
                print("- Thread terminated by user:", e)
            except Exception as e:
                print("- Thread failed in error:", e)
                traceback.print_exc()
                tbstr = traceback.format_tb(e.__traceback__)
                wx.CallAfter(wx.MessageBox,
                             f"{e}\n\n" + tbstr[-1] + f"{type(e).__name__}: {e}",
                             f"Error in the thread running {f.__name__!r}\n\n",
                             style=wx.ICON_ERROR)
            finally:
                self.active = 0
                wx.CallAfter(self.handler, 'thread_end', self)
        
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
        """Stop the thread.
        
        Note:
            Use ``check`` method where you want to stop.
            Even after the message dialog is displayed, the thread
            does not suspend until check (or event.wait) is called.
        """
        def _stop():
            with wx.BusyInfo("One moment please, "
                             "waiting for threads to die..."):
                self.worker.join(1)
        if self.running:
            self.active = 0
            wx.CallAfter(_stop)  # main thread で終了させる


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
    reloadable = True
    unloadable = True
    
    graph = property(lambda self: self.parent.graph)
    output = property(lambda self: self.parent.output)
    histogram = property(lambda self: self.parent.histogram)
    selected_view = property(lambda self: self.parent.selected_view)
    
    message = property(lambda self: self.parent.message)
    
    ## thread_type = Thread
    thread = None
    
    ## layout helper function (internal use only)
    pack = mwx.pack
    
    ## funcall = interactive_call (internal use only)
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
        """Attach artists (e.g., patches) to the given axes."""
        for art in artists:
            if art.axes:
                art.remove()
                art._transformSet = False
            axes.add_artist(art)
            if art not in self.__artists:
                self.__artists.append(art)
    
    def detach_artists(self, *artists):
        """Detach artists (e.g., patches) from their axes."""
        for art in artists:
            if art.axes:
                art.remove()
                art._transformSet = False
            self.__artists.remove(art)
    
    def __init__(self, parent, session=None):
        if hasattr(self, 'handler'):
            warn(f"Duplicate iniheritance of CtrlInterface by {self}.")
        else:
            CtrlInterface.__init__(self)
        
        self.parent = parent
        self.__artists = []
        
        try:
            ## Check if parameters exists without triggering dynamic lookup.
            inspect.getattr_static(self, "parameters")
        except AttributeError:
            self.parameters = None
        
        def copy_params(evt, checked_only=False):
            if isinstance(evt.EventObject, (wx.TextEntry, stc.StyledTextCtrl)):
                evt.Skip()
            elif self.parameters:
                self.copy_to_clipboard(checked_only)
        
        def paste_params(evt, checked_only=False):
            if isinstance(evt.EventObject, (wx.TextEntry, stc.StyledTextCtrl)):
                evt.Skip()
            elif self.parameters:
                self.paste_from_clipboard(checked_only)
        
        def reset_params(evt, checked_only=False):
            self.Draw(None)
            if self.parameters:
                self.reset_params(checked_only)
        
        self.handler.append({ # DNA<Layer>
            None : {
                   'page_shown' : [ None, _F(self.Draw, show=True)  ],
                  'page_closed' : [ None, _F(self.Draw, show=False) ],
                  'page_hidden' : [ None, _F(self.Draw, show=False) ],
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
                lambda v: copy_params(v, checked_only=wx.GetKeyState(wx.WXK_SHIFT)),
                lambda v: v.Enable(bool(self.parameters))),
                
            (wx.ID_PASTE, "&Paste params\t(C-v)", "Read params",
                lambda v: paste_params(v, checked_only=wx.GetKeyState(wx.WXK_SHIFT)),
                lambda v: v.Enable(bool(self.parameters))),
            (),
            (wx.ID_RESET, "&Reset params\t(C-n)", "Reset params", Icon('-'),
                lambda v: reset_params(v, checked_only=wx.GetKeyState(wx.WXK_SHIFT)),
                lambda v: v.Enable(bool(self.parameters))),
            (),
            (mwx.ID_(201), "&Reload module", "Reload", Icon('load'),
                lambda v: self.parent.reload_plug(self),
                lambda v: v.Enable(self.reloadable
                            and not (self.thread and self.thread.active))),
                
            (mwx.ID_(202), "&Unload module", "Unload", Icon('delete'),
                lambda v: self.parent.unload_plug(self),
                lambda v: v.Enable(self.unloadable
                            and not (self.thread and self.thread.active))),
            (),
            (mwx.ID_(203), "&Dive into {!r}".format(self.__module__), "dive", Icon('core'),
                lambda v: self.parent.inspect_plug(self)),
        ]
        self.Bind(wx.EVT_CONTEXT_MENU,
                  lambda v: Menu.Popup(self, self.menu))
        
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        self.Bind(wx.EVT_SHOW, self.OnShow)
        
        try:
            self.Init()
        except Exception as e:
            traceback.print_exc()  # Failed to initialize the plug.
            if parent:
                bmp = wx.StaticBitmap(self, bitmap=Icon('!!!'))
                txt = wx.StaticText(self, label="Exception")
                txt.SetToolTip(str(e))
                self.layout((bmp, txt), row=2)
        try:
            if session:
                self.load_session(session)
        except Exception:
            traceback.print_exc()  # Failed to load the plug session.
    
    def Init(self):
        """Initialize layout before load_session (to be overridden)."""
        pass
    
    def load_session(self, session):
        """Restore settings from a session file (to be overridden)."""
        if 'params' in session:
            self.parameters = session['params']
    
    def save_session(self, session):
        """Save settings in a session file (to be overridden)."""
        if self.parameters:
            session['params'] = self.parameters
    
    def OnDestroy(self, evt):
        if evt.EventObject is self:
            if self.thread and self.thread.active:
                ## self.thread.active = 0
                self.thread.Stop()
            del self.Arts
        evt.Skip()
    
    def OnShow(self, evt):
        if not self:
            return
        if isinstance(self.Parent, aui.AuiNotebook):
            if evt.IsShown():
                self.handler('page_shown', self)
            else:
                self.handler('page_hidden', self)
        evt.Skip()
    
    Shown = property(
        lambda self: self.IsShown(),
        lambda self, v: self.Show(v))
    
    def IsShown(self):
        """Return True if the window is physically visible on the screen.
        
        (override) Equivalent to ``IsShownOnScreen``.
                   Note: The instance could be a page within a notebook.
        """
        ## return self.pane.IsShown()
        return self.IsShownOnScreen()
    
    def Show(self, show=True):
        """Shows or hides the window.
        
        (override) Show associated pane window.
                   Note: This might be called from a thread.
        """
        wx.CallAfter(self.parent.show_pane, self, show)  # Show pane windows in the main thread.
    
    Drawn = property(
        lambda self: self.IsDrawn(),
        lambda self, v: self.Draw(v))
    
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
            ## To avoid RuntimeError, check if canvas object has been deleted.
            canvas = art.axes.figure.canvas
            if canvas:
                canvas.draw_idle()
        except Exception as e:
            print(f"- Failed to draw Arts of {self.__module__}.", e)
            del self.Arts


class Layer(LayerInterface, KnobCtrlPanel):
    """Graphman.Layer
    """
    def __init__(self, parent, session=None, **kwargs):
        KnobCtrlPanel.__init__(self, parent, **kwargs)
        LayerInterface.__init__(self, parent, session)


def register(cls, module=None):
    """Register dummy plug; Add module.Plugin <Layer>.
    """
    if not module:
        module = inspect.getmodule(cls) # rebase module or __main__
    
    if issubclass(cls, LayerInterface):
        cls.__module__ = module.__name__ # __main__ to module
        warn(f"Duplicate iniheritance of LayerInterface by {cls}.")
        module.Plugin = cls
        return cls
    
    class _Plugin(LayerInterface, cls):
        def __init__(self, parent, session=None, **kwargs):
            cls.__init__(self, parent, **kwargs)
            LayerInterface.__init__(self, parent, session)
    
    _Plugin.__module__ = cls.__module__ = module.__name__
    _Plugin.__name__ = cls.__name__ + str("~")
    _Plugin.__doc__ = cls.__doc__
    module.Plugin = _Plugin
    return _Plugin


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
            self.infobar.ShowMessage(self.frame.annotation)
    
    def update_infobar(self, frame):
        """Show infobar (frame.annotation)."""
        if self.infobar.IsShown():
            self.infobar.ShowMessage(frame.annotation)
    
    def get_markups_visible(self):
        return self.marked.get_visible()
    
    def set_markups_visible(self, v):
        self.selected.set_visible(v)
        self.marked.set_visible(v)
        self.rected.set_visible(v)
        self.update_art_of_mark()
    
    def remove_markups(self):
        del self.selector
        del self.markers
        del self.region
    
    def hide_layers(self):
        for plug in self.parent.get_all_plugs():
            for art in plug.Arts:
                art.set_visible(0)
        self.remove_markups()
        self.draw()


class MyFileDropLoader(wx.FileDropTarget):
    """File Drop interface
    
    Args:
        target : target view to drop in, e.g. frame, graph, pane, etc.
        loader : mainframe
    """
    def __init__(self, target, loader):
        wx.FileDropTarget.__init__(self)
        
        self.view = target
        self.loader = loader
    
    def OnDropFiles(self, x, y, filenames):
        pos = self.view.ScreenPosition + (x, y)
        paths = []
        for fn in filenames:
            name, ext = os.path.splitext(fn)
            if ext == '.py' or os.path.isdir(fn):
                self.loader.load_plug(fn, show=1,
                                          floating_pos=pos,
                                          force=wx.GetKeyState(wx.WXK_ALT))
            elif ext == '.jssn':
                self.loader.load_session(fn)
            elif ext == '.index':
                self.loader.load_index(fn, self.view)
            else:
                paths.append(fn) # image file just stacks to be loaded
        if paths:
            self.loader.load_frame(paths, self.view)
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
    
    @property
    def graphic_windows_on_screen(self):
        return [w for w in self.__graphic_windows if w.IsShownOnScreen()]
    
    def __init__(self, *args, **kwargs):
        mwx.Frame.__init__(self, *args, **kwargs)
        
        self._mgr = aui.AuiManager()
        self._mgr.SetManagedWindow(self)
        self._mgr.SetDockSizeConstraint(0.5, 0.5)
        
        self.__plugins = {} # modules in the order of load/save
        
        self.__graph = Graph(self, log=self.message, margin=None)
        self.__output = Graph(self, log=self.message, margin=None)
        
        self.__histgrm = Histogram(self, log=self.message, margin=None, size=(130,65))
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
                          aui.AuiPaneInfo().CenterPane()
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
                
            (wx.ID_SAVEAS, "&Save as TIFFs", "Save buffers as a multi-page tiff", Icon('saveall'),
                lambda v: self.save_buffers_as_tiffs(),
                lambda v: v.Enable(self.__view.frame is not None)),
            (),
            ("Index", (
                (mwx.ID_(11), "&Import index\tCtrl+Shift+o", "Import index file", Icon('open'),
                    lambda v: self.load_index()),
                    
                (mwx.ID_(12), "&Export index\tCtrl+Shift+s", "Export index file", Icon('saveas'),
                    lambda v: self.save_index(),
                    lambda v: v.Enable(self.__view.frame is not None)),
                )),
            (),
            ("Session", (
                (mwx.ID_(15), "&Open session", "Open session file",
                    lambda v: self.load_session()),
                    
                (mwx.ID_(16), "&Save session", "Save session file",
                    lambda v: self.save_session()),
                    
                (mwx.ID_(17), "&Save session as", "Save session file as",
                    lambda v: self.save_session_as()),
                )),
            (),
            ("Options", []), # reserved for optional app settings
            (),
            (mwx.ID_(13), "&Graph window\tF9", "Show graph window", wx.ITEM_CHECK,
                lambda v: self.show_pane(self.graph, v.IsChecked()),
                lambda v: v.Check(self.graph.IsShownOnScreen())),
                
            (mwx.ID_(14), "&Output window\tF10", "Show Output window", wx.ITEM_CHECK,
                lambda v: self.show_pane(self.output, v.IsChecked()),
                lambda v: v.Check(self.output.IsShownOnScreen())),
            (),
        ]
        self.menubar["Edit"] = [
            (wx.ID_COPY, "&Copy\t(C-c)", "Copy buffer to clipboard", Icon('copy'),
                lambda v: self.__view.write_buffer_to_clipboard()),
                
            (wx.ID_PASTE, "&Paste\t(C-v)", "Paste buffer from clipboard", Icon('paste'),
                lambda v: self.__view.read_buffer_from_clipboard()),
            (),
            (mwx.ID_(21), "Toggle &markers", "Show/Hide markups", wx.ITEM_CHECK, Icon('+'),
                lambda v: self.__view.set_markups_visible(v.IsChecked()),
                lambda v: v.Check(self.__view.get_markups_visible())),
                
            (mwx.ID_(22), "&Remove markers", "Remove markups", Icon('-'),
                lambda v: self.__view.remove_markups()),
            (),
            (mwx.ID_(23), "Hide all &layers", "Hide all layers", Icon('xr'),
                lambda v: self.__view.hide_layers()),
            (),
            (mwx.ID_(24), "&Histogram\tCtrl-h", "Show histogram window", wx.ITEM_CHECK,
                lambda v: self.show_pane(self.histogram, v.IsChecked()),
                lambda v: v.Check(self.histogram.IsShownOnScreen())),
                
            (mwx.ID_(25), "&Invert color\t(C-i)", "Invert colormap", wx.ITEM_CHECK,
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
            ("Standard colors",
                [_cmenu(i, c) for i, c in enumerate(colours) if c.islower()]),
                
            ("Other colors",
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
        
        def show_frameview(frame):
            wx.CallAfter(self.show_pane, frame.parent)  # Show graph / output in the main thread.
        
        self.graph.handler.append({ # DNA<Graph:Frame>
            None : {
                  'frame_shown' : [ None, self.set_title ],
                 'frame_loaded' : [ None, show_frameview ],
               'frame_modified' : [ None, show_frameview ],
               'frame_selected' : [ None, self.set_title ],
                  'canvas_draw' : [ None, lambda v: self.sync(self.graph, self.output) ],
            },
        })
        self.output.handler.append({ # DNA<Graph:Frame>
            None : {
                  'frame_shown' : [ None, self.set_title ],
                 'frame_loaded' : [ None, show_frameview ],
               'frame_modified' : [ None, show_frameview ],
               'frame_selected' : [ None, self.set_title ],
                  'canvas_draw' : [ None, lambda v: self.sync(self.output, self.graph) ],
            },
        })
        
        ## Add main-menu to context-menu
        self.graph.menu += self.menubar["Edit"][2:7]
        self.output.menu += self.menubar["Edit"][2:7]
        
        self._mgr.Bind(aui.EVT_AUI_PANE_CLOSE, self.OnPaneClose)
        
        self.Bind(wx.EVT_ACTIVATE, self.OnActivate)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        
        def on_move(evt, show):
            def _display(view, show):
                if view.frame:
                    view.frame.set_visible(show)
                    if show:
                        view.draw()
            _display(self.graph, show)
            _display(self.output, show)
            evt.Skip()
        self.Bind(wx.EVT_MOVE_START, lambda v: on_move(v, show=0))
        self.Bind(wx.EVT_MOVE_END, lambda v: on_move(v, show=1))
        
        ## Custom Key Bindings
        self.define_key('* C-g', self.Quit)
        
        @self.shellframe.define_key('* C-g')
        def quit(evt):
            """Dispatch quit to the main Frame."""
            self.handler('C-g pressed', evt)
        
        ## Accepts DnD
        self.SetDropTarget(MyFileDropLoader(self.graph, self))
    
    SYNC_SWITCH = True
    
    def sync(self, a, b):
        """Synchronize b to a."""
        if (self.SYNC_SWITCH
                and a.frame and b.frame
                and a.frame.unit == b.frame.unit
                and a.buffer.shape == b.buffer.shape):
            b.xlim = a.xlim
            b.ylim = a.ylim
            b.OnDraw(None)
            b.canvas.draw_idle()
    
    def set_title(self, frame):
        ssn = os.path.basename(self.session_file or '--')
        ssn, _ = os.path.splitext(ssn)
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
        n = sum(bool(plug.thread and plug.thread.active) for plug in self.get_all_plugs())
        if n:
            s = 's' if n > 1 else ''
            if wx.MessageBox( # Confirm closing the thread.
                    f"Currently  running {n} thread{s}.\n\n"
                    "Continue closing?",
                    style=wx.YES_NO|wx.ICON_INFORMATION) != wx.YES:
                self.message("The close has been canceled.")
                evt.Veto()
                return
            self.Quit()
        n = sum(frame.pathname is None for frame in self.graph.all_frames)
        if n:
            s = 's' if n > 1 else ''
            if wx.MessageBox( # Confirm closing the frame.
                    f"You are closing {n} unsaved frame{s}.\n\n"
                     "Continue closing?",
                    style=wx.YES_NO|wx.ICON_INFORMATION) != wx.YES:
                self.message("The close has been canceled.")
                evt.Veto()
                return
        evt.Skip()
    
    def Destroy(self):
        self._mgr.UnInit()
        return mwx.Frame.Destroy(self)
    
    ## --------------------------------
    ## pane window interface
    ## --------------------------------
    
    def get_pane(self, name):
        """Get named pane or notebook pane.
        
        Args:
            name : str or plug object.
        """
        plug = self.get_plug(name)
        if plug:
            name = plug.category or plug
        if name:
            return self._mgr.GetPane(name)
    
    def show_pane(self, name, show=True, interactive=False):
        """Show named pane or notebook pane."""
        pane = self.get_pane(name)
        if not pane.IsOk():
            return
        
        ## Set the graph and output window sizes to half & half.
        ## ドッキング時に再計算される
        if name == "output" or name is self.output:
            w, h = self.graph.GetClientSize()
            pane.best_size = (w//2 - 3, h)  # 分割線幅補正 -12pix (Windows only ?)
        
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
        
        plug = self.get_plug(name)  # -> None if pane.window is a Graph
        win = pane.window
        try:
            shown = plug.IsShown()
        except AttributeError:
            shown = pane.IsShown()
        
        if show and not shown:
            if isinstance(win, aui.AuiNotebook):
                j = win.GetPageIndex(plug)
                if j != win.Selection:
                    win.Selection = j  # the focus moves => EVT_SHOW
                else:
                    plug.handler('page_shown', plug)
            else:
                win.handler('page_shown', win)
        elif not show and shown:
            if isinstance(win, aui.AuiNotebook):
                for plug in win.get_pages():
                    plug.handler('page_closed', plug)
            else:
                win.handler('page_closed', win)
        
        ## Modify the floating position of the pane when displayed.
        ## Note: This is a known bug in wxWidgets 3.17 -- 3.20,
        ##       and will be fixed in wx ver 4.2.1.
        if wx.Display.GetFromWindow(pane.window) == -1:
            pane.floating_pos = wx.GetMousePosition()
        
        pane.Show(show)
        self._mgr.Update()
        return (show != shown)
    
    def update_pane(self, name, **props):
        """Update the layout of the pane (internal use only).
        
        Note:
            This is called automatically from load_plug,
            and should not be called directly from user.
        """
        pane = self.get_pane(name)
        for k, v in props.items():
            if v is not None:
                setattr(pane, k, v)
        
        plug = self.get_plug(name)
        if plug:
            dock = plug.dockable
            if not isinstance(dock, bool):
                pane.dock_direction = dock
            if not plug.caption:
                pane.CaptionVisible(False)       # no caption bar
                pane.Gripper(dock not in (0,5))  # show a grip when docked
            pane.Dockable(dock)
        
        if pane.dock_direction:
            pane.Dock()
        else:
            pane.Float()
    
    def OnPaneClose(self, evt): #<wx.aui.AuiManagerEvent>
        pane = evt.GetPane()
        win = pane.window
        if isinstance(win, aui.AuiNotebook):
            for plug in win.get_pages():
                plug.handler('page_closed', plug)
        else:
            win.handler('page_closed', win)
        evt.Skip(False) # Don't skip to avoid being called twice.
    
    ## --------------------------------
    ## Plugin <Layer> interface
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
        """Get named plug window."""
        if isinstance(name, str):
            if name.endswith(".py"):
                name, _ = os.path.splitext(os.path.basename(name))
            if name in self.plugins:
                return self.plugins[name].__plug__
        elif isinstance(name, LayerInterface):
            return name
    
    def get_all_plugs(self):
        for name, module in self.plugins.items():
            yield module.__plug__
    
    def load_plug(self, root, force=False, session=None, show=False,
                        dock=0, floating_pos=None, floating_size=None,
                        **kwargs):
        """Load plugin.
        
        Args:
            root    : Plugin <Layer> module, or name of the module.
                      Any wx.Window object can be specified (as dummy-plug).
                      However, do not use this mode in release versions.
            force   : force loading even if it is already loaded
            session : Conditions for initializing the plug and starting session
            show    : the pane is shown after loaded
            dock    : dock_direction (1:top, 2:right, 3:bottom, 4:left, 5:center)
            floating_pos: posision of floating window
            floating_size: size of floating window
            
            **kwargs: keywords for Plugin <Layer>
        
        Returns:
            None if succeeded else False
        
        Note:
            The root module must contain a class Plugin <Layer>.
        """
        props = dict(dock_direction=dock,
                     floating_pos=floating_pos,
                     floating_size=floating_size)
        
        if inspect.ismodule(root):
            name = root.__file__  # @TODO root.__name__
        elif inspect.isclass(root):
            name = inspect.getsourcefile(root)
        else:
            name = root
        dirname_, name = os.path.split(name)  # if the name is full path,...
        if name.endswith(".py"):
            name = name[:-3]
        
        ## Check if the plug is already loaded or needs to be reloaded.
        plug = self.get_plug(name)
        if plug and not force:
            self.update_pane(name, **props)
            self.show_pane(name, show)
            try:
                if session:
                    plug.load_session(session)
            except Exception:
                traceback.print_exc()  # Failed to load the plug session.
            return None
        
        ## Update the include-path to load the module correctly.
        if os.path.isdir(dirname_):
            if dirname_ in sys.path:
                sys.path.remove(dirname_)
            sys.path.insert(0, dirname_)
        elif dirname_:
            print(f"- No such directory {dirname_!r}.")
            return False
        
        ## Load or reload the root module, and check whether it contains a class named `Plugin`.
        try:
            if name in sys.modules:
                module = reload(sys.modules[name])
            else:
                module = import_module(name)
        except Exception:
            traceback.print_exc()  # Unable to load the module.
            return False
        else:
            if not hasattr(module, 'Plugin'):
                if isinstance(root, type):
                    ## warn(f"Use dummy plug for {name!r}.")
                    module.__dummy_plug__ = root
                    register(root, module)
            else:
                if hasattr(module, '__dummy_plug__'):
                    root = module.__dummy_plug__          # old class (imported)
                    cls = getattr(module, root.__name__)  # new class (reloaded)
                    register(cls, module)
        
        ## Note: name (module.__name__) != Plugin.__module__ if module is a package.
        try:
            Plugin = module.Plugin   # Check if the module has a class `Plugin`.
            title = Plugin.category  # Plugin <LayerInterface>
            
            pane = self._mgr.GetPane(title)  # Check if <pane:title> is already registered.
            if pane.IsOk():
                if not isinstance(pane.window, aui.AuiNotebook):
                    raise NameError("Notebook name must not be the same as any other plugin")
            
            pane = self.get_pane(name)  # Check if <pane:name> is already registered.
            if pane.IsOk():
                if name not in self.plugins:
                    raise NameError("Plugin name must not be the same as any other pane")
            
        except (AttributeError, NameError) as e:
            traceback.print_exc()
            wx.CallAfter(wx.MessageBox,  # Show the message after load_session has finished.
                         f"{e}\n\n" + traceback.format_exc(),
                         f"Error in loading {module.__name__!r}",
                         style=wx.ICON_ERROR)
            return False
        
        ## Unload the plugin if loaded.
        if pane.IsOk():
            show = show or pane.IsShown()
            props.update(
                dock_direction = pane.IsDocked() and pane.dock_direction,
                floating_pos = floating_pos or pane.floating_pos[:], # copy unloading pane
                floating_size = floating_size or pane.floating_size[:], # copy unloading pane
            )
            self.unload_plug(name)
        
        ## Create the plugin object.
        try:
            plug = Plugin(self, session, **kwargs)
        except Exception as e:
            traceback.print_exc()
            wx.CallAfter(wx.MessageBox,  # Show the message after load_session has finished.
                         f"{e}\n\n" + traceback.format_exc(),
                         f"Error in loading {name!r}",
                         style=wx.ICON_ERROR)
            return False
        
        ## Add to the list after the plug is created successfully.
        self.plugins[name] = module
        
        ## Set reference of a plug (one module, one plugin).
        module.__plug__ = plug
        
        ## Create pane or notebook pane.
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
                size = plug.GetSize() + (2,30)  # padding for notebook
                nb = AuiNotebook(self, name=title)
                nb.AddPage(plug, caption)
                self._mgr.AddPane(nb, aui.AuiPaneInfo()
                                         .Name(title).Caption(title)
                                         .FloatingSize(size).MinSize(size).Show(0))
            j = nb.GetPageIndex(plug)
            tips = "[{}]\n{}".format(plug.__module__, plug.__doc__)
            nb.SetPageToolTip(j, tips.strip())
        else:
            nb = None
            size = plug.GetSize()
            self._mgr.AddPane(plug, aui.AuiPaneInfo()
                                       .Name(name).Caption(caption)
                                       .FloatingSize(size).MinSize(size).Show(0))
        
        ## Set winow.Name for inspection.
        plug.Name = name
        
        self.update_pane(name, **props)
        self.show_pane(name, show)
        
        ## Create a menu.
        plug.__Menu_item = None
        
        if not hasattr(module, 'ID_'):  # give a unique index to the module
            global __plug_ID__          # cache ID *not* in [ID_LOWEST(4999):ID_HIGHEST(5999)]
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
                lambda v: v.Check(plug.IsShown()),
            )
            if menu not in self.menubar:
                self.menubar[menu] = []
            self.menubar[menu] += [plug.__Menu_item]
            self.menubar.update(menu)
        return None
    
    def unload_plug(self, name):
        """Unload plugin and detach the pane from UI manager."""
        plug = self.get_plug(name)
        if not plug:
            print(f"- {name!r} is not listed in plugins.")
            return
        
        del self.plugins[plug.Name]
        
        if plug.__Menu_item:
            menu, sep, tail = plug.menukey.rpartition('/')
            menu = menu or Layer.MENU
            self.menubar[menu].remove(plug.__Menu_item)
            self.menubar.update(menu)
        
        if isinstance(plug.Parent, aui.AuiNotebook):
            nb = plug.Parent
            j = nb.GetPageIndex(plug)
            nb.RemovePage(j) # just remove page
            ## nb.DeletePage(j) # Destroys plug object too.
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
    
    def reload_plug(self, name):
        """Reload plugin."""
        plug = self.get_plug(name)
        if not plug:
            print(f"- {name!r} is not listed in plugins.")
            return
        if not plug.reloadable:
            print(f"- {name!r} is not reloadable.")
            return
        
        session = {}
        try:
            print("Reloading {}...".format(plug))
            plug.save_session(session)
        except Exception:
            traceback.print_exc()  # Failed to save the plug session.
        self.load_plug(plug.__module__, force=1, session=session)
    
    def inspect_plug(self, name):
        """Dive into the process to inspect plugs in the shell."""
        plug = self.get_plug(name)
        if not plug:
            print(f"- {name!r} is not listed in plugins.")
            return
        
        shell = self.shellframe.clone_shell(plug)
        
        @shell.handler.bind("shell_activated")
        def init(shell):
            """Called when the plug shell is activated."""
            nonlocal plug
            _plug = self.get_plug(name)
            if _plug is not plug:
                shell.target = _plug or self  # Reset the target to the reloaded plug.
            plug = _plug
        init(shell)
        self.shellframe.Show()
        if wx.GetKeyState(wx.WXK_SHIFT): # open the source code.
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
        """Stop all Layer threads."""
        for plug in self.get_all_plugs():
            thread = plug.thread  # Note: thread can be None or shared.
            if thread and thread.active:
                ## thread.active = 0
                thread.Stop()
    
    ## --------------------------------
    ## load/save index file
    ## --------------------------------
    ATTRIBUTESFILE = "results.index"
    
    def load_index(self, filename=None, view=None):
        """Load frames :ref to the Index file.
        
        If no view given, the currently selected view is chosen.
        """
        if not view:
            view = self.selected_view
        
        if not filename:
            default_path = view.frame.pathname if view.frame else None
            with wx.FileDialog(self, "Select index file to import",
                    defaultDir=os.path.dirname(default_path or ''),
                    defaultFile=self.ATTRIBUTESFILE,
                    wildcard="Index (*.index)|*.index|"
                             "ALL files (*.*)|*.*",
                    style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return None
                filename = dlg.Path
        
        res, mis = self.read_attributes(filename)
        
        paths = [attr['pathname'] for attr in res.values()]
        frames = self.load_buffer(paths, view)
        if frames:
            for frame in frames:
                frame.update_attr(res.get(frame.name))
        
        n = len(frames)
        self.message(
            "{} frames were imported, "
            "{} files were skipped, "
            "{} files are missing.".format(n, len(res)-n, len(mis)))
        print(self.message.read())
        return frames
    
    def save_index(self, filename=None, frames=None):
        """Save frames :ref to the Index file.
        """
        view = self.selected_view
        if not frames:
            frames = view.all_frames
            if not frames:
                return None
        
        if not filename:
            default_path = view.frame.pathname if view.frame else None
            with wx.FileDialog(self, "Select index file to export",
                    defaultDir=os.path.dirname(default_path or ''),
                    defaultFile=self.ATTRIBUTESFILE,
                    wildcard="Index (*.index)|*.index",
                    style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return None
                filename = dlg.Path
        
        savedir = os.path.dirname(filename)
        output_frames = []
        for frame in frames:
            try:
                self.message("Export index of {!r}...".format(frame.name))
                fn = frame.pathname
                if not fn:
                    fn = os.path.join(savedir,
                            re.sub(r'[\/:*?"<>|]', '_', frame.name)) # replace invalid chars
                if not os.path.exists(fn):
                    if not fn.endswith('.tif'):
                        fn += '.tif'
                    self.write_buffer(fn, frame.buffer)
                    frame.pathname = fn
                    frame.name = os.path.basename(fn) # new name and pathname
                output_frames.append(frame)
                print(' ', self.message("\b done."))
            except OSError as e:
                print('-', self.message("\b failed.", e))
        
        frames = output_frames
        res, mis = self.write_attributes(filename, frames)
        n = len(frames)
        self.message(
            "{} frames were exported, "
            "{} files were skipped, "
            "{} files are missing.".format(n, len(res)-n, len(mis)))
        print(self.message.read())
        return frames
    
    ## --------------------------------
    ## load/save frames and attributes
    ## --------------------------------
    
    @classmethod
    def read_attributes(self, filename):
        """Read attributes file."""
        from numpy import nan, inf  # noqa # necessary to eval
        import datetime             # noqa # necessary to eval
        try:
            res = {}
            mis = {}
            savedir = os.path.dirname(filename)
            with open(filename) as i:
                res.update(eval(i.read())) # read res <dict>
            
            for name, attr in tuple(res.items()):
                fn = os.path.join(savedir, name) # search by relpath (dir / name)
                if os.path.exists(fn):
                    attr.update(pathname=fn)  # if found, update pathname
                else:
                    fn = attr.get('pathname') # if not found, try pathname
                    if fn.startswith(r'\\'):
                        warn(f"The pathname of {fn!r} contains network path, "
                             f"so the search may take long time.", stacklevel=3)
                    if not os.path.exists(fn):
                        mis[name] = res.pop(name) # pop missing items
        except FileNotFoundError:
            pass
        except Exception as e:
            print("- Failed to read attributes.", e)
            wx.MessageBox(str(e), style=wx.ICON_ERROR)
        return res, mis
    
    @classmethod
    def write_attributes(self, filename, frames):
        """Write attributes file."""
        try:
            res, mis = self.read_attributes(filename)
            new = dict((x.name, x.attributes) for x in frames)
            
            ## `res` order may differ from that of given frames,
            ## so we take a few steps to merge `new` to be exported.
            res.update(new) # res updates to new info,
            new.update(res) # copy res back keeping new order.
            
            with open(filename, 'w') as o:
                print(pformat(tuple(new.items())), file=o)
            
        except Exception as e:
            print("- Failed to write attributes.", e)
            wx.MessageBox(str(e), style=wx.ICON_ERROR)
        return new, mis
    
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
                    fn = os.path.join(savedir, self.ATTRIBUTESFILE)
                    res, mis = self.read_attributes(fn)
                    savedirs[savedir] = res
                results = savedirs[savedir]
                frame.update_attr(results.get(frame.name))
        return frames
    
    def save_frame(self, path=None, frame=None):
        """Save frame to a file.
        
        Save buffer and the attributes of the frame.
        """
        frame = self.save_buffer(path, frame)
        if frame:
            savedir = os.path.dirname(frame.pathname)
            fn = os.path.join(savedir, self.ATTRIBUTESFILE)
            res, mis = self.write_attributes(fn, [frame])
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
    
    @ignore(ResourceWarning)
    def load_buffer(self, paths=None, view=None):
        """Load buffers from paths to the view window.
        
        If no view given, the currently selected view is chosen.
        """
        if not view:
            view = self.selected_view
        
        if isinstance(paths, str): # for single frame
            paths = [paths]
        
        if paths is None:
            default_path = view.frame.pathname if view.frame else None
            with wx.FileDialog(self, "Open image files",
                    defaultDir=os.path.dirname(default_path or ''),
                    defaultFile='',
                    wildcard='|'.join(self.wildcards),
                    style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST
                                    |wx.FD_MULTIPLE) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return None
                paths = dlg.Paths
        frames = []
        frame = None
        try:
            for i, path in enumerate(paths):
                fn = os.path.basename(path)
                self.message("Loading {!r} ({} of {})...".format(fn, i+1, len(paths)))
                try:
                    buf, info = self.read_buffer(path)
                except Image.UnidentifiedImageError:
                    retvals = self.handler('unknown_format', path)
                    if retvals and any(retvals):
                        continue
                    raise # no context or no handlers or cannot identify image file
                except FileNotFoundError as e:
                    print(e)
                    continue
                
                if isinstance(buf, TiffImageFile) and buf.n_frames > 1: # multi-page tiff
                    n = buf.n_frames
                    d = len(str(n))
                    for j in range(n):
                        self.message("Loading {!r} [{} of {} pages]...".format(fn, j+1, n))
                        buf.seek(j)
                        name = "{:0{d}}-{}".format(j, fn, d=d)
                        frame = view.load(buf, name, show=0)
                else:
                    frame = view.load(buf, fn, show=0, pathname=path, **info)
                    frames.append(frame)
            self.message("\b done.")
        except Exception as e:
            self.message("\b failed.")
            wx.MessageBox(str(e), style=wx.ICON_ERROR)
        
        if frame:
            view.select(frame)
        return frames
    
    def save_buffer(self, path=None, frame=None):
        """Save buffer of the frame to a file.
        """
        view = self.selected_view
        if not frame:
            frame = view.frame
            if not frame:
                return None
        
        if not path:
            default_path = view.frame.pathname if view.frame else None
            with wx.FileDialog(self, "Save buffer as",
                    defaultDir=os.path.dirname(default_path or ''),
                    defaultFile=re.sub(r'[\/:*?"<>|]', '_', frame.name), # replace invalid chars
                    wildcard='|'.join(self.wildcards),
                    style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return None
                path = dlg.Path
        try:
            name = os.path.basename(path)
            self.message("Saving {!r}...".format(name))
            
            self.write_buffer(path, frame.buffer)
            frame.name = name
            frame.pathname = path
            
            self.message("\b done.")
            return frame
        except ValueError:
            ## ValueError('unknown file extension')
            if not path.endswith('.tif'):
                return self.save_buffer(path + '.tif', frame)
            raise
        except Exception as e:
            self.message("\b failed.")
            wx.MessageBox(str(e), style=wx.ICON_ERROR)
            return None
    
    def save_buffers_as_tiffs(self, path=None, frames=None):
        """Save buffers to a file as a multi-page tiff."""
        if not frames:
            frames = self.selected_view.all_frames
            if not frames:
                return None
        
        if not path:
            with wx.FileDialog(self, "Save buffers as a multi-page tiff",
                    defaultFile="Stack-image",
                    wildcard="TIF file (*.tif)|*.tif",
                    style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return None
                path = dlg.Path
        try:
            name = os.path.basename(path)
            self.message("Saving {!r}...".format(name))
            with wx.BusyInfo("One moment please, "
                             "now saving {!r}...".format(name)):
                stack = [Image.fromarray(x.buffer.astype(int)) for x in frames]
                stack[0].save(path,
                              save_all=True,
                              compression="tiff_deflate", # cf. tiff_lzw
                              append_images=stack[1:])
            self.message("\b done.")
            wx.MessageBox("{} files successfully saved into\n{!r}.".format(len(stack), path))
            return True
        except Exception as e:
            self.message("\b failed.")
            wx.MessageBox(str(e), style=wx.ICON_ERROR)
            return False
    
    ## --------------------------------
    ## load/save session
    ## --------------------------------
    session_file = None
    
    def load_session(self, filename=None, flush=True):
        """Load session from file."""
        if not filename:
            with wx.FileDialog(self, 'Load session',
                    wildcard="Session file (*.jssn)|*.jssn",
                    style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST
                                    |wx.FD_CHANGE_DIR) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                filename = dlg.Path
        
        if flush:
            for name in list(self.plugins):  # plugins:dict mutates during iteration
                self.unload_plug(name)
            del self.graph[:]
            del self.output[:]
        
        self.session_file = os.path.abspath(filename)
        
        ## Load the session in the shell.
        self.message("Loading session from {!r}...".format(self.session_file))
        
        shell = self.shellframe.rootshell
        shell.locals.update(
            nan = np.nan,
            inf = np.inf,
        )
        with open(self.session_file) as i:
            shell.Execute(i.read())
        self._mgr.Update()
        self.menubar.reset()
        
        ## Reposition the window if it is not on the desktop.
        if wx.Display.GetFromWindow(self) == -1:
            self.Position = (0, 0)
        
        ## LoadPerspective => 表示状態の不整合．手動でイベントを発生させる．
        for pane in self._mgr.GetAllPanes():
            if pane.IsShown():
                win = pane.window
                if isinstance(win, aui.AuiNotebook):
                    win = win.CurrentPage
                win.handler('page_shown', win)
        
        self.message("\b done.")
    
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
        
        self.message("Saving session to {!r}...".format(self.session_file))
        
        with open(self.session_file, 'w') as o,\
          np.printoptions(threshold=np.inf):  # printing all(inf) elements
            o.write("#! Session file (This file is generated automatically)\n")
            o.write("self.SetSize({})\n".format(self.Size))
            o.write("self.SetPosition({})\n".format(self.Position))
            
            for name, module in self.plugins.items():
                plug = self.get_plug(name)
                if '.' not in name:
                    name = module.__file__  # Replace the name with full path.
                    if hasattr(module, '__path__'):  # is the module a package?
                        name = os.path.dirname(name)
                session = {}
                try:
                    plug.save_session(session)
                except Exception:
                    traceback.print_exc()  # Failed to save the plug session.
                o.write("self.load_plug({!r}, session={})\n".format(name, session or None))
            o.write("self._mgr.LoadPerspective({!r})\n".format(self._mgr.SavePerspective()))
            
            def _save(view):
                paths = [x.pathname for x in view.all_frames if x.pathname]
                o.write(f"self.{view.Name}.unit = {view.unit:g}\n")
                o.write(f"self.load_frame({paths!r}, self.{view.Name})\n")
                try:
                    if view.frame.pathname in paths:
                        o.write(f"self.{view.Name}.select({view.frame.name!r})\n")
                except Exception:
                    pass
            
            _save(self.graph)
            _save(self.output)
        
        self.message("\b done.")
