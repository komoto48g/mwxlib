#! python3
"""mwxlib framework (based on matplotlib/wx)
"""
from .framework import __version__, __author__
from .framework import FSM
from .framework import Menu, MenuBar, StatusBar
from .framework import App, Frame, MiniFrame, ShellFrame

## Controls
## from . import controls
## from .controls import Param, LParam, Knob, ControlPanel, Clipboard, Icon
## from .controls import Button, ToggleButton, TextCtrl, Choice, Gauge, Indicator

## Plugman
## from . import graphman
## from .graphman import Frame, Layer, Thread, Graph

## Matplot
## from .matplot2 import MatplotPanel
## from .matplot2g import GraphPlot
## from .matplot2lg import LinePlot
## from .matplot2lg import Histogram
## from .matplot2lg import LineProfile

## Gnuplot
## from .mgplt import Gnuplot
## from .mgplt import GnuplotFrame


def deb(target=None, loop=True, locals=None, **kwargs):
    """Dive into the process.
    
    Args:
        target  : Object or module (default None).
                  If None, the target is set to `__main__`.
        loop    : If True, the app and the mainloop will be created.
                  Otherwise, neither the app nor the mainloop will be created.
        locals  : Additional context of the shell
        
        **kwargs: Nautilus arguments
        
            - introText         : introductory of the shell
            - startupScript     : startup script file (default None)
            - execStartupScript : True => Execute the startup script.
            - ensureClose       : True => EVT_CLOSE will close the window.
                                  False => EVT_CLOSE will hide the window.
    
    Note:
        This will execute the startup script $(PYTHONSTARTUP).
    """
    import wx
    
    quote_unqoute = """
        Anything one man can imagine, other man can make real.
        --- Jules Verne (1828--1905)
        """
    kwargs.setdefault("introText",
                      "mwx {}".format(__version__) + quote_unqoute)
    kwargs.setdefault("execStartupScript", True)
    kwargs.setdefault("ensureClose", True)
    
    app = wx.GetApp() or wx.App()
    frame = ShellFrame(None, target, **kwargs)
    frame.Show()
    frame.rootshell.SetFocus()
    if locals:
        frame.rootshell.locals.update(locals)
    if loop and not app.GetMainLoop():
        app.MainLoop()
    return frame
