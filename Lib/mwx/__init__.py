#! python3
# -*- coding: utf-8 -*-
"""mwxlib (based on matplotlib/wx)
"""
## from . import framework
from .framework import __version__, __author__
from .framework import apropos, typename
from .framework import FSM
from .framework import pack, hotkey
from .framework import Menu, MenuBar, StatusBar
from .framework import Frame, MiniFrame, ShellFrame
from .framework import funcall # curry spices

## from . import controls as wdigets
## from .controls import Param, LParam, Knob, ControlPanel, Icon
## from .controls import Button, ToggleButton, TextCtrl, Choice, Gauge, Indicator

## matplot
## from .matplot2 import MatplotPanel
## from .matplot2g import GraphPlot
## from .matplot2lg import LinePlot
## from .matplot2lg import Histogram
## from .matplot2lg import LineProfile

## from . import graphman
## from .graphman import Layer, Thread, Graph
## from .graphman import Frame as Graphman

## Gnuplot
## from .mgplt import Gnuplot
## from .mgplt import GnuplotFrame

## mwx.reload
from importlib import reload

import traceback
import wx


def deb(target=None, app=None, startup=None, **kwargs):
    """Dive into the process from your diving point
    for debug, break, and inspection of the target
    --- Put me at breakpoint.
    
    target : object or module. Default None sets target as __main__.
       app : an instance of App.
             Default None may create a local App and the mainloop.
             If app is True, neither the app nor the mainloop will be created.
             If app is given and not started the mainloop yet,
             the app will enter the mainloop herein.
   startup : called after started up (not before)
  **kwargs : Nautilus arguments
    locals : additional context (localvars:dict) to the shell
    execStartupScript : First, execute your script ($PYTHONSTARTUP:~/.py)
    """
    quote_unqoute = """
        Anything one man can imagine, other man can make real.
        --- Jules Verne (1828--1905)
        """
    kwargs.setdefault("introText",
                      "mwx {}".format(__version__) + quote_unqoute)
    
    app = app or wx.GetApp() or wx.App()
    frame = ShellFrame(None, target, **kwargs)
    frame.Unbind(wx.EVT_CLOSE) # EVT_CLOSE surely close the window
    frame.Show()
    frame.rootshell.SetFocus()
    if startup:
        shell = frame.rootshell
        try:
            startup(shell)
            frame.handler.bind('shell_cloned', startup)
        except Exception as e:
            shell.message("- Failed to startup: {!r}".format(e))
            traceback.print_exc()
        else:
            shell.message("The startup was completed successfully.")
    if isinstance(app, wx.App) and not app.GetMainLoop():
        app.MainLoop()
    return frame
