#! python3
"""Test suite.

Get the wx.App or wx.Frame instance and start the main-loop if needed.

Usage:
    with testApp() as app:
        frm = wx.Frame(None)
        frm.Show()

Is equivalent to:
    app = wx.App()
    frm = wx.Frame(None)
    frm.Show()
    app.MainLoop()
"""
from contextlib import contextmanager
import wx

__all__ = ["testApp", "testFrame", "deb"]


@contextmanager
def testApp():
    app = wx.GetApp() or wx.App()
    yield app
    if not app.GetMainLoop():
        app.MainLoop()
## wx.App.run = staticmethod(testApp)


@contextmanager
def testFrame(f=wx.Frame, **kwargs):
    with testApp():
        frm = f(None, **kwargs)
        yield frm
        frm.Show()
## wx.Frame.run = staticmethod(testFrame)


def deb(target=None, loop=True, locals=None, **kwargs):
    """Dive into the process.
    
    Args:
        target: Object or module (default None).
                If None, the target is set to `__main__`.
        loop:   If True, the app and the mainloop will be created.
        locals: Additional context of the shell.
        
        **kwargs: ShellFrame and Nautilus arguments.
        
            - session: file name of the session. Defaults to None.
            - introText: introductory of the shell
            - startupScript: startup script file (default None)
            - execStartupScript: True => Execute the startup script.
    
    Note:
        This will execute the startup script $(PYTHONSTARTUP).
    """
    from .framework import ShellFrame
    
    app = wx.GetApp() or wx.App()
    frame = ShellFrame(None, target, **kwargs)
    frame.standalone = True
    frame.Show()
    frame.rootshell.SetFocus()
    if locals:
        frame.rootshell.locals.update(locals)
    if loop and not app.GetMainLoop():
        app.MainLoop()
    return frame
