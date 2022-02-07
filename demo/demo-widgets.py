#! python3
# -*- coding: utf-8 -*-
from numpy import inf
import wx
import mwx
import mwx.controls
mwx.reload(mwx.controls)
from mwx.controls import Param, LParam
from mwx.controls import Icon, Button, ToggleButton, TextCtrl, Choice
from mwx.graphman import Layer, Frame


class Plugin(Layer):
    menu = "Plugins/&Demo"
    
    def Init(self):
        
        def trace(v):
            "trace event"
            print(v)
        
        self.btn = Button(self, label="button",
                        handler=trace,
                        tip="this is a button",
                        icon='v',
                        size=(100,-1),
                        )
        self.btn2 = ToggleButton(self, label="toggle-button",
                        handler=lambda v: self.statusline(v.GetInt(), v.IsChecked()),
                        tip="this is a toggle-button",
                        icon=('w','v'),
                        size=(100,-1),
                        )
        self.text = TextCtrl(self, label="ctrl label",
                        handler=lambda v: self.statusline(v.Value, "enter"),
                        updater=lambda v: self.statusline(v.Value, "update"),
                        tip="this is a textctrl",
                        icon=wx.ART_NEW,
                        readonly=0,
                        value="default value",
                        size=(200,22),
                        )
        self.choice = Choice(self, label="ctrl label",
                         handler=lambda v: self.statusline(v.Value, "selected"),
                         updater=lambda v: self.statusline(v.Value, "update"),
                         choices=['1','2','3'],
                         tip="this is a choice",
                         icon=wx.ART_NEW,
                         readonly=0,
                         selection=0,
                         size=(200,22),
                         )
        self.layout((
                self.btn,
                self.btn2,
                wx.StaticLine(self, size=(200,-1)),
                (),
                self.text, None,
                self.choice, None,
            ),
            title="Custom controls",
            row=2, expand=0,
        )
        
        self.LP =  LParam('L', (-1,1,0.01), 0,
                        handler=print,
                        tip="Linear param"
                            "\n In addition to direct key input to the textctrl,"
                            "\n [up][down][wheelup][wheeldown] keys can be used,"
                            "\n with modifiers S- 2x, C- 16x, and M- 256x steps."
                            "\n [Mbutton] resets to the std. value if it exists."
                        )
        self.P = Param('U', (1,2,3,inf))
        
        self.layout((
                self.LP,
                self.P,
            ),
            title="Custom param controls",
            row=1, expand=1, show=1, 
            type='slider', style='chkbox', lw=20, tw=40, cw=100, h=22,
        )
        
        self.textctrl = wx.TextCtrl(self,
                        value=TextCtrl.__doc__,
                        size=(200,100),
                        style=wx.TE_MULTILINE
                            | wx.TE_PROCESS_TAB
                            | wx.TE_RICH
                            | wx.TE_AUTO_URL
                        )
        self.statusline = mwx.StatusBar(self, style=wx.STB_DEFAULT_STYLE)
        
        self.layout((
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
