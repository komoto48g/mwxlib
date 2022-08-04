#! python3
# -*- coding: utf-8 -*-
"""mwxlib framework (based on matplotlib/wx)
"""
from .utilus import apropos, typename, FSM
from .framework import __version__, __author__
from .framework import pack, Menu, MenuBar, StatusBar
from .framework import Frame, MiniFrame, ShellFrame

## from . import controls
## from .controls import Param, LParam, Knob, ControlPanel, Icon
## from .controls import Button, ToggleButton, TextCtrl, Choice, Gauge, Indicator

## from . import graphman
## from .graphman import Layer, Thread, Graph
## from .graphman import Frame as Graphman

## Matplot
## from .matplot2 import MatplotPanel
## from .matplot2g import GraphPlot
## from .matplot2lg import LinePlot
## from .matplot2lg import Histogram
## from .matplot2lg import LineProfile

## Gnuplot
## from .mgplt import Gnuplot
## from .mgplt import GnuplotFrame

from importlib import reload
import wx


def deb(target=None, app=None, locals=None, **kwargs):
    """Dive into the process.
    
    Args:
        target  : Object or module (default None).
                  If None, the target is set to `__main__`.
        app     : An instance of wx.App (default None).
                  If None, the app and the mainloop will be created.
                  If specified, the app will enter the mainloop locally.
                  Otherwise, neither the app nor the mainloop will be created.
        locals  : Additional context of the shell
        
        **kwargs : Nautilus arguments
        
            - introText         : introductory of the shell
            - startupScript     : startup script file (default None)
            - execStartupScript : True => execute the startup script
            - ensureClose       : True => EVT_CLOSE surely close the window
    
    Note:
        This will execute the startup script $(PYTHONSTARTUP).
    """
    quote_unqoute = """
        Anything one man can imagine, other man can make real.
        --- Jules Verne (1828--1905)
        """
    kwargs.setdefault("introText",
                      "mwx {}".format(__version__) + quote_unqoute)
    kwargs.setdefault("execStartupScript", True)
    kwargs.setdefault("ensureClose", True)
    
    if app is None:
        app = wx.GetApp() or wx.App()
    frame = ShellFrame(None, target, **kwargs)
    frame.Show()
    shell = frame.rootshell
    shell.SetFocus()
    if locals:
        shell.locals.update(locals)
    if isinstance(app, wx.App) and not app.GetMainLoop():
        app.MainLoop()
    return frame
