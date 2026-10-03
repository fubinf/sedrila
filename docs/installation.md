# sedrila Installation

## 1. User installation

Get [pipx](https://pipx.pypa.io/stable/installation/) and then do

```
pipx install sedrila
```


## 2. Developer installation

In case you want to make changes to sedrila yourself,
this is how to set up development:
Get [uv](https://docs.astral.sh/uv/getting-started/installation/) and then do

```
git clone git@github.com:fubinf/sedrila.git
cd sedrila
uv sync
source .venv/bin/activate
alias sedrila="PYTHONPATH=`pwd` python -m sedrila"
sedrila --help
```

`uv sync` creates the venv `.venv` and installs all dependencies (including the dev group) into it.  
Use `source .venv/bin/activate` each time you want to work on this developer install;
while it is active, `uv run --active ...` and plain `python`/`pytest` use that same venv.  
As usual, use `deactivate` to deactivate the venv when needed.  
Put the `sedrila` alias in your `.bashrc` and use it each time you want to call
sedrila conveniently; replace the ``pwd`` with the sedrila directory.
(This alias will soon be replaced by a sedrila executable in the venv.)
