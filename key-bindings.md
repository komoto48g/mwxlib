# key bindings

キー割り当て一覧

    global-map : (0 :default)
     ctl-x-map : 'C-x' ... extention map for the frame
      spec-map : 'C-c' ... spefific map for the editors and the shell
       esc-map : 'escape'


## Shell

Global bindings: (see also `self.inspector.handler@filling`)

	[ 0 ]
                   C-S-d : 0, duplicate_line~<'Duplicate an expression at the caret-line'>
                     C-d : 0, duplicate_line~<'Duplicate an expression at the caret-line'>
                     C-f : 0, OnFindText
                   C-f12 : 0, clone_shell~<'Clone the current shell'>
                     C-w : 0, close_shell~<'Close the current shell'>
                     C-x : 'C-x', prefix_command_hook, skip
                     M-f : 0, OnFilterText
                   M-f12 : 0, close_shell~<'Close the current shell'>
                  M-left : 0, other_window~<'Focus moves to other window'>
                     M-q : 0, close<'Close the window'>
                 M-right : 0, other_window~<'Focus moves to other window'>
                   S-f12 : 0, clear_shell~<'Clear the current shell'>
                    S-f3 : 0, OnFindPrev
                Xbutton1 : 0, other_editor~<'Focus moves to other page (no loop)'>
                Xbutton2 : 0, other_editor~<'Focus moves to other page (no loop)'>
                      f1 : 0, About
                     f11 : 0, show_page~<'Toggle ghost'>
                     f12 : 0, close<'Close the window'>
                      f3 : 0, OnFindNext
	[ 'C-x' ]
                     S-h : 0, show_page~<'Show History'>
                       h : 0, show_page~<'Show Help'>
                    home : 0, show_page~<'Show root shell'>
                       i : 0, show_page~<'Show wit'>
                       j : 0, show_page~<'Show Scratch'>
                       l : 0, show_page~<'Show Log'>
                       m : 0, show_page~<'Show monitor'>
                       n : 0, other_editor~<'Focus moves to other page (no loop)'>
                       p : 0, other_editor~<'Focus moves to other page (no loop)'>
                       r : 0, show_page~<'Show root shell'>


## Nautilus

Modes:

     -- : [0] global-map
    TAB : [1] history-comp-mode
    M-. : [2] word-comp-mode
    M-/ : [3] apropos-comp-mode
    M-, : [4] text-comp-mode
    M-m : [5] module-comp-mode

Global bindings:

	[ 0 ]
                       . : 2, OnEnterDot<'Called when dot(.) pressed'>
                     C-@ : 0, goto_marker~
                   C-S-@ : 0, goto_line_marker~
                C-S-down : 0, LineDownExtend~~<'Move caret down one line extending selection to new caret position.'>
               C-S-enter : 0, wx.py.shell:insertLineBreak~<'Insert a new line break.'>
                   C-S-f : 0, set_marker~
              C-S-insert : 0, Paste~<'Replace selection with clipboard contents.'>
                   C-S-l : 0, recenter~<'Scroll the cursor line to the center of screen'>
                C-S-left : 0, selection_backward_word_or_paren~
               C-S-right : 0, selection_forward_word_or_paren~
                 C-S-tab : 0, delete_backward_space_like_tab~<'Delete half-width spaces backward as if feeling like a S-tab'>
                  C-S-up : 0, LineUpExtend~~<'Move caret up one line extending selection to new caret position.'>
                   C-S-v : 0, Paste~<'Replace selection with clipboard contents.'>
                     C-a : 0, beggining_of_line~
             C-backspace : 0, skip
                     C-c : 'C-c', prefix_command_hook, skip
                     C-e : 0, end_of_line~
                 C-enter : 0, wx.py.shell:insertLineBreak~<'Insert a new line break.'>
                     C-h : 0, call_helpTip<'Show tooltips for the selected topic'>
                     C-j : 0, call_tooltip<'Call ToolTip of the selected word or command line'>
                     C-k : 0, kill_line~
                     C-l : 0, recenter~<'Scroll the cursor line to the center of screen'>
                  C-left : 0, OnBackspace<'Called when backspace (or *left) pressed'>
                 C-right : 0, WordRightEnd~~<'Move caret right one word, position cursor at end of word.'>
                 C-space : 0, set_marker~
                     C-t : 0, noskip
                   C-tab : 0, insert_space_like_tab~<'Enter half-width spaces forward as if feeling like a tab'>
                     C-v : 0, Paste~<'Replace selection with clipboard contents.'>
                     C-x : 'C-x', prefix_command_hook, skip
                     M-, : 4, call_text_autocomp<'Called when text-comp mode'>
                     M-. : 2, call_word_autocomp<'Called when word-comp mode'>
                     M-/ : 3, call_apropos_autocomp<'Called when apropos mode'>
                     M-a : 0, back_to_indentation~
                  M-down : 0, goto_next_mark~
                     M-e : 0, end_of_line~
                 M-enter : 0, duplicate_command~
                     M-h : 0, call_helpTip2
                     M-j : 0, call_tooltip2<'Call ToolTip of the selected word or repr'>
                     M-m : 5, call_module_autocomp<'Called when module-comp mode'>
                     M-n : 1, call_history_comp<'Called when history-comp mode'>
                     M-p : 1, call_history_comp<'Called when history-comp mode'>
                    M-up : 0, goto_previous_mark~
             S-backspace : 0, backward_kill_line~
                S-insert : 0, Paste~<'Replace selection with clipboard contents.'>
                 S-space : 0, set_line_marker~
                   S-tab : 0, skip
                   enter : 0, OnEnter<'Called when enter pressed'>
                  escape : -1, OnEscape<'Called when escape pressed'>
                      f9 : 0, wrap~<'toggle-fold-type'>
                  insert : 0, over~<'toggle-over'>
                    left : 0, OnBackspace<'Called when backspace (or *left) pressed'>
                   space : 0, OnSpace<'Called when space pressed'>
                     tab : 1, call_history_comp<'Called when history-comp mode'>
	[ 'C-x' ]
                       [ : 0, skip, goto_char~<'beginning-of-buffer'>
                       ] : 0, skip, goto_char~<'end-of-buffer'>
	[ 'C-c' ]
                     C-c : 0, goto_matched_paren~
