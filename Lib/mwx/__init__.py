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
from .framework import deb

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
