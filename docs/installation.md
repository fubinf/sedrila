# User installation

Get [pipx](https://pipx.pypa.io/stable/installation/) and then do

```
pipx install sedrila
```


# Developer installation

In case you want to make changes to sedrila yourself,
this is how to set up development:
Get [poetry](https://python-poetry.org/docs/) and then do

```
git clone git@github.com:fubinf/sedrila.git
cd sedrila
poetry install
alias act_poetry="source $(poetry env info --path)/bin/activate"
act_poetry
alias sedrila="python `pwd`/py/sedrila.py"
sedrila --help
```

`poetry install` creates a venv and installs all dependencies into it.  
Put the `act_poetry` alias in your `.bashrc` and use it each time you want to work
on a poetry-based developer install like this.  
As usual, use `deactivate` to deactivate the poetry-generated venv when needed.  
Put the `sedrila` alias in your `.bashrc` and use it each time you want to call
sedrila conveniently; replace the ``pwd`` with the sedrila directory.
(This alias will soon be replaced by a sedrila executable in the venv.)
