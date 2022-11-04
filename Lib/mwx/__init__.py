#! python3
# -*- coding: utf-8 -*-
"""mwxlib framework (based on matplotlib/wx)
"""
from .utilus import apropos, FSM
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
import contextlib
import wx


@contextlib.contextmanager
def app(loop=True):
    try:
        app = wx.GetApp() or wx.App()
        yield app
    finally:
        if loop and not app.GetMainLoop():
            app.MainLoop()


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
    if loop:
        app = wx.GetApp() or wx.App()
    frame = ShellFrame(None, target, **kwargs)
    frame.Show()
    shell = frame.rootshell
    shell.SetFocus()
    if locals:
        shell.locals.update(locals)
    if loop and not app.GetMainLoop():
        app.MainLoop()
    return frame
