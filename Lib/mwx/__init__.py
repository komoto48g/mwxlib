#! python
# -*- coding: utf-8 -*-
"""mwxlib (based on matplotlib/wx)
"""
from __future__ import division, print_function
from __future__ import unicode_literals
from __future__ import absolute_import

## from . import framework
from .framework import __version__, __author__
from .framework import apropos, typename
from .framework import SSM, FSM
from .framework import pack
from .framework import Menu, MenuBar, StatusBar
from .framework import Frame, MiniFrame, InspectorFrame, Editor, Nautilus
from .framework import funcall, postcall # curry spices
from .framework import deb

## widgets
## from .controls import Param, LParam, ControlPanel
## from .controls import Icon, Button, ToggleButton, TextCtrl, Choice

## matplot
from .matplot2 import MatplotPanel
from .matplot2g import GraphPlot
from .matplot2lg import LinePlot
from .matplot2lg import Histogram
from .matplot2lg import LineProfile

## from . import mgplt3 as mgplt
from .mgplt3 import Gplot
from .mgplt3 import GplotFrame

try:
    from importlib import reload
except ImportError:
    reload = reload
