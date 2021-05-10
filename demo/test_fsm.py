#! python
# -*- coding: utf-8 -*-
"""Test of FSM [A Gate Keeper]

Usage: Input 'coin' or 'pass' to the prompt.
    Press [C-c] or 'q', 'bye', and any other inputs will terminate the loop.
"""
from __future__ import (division, print_function,
                        absolute_import, unicode_literals)
import mwx


Locked, Unlocked = 'Locked', 'Unlocked' # states

Coin, Pass = 'coin', 'pass' # inputs

fsm = mwx.FSM({
        Locked : {
            Coin : (Unlocked, lambda: print("\tGate is unlocked")),
            Pass : (Locked,   lambda: print("\tWait! (ﾟДﾟ)ｺﾞﾙｧ")),
        },
        Unlocked : {
            Coin : (Unlocked, lambda: print("\tThanks! (ﾟ∀ﾟ)ｲｯﾃﾖｼ")),
            Pass : (Locked,   lambda: print("\tGate is locked")),
        },
    },
    default = Locked
)

if __name__ == "__main__":
    while fsm(input("[{}] > ".format(fsm.current_state))):
        pass
    print('Au revoir!')
