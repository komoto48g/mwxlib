#! python
# -*- coding: utf-8 -*-
"""Graph manager

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
from __future__ import division, print_function
from __future__ import unicode_literals
from __future__ import absolute_import
from collections import OrderedDict
from pprint import pprint, pformat
import subprocess
import threading
import traceback
import inspect
## import codecs
import sys
import os
import platform
import re
import wx
from wx import aui
## import wx.lib.agw.aui as aui
import numpy as np
from . import framework as mwx
from .controls import Icon
from .controls import ControlPanel
from .matplot2g import GraphPlot
from .matplot2lg import Histogram
## from matplotlib import pyplot as plt
## from matplotlib import colors
## from matplotlib import cm
from PIL import Image
from PIL import ImageFile
from PIL.TiffImagePlugin import TiffImageFile

try:
    from importlib import reload
except ImportError:
    pass

LITERAL_TYPE = (str,) if sys.version_info >= (3,0) else (str,unicode)



class Thread(object):
    """Thread for graphman.Layer
    The thread `worker runs the given method `target which is bound to `owner object.
    The `target must be a method bound to an instance (__self__) of Layer, not staticmethod.
    
    is_active : flag of being kept going
                Check this to see the thread is running and intended being kept going
   is_running : flag of being running now
                Watch this to verify the worker is alive after it has been inactivated
    """
    is_active = property(lambda self: self.__keepGoing)
    is_running = property(lambda self: self.__isRunning)
    
    flag = property(lambda self: self.__flag)
    
    def check(self, timeout=None):
        """Wait flag or interrupt the process
        The caller pauses the thread (flag.clear) and calls check.
        The chequer waits for the flag to be set.
        """
        ## The event.wait returns immediately when it is True (:set)
        ## and blocks until the internal flag is True when it is False (:clear)
        try:
            if not self.__flag.wait(timeout):
                raise KeyboardInterrupt("timeout")
            if not self.is_active:
                raise KeyboardInterrupt("terminated by user")
        finally:
            self.__flag.set()
    
    def pause(self, msg=""):
        """Pause the process where called
        The caller should check the retval and decide whether to stop the thread.
        """
        try:
            self.__flag.clear()
            if wx.MessageBox(msg + "\n"
                "\n Press [OK] to continue."
                "\n Press [CANCEL] to terminate the process.",
                style = wx.OK|wx.CANCEL|wx.ICON_WARNING) != wx.OK:
                    ## self.Stop() # 必要があれば呼び出し側で行う
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
    
    def __del__(self):
        if self.is_active:
            self.Stop()
    
    def __enter__(self):
        f = inspect.currentframe().f_back
        m = inspect.getmodule(f)
        if not self.is_active:
            raise Warning("The thread is not running (cannot enter {})".format(f.f_code.co_name))
        
        event = "{}:{}:enter".format(m.__name__, f.f_code.co_name)
        self.owner.handler(event, self)
    
    def __exit__(self, t, v, tb):
        f = inspect.currentframe().f_back
        m = inspect.getmodule(f)
        if t:
            ## print("Thread:exception: {!r}".format(v))
            ## print("Traceback:\n{}".format(''.join(traceback.format_tb(tb))))
            ## 
            event = "{}:{}:error".format(m.__name__, f.f_code.co_name)
            self.owner.handler(event, self)
        
        event = "{}:{}:exit".format(m.__name__, f.f_code.co_name)
        self.owner.handler(event, self)
    
    def __call__(self, f, *args, **kwargs):
        """Decorator of thread starter function
        Note: event args *v are ignored when decorated by this call
        """
        def _f(*v):
            return self.Start(f, *(v+args), **kwargs)
        _f.__name__ = f.__name__
        _f.__doc__ = f.__doc__
        return _f
    
    def Start(self, f, *args, **kwargs):
        if not f:
            return lambda f: self.Start(f, *args, **kwargs)
        
        def _f(*args, **kwargs):
            try:
                self.owner.handler('thread_begin', self)
                self.result = f(*args, **kwargs)
                
            except Warning as e:
                print("- Thread:execution stoped: {}".format(e))
                
            except KeyboardInterrupt as e:
                print("- Thread:execution stoped: {}".format(e))
                
            except Exception as e:
                traceback.print_exc()
                print("- Thread:exception occurred in {!r}: {!r}".format(mwx.typename(f), e))
                self.owner.handler('thread_error', self)
                
            finally:
                self.__keepGoing = self.__isRunning = 0
                self.owner.handler('thread_end', self)
        
        if self.__isRunning:
            wx.MessageBox("The thread is running (Press C-g to quit).", style=wx.ICON_WARNING)
            return
        
        if not self.owner:
            self.owner = f.__self__
        self.target = f
        self.result = None
        self.__keepGoing = self.__isRunning = 1
        self.worker = threading.Thread(target=_f, args=args, kwargs=kwargs)
        ## self.worker.setDaemon(True)
        self.worker.start()
        return self
    
    @mwx.postcall
    def Stop(self):
        self.__keepGoing = 0
        if self.__isRunning:
            busy = wx.BusyInfo("One moment please, now waiting for threads to die...")
            self.owner.handler('thread_quit', self)
            self.worker.join(1)
            ## sys.exit(1)


class Layer(ControlPanel):
    """Graphman.Layer
    
      menu : menu string in parent menubar
   menustr : menu-item string in parent menubar
  category : title of notebook holder, otherwise None for single pane
   caption : flag to set the pane caption to be visible (default caption is __module__)
             a string can also be specified
  dockable : flag to set the pane to be dockable
  dock_dir : docking direction (1:top, 2:right, 3:bottom, 4:left, *5:center) or None as it is
reloadable : flag to set the layer to be reloadable
unloadable : flag to set the layer to be unloadable
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
    dock_dir = None
    editable = True # to be deprecated
    reloadable = True
    unloadable = True
    
    parent = property(lambda self: self.__parent)
    message = property(lambda self: self.__parent.statusbar)
    
    graph = property(lambda self: self.__parent.graph)
    output = property(lambda self: self.__parent.output)
    histogram = property(lambda self: self.__parent.histogram)
    selected_view = property(lambda self: self.__parent.selected_view)
    
    ## Thread = Thread
    thread = None # as worker<Thread>
    
    handler = property(lambda self: self.__handler)
    
    @property
    def Arts(self):
        """List of arts <matplotlib.artist.Artist> drawn on the graph or output window"""
        return self.__artists
    
    @Arts.setter
    def Arts(self, arts):
        for art in self.__artists:
            art.remove()
        self.__artists = arts or []
    
    @Arts.deleter
    def Arts(self):
        self.Arts = []
    
    def __init__(self, parent, **kwargs):
        if parent:
            ControlPanel.__init__(self, parent, size=(130,24)) # keep minimum size
        
        self.__parent = parent #= self.Parent, but not always if whose son is floating
        self.__artists = []
        self.__handler = mwx.FSM({0:{}})
        
        self.handler.update({ #<graphman.Layer handler>
            None : {
                 'thread_begin' : [ None ], # thread begins processing
                   'thread_end' : [ None ], # thread closed processing
                  'thread_quit' : [ None ], # terminated by user
                 'thread_error' : [ None ], # failed in error
                  'pane_loaded' : [ None ],
                   'pane_shown' : [ None, lambda: self.Draw(True), lambda: self.Activate(True), ],
                  'pane_hidden' : [ None, lambda: self.Draw(False) ],
                  'pane_closed' : [ None, lambda: self.Draw(False), lambda: self.Activate(False), ],
                 'pane_removed' : [ None ],
            },
        })
        
        ## ControlPanel.Menu (override)
        self.Menu = [
            (wx.ID_COPY, "&Copy params\t(C-c)", "Copy params",
                lambda v: self.copy_to_clipboard()),
                
            (wx.ID_PASTE, "&Paste params\t(C-v)", "Read params",
                lambda v: self.paste_from_clipboard()),
            (),
            (wx.ID_RESET, "&Reset params", "Reset params", Icon('-'),
                lambda v: (self.Draw(False), self.reset_params())),
        ]
        if self.editable: self.Menu += [
            (),
            (wx.ID_EDIT, "&Edit module", "Edit module src", Icon('pen'),
                lambda v: self.parent.edit_plug(self.__module__),
                lambda v: v.Enable(self.editable)),
                
            (mwx.ID_(201), "&Reload module", "Reload module", Icon('load'),
                lambda v: self.parent.load_plug(self.__module__,
                            show=1, force=1, session=self.get_current_session()),
                lambda v: v.Enable(self.reloadable
                            and not (self.thread and self.thread.is_active))),
                
            (mwx.ID_(202), "&Unload module", "Unload module", Icon('delete'),
                lambda v: self.parent.unload_plug(self.__module__),
                lambda v: v.Enable(self.unloadable
                            and not (self.thread and self.thread.is_active))),
        ]
        self.Menu += [
            (),
            (mwx.ID_(203), "&Dive into {!r}".format(self.__module__), "deb", Icon('core'),
                lambda v: self.parent.inspect_plug(self.__module__)),
        ]
        
        @mwx.connect(self, wx.EVT_WINDOW_DESTROY)
        def destroy(evt):
            if self.thread and self.thread.is_active:
                self.thread.Stop()
            del self.Arts
            evt.Skip()
        
        try:
            self.Init()
            
            session = kwargs.get('session')
            if session is not None:
                wx.CallAfter(self.set_current_session, session)
            
        except RuntimeError:
            if parent: # unless stand-alone Layer <wx.Window> object is intended ?
                raise
            
        except Exception as e:
            traceback.print_exc()
            if parent:
                bmp = wx.StaticBitmap(self, bitmap=Icon('!!!'))
                txt = wx.StaticText(self, label="Exception")
                txt.SetToolTip(repr(e))
                self.layout(None, (bmp, txt), row=2)
    
    def Init(self):
        """Initialize me safely (to be overrided)"""
        pass
    
    def get_current_session(self):
        """Return settings to be saved in session file (to be overrided)"""
        pass
    
    def set_current_session(self, session):
        """Restore settings to be loaded from session file (to be overrided)"""
        pass
    
    def IsShown(self):
        return self.parent.get_pane(self).IsShown()
    
    def Show(self, show=True):
        """Show the pane accociated to the plug"""
        self.parent.show_pane(self, show)
    
    ## def IsDrawn(self):
    ##     return any(art.get_visible() for art in self.Arts)
    
    def Draw(self, show=True):
        """Draw arts in the view
        Called when shown, hidden, and closed"""
        if not self.Arts:
            return
        try:
            for art in self.Arts:
                art.set_visible(show)
            
            ## Arts may be belonging to either graph, output, and any other window.
            ## where we can access to the canvas of the art as, though complicated,
            art.axes.figure.canvas.draw_idle()
            
        except RuntimeError as e:
            print("- {}: Arts failed drawing on".format(self.__module__), e)
            del self.Arts
    
    def Activate(self, show=True):
        """Activate the layer (to be overrided)
        Called when shown or closed"""
        pass
    
    def Destroy(self):
        """Kill me softly (to be overrided)"""
        return ControlPanel.Destroy(self)


class Graph(GraphPlot):
    """GraphPlot (override) to better make use for graph manager
    """
    parent = property(lambda self: self.__parent)
    loader = property(lambda self: self.__loader)
    
    def __init__(self, parent, loader=None, **kwargs):
        GraphPlot.__init__(self, parent, **kwargs)
        
        self.__parent = parent
        self.__loader = loader or parent
        
        self.handler.append({ #<Graph handler>
            None : {
                   'f5 pressed' : [ None, self.refresh ],
                  'frame_shown' : [ None, self.update_infobar ],
              'shift+a pressed' : [ None, self.toggle_infobar ],
             'canvas_focus_set' : [ None, lambda v: self.loader.select_view(self) ],
            },
        })
        ## ドロップターゲットを許可する
        self.SetDropTarget(MyFileDropLoader(self, loader=self.loader))
    
    def refresh(self, evt):
        if self.frame:
            self.frame.update_buffer()
            self.draw()
    
    def toggle_infobar(self, evt):
        """Toggle infobar (frame.annotation)"""
        if self.frame:
            if self.infobar.IsShown():
                self.infobar.Dismiss()
            else:
                self.infobar.ShowMessage(str(self.frame.annotation))
                ## wx.CallLater(4000, self.infobar.Dismiss) # dismiss in time automatically
    
    def update_infobar(self, frame):
        """Show infobar (frame.annotation)"""
        if self.frame:
            if self.infobar.IsShown():
                self.infobar.ShowMessage(str(self.frame.annotation))
    
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
    def __init__(self, target, loader):
        wx.FileDropTarget.__init__(self)
        self.__target = target
        self.__loader = loader
    
    def OnDropFiles(self, x, y, filenames):
        target = self.__target
        loader = self.__loader
        pos = target.ScreenPosition + (x,y)
        if isinstance(target, Frame):
            target = None
        paths = []
        for path in filenames:
            name, ext = os.path.splitext(path)
            if ext == '.py' or os.path.isdir(path):
                loader.load_plug(path, show=1, floating_pos=pos,
                                       force=wx.GetKeyState(wx.WXK_ALT))
            elif ext == '.jssn':
                loader.load_session(path)
            elif ext == '.results' or not ext:
                loader.load_file(path, target)
            else:
                paths.append(path) # image file just stacks to be loaded
        if paths:
            loader.load_frame(paths, target)
        return True


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
    
    ## @property
    ## def selected_graphic_window(self):
    ##     """currently focused graphic window
    ##     if no focus has any graphic windows, the main graph is returned
    ##     """
    ##     return next((w for w in self.__graphic_windows
    ##                 if w.canvas.HasFocus()), self.graph)
    
    @property
    def graphic_windows(self):
        """graphic windows list
        including [0] graph [1] output [2:] others(user-defined)
        """
        return self.__graphic_windows
    
    @property
    def graphic_windows_on_screen(self):
        return [w for w in self.__graphic_windows if w.IsShownOnScreen()]
    
    def __init__(self, *args, **kwargs):
        mwx.Frame.__init__(self, *args, **kwargs)
        
        #<wx.aui.AuiManager> <wx.aui.AuiPaneInfo>
        self._mgr = aui.AuiManager()
        self._mgr.SetManagedWindow(self)
        self._mgr.SetDockSizeConstraint(0.5, 0.5)
        
        ## self._mgr.SetAutoNotebookStyle(
        ##     agwStyle = aui.AUI_NB_SMART_TABS|aui.AUI_NB_TAB_MOVE|aui.AUI_NB_TAB_SPLIT
        ##       |aui.AUI_NB_TAB_FLOAT|aui.AUI_NB_TAB_EXTERNAL_MOVE|aui.AUI_NB_SCROLL_BUTTONS
        ##     &~(aui.AUI_NB_CLOSE_ON_ACTIVE_TAB|aui.AUI_NB_CLOSE_BUTTON|aui.AUI_NB_SUB_NOTEBOOK)
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
                
            (wx.ID_SAVE, "&Save\tCtrl-s", "Save buffer as", Icon('save'),
                lambda v: self.save_frame(),
                lambda v: v.Enable(self.__view.frame is not None)),
            
            (wx.ID_SAVEAS, "&Save as tiffs", "Save buffers as a statck-tiff", Icon('saveas'),
                lambda v: self.save_buffers_as_tiffs(),
                lambda v: v.Enable(self.__view.frame is not None)),
            (),
            (mwx.ID_(11), "&Import index", "Import buffers and attributes", Icon('open'),
                lambda v: self.import_index()),
                
            (mwx.ID_(12), "&Export index", "Export buffers and attributes", Icon('saveas'),
                lambda v: self.export_index(),
                lambda v: v.Enable(self.selected_view.frame is not None)),
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
                
            (mwx.ID_(25), "&Invert Color\tCtrl-i", "Invert colormap", wx.ITEM_CHECK,
                lambda v: self.__view.invert_cmap(),
                lambda v: v.Check(self.__view.get_cmap()[-2:] == "_r")),
        ]
        ## def cmenu(name, i):
        ##     return (30+i, "&"+name, name, wx.ITEM_CHECK,
        ##         lambda v: self.__view.set_cmap(name),
        ##         lambda v: v.Check(self.__view.get_cmap() == name
        ##                        or self.__view.get_cmap() == name+"_r"),
        ##     )
        ## lscm = [c for c in dir(cm) if c[-2:] != "_r"
        ##         and isinstance(getattr(cm,c), colors.LinearSegmentedColormap)]
        ## 
        ## self.menubar["Edit"] += [
        ##     (mwx.ID_(26), "Default Color", "gray scale", wx.ITEM_CHECK,
        ##         lambda v: self.__view.set_cmap('gray'),
        ##         lambda v: v.Check(self.__view.get_cmap()[:4] == "gray")),
        ##         
        ##     ("Standard Color", [cmenu(c,i) for i,c in enumerate(lscm) if c.islower()]),
        ##     ("+Another Color", [cmenu(c,i) for i,c in enumerate(lscm) if not c.islower()]),
        ## ]
        self.menubar[Layer.menu] = [ # Plugins menu
            (mwx.ID_(100), "&Load Plugs", "Load plugins", Icon('load'),
                self.OnLoadPlugins),
            
            (mwx.ID_(101), "&Quit Plugs\tCtrl-g", "Stop all plugin threads", Icon('exit'),
                self.Quit),
            (),
        ]
        self.menubar.reset()
        
        ## フレーム変更時の描画設定
        self.graph.handler.append({ #<Graph handler>
            None : {
                  'frame_shown' : [ None, self.OnShowFrame ],
                 'frame_loaded' : [ None, lambda v: self.show_pane("graph") ],
               'frame_modified' : [ None, lambda v: self.show_pane("graph") ],
               'frame_selected' : [ None, self.OnShowFrame ],
                  'canvas_draw' : [ None, lambda v: self.sync(self.graph, self.output) ],
            }
        })
        self.output.handler.append({ #<Graph handler>
            None : {
                  'frame_shown' : [ None, self.OnShowFrame ],
                 'frame_loaded' : [ None, lambda v: self.show_pane("output") ],
               'frame_modified' : [ None, lambda v: self.show_pane("output") ],
               'frame_selected' : [ None, self.OnShowFrame ],
                  'canvas_draw' : [ None, lambda v: self.sync(self.output, self.graph) ],
            }
        })
        
        ## コンテキストメニューに追加
        ## self.graph.Menu += self.menubar["File"][3:5]
        self.graph.Menu += self.menubar["Edit"][2:8]
        
        ## self.output.Menu += self.menubar["File"][3:5]
        self.output.Menu += self.menubar["Edit"][2:8]
        
        ## その他
        self._mgr.Bind(aui.EVT_AUI_PANE_CLOSE, self.OnPaneClose)
        
        self.Bind(wx.EVT_CLOSE, self.OnCloseFrame)
        
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
        if isinstance(f, type(sys)):
            name, ext = os.path.splitext(f.__file__)
            f = name + '.py'
        subprocess.Popen('{} "{}"'.format(self.Editor, f))
    
    def OnShowFrame(self, frame):
        self.SetTitle("{}@{} - [{}] {}".format(
            self.__class__.__name__,
            platform.node(),
            os.path.splitext(os.path.basename(self.session_file or '--'))[0],
            (frame.pathname or frame.name) if frame else '',
        ))
    
    def OnCloseFrame(self, evt): #<wx._core.CloseEvent>
        with wx.MessageDialog(None, "Do you want to save session before closing program?",
            "{}@{} - [{}]".format(self.__class__.__name__,
                            platform.node(), os.path.basename(self.session_file or '--')),
            style=wx.YES_NO|wx.CANCEL|wx.ICON_INFORMATION) as dlg:
            ret = dlg.ShowModal()
            if ret == wx.ID_YES:
                if not self.save_session():
                    return
            elif ret == wx.ID_CANCEL:
                return
            evt.Skip()
    
    def Destroy(self):
        for pane in self._mgr.GetAllPanes():
            pane.window.Destroy()
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
        elif isinstance(name, Layer):
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
        
        ## (shift + menu) reset floating position of a stray window
        if wx.GetKeyState(wx.WXK_SHIFT) and name != "graph":
            
            ## (alt + shift + menu) reload plugin
            if wx.GetKeyState(wx.WXK_ALT):
                plug = self.get_plug(name)
                if isinstance(plug, Layer):
                    self.load_plug(name, show=1, force=plug.reloadable)
                    pane = self.get_pane(name)
            
            ## (ctrl + shift + menu) reset floating position of a stray window
            if wx.GetKeyState(wx.WXK_CONTROL):
                pane.floating_pos = wx.GetMousePosition()
            show = True
        
        ## for Layers only 
        plug = self.get_plug(name)
        
        if isinstance(plug, Layer):
            nb = plug.__notebook
            if nb:
                nb.SetSelection(nb.GetPageIndex(plug))
        
        if show and not pane.IsShown(): plug.handler('pane_shown')
        elif not show and pane.IsShown(): plug.handler('pane_closed')
        
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
        
        docking = kwargs.get('docking')
        if docking:
            pane.dock_direction = docking
            pane.Dock()
        else:
            pane.Float()
        
        ## for Layers only (graph window has not plug.constants)
        plug = self.get_plug(name)
        
        if isinstance(plug, Layer):
            if isinstance(plug.caption, LITERAL_TYPE) and not plug.category:
                pane.CaptionVisible(1)
                pane.Caption(plug.caption)
            else:
                pane.CaptionVisible(bool(plug.caption))
            pane.Gripper(not plug.caption) # if no caption, grip
            pane.Dockable(plug.dockable)
            if plug.dockable and plug.dock_dir: # ドッキング可能でその方向が指定されていれば
                pane.Direction(plug.dock_dir)   # その指定方向を優先する
                pane.Dock()
            
            nb = plug.__notebook
            if nb:
                nb.SetSelection(nb.GetPageIndex(plug))
                
        if show and not pane.IsShown(): plug.handler('pane_shown')
        elif not show and pane.IsShown(): plug.handler('pane_closed')
        
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
    ## plugins(layer) interface
    ## --------------------------------
    plugins = property(lambda self: self.__plugins)
    
    __new_ID_ = 1001 # use ID_ *not* in [ID_LOWEST(4999):ID_HIGHEST(5999)]
    
    def require(self, name):
        """Get named plug window
        If not found, try to load it once.
        
        Note: when called in thread, the display of AuiPane might be broken.
        In that case, Select menu with [C-M-S] to reload after the thread exits.
        """
        plug = self.get_plug(name)
        if plug is None:
            try:
                ret = self.load_plug(name) # スレッド中に AuiPane の表示がおかしくなる ?
            except Exception:
                return # ignore load failure, ret nil
            return self.get_plug(name)
        return plug
    
    def get_plug(self, name):
        """Find named plug window in registred plugins"""
        if name in self.plugins:
            return self.plugins[name].__plug__
        if isinstance(name, Layer):
            return name
        return self._mgr.GetPane(name).window
    
    def load_plug(self, root, show=False,
            docking=False, layer=0, pos=0, row=0, prop=10000,
            floating_pos=None, floating_size=None, force=False, **kwargs):
        """Load plugin module
        The module `root must have 'class Plugin' derived from <mwx.graphman.Layer>
        
        root : Layer object, module, or `name of module
        show : the pane is to be shown when loaded
     docking : dock_direction (1:top,2:right,3:bottom,4:left, 0 or False:Float)
       force : force loading even when it were already loaded
       layer : docking layer
         pos : docking position
         row : docking row position
        prop : docking proportion < 1e6 ?
     floating_pos/size : for floating window
        """
        if isinstance(root, type(sys)): #<type 'module'>
            root = root.__file__
        
        if isinstance(root, Layer):
            root = root.__module__
        
        root = os.path.normpath(root)
        dirname = os.path.dirname(root)
        name = os.path.basename(root)
        if root.endswith(".py") or root.endswith(".pyc"):
            name, ext = os.path.splitext(name)
        
        pane = self.get_pane(name)
        
        if pane.IsOk(): # [name] がすでに登録されている
            if not force:
                self.update_pane(name, show=show,
                    docking=docking, layer=layer, pos=pos, row=row, prop=prop,
                    floating_pos=floating_pos, floating_size=floating_size
                )
                session = kwargs.get('session') # session が指定されていれば優先
                if session:
                    plug = self.get_plug(name)
                    plug.set_current_session(session)
                return
            
            show = show or pane.IsShown()
            docking = pane.IsDocked() and pane.dock_direction
            layer = pane.dock_layer
            pos = pane.dock_pos
            row = pane.dock_row
            prop = pane.dock_proportion
            floating_pos = floating_pos or pane.floating_pos[:] # copy (!pane is to be unloaded)
            floating_size = floating_size or pane.floating_size[:] # copy
        
        if os.path.isdir(dirname): # to import name
            if dirname in sys.path:
                sys.path.remove(dirname) # インクルードパスの先頭に移動するためにいったん削除
            sys.path.insert(0, dirname) # インクルードパスの先頭に追加する
        
        ## if os.path.isdir(root): # when if root:module is a package
        ##     if root in sys.path:
        ##         sys.path.remove(root)
        ##     sys.path.insert(0, root)
        
        try:
            self.statusbar("Loading plugin {!r}...".format(name))
            if name in sys.modules:
                module = reload(sys.modules[name])
            else:
                module = __import__(name, fromlist=[''])
            
        except ImportError as e:
            print(self.statusbar("\b failed to import: {}".format(e)))
            return False
        
        try:
            if pane.IsOk() and force:
                self.unload_plug(name) # 一旦アンロードする
            
            ## To refer the module in Plugin.Init, add to the list in advance with the constructor
            ## self.plugins[name] = module
            
            ## Create a plug and register to plugins list プラグインのロード開始
            plug = module.Plugin(self, **kwargs)
            
            ## set reference of a plug (one module, one plugin)
            module.__plug__ = plug
            
            ## rename when if root:module is a package
            name = plug.__module__
            
            ## when the plug is created successfully, add to the list
            self.plugins[name] = module
            
            plug.handler('pane_loaded')
            
            ## create a pane or notebook pane
            caption = plug.caption if isinstance(plug.caption, LITERAL_TYPE) else name
            title = plug.category
            if title:
                pane = self._mgr.GetPane(title)
                if pane.IsOk():
                    nb = pane.window
                    if not isinstance(nb, aui.AuiNotebook):
                        ## AuiManager .Name をダブって登録することはできない
                        ## Notebook.title (category) はどのプラグインとも別名にすること
                        raise NameError("Notebook name must not be the same as any other plugins")
                    show = pane.IsShown()
                else:
                    size = plug.GetSize() + (2,30)
                    nb = aui.AuiNotebook(self,
                        style = (aui.AUI_NB_DEFAULT_STYLE|aui.AUI_NB_BOTTOM)
                              &~(aui.AUI_NB_CLOSE_ON_ACTIVE_TAB|aui.AUI_NB_MIDDLE_CLICK_CLOSE))
                    self._mgr.AddPane(nb, aui.AuiPaneInfo()
                        .Name(title).Caption(title).FloatingSize(size).MinSize(size).Show(0))
                    
                    @mwx.connect(nb, aui.EVT_AUINOTEBOOK_TAB_RIGHT_DOWN)
                    def show_menu(evt): #<wx._aui.AuiNotebookEvent>
                        ## nb.SetSelection(evt.Selection)
                        plug = nb.GetPage(evt.Selection)
                        mwx.Menu.Popup(nb, plug.Menu)
                    
                    @mwx.connect(nb, aui.EVT_AUINOTEBOOK_PAGE_CHANGED)
                    def on_page_changed(evt): #<wx._aui.AuiNotebookEvent>
                        nb.CurrentPage.handler('pane_shown')
                        evt.Skip()
                    
                    @mwx.connect(nb, aui.EVT_AUINOTEBOOK_PAGE_CHANGING)
                    def on_page_changing(evt): #<wx._aui.AuiNotebookEvent>
                        plug = nb.GetPage(evt.Selection)
                        if nb.CurrentPage:
                            if nb.CurrentPage is not plug:
                                nb.CurrentPage.handler('pane_hidden')
                        evt.Skip() # must skip to the next handler, but called twice when click?
                    
                nb.AddPage(plug, caption)
                
                j = nb.GetPageIndex(plug)
                nb.SetPageToolTip(j, "[{}]\n{}".format(plug.__module__, plug.__doc__))
                nb.SetSelection(j)
                
            else:
                nb = None
                size = plug.GetSize() + (2,2)
                self._mgr.AddPane(plug, aui.AuiPaneInfo()
                    .Name(name).Caption(caption).FloatingSize(size).MinSize(size).Show(0))
            
            ## set reference of notebook (optional)
            plug.__notebook = nb
            
            self.update_pane(name, show=show,
                docking=docking, layer=layer, pos=pos, row=row, prop=prop,
                floating_pos=floating_pos, floating_size=floating_size
            )
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
                self.menubar[plug.menu] += [plug.__Menu_item]
                self.menubar.update(plug.menu)
            
            self.statusbar("\b done.")
            
        except Exception as e:
            self.statusbar("\b failed: {!r}".format(e))
            wx.CallAfter(wx.MessageBox, traceback.format_exc(),
                caption="Error in loading {!r}".format(name), style=wx.ICON_ERROR)
            traceback.print_exc()
            return False
    
    def unload_plug(self, name):
        """Unload plugin module and detach the pane from UI manager"""
        try:
            ## self.statusbar("Unloading plugin {!r}...".format(name))
            plug = self.get_plug(name)
            if name in self.plugins:
                del self.plugins[name]
            
            nb = plug.__notebook
            if nb:
                j = nb.GetPageIndex(plug)
                nb.RemovePage(j) # just remove page
                ## nb.DeletePage(j) # cf. destroy plug object too
            
            if plug.menu:
                self.menubar[plug.menu].remove(plug.__Menu_item)
                self.menubar.update(plug.menu)
            
            self._mgr.DetachPane(plug)
            self._mgr.Update()
            
            plug.handler('pane_closed')
            plug.handler('pane_removed')
            plug.Destroy()
            
            if nb and not nb.PageCount:
                self._mgr.DetachPane(nb) # detach notebook pane
                self._mgr.Update()
                nb.Destroy()
            
        except Exception as e:
            ## self.statusbar("\b failed: {!r}".format(e))
            traceback.print_exc()
    
    def edit_plug(self, name):
        self.edit(self.plugins[name])
    
    def inspect_plug(self, name):
        """Dive into the process to inspect plugs in the shell
        
        The plugins and modules are to be reloaded and lost, so we accessed as property.
        l: plugin  (cf. lm.__plug__)
        lm: module (cf. l.__module__ @sys.modules.get)
        """
        self.__class__.l = property(lambda self: self.get_plug(name))
        self.__class__.lm = property(lambda self: self.plugins.get(name))
        
        shell = self.inspector.shell
        shell.clearCommand()
        shell.SetFocus()
        shell.write(
            "#include plug {!r} as propperty:\n"
            "<-- self.l : {!r}\n"
            "<-- self.lm : {!r}\n".format(name, self.l, self.lm))
        shell.prompt()
        ## self.inspector.Show()
        
        shell = self.inspector.shell.clone(self.l)
        
        @shell.handler.bind("shell_activated")
        def init(shell):
            shell.target = self.get_plug(name)
        init(shell)
    
    def OnLoadPlugins(self, evt):
        with wx.FileDialog(self, "Load a plugin file",
            wildcard="Python file (*.py)|*.py",
            style=wx.FD_OPEN|wx.FD_MULTIPLE|wx.FD_FILE_MUST_EXIST) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                for path in dlg.Paths:
                    self.load_plug(path)
    
    def Quit(self, evt):
        """Stop all Layer.thread"""
        ## threads = [t for t in threading.enumerate() if t.name != 'MainThread']
        for name in self.plugins:
            plug = self.get_plug(name)
            if plug.thread and plug.thread.is_active:
                plug.thread._Thread__keepGoing = 0 # is_active=False 直接切り替える
                plug.thread.Stop() # @postcall なのですぐに止まらない
    
    ## --------------------------------
    ## load/save index file
    ## --------------------------------
    
    def load_file(self, path, target):
        ## e = ("Unknown file type: {}\n"
        ##      "Dropped to the target: {}".format(path, target))
        ## wx.MessageBox(str(e), style=wx.ICON_ERROR)
        return self.import_index(path, target)
    
    def import_index(self, f=None, target=None):
        """Load frames :ref to the Attributes file
        """
        if not target:
            target = self.selected_view
        
        if not f:
            with wx.FileDialog(self, "Select path to import",
                defaultFile=self.ATTRIBUTESFILE,
                wildcard="Attributes (*.results)|*.results",
                style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                f = dlg.Path
        
        res, mis = self.read_attributes(f)
        
        paths = [attr['pathname'] for attr in res.values()]
        frames = self.load_buffer(paths, target) or []
        for frame in frames:
            frame.update_attributes(res.get(frame.name))
        
        self.statusbar(
            "{} frames were imported, "
            "{} files are missing.".format(len(res), len(mis)))
        return True
    
    def export_index(self, f=None, frames=None):
        """Save frames :ref to the Attributes file
        """
        if frames is None:
            frames = self.selected_view.all_frames
            if not frames:
                return
        
        if not f:
            with wx.FileDialog(self, "Select path to export",
                defaultFile=self.ATTRIBUTESFILE,
                wildcard="Attributes (*.results)|*.results",
                style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                f = dlg.Path
        
        savedir = os.path.dirname(f)
        for frame in frames:
            name = re.sub("[\\/:*?\"<>|]", '_', frame.name) # normal-basename
            path = os.path.join(savedir, name)
            if not os.path.exists(path):
                if not path.endswith('.tif'):
                    path += '.tif'
                self.save_buffer(path, frame)
        
        res, mis = self.write_attributes(f, frames)
        
        self.statusbar(
            "{} frames were exported, "
            "{} files are missing.".format(len(res), len(mis)))
        return True
    
    ## --------------------------------
    ## load/save frames and attributes 
    ## --------------------------------
    ATTRIBUTESFILE = "index.results"
    
    @classmethod
    def read_attributes(self, f):
        """Read attributes file"""
        from numpy import nan,inf
        import datetime
        try:
            res = OrderedDict()
            mis = OrderedDict()
            savedir = os.path.dirname(f)
            
            with open(f) as i:
                res.update(eval(i.read())) # restore (locals: datetime, nan, inf)
            
            for name, attr in tuple(res.items()):
                path = os.path.join(savedir, name)
                if not os.path.exists(path): # check & pop missing files
                    ## print("- {!r} in the record is missing... pass".format(name))
                    res.pop(name)
                    mis.update({name:attr})
                else:
                    attr.update(pathname=path)
        except FileNotFoundError:
            pass
        except Exception as e:
            print("- Failed to read attributes:", e)
            pass
        finally:
            return res, mis # finally raise no exceptions
    
    @classmethod
    def write_attributes(self, f, frames):
        """Write attributes file"""
        try:
            res, mis = self.read_attributes(f)
            new = OrderedDict((x.name, x.attributes) for x in frames)
            
            ## res order may differ from that of given new frames.
            ## OrderedDict does not change the order even when updated,
            ##   so we take a few steps to update results to be exported.
            newres = new.copy()
            res.update(new) # res updates to new info,
            new.update(res) # copy res back keeping new order.
            
            with open(f, 'w') as o:
                pprint(tuple(new.items()), stream=o) # save all attributes
            
        except Exception as e:
            print("- Failed to write attributes:", e)
            pass
        finally:
            return newres, mis
    
    def load_frame(self, paths=None, target=None):
        """Load frame(s) from paths to the target window
        
        Call load_buffer and load the attributes of the frame(s).
        If the file names duplicate, the latter takes priority.
        """
        frames = self.load_buffer(paths, target)
        if frames:
            ls = [os.path.dirname(frame.pathname) for frame in frames]
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
        
        Call save_buffer and save the attributes of the frame.
        """
        frame = self.save_buffer(path, frame)
        if frame:
            savedir = os.path.dirname(frame.pathname)
            f = os.path.join(savedir, self.ATTRIBUTESFILE)
            res, mis =self.write_attributes(f, [frame])
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
        """Read buffer from `path file (to be overrided)"""
        if sys.version_info < (3,0):
            path = path.encode('shift-jis') # using Windows file encoding
        
        ## buf = cv2.imread(path) # ▲ ok? bad sometime.
        ## buf = plt.imread(path) # ▲ MPL fails in rading tif of <float>
        buf = Image.open(path) # good. PIL is the best way to read an image file
        info = {}
        if isinstance(buf, TiffImageFile): # tiff はそのまま返して後処理に回す
            return buf, info
        
        if buf.mode[:3] == 'RGB':  # 今のところカラー画像には対応する気はない▼
            buf = buf.convert('L') # ここでグレースケールに変換する
        
        ## return np.asarray(buf), info # ref
        return np.array(buf), info # copy
    
    @staticmethod
    def write_buffer(path, buf):
        """Write buffer to `path file (to be overrided)"""
        ## cv2.imwrite(path, buf)              # ▲ ok? maybe... not so sure.
        ## plt.imsave(path, buf, cmap='gray')  # ▲ MPL saves as RGB (but not gray!)
        Image.fromarray(buf).save(path) # good. PIL saves as L,I,F, or RGB.
    
    @staticmethod
    def write_buffers_stack(path, buffers):
        """Write stack of `buffers to `path file (to be overrided)"""
        ## buffer <float32> cannot be stacked to tiff
        stack = [Image.fromarray(buf.astype(int)) for buf in buffers]
        stack[0].save(path,
                save_all=True,
                compression="tiff_deflate", # cf. tiff_lzw
                append_images=stack[1:])
    
    def load_buffer(self, paths=None, target=None):
        """Load buffers from paths to the target window
        
        If no target given, the currently selected view is chosen.
        """
        if not target:
            target = self.selected_view
        
        if isinstance(paths, LITERAL_TYPE): # for single frame:backward compatibility
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
                
                buf, info = self.read_buffer(path)
                
                frame = target.load(buf, f, show=0, # do not show while loading
                                    pathname=path, **info)
                frames.append(frame)
                
                if isinstance(buf, TiffImageFile) and buf.n_frames > 1: # multi-page tiff
                    n = buf.n_frames
                    dg = int(np.log10(n))
                    fmt = "{{:0>{}}}".format(dg+1) # zero padding for numerical sorting
                    for j in range(1,n):
                        self.statusbar("Loading {!r} [{} of {} pages]...".format(f, j+1, n))
                        buf.seek(j)
                        name = "{}-{}".format(fmt.format(j), f)
                        frame = target.load(buf, name, show=0, pathname=None)
            
            self.statusbar("\b done.")
            target.select(frame)
            return frames
        
        except Exception as e:
            print(self.statusbar("\b failed: {!r}".format(e)))
            wx.MessageBox(str(e), style=wx.ICON_ERROR)
    
    def save_buffer(self, path=None, frame=None):
        """Save a buffer of the frame to the path
        
        If no target given, the currently selected view is chosen.
        """
        if not frame:
            frame = self.selected_view.frame
            if not frame:
                return
        
        if not path:
            with wx.FileDialog(self, "Save buffer as",
                defaultFile=re.sub("[\\/:*?\"<>|]", '_', frame.name), # normal-basename
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
            print(self.statusbar("\b failed: {!r}".format(e)))
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
            
            self.write_buffers_stack(path, [frame.buffer for frame in frames])
            self.statusbar("\b done.")
            return frames
        
        except Exception as e:
            print(self.statusbar("\b failed: {!r}".format(e)))
    
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
        try:
            self.session_file = os.path.abspath(f)
            self.statusbar("Loading session from {!r}...".format(f))
            
            ## with codecs.open(f, encoding='shift-jis') as i:
            with open(f) as i:
                self.inspector.shell.Execute(i.read())
                self.menubar.reset()
                dirname = os.path.dirname(f)
                if dirname:
                    os.chdir(dirname)
            
            self.statusbar("\b done.")
            return True
        
        except Exception as e:
            print(self.statusbar("\b failed: {!r}".format(e)))
            return False
        finally:
            self.OnShowFrame(None) # update titlebar
    
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
        
        ## with codecs.open(f, 'w', encoding='shift-jis') as o:
        with open(f, 'w') as o:
            o.write('\n'.join((
                "#! wxpyJemacs session file (This file is generated automatically)",
                "self.SetSize({})".format(self.Size),
                "self.inspector.SetSize({})".format(self.inspector.Size),
                "self.inspector.Show({})".format(self.inspector.IsShown()),
                "self.inspector.shell.wrap({})".format(self.inspector.shell.WrapMode),
            "")))
            for name in ('output', 'histogram'): # save built-in window layout
                pane = self.get_pane(name)
                o.write("self.update_pane('{name}', show={show}, docking={dock}, "
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
                o.write("self.load_plug('{name}', show={show}, docking={dock}, "
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
                 session = plug.get_current_session(),
                ))
            paths = [x.pathname for x in self.graph.all_frames if x.pathname]
            if paths:
                ## paths = sorted(set(paths), key=paths.index) # 順序は保持して重複を除く
                o.write("self.load_buffer(\n{})\n".format(pformat(paths, width=160)))
            
            ## set-global-unit
            o.write("self.graph.unit = {}\n".format(self.graph.unit))
            o.write("self.output.unit = {}\n".format(self.output.unit))
            
            ## set-local-unit
            for frame in self.graph.all_frames:
                if frame.localunit and frame.pathname: # localunit:need-buffer-save-?
                    o.write("self.graph.find_frame({!r}).unit = {}\n".format(
                            frame.name, frame.localunit))
            ## select-page
            if self.graph.frame:
                o.write("self.graph.select({!r})\n".format(self.graph.frame.name))
            
            o.write('# end of session\n')
            
        self.statusbar("\b ok")
        self.OnShowFrame(None) # update titlebar
        return True


## Plugin = Layer


if __name__ == '__main__':
    app = wx.App()
    frm = Frame(None)
    frm.handler.debug = 0
    frm.graph.handler.debug = 0
    frm.output.handler.debug = 0
    
    frm.load_buffer(u"C:/usr/home/workspace/images/sample.bmp")
    frm.load_buffer(u"C:/usr/home/workspace/images/サンプル.bmp")
    ## frm.load_buffer(u"C:/usr/home/workspace/images/Stack_image.tif")
    
    ## n = 512
    ## x = np.arange(-n,n)/n
    ## y = np.arange(-n,n)/n
    ## X, Y = np.meshgrid(x, y)
    ## ## X, Y = np.mgrid[-n:n,-n:n] /n
    ## z = np.exp(-(X**2 + Y**2)) - 1/2
    ## frm.graph.load(z)
    ## frm.graph.load(np.randn(1024,1024))
    
    ## 次の二つは別モジュール
    ## frm.load_plug('templates.template.py', show=1)
    frm.load_plug('C:/usr/home/workspace/tem13/gdk/templates/template.py', show=1)
    frm.load_plug('C:/usr/home/workspace/tem13/gdk/templates/template2.py', show=1)
    
    frm.Show()
    app.MainLoop()
