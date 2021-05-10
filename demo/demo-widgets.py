#! python
# -*- coding: utf-8 -*-
import wx
import mwx
from numpy import inf
from mwx.graphman import Layer, Frame


class Plugin(Layer):
    menu = "Plugins/&Demo"
    
    def Init(self):
        self.layout('Custom controls', (
            mwx.Button(self, label="button",
                handler=lambda v: self.statusline(v.String, "pressed"),
                    tip="this is a button",
                    icon='v',
                    size=(100,-1)),
            
            mwx.ToggleButton(self, label="toggle-button",
                handler=lambda v: self.statusline(v.IsChecked(), "checked"),
                    tip="this is a toggle-button",
                    icon=None,
                    size=(100,-1)),
            
            ## wx.StaticLine(self, size=(200,-1)),
            (),
            mwx.TextCtrl(self, label="ctrl label",
                handler=lambda v: self.statusline(v.String, "enter"),
                updater=lambda v: self.statusline(v.value, "update"),
                    tip="this is a textctrl",
                    icon=wx.ART_NEW,
                    size=(200,-1)),
            (),
            mwx.Choice(self, label="ctrl label",
                handler=lambda v: self.statusline(v.String, "selected"),
                updater=lambda v: self.statusline(v.value, "update"),
                choices=['1','2','3'],
                selection=1,
                    tip="this is a choice",
                    readonly=0,
                    icon=wx.ART_NEW,
                    size=(200,-1)),
            ),
            row=2, expand=0,
        )
        self.LP =  mwx.LParam('L', (-1,1,0.01), 0, handler=print,
            doc="Linear param"
                "\n In addition to direct key input to the textctrl,"
                "\n [up][down][wheelup][wheeldown] keys can be used,"
                "\n with modifiers S- 2x, C- 16x, and M- 256x steps."
                "\n [Mbutton] resets to the std. value if it exists.")
        
        self.P = mwx.Param('U', (1,2,3,inf), handler=print)
        
        self.layout('Custom param controls', (
            self.LP,
            self.P,
            ),
            row=1, expand=1, show=1, 
            type='slider', lw=20, tw=40, cw=100, h=22,
        )
        self.statusline = mwx.StatusBar(self, style=wx.STB_DEFAULT_STYLE)
        self.layout(None, (
            mwx.TextCtrl(self, '',
                handler=lambda v: self.statusline(v.String, "enter"),
                updater=lambda v: self.statusline(v.value, "update"),
                value = mwx.TextCtrl.__doc__,
                    tip="this is a textctrl",
                    icon='v',
                    size=(210,100),
                    style=wx.TE_MULTILINE),
            
            self.statusline,
            ),
            row=1, expand=2, border=0,
        )


if __name__ == "__main__":
    app = wx.App()
    frm = Frame(None)
    frm.load_plug(__file__, show=1)
    frm.Show()
    app.MainLoop()
