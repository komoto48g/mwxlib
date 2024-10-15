#! python3
"""mwxlib framework (based on matplotlib/wx)
"""
from .framework import __version__, __author__
from .framework import FSM, TreeList
from .framework import Menu, MenuBar, StatusBar
from .framework import Frame, MiniFrame, ShellFrame, deb, TestSuite

## Controls
from .controls import Param, LParam, Knob, ControlPanel, Clipboard, Icon
from .controls import Button, ToggleButton, ClassicButton, TextCtrl, Choice, Gauge, Indicator

## Plugman
## from .graphman import Frame as GraphmanFrame, Layer, Thread, Graph
## from .graphman import MatplotPanel, GraphPlot, LinePlot, LineProfile, Histogram

## Gnuplot
## from .mgplt import Gnuplot, GnuplotFrame
