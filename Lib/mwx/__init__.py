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
from .framework import Frame, MiniFrame, ShellFrame, Editor, Nautilus
from .framework import funcall # curry spices
from .framework import deb

## widgets
## from .controls import Param, LParam, Knob, ControlPanel
## from .controls import Icon, Button, ToggleButton, TextCtrl, Choice

## matplot
## from .matplot2 import MatplotPanel
## from .matplot2g import GraphPlot
## from .matplot2lg import LinePlot
## from .matplot2lg import Histogram
## from .matplot2lg import LineProfile

## from . import graphman

## from . import mgplt3 as mgplt
from .mgplt3 import Gplot
from .mgplt3 import GplotFrame

## mwx.reload
from importlib import reload
