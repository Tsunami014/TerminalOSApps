"""
Name: Test package
Description: A testing package to test the downloading and stuff
Author: Tsunami014
Email: tsunami014@duck.com
Version: 0.1.0
"""

from API import App, Popup, StaticPos, RelativePos
import widgets as wids
import bar

class Test(App):
    def init_widgets(self):
        return [
            wids.Text(StaticPos(0, 0), 'Hello, World!'), 
            wids.Button(StaticPos(0, 1), 'Click me!', lambda: Popup(wids.Text(StaticPos(0, 0), 'This is a popup!\nHi!'))),
            wids.TextInput(RelativePos(1, 0, len('Hello, World! '), 0), placeholder='Type here: ')
        ]

def load():
    bar.BarApp(Test)
