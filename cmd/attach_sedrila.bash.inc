# for bash: source /absolute/path/to/attach_sedrila.bash.inc
# defines alias 'sedrila' for calling sedrila

sedrilacmdabsdir="`realpath ${BASH_SOURCE:-$0}`"
sedrilacmddir="`dirname $sedrilacmdabsdir`"
sedriladir="`dirname $sedrilacmddir`"
sedrilacmd="$sedriladir/py/sedrila.py"
alias sedrila="python $sedrilacmd"
