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

sys.path.append("../Lib")
from mwx.controls import Button, Icon, Indicator, Gauge
from mwx.graphman import Layer


class Plugin(Layer):
    menukey = "Plugins/&Demo/"

    def Init(self):
        def _icon(k):
            return Button(self, label=k, icon=Icon.iconify(k, 22, 22))
        
        ## #> https://icon-sets.iconify.design/openmoji/
        ## self.layout([
        ##         _icon("openmoji:annoyed-face-with-tongue"),
        ##         _icon("openmoji:frog"),
        ##     ],
        ##     title="Iconify", row=2, show=0,
        ## )
        
        self.layout([
                Button(self, icon="bullet('blue', 8)"),
                Button(self, icon=Icon.bullet('red', ec='blue')),
                Button(self, icon=Icon.bullet('yellow', ec='blue')),
                Button(self, icon=Icon.bullet('green', ec='blue')),
                Button(self, icon=Icon('file', Icon.bullet('red'))),
                Button(self, icon=Icon('file', Icon.bullet('yellow'))),
                Button(self, icon=Icon('file', Icon.bullet('green'))),
                Button(self, icon=Icon('script', Icon('!!'))),
                Gauge(self, value=24, size=(-1,14)),
                Indicator(self, value=0b111),
            ],
            title="Bullets", row=10, show=1,
        )
        
        def _btn2(back, fore, r=3/4):
            return Button(self, label=str(fore),
                                icon=Icon(back, fore, (16,16), r))
        
        ls = 'v w x + - ! !! !!! help tag pencil'.split()
        self.layout([
                *[_btn2('folder', x) for x in ls],
                *[_btn2('file', x) for x in ls],
            ],
            title="Icon2", row=len(ls),
        )
        self.layout(
            (Button(self, k, icon=k, size=(80,-1)) for k in Icon.provided_arts),
            title="Provided art images",
            row=6, show=0,
        )
        self.layout(
            (Button(self, k, icon=k, size=(80,-1)) for k in Icon.custom_images),
            title="Custom art images",
            row=6, show=0,
        )
