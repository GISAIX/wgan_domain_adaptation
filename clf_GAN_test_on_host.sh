#!/bin/bash
#
# Script to send job to BIWI clusters using qsub.
# Usage: qsub train_on_host.sh
# Adjust line '-l hostname=xxxxx' before runing.
# The script also requires changing the paths of the CUDA and python environments
# and the code to the local equivalents of your machines.
# Author: Christian F. Baumgartner (c.f.baumgartner@gmail.com)

## SET THE FOLLOWING VARIABLES ACCORDING TO YOUR SYSTEM ##
CUDA_HOME=/scratch_net/brossa/jdietric/libs/cuda-8.0
PROJECT_HOME=/scratch_net/brossa/jdietric/PycharmProjects/mri_domain_adapt
VIRTUAL_ENV_PATH=/scratch_net/brossa/jdietric/libs/virtual_envs/env_gpu

## SGE Variables:
#
## otherwise the default shell would be used
#$ -S /bin/bash
#
## <= 2h is short queue, <= 24h is middle queue, <= 120 h is long queue
#$ -l h_rt=0:30:00

## the maximum memory usage of this job, (below 4G does not make much sense)
#$ -l h_vmem=15G

# Host and gpu settings
#$ -l gpu
##$ -l hostname=biwirender04  ## <-------------- Comment in or out to force a specific machine

## stderr and stdout are merged together to stdout
#$ -j y
#
# logging directory. preferably on your scratch
#$ -o /scratch_net/brossa/jdietric/logs/test_gen_clf/  ## <---------------- CHANGE TO MATCH YOUR SYSTEM
#
## send mail on job's end and abort
#$ -m a

## LOCAL PATHS
# I think .bashrc is not executed on the remote host if you use qsub, so you need to set all the paths
# and environment variables before exectuting the python code.

# cuda paths
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$CUDA_HOME/extras/CUPTI/lib64:$LD_LIBRARY_PATH

# for pyenv
export PATH="/home/baumgach/.pyenv/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

# activate virtual environment
source $VIRTUAL_ENV_PATH/bin/activate

## EXECUTION OF PYTHON CODE:
python $PROJECT_HOME/clf_GAN_test.py

echo "Hostname was: `hostname`"
echo "Reached end of job file."


