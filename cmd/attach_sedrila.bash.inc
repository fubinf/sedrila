# for bash: source /absolute/path/to/attach_sedrila.bash.inc
# defines alias 'sedrila' for calling sedrila

sedrilacmddir="`dirname $BASH_SOURCE`"
sedriladir="`dirname $sedrilacmddir`"
sedrilacmd="$sedriladir/py/sedrila.py"
alias sedrila="python $sedrilacmd"
