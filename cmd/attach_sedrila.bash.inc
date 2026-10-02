# for bash: source /absolute/path/to/attach_sedrila.bash.inc
# defines alias 'sedrila' for calling sedrila

sedrilacmdabsdir="`realpath ${BASH_SOURCE:-$0}`"
sedrilacmddir="`dirname $sedrilacmdabsdir`"
sedriladir="`dirname $sedrilacmddir`"
sedrilacmd="-m sedrila"  # sedriladir must be on the PYTHONPATH, see below

# check whether Python3 is installed
if command -v python3 &> /dev/null; then
  alias sedrila="PYTHONPATH=$sedriladir python3 $sedrilacmd"
else
  alias sedrila="PYTHONPATH=$sedriladir python $sedrilacmd"
fi
