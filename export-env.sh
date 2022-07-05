#!/bin/bash

cd "$(dirname "$0")" || exit 1

eval "$(command conda 'shell.bash' 'hook' 2> /dev/null)"

conda deactivate

conda activate audio-lessons || exit 1

conda env export --no-builds | grep -v "prefix:" > environment.yml

