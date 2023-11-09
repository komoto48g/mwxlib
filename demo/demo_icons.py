#! python3
"""mwxlib icons library

Default icons are provided by `wx.ArtProvider`.
Optional icons are provided by:

- [famfamfam: Silk icons](http://www.famfamfam.com/lab/icons/silk/) designed by Mark James.
- [Tango desktop project](http://tango.freedesktop.org/Tango_Desktop_Project).
- [Iconify - Freedom to choose icons](https://iconify.design/).

Note:
    Other icons could be attributed to other open sources.
    This is a mish-mash of stuff from all over the internet.
    If I missed an author credit or attribution, please let me know.
"""
import sys
import wx

sys.path.append("../Lib")
from mwx.controls import Button, Icon, Icon2, Iconify
from mwx.graphman import Layer, Frame


class Plugin(Layer):
    menukey = "Plugins/&Demo/"
    
    def Init(self):
        def _btn(k):
            return Button(self, label=k, icon=Iconify(k, 22, 22))
        
        #> https://icon-sets.iconify.design/openmoji/
        ## self.layout([
        ##         _btn("openmoji:annoyed-face-with-tongue"),
        ##         _btn("openmoji:frog"),
        ##     ],
        ##     title="Iconify", row=2, show=0,
        ## )
        
        def _btn2(back, fore):
            icon = Icon2(back, fore, (16,16), 0.6)
            return Button(self, label='', tip=fore, icon=icon)
        
        a = 'folder'
        b = 'file'
        ls = 'v w x + - ! !! !!! help tag'.split()
        self.layout([
                *[_btn2(a, x) for x in ls],
                *[_btn2(b, x) for x in ls],
            ],
            title="Icon2", row=len(ls),
        )
        self.layout(
            (Button(self, k, icon=v, size=(80,-1), tip=str(v))
                    for k, v in Icon.provided_arts.items()),
            title="Provided art images",
            row=6, show=0
        )
        self.layout(
            (Button(self, k, icon=v, size=(80,-1))
                    for k, v in Icon.custom_images.items()),
            title="Custom art images",
            row=6, show=0
        )


if __name__ == "__main__":
    app = wx.App()
    frm = Frame(None)
    frm.load_plug(Plugin, show=1)
    frm.Show()
    app.MainLoop()
