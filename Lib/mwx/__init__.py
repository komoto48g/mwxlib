#! python3
"""mwxlib framework (based on matplotlib/wx)
"""
from .framework import __version__, __author__   # noqa
from .framework import FSM, TreeList             # noqa
from .framework import Menu, MenuBar, StatusBar  # noqa
from .framework import Frame, MiniFrame, ShellFrame, deb  # noqa

## Controls
from .controls import Param, LParam, Knob, ControlPanel, Clipboard, Icon  # noqa
from .controls import Button, ToggleButton, ClassicButton, TextBox, Choice, Gauge, Indicator  # noqa

## Plugman
# from .graphman import Frame as GraphmanFrame, Layer, Thread, Graph
# from .matplot2 import MatplotPanel
# from .matplot2g import GraphPlot
# from .matplot2lg import LinePlot, LineProfile, Histogram

## Gnuplot
# from .mgplt import Gnuplot, GnuplotFrame
