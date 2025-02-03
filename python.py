"""
Name: Python
Description: An app to make and run Python code!
Author: Tsunami014
"""
from API import App, ResizableWindow, strLen, split, StaticPos
from widgets import findLines
import widgets as wids
import threading
import subprocess
import json
import queue
import bar
import os
import sys
import time
import regex

class Linting:
    def __init__(self):
        # Queues for responses (requests with an id) and notifications.
        self.response_queue = queue.Queue()
        self.notification_queue = queue.Queue()

        self.server_proc = subprocess.Popen(
            ["ruff", "server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0  # unbuffered
        )

        # Start a thread to continuously read messages from the server.
        self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.reader_thread.start()

        # Send initialize request.
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "processId": None,
                "rootUri": None,
                "capabilities": {}
            }
        }
        self._send(init_request)
        init_response = self._wait_for_response(1)
        # print("Initialization response:", init_response)

        # Optionally, send an initialized notification as per LSP.
        self._send({
            "jsonrpc": "2.0",
            "method": "initialized",
            "params": {}
        })

    def _send(self, data):
        """Send a JSON-RPC message to the language server."""
        message = json.dumps(data)
        # Frame the message with HTTP-like headers.
        header = f"Content-Length: {len(message.encode('utf-8'))}\r\n\r\n"
        self.server_proc.stdin.write(header.encode('utf-8'))
        self.server_proc.stdin.write(message.encode('utf-8'))
        self.server_proc.stdin.flush()

    def _read_loop(self):
        """Continuously read messages from the language server and distribute them."""
        while True:
            try:
                # Read header line.
                header_line = self.server_proc.stdout.readline().decode('utf-8')
                if not header_line:
                    break  # Process has ended.
                if header_line.startswith("Content-Length:"):
                    # Extract content length.
                    try:
                        content_length = int(header_line.strip().split(" ")[1])
                    except (IndexError, ValueError):
                        continue
                    # Read the blank line.
                    self.server_proc.stdout.readline()
                    # Read the content.
                    content = self.server_proc.stdout.read(content_length).decode('utf-8')
                    message = json.loads(content)
                    # If the message has an "id", assume it’s a response; otherwise, treat as a notification.
                    if "id" in message:
                        self.response_queue.put(message)
                    elif "method" in message:
                        self.notification_queue.put(message)
            except Exception as e:
                print("Error in read loop:", e)
                break

    def _wait_for_response(self, message_id, timeout=5):
        """Wait for a response with a specific id from the server."""
        start_time = time.time()
        while True:
            try:
                response = self.response_queue.get(timeout=timeout)
                if response.get("id") == message_id:
                    return response
            except queue.Empty:
                break
            if time.time() - start_time > timeout:
                break
        return None

    def lint(self, code):
        """Send the code as an in-memory document and wait for linting diagnostics."""
        # Send a didOpen notification with the document content.
        self._send({
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {
                    "uri": "inmemory://model/1",  # Custom URI for in-memory file.
                    "languageId": "python",
                    "version": 1,
                    "text": code
                }
            }
        })

        # Optionally, you can send didChange notifications if you plan on incremental changes.

        # Wait for a publishDiagnostics notification for this document.
        diagnostics = None
        start_time = time.time()
        while time.time() - start_time < 5:  # Wait up to 5 seconds.
            try:
                notification = self.notification_queue.get(timeout=1)
                if notification.get("method") == "textDocument/publishDiagnostics":
                    params = notification.get("params", {})
                    if params.get("uri") == "inmemory://model/1":
                        diagnostics = params.get("diagnostics")
                        break
            except queue.Empty:
                continue
        return diagnostics

    def __del__(self):
        if self.server_proc:
            self.server_proc.kill()

class LintInBG:
    def __init__(self, getCodeFunc):
        self.getCodeFunc = getCodeFunc
        self.linting = Linting()
        self.lastlints = []
        self.thread = threading.Thread(target=self._lint, daemon=True)
        self.thread.start()
    
    def _lint(self):
        while True:
            code = self.getCodeFunc()
            if code:
                diagnostics = self.linting.lint(code)
                self.lastlints = diagnostics or []
            else:
                self.lastlints = []
            time.sleep(0.5)

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

class LintingTextInput(wids.TextInput):
    def __init__(self, pos, max_width=None, max_height=None, placeholder='', start=''):
        super().__init__(pos, max_width, max_height, placeholder, start)
        self.linter = LintInBG(lambda: self.text)
    
    @property
    def lints(self):
        """A list of linting diagnostics in the format:
        
        `[{'start': character, 'end': character, 'message': str, 'severity': int}]`
        """
        lines = self.text.split('\n')
        out = []
        for lnt in self.linter.lastlints:
            if 'range' in lnt:
                start = sum([(len(i)+1) for i in lines[:lnt['range']['start']['line']]] or [0])+lnt['range']['start']['character']
                end = sum([(len(i)+1) for i in lines[:lnt['range']['end']['line']]] or [0])+lnt['range']['end']['character']
            else:
                start = sum([(len(i)+1) for i in lines[:lnt['start']['line']]] or [0])+lnt['start']['character']
                end = sum([(len(i)+1) for i in lines[:lnt['end']['line']]] or [0])+lnt['end']['character']
            if 'code' in lnt:
                msg = lnt['code'] + ': ' + lnt['message']
            else:
                msg = lnt['message']
            out.append({
                'start': start,
                'end': end,
                'message': msg,
                'severity': lnt['severity']
            })
        return out
    
    def draw(self):
        if self.text == '':
            lnts = []
            if self.placeholder != '':
                lines = findLines(self.placeholder, self.max_width)
                lines = [f'\033[90m{i}\033[39m' for i in lines]
            else:
                if self.max_width is not None:
                    lines = [' '*self.max_width]
                else:
                    lines = ['']
        else:
            lnts = self.lints
            txt = self.text
            for col, lets, type in [
                ('34', [
                    'if', 'elif', 'else', 'for', 'while', 'with', 'def', 'class', 'return', 'break', 'continue', 'pass', 'raise', 'import', 'from', 'as', 'in',
                    'and', 'or', 'not', 'is', 'del', 'assert', 'global', 'nonlocal', 'lambda', 'yield', 'try', 'except', 'finally', 'raise', 'True', 'False', 'None'
                ], 'word'),
                ('33', [
                    'print', 'input', 'open', 'range', 'enumerate', 'zip', 'map', 'filter', 'sorted', 'reversed', 'sum', 'min', 'max', 'any', 'all', 'len', 'abs', 
                    'round', 'pow', 'divmod', 'int', 'float', 'str', 'list', 'tuple', 'dict', 'set', 'frozenset', 'bool', 'type', 'range', 'slice', 'complex', 'bytes', 
                    'bytearray', 'memoryview', 'object', 'super', 'staticmethod', 'classmethod', 'property', 'staticmethod', 'classmethod', 'property', 'iter', 'next',
                    'hasattr', 'getattr', 'setattr', 'delattr', 'vars', 'dir', 'locals', 'globals', 'exec', 'eval', 'compile', 'open', 'isinstance', 'issubclass', 'callable',
                    'id', 'hash', 'repr', 'chr', 'ord', 'bin', 'oct', 'hex', 'format', 'ascii', 'repr', 'str', 'bytes', 'bytearray', 'memoryview', 'complex', 'int', 'float',
                    'list', 'tuple', 'dict', 'set', 'frozenset', 'bool', 'type', 'range', 'slice', 'object', 'property', 'staticmethod', 'classmethod', 'super', 'iter', 'next',
                ], 'word'),
                ('92', '0123456789"\'', 'all'),
                ('35', '+-/*@=><%&|^~', 'all'),
                ('37', '.,:;()[]{}', 'all'),
            ]:
                for l in lets:
                    if type == 'word':
                        txt = regex.sub('\x1B[@-_][0-?]*[ -\\/]*[@-~](*SKIP)(*FAIL)|\\b'+regex.escape(l)+'\\b', '\033['+col+';24m'+l+'\033[39;4m', txt)
                    else:
                        txt = regex.sub('\x1B[@-_][0-?]*[ -\\/]*[@-~](*SKIP)(*FAIL)|'+regex.escape(l), '\033['+col+';24m'+l+'\033[39;4m', txt)
            
            txt = regex.sub(r'#.*', '\033[90m\\g<0>\033[39m', txt)

            end = '\033[39;4m'
            
            for lnt in lnts:
                if lnt['severity'] == 1:
                    col = '\033[91;24m'
                elif lnt['severity'] == 2:
                    col = '\033[93;24m'
                else:
                    raise ValueError(f'Unknown severity: {lnt["severity"]} for error {lnt}')
                spl = split(txt)
                idx = 0
                i = 0
                realIdx = 0
                while idx < len(spl) and realIdx < lnt['start']:
                    if spl[idx][0] != '\033':
                        realIdx += 1
                    i += len(spl[idx])
                    idx += 1
                while idx < len(spl) and spl[idx][0] == '\033':
                    i += len(spl[idx])
                    idx += 1
                startIdx = i
                while idx < len(spl) and realIdx < lnt['end']:
                    if spl[idx][0] != '\033':
                        realIdx += 1
                    i += len(spl[idx])
                    idx += 1
                mid = txt[startIdx:i].replace(' ', '·')
                if mid.strip('\n') == '':
                    mid = '¶'+mid
                txt = txt[:startIdx]+col+mid+end+txt[i:]
            lines = findLines(txt, self.max_width)
        self.width = self.max_width or max(strLen(i) for i in lines)+1
        lines = [f'\033[4m{i + ' '*(self.width-strLen(i))}\033[24m' for i in lines]
        
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
        
        if self.API.RMB:
            mp = self.API.Mouse
            if mp[0] >= x and mp[0] < x+self.width and mp[1] >= y and mp[1] <= y+self.height:
                relx, rely = mp[0]-x-1, mp[1]-y-1
                endidx = 0
                y = 0
                if self.max_width is not None:
                    paragraph = ''
                    for paragraph in self.text.split('\n'):
                        if y == rely:
                            break
                        while len(paragraph) > self.max_width:
                            space_index = paragraph.rfind(' ', 0, self.max_width)
                            if space_index == -1:
                                space_index = self.max_width
                            endidx += len(paragraph[:space_index])
                            y += 1
                            paragraph = paragraph[space_index:].lstrip()
                            if y == rely:
                                break
                        if y == rely:
                            break
                        endidx += len(paragraph)+1
                        y += 1
                else:
                    paragraph = ''
                    for paragraph in self.text.split('\n'):
                        if y == rely:
                            break
                        endidx += len(paragraph)+1
                        y += 1
                
                if relx <= len(paragraph):
                    endidx += relx
                    problems = [i for i in lnts if i['start'] <= endidx < i['end'] or (i['start'] == i['end'] == endidx)]
                    idx = 0
                    for prob in problems:
                        if prob['severity'] == 1:
                            col = '41'
                        elif prob['severity'] == 2:
                            col = '43'
                        else:
                            raise ValueError(f'Unknown severity: {prob["severity"]} for error {prob}')
                        lines = findLines(prob['message'], self.max_width-relx)
                        for line in lines:
                            end = ';4' if rely+idx+1 < self.height else ''
                            self._Write(mp[0]-1, mp[1]+idx, '\033[', col, ';24;39m', line, '\033[49', end, 'm')
                            idx += 1

class Python(App):
    def __new__(cls, *args, **kwargs):
        inst = object.__new__(cls, *args, **kwargs)
        inst.Win = SplitWindow(0, 0, *inst.init_widgets())
        inst.Win.fullscreen()
        inst.Win.update()
        return inst
    
    def init_widgets(self):
        return [
            LintingTextInput(StaticPos(0, 0)),
            wids.Text(StaticPos(1, 0), '')
        ]

def load():
    bar.BarApp(Python)
