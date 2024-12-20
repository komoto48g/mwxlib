#! python3
import sys
import wx

sys.path.append("../Lib")
from mwx.controls import Icon
from mwx.framework import Frame


class Frame(Frame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        ## Do not use menu IDs in [ID_LOWEST(4999):ID_HIGHEST(5999)]
        
        self.menubar["File"][0:0] = [
            (101, "&Open\tctrl+o", "Opent the document", Icon('open'),
                lambda v: print("You chose File->Open")),
                
            (102, "&Save\tctrl+s", "Save the document", Icon('save'),
                lambda v: print("You chose File->Save")),
            (),
        ]
        self.menubar["View"] = [
            (103, "&one", "1", wx.ITEM_RADIO, lambda v: print("You chose", 1)),
            (104, "&two", "2", wx.ITEM_RADIO, lambda v: print("You chose", 2)),
            (105, "&foo", "3", wx.ITEM_RADIO, lambda v: print("You chose", 3)),
            (),
            (106, "&Check", "check update test", wx.ITEM_CHECK, Icon('v'),
                print,  #<wx._core.CommandEvent>
                print,  #<wx._core.UpdateUIEvent>
                print), #<wx._core.MenuEvent>
            (),
            ("&Print", (
                (111, "setup\tctrl+shift+s", Icon('+'), lambda v: print("setup")),
                (112, "preview\tctrl+shift+p", Icon('-'), lambda v: print("preview")),
                ),
            ),
        ]
        self.menubar["Test/&Submenu"] = [ # add nested submenu into new menu
            ("&Print", (
                (121, "setup", Icon('+'), lambda v: print("setup")),
                (122, "preview", Icon('-'), lambda v: print("preview")),
                ),
            ),
        ]
        self.menubar["Test/&Submenu/&Print2"] = [ # add nested submenu into new menu
            (121, "setup", Icon('+'), lambda v: print("setup")),
            (122, "preview", Icon('-'), lambda v: print("preview")),
        ]
        self.menubar.reset()


if __name__ == "__main__":
    from mwx.testsuite import *
    with testApp():
        frm = Frame(None)
        frm.Show()
