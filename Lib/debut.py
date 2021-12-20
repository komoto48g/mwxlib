#! python3
# -*- coding: utf-8 -*-
"""deb utility

Test for snippets of code, syntax, semantics, interface,
  everything one can imagine
"""
__version__ = "1.0"
__author__ = "Kazuya O'moto <komoto@jeol.co.jp>"
from six.moves import builtins
from functools import partial, reduce
import operator as op
import numpy as np
import re
import mwx
from mwx.framework import extract_words_from_tokens

SEP1 = "`@=+-/*%<>&|^~;\t\r\n"   # ` OPS + SEPARATOR_CHARS; nospace, nocomma
SEP2 = "`@=+-/*%<>&|^~;, \t\r\n" # @ OPS + SEPARATOR_CHARS;

np.set_printoptions(linewidth=256) # default 75

if 1:
    """Shell built-in utility:
    
    --------
    >>> 5 @range @(reduce, op.mul)
    ==> partial(reduce, op.mul)(range(5))
    ==> reduce(op.mul, range(5))
    24
    --------
    >>> 5 @range @(do, p, end=',')
    ==> partial(do, p, end=',')(range(5))
    ==> do.results = tuple(p(v, end=',') for v in range(5))
    0,1,2,3,4,
    >>> do.results
    (None, None, None, None, None)
    """
    def do(f, *iterables, **kwargs):
        if not iterables:
            return partial(do, f, **kwargs)
        do.results = tuple(map(partial(f, **kwargs), *iterables))
    
    builtins.do = do
    builtins.reduce = reduce
    builtins.partial = partial


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
                    '*' : (0, self.feed),
                    '@' : (0, self.pullback),
                   '@=' : (0, self.pullback_dcor),
                 '@[*]' : (0, self.pullback_vargs),
            },
        }, default=0)
        
        ## self.handler.debug = 4
    
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
        c = self.handler.event
        while r and r[0] in SEP2: # eat whites, seps, and ops
            c += r.pop(0)
        return self.handler(c, l, r)
    
    def feed(self, l, r):
        c = self.handler.event
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
        rhs = re.sub(r"(\(.*\))",       # @(y1,...,yn)
                     r"partial\1", rhs) # --> partial(y1,...,yn)
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
        l[:] = ["apropos({0}, {1!r}, ignorecase={2}, alias={0!r}, "
                "pred={3!r}, locals=self.shell.interp.locals)".format(
                head or 'this', hint.strip(), len(cc) < 2, pred or None)]


def init_shell(self):
    """Initialize shell/editor environs
    """
    @self.define_key('M-w')
    def copy_region():
        if self.mark is None:
            self.message("no mark")
        else:
            self.Anchor = self.mark
            self.Copy()
    
    ## @self.define_key('C-x [', pos=0, doc="beginning-of-buffer")
    ## @self.define_key('C-x ]', pos=-1, doc="end-of-buffer")
    ## def goto(pos):
    ##     self.goto_char(pos)
    ## 
    ## @self.define_key('M-enter')
    ## def duplicate_command(clear=True):
    ##     cmd = self.getMultilineCommand()
    ##     if cmd:
    ##         if clear:
    ##             self.clearCommand()
    ##         self.write(cmd, -1)
    
    ## Theme: 'Dive into the night'
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
        "STC_P_WORD3"           : "fore:#ff0000,back:#ffff00", # custom style for search word
        "STC_P_DEFNAME"         : "fore:#e0c080,bold",
        "STC_P_CLASSNAME"       : "fore:#e0c080,bold",
        "STC_P_DECORATOR"       : "fore:#e08040",
        "STC_P_OPERATOR"        : "",
        "STC_P_NUMBER"          : "fore:#ffc080",
    })
    self.wrap(0)
    self.parent.About()
    self.magic_interpret = MagicInterpreter(self)


def dive(*args):
    """Dive into the process, from your diving point.
    Divers:
    This executes your startup script ($PYTHONSTARTUP:~/.py).
    Then, call post-startup function defined above.
    """
    mwx.deb(*args,
        startup=init_shell,
        execStartupScript=True,
        ## quote unqoute
        introText=f"""deb {__version__}
        Anything one man can imagine, other man can make real.
        --- Jules Verne (1828--1905)
        """,
        size=(854,480))


if __name__ == '__main__':
    dive()
