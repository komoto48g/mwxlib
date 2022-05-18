#! python3
# -*- coding: utf-8 -*-
import wx
from mwx.controls import Button, Icon
from mwx.graphman import Layer, Frame


class Plugin(Layer):
    menu = "Plugins/&Demo"
    
    def Init(self):
        self.layout(
            (Button(self, k, icon=k, size=(80,-1), tip=str(v))
                    for k, v in Icon.provided_arts.items()),
            title="Provided art images",
            row=6, show=0
        )
        self.layout(
            (Button(self, k, icon=k, size=(80,-1))
                    for k, v in Icon.custom_images.items()),
            title="Custom art images",
            row=6, show=0
        )


if __name__ == "__main__":
    app = wx.App()
    frm = Frame(None)
    frm.load_plug(__file__, show=1)
    frm.Show()
    app.MainLoop()
