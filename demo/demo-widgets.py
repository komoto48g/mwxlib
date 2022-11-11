#! python3
# -*- coding: utf-8 -*-
import wx
import mwx
from numpy import inf
from mwx.controls import Param, LParam
from mwx.controls import Icon, Button, ToggleButton, TextCtrl, Choice
from mwx.graphman import Layer, Frame


def iconify(icon, w, h):
    ## if wx.VERSION >= (4,2,0):
    try:
        import wx.svg
        import requests
        url = "https://api.iconify.design/{}.svg".format(icon.replace(':', '/'))
        content = requests.get(url).content
        img = wx.svg.SVGimage.CreateFromBytes(content)
        bmp = img.ConvertToScaledBitmap(wx.Size(w, h))
        return bmp
    except Exception:
        pass


class Plugin(Layer):
    menukey = "Plugins/&Demo/"
    
    def Init(self):
        self.btn = Button(self, label="button",
                        handler=lambda v: self.statusline(v.Int, v.IsChecked()),
                        tip="this is a button",
                        ## icon='v',
                        icon=iconify("openmoji:annoyed-face-with-tongue", 32, 32),
                        size=(80,-1),
                        )
        self.btn2 = ToggleButton(self, label="toggle-button",
                        handler=lambda v: self.statusline(v.Int, v.IsChecked()),
                        tip="this is a toggle-button",
                        icon=('w','v'), # must be the same size icon
                        size=(120,-1),
                        )
        self.text = TextCtrl(self, label="control",
                        handler=lambda v: self.statusline(v.Value, "enter"),
                        updater=lambda v: self.statusline(v.Value, "update"),
                        tip="this is a textctrl",
                        icon=wx.ART_NEW,
                        readonly=0,
                        value="default value",
                        size=(200,22),
                        )
        self.choice = Choice(self, label="control",
                        handler=lambda v: self.statusline(v.Value, "selected"),
                        updater=lambda v: self.statusline(v.Value, "update"),
                        choices=['1','2','3'],
                        tip="this is a choice",
                        icon=wx.ART_NEW,
                        readonly=0,
                        size=(200,22),
                        )
        self.layout((
                self.btn,
                self.btn2,
                wx.StaticLine(self), None,
                self.text, None,
                self.choice, None,
            ),
            title="Custom controls",
            row=2, expand=1,
        )
        
        def trace(v):
            """Trace events"""
            print("$(v) = {!r}".format(v))
        
        self.L =  LParam('L', (-1,1,0.01), 0,
                        handler=print,
                        tip="Linear param\n\n"
                            "In addition to direct key input to the textctrl,\n"
                            "[up][down][wheelup][wheeldown] keys can be used,\n"
                            "with modifiers S- 2x, C- 16x, and M- 256x steps.\n"
                            "[Mbutton] resets to the std. value if it exists.\n")
        self.U = Param('U', (1,2,3,inf))
        
        self.layout((
                self.L,
                self.U,
            ),
            title="Custom param controls",
            expand=1, show=1,
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
        self.statusline = mwx.StatusBar(self)
        
        ## self.layout((self.textctrl,), expand=2)
        ## self.layout((self.statusline,), expand=1, border=0)
        self.layout((
                self.textctrl,
                (self.statusline, 0, wx.EXPAND),
            ),
            expand=2, border=0, vspacing=0,
        )


if __name__ == "__main__":
    app = wx.App()
    frm = Frame(None)
    frm.load_plug(__file__, show=1)
    frm.Show()
    app.MainLoop()
