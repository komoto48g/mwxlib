#! python3
"""Test suite for App, Frame, and ControlPanel.

Get the wx.App or wx.Frame instance and start the main-loop if needed.

Usage:
    with testApp() as app:
        frm = wx.Frame(None)
        frm.Show()

Is equivlent to:
    app = wx.App()
    frm = wx.Frame(None)
    frm.Show()
    app.MainLoop()
"""
from contextlib import contextmanager
import wx

__all__ = ["testApp", "testFrame", "Plugman", "testPanel"]


@contextmanager
def testApp():
    app = wx.GetApp() or wx.App()
    yield app
    if not app.GetMainLoop():
        app.MainLoop()
## wx.App.run = staticmethod(testApp)


@contextmanager
def testFrame(**kwargs):
    with testApp():
        frm = wx.Frame(None, **kwargs)
        yield frm
        frm.Show()
## wx.Frame.run = staticmethod(testFrame)


@contextmanager
def Plugman(**kwargs):
    import mwx.graphman
    with testApp():
        frm = mwx.graphman.Frame(None, **kwargs)
        yield frm
        frm.Show()


@contextmanager
def testPanel(**kwargs):
    import mwx
    with testApp():
        frm = mwx.Frame(None)
        panel = mwx.ControlPanel(frm, **kwargs)
        yield panel
        panel.Sizer.Fit(frm)
        frm.Show()
