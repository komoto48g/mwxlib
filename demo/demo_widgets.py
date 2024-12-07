#! python3
import sys
import wx
from numpy import nan, inf

sys.path.append("../Lib")
from mwx.controls import Param, LParam
from mwx.controls import Button, ToggleButton, TextBox, Choice, Icon
from mwx.framework import StatusBar
from mwx.graphman import Layer


class Plugin(Layer):
    menukey = "Plugins/&Demo/"
    
    def Init(self):
        def on_press(v):
            """Test button."""
            self.statusline(v.Int, v.IsChecked())
        
        def on_enter(v):
            """Enter value."""
            self.statusline(f"Enter {v.Value!r}")
        
        def on_update(v):
            """Update value."""
            self.statusline(f"Update {v.Value!r}")
        
        self.btn = Button(self, label="button",
                        handler=on_press,
                        icon=Icon.iconify("openmoji:annoyed-face-with-tongue", 32, 32),
                        size=(80,-1),
                        )
        self.btn2 = ToggleButton(self, label="toggle-button",
                        handler=on_press,
                        icon=('w','v'), # must be the same size icon
                        size=(120,-1),
                        )
        self.text = TextBox(self, label="control",
                        ## handler=lambda v: self.statusline(f"Enter {v.Value!r}"),
                        ## updater=lambda v: self.statusline(f"Update {v.Value!r}"),
                        handler=on_enter,
                        updater=on_update,
                        icon=wx.ART_NEW,
                        size=(200,22),
                        value="default value",
                        ## style=wx.TE_READONLY, # readonly=0,
                        )
        self.choice = Choice(self, label="control",
                        handler=lambda v: self.statusline(f"Select {v.Value!r}"),
                        updater=lambda v: self.statusline(f"Update {v.Value!r}"),
                        choices=['1','2','3'],
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
        
        self.L = LParam('L', (-1, 1, 0.01), 0, handler=self.trace)
        self.U = Param('U', (1,2,3,inf), nan, handler=print)
        
        self.layout((
                self.L,
                self.U,
            ),
            title="Custom param controls", expand=1, show=1,
            type='slider', style='chkbox', cw=100, lw=20, tw=40, h=22,
        )
        
        self.textctrl = wx.TextCtrl(self,
                                    value=wx.TextCtrl.__doc__,
                                    size=(200,100),
                                    style=wx.TE_MULTILINE
                                         |wx.TE_PROCESS_TAB
                                         |wx.TE_RICH
                                         |wx.TE_AUTO_URL
                            )
        self.statusline = StatusBar(self)
        
        self.layout((
                self.textctrl,
                (self.statusline, 0, wx.EXPAND),
            ),
            expand=2, border=0, vspacing=0,
        )

    def trace(self, v):
        """Trace events.
        
        In addition to direct key input to the textctrl,
        [up][down][wheelup][wheeldown] keys can be used,
        with modifiers S- 2x, C- 16x, and M- 256x steps.
        
        [Mbutton] resets to the std. value if it exists.
        """
        print(v)


if __name__ == "__main__":
    from mwx.testsuite import *
    with Plugman() as frm:
        frm.load_plug(Plugin, show=1)
