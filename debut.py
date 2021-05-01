#! python
# -*- coding: utf-8 -*-
"""deb utility

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
from __future__ import (division, print_function,
                        absolute_import, unicode_literals)
import mwx
import numpy as np

np.set_printoptions(linewidth=256) # default 75


def init_spec(self):
    """Initialize shell/editor and the environs
    """
    @self.define_key('C-tab')
    def insert_space_like_tab():
        """タブの気持ちになって半角スペースを前向きに入力する
        Enter half-width spaces forward as if feeling like a tab
        """
        self.eat_white_forward()
        
        _text, lp = self.CurLine
        n = lp % 4
        self.write(' ' * (4-n))
    
    @self.define_key('C-S-tab')
    def delete_backward_space_like_tab():
        """シフト+タブの気持ちになって半角スペースを後ろ向きに消す
        Delete half-width spaces backward as if feeling like a shift+tab
        """
        self.eat_white_forward()
        
        _text, lp = self.CurLine
        n = lp % 4 or 4
        for i in range(n):
            p = self.cur
            if self.preceding_char == ' ' and p != self.bol:
                self.Replace(p-1, p, '')
            else:
                break
    
    @self.define_key('M-w')
    def copy_region():
        with self.Excursion(self):
            self.SetCurrentPos(self.mark)
            self.Copy()
    
    @self.define_key('M-S-,', pos=0, doc="beginning-of-buffer")
    @self.define_key('M-S-.', pos=-1, doc="end-of-buffer")
    def goto(pos):
        self.goto_char(pos)
    
    self.set_style({
        "STC_STYLE_DEFAULT"     : "fore:#cccccc,back:#202020,face:MS Gothic,size:9",
        "STC_STYLE_CARETLINE"   : "fore:#ffffff,back:#012456,size:2",
        "STC_STYLE_LINENUMBER"  : "fore:#000000,back:#f0f0f0,size:9",
        "STC_STYLE_BRACELIGHT"  : "fore:#ffffff,back:#202020,bold",
        "STC_STYLE_BRACEBAD"    : "fore:#ffffff,back:#ff0000,bold",
        "STC_STYLE_CONTROLCHAR" : "size:9",
        "STC_P_DEFAULT"         : "fore:#cccccc,back:#202020",
        "STC_P_IDENTIFIER"      : "fore:#cccccc",
        "STC_P_COMMENTLINE"     : "fore:#42c18c,back:#004040",
        "STC_P_COMMENTBLOCK"    : "fore:#42c18c,back:#004040,eol",
        "STC_P_CHARACTER"       : "fore:#a0a0a0",
        "STC_P_STRING"          : "fore:#a0a0a0",
        "STC_P_TRIPLE"          : "fore:#a0a0a0,back:#004040,eol",
        "STC_P_TRIPLEDOUBLE"    : "fore:#a0a0a0,back:#004040,eol",
        "STC_P_STRINGEOL"       : "fore:#808080",
        "STC_P_WORD"            : "fore:#80a0ff",
        "STC_P_WORD2"           : "fore:#ff80ff",
        "STC_P_DEFNAME"         : "fore:#e0c080,bold",
        "STC_P_CLASSNAME"       : "fore:#e0c080,bold",
        "STC_P_DECORATOR"       : "fore:#e08040",
        "STC_P_OPERATOR"        : "",
        "STC_P_NUMBER"          : "fore:#ffc080",
    })
    self.wrap(0)


def dive(*args):
    """Dive into the process, from your diving point.
To Divers:
    This executes your startup script ($PYTHONSTARTUP:~/.py).
    Then, call spec (post-startup function defined above),
    """
    mwx.deb(*args, startup=init_spec, execStartupScript=True,
        introText = """
        Anything one man can imagine, other man can make real.
        --- Jules Verne (1828--1905)
        """)


if __name__ == '__main__':
    dive()
