#! python3
"""mwxlib framework (based on matplotlib/wx)
"""
from .framework import __version__, __author__
from .framework import FSM
from .framework import Menu, MenuBar, StatusBar
from .framework import Frame, MiniFrame, ShellFrame, deb

## Controls
## from . import controls
from .controls import Param, LParam, Knob, ControlPanel, Clipboard, Icon
from .controls import Button, ToggleButton, TextCtrl, Choice, Gauge, Indicator

## Plugman
## from . import graphman
## from .graphman import Frame as GraphFrame, Layer, Thread, Graph

## Matplot
## from .matplot2 import MatplotPanel
## from .matplot2g import GraphPlot
## from .matplot2lg import LinePlot
## from .matplot2lg import Histogram
## from .matplot2lg import LineProfile

## Gnuplot
## from .mgplt import Gnuplot, GnuplotFrame
