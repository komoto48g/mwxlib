#! python3
# -*- coding: utf-8 -*-
"""mwxlib (based on matplotlib/wx)
"""
## Framework
from .framework import __version__, __author__
from .utilus import apropos, typename, where
from .utilus import FSM
from .utilus import funcall
from .framework import pack, postcall
from .framework import Menu, MenuBar, StatusBar
from .framework import Frame, MiniFrame, ShellFrame

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

from importlib import reload
import wx


def deb(target=None, app=None, locals=None, **kwargs):
    """Dive into the process from your diving point
    for debug, break, and inspection of the target
    
    Args:
         target : Object or module.
                  Default None sets target to __main__.
            app : An instance of App.
                  Default None may create a local App and the mainloop.
                  If app is True, neither the app nor the mainloop will be created.
                  If app is given and not started the mainloop yet,
                  the app will enter the mainloop herein.
         locals : Additional context of the shell
       **kwargs : Nautilus arguments
            introText : introductory of the shell
        startupScript : startup script (default None)
    execStartupScript : execute your startup script ($PYTHONSTARTUP:~/.py)
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
    shell = frame.rootshell
    shell.SetFocus()
    if locals:
        shell.locals.update(locals)
    if isinstance(app, wx.App) and not app.GetMainLoop():
        app.MainLoop()
    return frame
