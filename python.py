"""
Name: Python
Description: An app to make and run Python code!
Author: Tsunami014
"""
from API import App, ResizableWindow, strLen, split, Popup, StaticPos
from multiprocess import Process, Pipe
import widgets as wids
import bar
import sys

class WritablePipe:
    def __init__(self, pipe):
        self.pipe = pipe
    
    def write(self, text):
        self.pipe.send(text)

class SplitWindow(ResizableWindow):
    def __init__(self, x, y, *widgets):
        self.split = None
        self._grabbingBar = None
        self.pipe = None
        self.process = None
        super().__init__(x, y, 50, 10, *widgets)
        self.update()
    
    def draw(self):
        self.Screen.Clear()
        for widget in self.widgets:
            if self.split is not None:
                pos = widget._pos
                if pos.x == 0:
                    widget.max_width = self.split-1
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
    
    def run(self, code, pipe):
        backup = sys.stdout
        sys.stdout = WritablePipe(pipe)
        try:
            exec(code, {}, {})
        except Exception as e:
            print(e)
        sys.stdout = backup
        pipe.close()
    
    def update(self):
        ret = super().update()

        mp = self.API.Mouse
        self.size = [max(self.size[0], 7), max(self.size[1], 3)]

        if self.split is None:
            self.split = self.size[0]//2
        
        if '\x1b[15~' in self.API.events or '\x1b[[E' in self.API.events:
            self.pipe, child_pipe = Pipe()
            self.widgets[1].text += '--------File--------\n'
            self.process = Process(target=self.run, args=(self.widgets[0].text, child_pipe,), daemon=True)
            self.process.start()
        
        if self.pipe is not None:
            if self.pipe.poll():
                try:
                    self.widgets[1].text += self.pipe.recv()
                except EOFError:
                    self.pipe = None
                    if self.process is not None:
                        if self.process.is_alive():
                            self.process.kill()
                        self.process = None
                    self.widgets[1].text += '--------END--------\n'
        
        if self.process is not None and not self.process.is_alive():
            self.process = None
            self.pipe = None
            self.widgets[1].text += '--------END--------\n'
        
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

class Python(App):
    def __new__(cls, *args, **kwargs):
        inst = object.__new__(cls, *args, **kwargs)
        inst.Win = SplitWindow(0, 0, *inst.init_widgets())
        return inst
    
    def init_widgets(self):
        return [
            wids.TextInput(StaticPos(0, 0), placeholder=' '),
            wids.Text(StaticPos(1, 0), '')
        ]

def load():
    bar.BarApp(Python)
