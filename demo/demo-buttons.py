#! python3
# -*- coding: utf-8 -*-
from __future__ import (division, print_function,
                        absolute_import, unicode_literals)
import wx
import mwx
import mwx.controls
mwx.reload(mwx.controls)
from mwx.controls import Button, Icon
from mwx.graphman import Layer, Frame


class Plugin(Layer):
    menu = "Plugins/&Demo"
    
    def Init(self):
        self.layout('Provided art images',
            (Button(self, k, icon=k, size=(80,-1))
                for k in sorted(Icon.provided_arts)),
            row=6, show=0
        )
        self.layout('Custom demo images',
            (Button(self, k, icon=k, size=(80,-1))
                for k in sorted(Icon.custom_images)),
            row=6, show=0
        )


if __name__ == "__main__":
    app = wx.App()
    frm = Frame(None)
    frm.load_plug(__file__, show=1)
    frm.Show()
    app.MainLoop()
