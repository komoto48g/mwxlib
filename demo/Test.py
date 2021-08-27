#! python3
# -*- coding: utf-8 -*-
"""Template of Layer

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
import wx
import mwx
from mwx.graphman import Layer, Frame


class Plugin(Layer):
    """Plugin template ver.0
    """
    def Init(self):
        """Initialize me safely (to be overrided)"""
        self.handler.update({
            0 : {
                   'f5 pressed' : (0, lambda v: self.reload_safe()),
            }
        })
    
    def Destroy(self):
        """Kill me safely (to be overrided)"""
        return Layer.Destroy(self)
    
    def get_current_session(self):
        """Return settings to be saved in session file (to be overrided)"""
        return True
    
    def set_current_session(self, session):
        """Restore settings to be loaded from session file (to be overrided)"""
        print("session =", session)


if __name__ == "__main__":
    app = wx.App()
    frm = Frame(None)
    frm.load_plug(__file__, show=1, docking=4)
    frm.load_buffer(u"./sample.bmp")
    frm.Show()
    app.MainLoop()
