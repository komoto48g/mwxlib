#! python
# -*- coding: utf-8 -*-
import wx
import mwx
from numpy import inf
from mwx.controls import Param, LParam
from mwx.controls import Button, ToggleButton, TextCtrl, Choice
from mwx.graphman import Layer, Frame


class Plugin(Layer):
    menu = "Plugins/&Demo"
    
    def Init(self):
        self.layout('Custom controls', (
            Button(self, label="button",
                handler=lambda v: self.statusline(v.String, "pressed"),
                    tip="this is a button",
                    icon='v',
                    size=(100,-1)),
            
            ToggleButton(self, label="toggle-button",
                handler=lambda v: self.statusline(v.IsChecked(), "checked"),
                    tip="this is a toggle-button",
                    icon=None,
                    size=(100,-1)),
            
            ## wx.StaticLine(self, size=(200,-1)),
            (),
            TextCtrl(self, label="ctrl label",
                handler=lambda v: self.statusline(v.String, "enter"),
                updater=lambda v: self.statusline(v.Value, "update"),
                    tip="this is a textctrl",
                    icon=wx.ART_NEW,
                    size=(200,-1)),
            (),
            Choice(self, label="ctrl label",
                handler=lambda v: self.statusline(v.String, "selected"),
                updater=lambda v: self.statusline(v.Value, "update"),
                choices=['1','2','3'],
                selection=1,
                    tip="this is a choice",
                    readonly=0,
                    icon=wx.ART_NEW,
                    size=(200,-1)),
            ),
            row=2, expand=0,
        )
        self.LP =  LParam('L', (-1,1,0.01), 0, handler=print,
            doc="Linear param"
                "\n In addition to direct key input to the textctrl,"
                "\n [up][down][wheelup][wheeldown] keys can be used,"
                "\n with modifiers S- 2x, C- 16x, and M- 256x steps."
                "\n [Mbutton] resets to the std. value if it exists.")
        
        self.P = Param('U', (1,2,3,inf), handler=print)
        
        self.layout('Custom param controls', (
            self.LP,
            self.P,
            ),
            row=1, expand=1, show=1, 
            type='slider', lw=20, tw=40, cw=100, h=22,
        )
        
        self.textctrl = TextCtrl(self, '',
                handler=lambda v: self.statusline(v.String, "enter"),
                updater=lambda v: self.statusline(v.Value, "update"),
                value = TextCtrl.__doc__,
                    tip="this is a textctrl",
                    icon='v',
                    size=(210,100),
                    style=wx.TE_MULTILINE|wx.TE_PROCESS_TAB
                         |wx.TE_RICH|wx.TE_AUTO_URL)
        
        self.statusline = mwx.StatusBar(self, style=wx.STB_DEFAULT_STYLE)
        
        self.layout(None, (
            self.textctrl,
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
