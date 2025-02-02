# TerminalOS apps
These are apps that can be run on [TerminalOS](https://github.com/Tsunami014/TerminalOS).

They are all avaliable in it's software manager.

You are welcome to PR in your own apps!

# To make an app
Make a python file that has a unique name and make sure it has things like `bar.register` or it won't do anything. Also, at the start of the file, you *should* have a docstring with the format:
```python
"""
Name: <name>
Description: <description>
Author: <author>
Email: <email>
Version: <version>
License: <license>
"""
# Rest of code here
```
All values in that are optional, and you can have other lines in it too. These values are what the user sees when installing.

*BE SURE TO ADD IN A `def load():` FUNCTION THAT RUNS THE APP, OTHERWISE YOUR APP WILL NOT WORK.*

# Apps list
- [Test](#test)
- [python](#python)

## Test
This is a test app that does nothing special.

## python
This is a python interpreter that can run python code.

### Pre-requisites
- Ruff: installable via `pip install ruff` or another method from [it's website](https://docs.astral.sh/ruff/installation/)
