# for bash: source /absolute/path/to/attach_sedrila.bash.inc
# defines alias 'sedrila' for calling sedrila

sedrilacmdabsdir="`realpath ${BASH_SOURCE:-$0}`"
sedrilacmddir="`dirname $sedrilacmdabsdir`"
sedriladir="`dirname $sedrilacmddir`"
sedrilacmd="$sedriladir/py/sedrila.py"

# check whether Python3 is installed
if command -v python3 &> /dev/null; then
  alias sedrila="python3 $sedrilacmd"
else
  alias sedrila="python $sedrilacmd"
fi
