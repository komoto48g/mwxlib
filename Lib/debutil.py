#! python3
# -*- coding: utf-8 -*-
"""deb utility

Test for magic syntax interpreter
"""
from functools import partial, reduce
import re
import wx
import mwx
from mwx.framework import extract_words_from_tokens

SEP1 = "`@=+-/*%<>&|^~;\t\r\n"   # ` OPS + SEPARATOR_CHARS; nospace, nocomma
SEP2 = "`@=+-/*%<>&|^~;, \t\r\n" # @ OPS + SEPARATOR_CHARS;

class MagicInterpreter(object):
    """Magic syntax interpreter
    
    --------
    Example:quoteback
    >>> 1`a`b
    - Input tokens: [1, `, a, `, b]
    - Output tokens to handler:
        -> [1] [`] [a, `, b]
        -> [a=1] [`] [b]
        -> b=a=1
    --------
    Example:pullback
    >>> 1,5 @range @list @p
    [1, 2, 3, 4]
    - Input tokens: [1, ',', 5, @, range, @, list, @, p]
    - Output tokens to handler:
        -> [1,',',5] [@] [range, @, list, @, p]
        -> [range(1,5)] [@] [list, @, p]
        -> [list(range(1,5))] [@] [p]
        => p(list(range(1,5)))
    --------
    Example:pullback+
    >>> 5 @range @(reduce, lambda x,y:x+y)
    10
    - Input tokens: [5, @, range, @, '(reduce, lambda x,y:x+y)']
    - Output tokens to handler:
        -> [5] [@] [range, @, '(reduce, lambda x,y:x+y)']
        -> [range(5)] [@] ['(reduce, lambda x,y:x+y)']
        -> [range(5)] [@] ['parital(reduce, lambda x,y:x+y)']
        => partial(reduce, lambda x,y:x+y)(range(5))
    --------
    Example:pullback*
    >>> 5 @range @*p
    0 1 2 3 4
    - Input tokens: [5, @, range, @, *, p]
    - Output tokens to handler:
        -> [5] [@] [range, @, *, p]
        -> [range(5)] [@] [*, p] --> fork
        -> [range(5)] [@*] [p]
        => p(*range(5))
    """
    def __init__(self, shell):
        self.handler = mwx.FSM({
            0 : {
                    '`' : (0, self.quoteback),
                    '@' : (1, self.fork),
              '[;\r\n]' : (0, self.feed),
                  '...' : (0, self.feed),
                  '[?]' : (0, self.apropos),
            },
            1 : {
                    '@' : (0, self.pullback),
                   '@=' : (0, self.pullback_dcor),
                 '@[*]' : (0, self.pullback_vargs),
            },
        }, default=0)
        
        self.handler.debug = 4
    
    def __call__(self, tokens):
        """Called before push
        and if tokens include non-pythonic chars `@?$
        
        Return interpreted command:str
        
        l:token is converted to a string and becomes part of the retval
                イベントハンドラによって文字列に変換され戻り値となる
        r:token is converted to pass to the recursive call
                次の call に渡すために変更される
        """
        for j,c in enumerate(tokens):
            l, r = tokens[:j], tokens[j+1:]
            ret = self.handler(c, l, r) # non-false value [...] if handled
            if ret:
                return ''.join(l) + self(r)
        return ''.join(tokens)
    
    def fork(self, l, r):
        c = self.handler.current_event
        if r and r[0] in SEP2: # eat whites, seps, and ops
            c += r.pop(0)
        return self.handler(c, l, r)
    
    def feed(self, l, r):
        c = self.handler.current_event
        while r and r[0].isspace(): # eat whites
            c += r.pop(0)
        l[:] = [''.join(l) + c]
    
    def quoteback(self, l, r):
        lhs = ''.join(l).strip() or '_'
        rhs = ''.join(extract_words_from_tokens(r, SEP1)).strip()
        r[0:0] = [f"{rhs}={lhs}"]
        l[:] = []
    
    def pullback(self, l, r):
        lhs = ''.join(l).strip() or '_'
        rhs = ''.join(extract_words_from_tokens(r, SEP2)).strip()
        rhs = re.sub(r"(\(.*\))",
                     r"partial\1", rhs) # --> partial(y,...)
        r[0:0] = [f"{rhs}({lhs})"]
        l[:] = []
    
    def pullback_vargs(self, l, r):
        l.insert(0, '*')
        self.pullback(l, r)
    
    def pullback_dcor(self, l, r):
        lhs = ''.join(l).strip() or '_'
        rhs = ''.join(extract_words_from_tokens(r, SEP2)).strip()
        r[0:0] = [f"{lhs}={rhs}({lhs!r})"]
        l[:] = []
    
    def apropos(self, l, r):
        head, sep, hint = ''.join(l).rpartition('.')
        cc, pred = re.search(r"(\?+)\s*(.*)", '?'+''.join(r)).groups()
        r[:] = []
        l[:] = ["apropos({0!r}, {1}, ignorecase={2}, alias={1!r}, "
                "pred={3!r}, locals=self.shell.interp.locals)".format(
                hint.strip(), head or 'this', len(cc) < 2, pred or None)]


def init_shell(self):
    self.magic_interpret = MagicInterpreter(self)
    self.parent.About()

if __name__ == '__main__':
    mwx.deb(startup=init_shell,
            execStartupScript=True,
            introText="""
            Anything one man can imagine, other man can make real.
            --- Jules Verne (1828--1905)
            """,
            size=(854,480))
