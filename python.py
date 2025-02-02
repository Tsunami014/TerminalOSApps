"""
Name: Python
Description: An app to make and run Python code!
Author: Tsunami014
"""
from API import App, ResizableWindow, strLen, split, Popup, StaticPos
from widgets import findLines
import widgets as wids
import threading
import subprocess
import bar
import os
import sys
import time

class WritablePipe:
    def __init__(self, elm):
        self.elm = elm
        # create a pipe: r for reading, w for writing
        self._r, self._w = os.pipe()
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def _reader(self):
        with os.fdopen(self._r, 'r', encoding='utf-8', errors='replace') as reader:
            for line in reader:
                self.elm.text += line

    def fileno(self):
        return self._w

class SplitWindow(ResizableWindow):
    def __init__(self, x, y, *widgets):
        self.split = None
        self._grabbingBar = None
        super().__init__(x, y, 50, 10, *widgets)
    
    def draw(self):
        self.Screen.Clear()
        for widget in self.widgets:
            if self.split is not None:
                pos = widget._pos
                if pos.x == 0:
                    widget.max_width = self.split-2
                else:
                    pos.x = self.split
                    widget.max_width = self.width-self.split-2
            widget.draw()
        
        if self.Screen.screen == {}:
            lines = []
        else:
            lines = ["" for _ in range(max(self.Screen.screen.keys())+1)]
        for idx, line in self.Screen.screen.items():
            lines[idx] = str(line)
        
        x, y = self.x, self.y

        if self.isFullscreen:
            width, height = self.API.get_terminal_size()
            self._Write(width-2, 0, ']X')
            for idx, ln in enumerate(lines):
                self._Write(x+1, y+idx+1, ln)
            self._Write(self.split, 0, '┬')
            for ln in range(self.API.get_terminal_size()[1]-2):
                self._Write(self.split, ln+1, '│')
        else:
            self._Write(x, y, '╭', '─'*(self.split-1), '┬', '─'*(self.size[0]-2-self.split-1), '[X')
            for idx, ln in enumerate(lines[:self.size[1]-2]):
                if len(ln) > self.size[0]-2:
                    spl = split(ln)
                    out = []
                    i = 0
                    for c in spl:
                        out.append(c)
                        if not c[0] == '\033':
                            i += 1
                            if i > self.size[0]-2:
                                break
                    ln = "".join(out)
                self._Write(x, y+idx+1, f'│{ln}{" "*(self.size[0]-2-strLen(ln))}│')
                self._Write(x+self.split, y+idx+1, '│')
            txt = '│'+' '*(self.split-1)+'│'+' '*(self.size[0]-2-self.split)+'│'
            for idx in range(len(lines), self.size[1]-2):
                self._Write(x, y+idx+1, txt)
            self._Write(x, y+self.size[1]-1, '╰', '─'*(self.split-1), '┴', '─'*(self.size[0]-2-self.split), '+')
    
    def _fixSplit(self):
        if self.isFullscreen:
            self.split = min(max(self.split, 5), self.API.get_terminal_size()[0]-3)
        else:
            self.split = min(max(self.split, 5), self.size[0]-3)
    
    def update(self):
        ret = super().update()

        mp = self.API.Mouse
        self.size = [max(self.size[0], 7), max(self.size[1], 3)]

        if self.split is None:
            if self.isFullscreen:
                self.split = self.API.get_terminal_size()[0]//2-1
            else:
                self.split = self.size[0]//2
        
        if '\x1b[15~' in self.API.events or '\x1b[[E' in self.API.events:
            self.widgets[1].text = '--------File--------\n'
            pipe = WritablePipe(self.widgets[1])
            subprocess.Popen([sys.executable, "-c", self.widgets[0].text], stdout=pipe, stderr=pipe)
        
        self._fixSplit()

        if self.API.LMB:
            if self.API.LMBP:
                if mp[0] == self.x+self.split and (self.isFullscreen or self.y < mp[1] <= self.y+self.height):
                    self._grabbingBar = mp[0]
            elif self._grabbingBar is not None:
                if mp[0] != self._grabbingBar:
                    self._grabbingBar = mp[0]
                    self.split = mp[0]-self.x
                    self._fixSplit()
                    return True
        else:
            self._grabbingBar = None
        return ret

class ExpandableTextInput(wids.TextInput):
    def draw(self):
        if self.text == '':
            if self.placeholder != '':
                lines = findLines(self.placeholder, self.max_width)
                lines = [f'\033[90m{i}\033[39m' for i in lines]
            else:
                if self.max_width is not None:
                    lines = [' '*self.max_width]
                else:
                    lines = ['']
        else:
            lines = findLines(self.text, self.max_width)
        self.width = self.max_width or max(strLen(i) for i in lines)+1
        lines = [f'\033[4m{i + ' '*(self.width-len(i))}\033[24m' for i in lines]
        
        self.height = len(lines)
        if self.max_height:
            self.height = min(self.height, self.max_height)

        x, y = self.pos
        
        for idx, line in enumerate(lines[:self.height]):
            self._Write(x, y+idx, line)
        

        if self.cursor is not None:
            if self.text == '' and self.placeholder != '':
                newchar = '\033[39m|\033[90m'
            else:
                newchar = '|'
            self.fix_cursor(lines)
            chars = split(self._Screen.Get(x+self.cursor[0], y+self.cursor[1]))
            if round(time.time()*3)%3 != 0:
                for idx in range(len(chars)):
                    if chars[idx][0] != '\033':
                        chars[idx] = newchar
                        break
                else:
                    chars = [newchar]+chars
            else:
                if all(i[0] == '\033' for i in chars):
                    chars = [' ']+chars
            self._Write(x+self.cursor[0], y+self.cursor[1], *chars)

class Python(App):
    def __new__(cls, *args, **kwargs):
        inst = object.__new__(cls, *args, **kwargs)
        inst.Win = SplitWindow(0, 0, *inst.init_widgets())
        inst.Win.fullscreen()
        inst.Win.update()
        return inst
    
    def init_widgets(self):
        return [
            ExpandableTextInput(StaticPos(0, 0)),
            wids.Text(StaticPos(1, 0), '')
        ]

def load():
    bar.BarApp(Python)
