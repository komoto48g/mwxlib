#! python3
import sys
import wx
from numpy import inf

sys.path.append("../Lib")
import mwx
from mwx.controls import Param, LParam
from mwx.controls import Button, ToggleButton, TextCtrl, Choice, Icon
from mwx.graphman import Layer, Frame


class Plugin(Layer):
    menukey = "Plugins/&Demo/"
    
    def Init(self):
        def on_press(v):
            """Test button."""
            self.statusline(v.Int, v.IsChecked())
        
        self.btn = Button(self, label="button",
                        handler=on_press,
                        tip="this is a button",
                        ## icon='v',
                        icon=Icon.iconify("openmoji:annoyed-face-with-tongue", 32, 32),
                        size=(80,-1),
                        )
        self.btn2 = ToggleButton(self, label="toggle-button",
                        handler=on_press,
                        tip="this is a toggle-button",
                        icon=('w','v'), # must be the same size icon
                        size=(120,-1),
                        )
        self.text = TextCtrl(self, label="control",
                        handler=lambda v: self.statusline(f"Enter {v.Value!r}"),
                        updater=lambda v: self.statusline(f"Update {v.Value!r}"),
                        tip="this is a textctrl",
                        icon=wx.ART_NEW,
                        size=(200,22),
                        value="default value",
                        ## style=wx.TE_READONLY, # readonly=0,
                        )
        self.choice = Choice(self, label="control",
                        handler=lambda v: self.statusline(f"Selected {v.Value!r}"),
                        updater=lambda v: self.statusline(f"update {v.Value!r}"),
                        choices=['1','2','3'],
                        tip="this is a choice",
                        icon=wx.ART_NEW,
                        size=(200,22),
                        value='2',
                        ## style=wx.CB_READONLY, # readonly=0,
                        )
        self.layout((
                self.btn,
                self.btn2,
                wx.StaticLine(self), None,
                self.text, None,
                self.choice, None,
            ),
            title="Custom controls", row=2, expand=1,
        )
        
        def trace(v):
            """Trace events.
            
            In addition to direct key input to the textctrl,
            [up][down][wheelup][wheeldown] keys can be used,
            with modifiers S- 2x, C- 16x, and M- 256x steps.
            [Mbutton] resets to the std. value if it exists.
            """
            print(v)
        
        self.L =  LParam('L', (-1,1,0.01), 0, handler=trace)
        self.U = Param('U', (1,2,3,inf))
        
        self.layout((
                self.L,
                self.U,
            ),
            title="Custom param controls", expand=1, show=1,
            type='slider', style='chkbox', cw=100, lw=20, tw=40, h=22,
        )
        
        ## Regular wx.TextCtrl is not handled by Clipboard copy and paste.
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
    frm.load_plug(Plugin, show=1)
    frm.Show()
    app.MainLoop()
