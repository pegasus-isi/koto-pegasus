#!/bin/bash
#----------------------------------------------------------------------------------#
# run_koto.sh
#    This is an example shell script to produce KOTO MC analysis files from GEANT4.
#
# author: C. Lin ( chiehlin@uchicago.edu )
# date  : Aug 9, 2022
#-----------------------------------------------------------------------------------#
#
#-----------------------------------------------------------------------------------#
# configuration for users
#-----------------------------------------------------------------------------------#
# - userflag: The flag to enable certain features during production.
# - nevent  : Number of events to be generated.
# - seed    : Random seed to generate MC. (-1: disable accidental overlay)
#
userflag=20210606
DecayMode=$1
NKL=1000
SeedID=$2

#------------------------------------------------------------------------------------#
# environment settings
#
echo "HOSTNAME = $HOSTNAME"
loc=`pwd`
echo "Current location = $loc"

echo -e "Set environment for ROOT and GEANT4."

source /opt/koto/root/v6.22.02/bin/thisroot.sh
source /opt/koto/geant4/10.05.p01/bin/geant4.sh

#####
# set e14 library (for simulation)
#
export E14_TOP_DIR="/opt/koto/e14/201605v6.2/e14"
export MY_TOP_DIR="/opt/koto/e14osg"
echo "E14_TOP_DIR =" $E14_TOP_DIR
echo "MY_TOP_DIR  =" $E14_TOP_DIR

####
# !!!!: E14_TOP_DIR and MY_TOP_DIR need to be set before executing setup.sh 
#
source /opt/koto/e14/201605v6.2/setup.sh

AccFile=$3

#####
# Point the E14ANA_EXTERNAL_DATA path to the uncompressed external file directory.
#
export E14ANA_EXTERNAL_DATA="./external"

#####
#
echo -e "\n\n\n\n"

##############
#Run Fast Sim
##############

OutFast=fastout_${DecayMode}_${SeedID}.root

${E14_TOP_DIR}/examples/gsim4test/bin/gsim4test ${TOP_DIR}/macro/fastmacro.mac ${OutFast} ${NKL} ${SeedID} ${SeedID}

################
#Event Seletion
################

SelectionInput=${OutFast}
Selection_Output=${DecayMode}Select_${SeedID}.root
Selection_Exec=selection

${Selection_Exec} ${SelectionInput} ${Selection_Output}

rm -f ${OutFast}

#Count Number of Events Generated

CountInput=${Selection_Output}
Count_Exec=countselection

${Count_Exec} ${CountInput}

##############
#Run Full Sim
##############

sed "s/KL3pi0Select_0.root/KL3pi0Select_${SeedID}.root/g" e14_201605_Full_KL3pi0_0.mac > e14_201605_Full_KL3pi0_${SeedID}.mac

OutFull=KL3pi0Full_${SeedID}.root

# run geant4
echo "Run GEANT4"
/opt/koto/e14/201605v6.2/e14/examples/gsim4test/bin/gsim4test e14_201605_Full_KL3pi0_${SeedID}.mac ${OutFull} ${NKL} ${SeedID} ${SeedID}

rm -f ${Selection_Output}
rm -f e14_201605_Full_KL3pi0_0.mac
rm -f e14_201605_Full_KL3pi0_${SeedID}.mac

#####
# uncompress parameter files
#
echo "Directory contents"
ls -a
tar -xvzf par.tar.gz
tar -xvzf common.tar.gz

#####
# for debugging:
#    print out the content after compression.
#
echo -e "\n\n\n\nContent after compression"
ls db
ls ftt
ls external


# gsim2dst
echo "Run gsim2dst"
dstout="dst.root"
#/e14osg/AnalysisCode/gsim2dst/bin/gsim2dst ${OutFull} ${dstout} ${AccFile} 0 ${SeedID} ${userflag} ./db ./ftt 0 

#rm -rf ${OutFull}
rm -rf ${AccFile}
rm -rf db 
rm -rf ftt
rm -rf par.tar.gz

# clustering
echo "Run clustering"
clusout="cluster.root"
clus_option="0"
#/e14osg/AnalysisCode/clusteringFromDst/bin/clusteringFromDst ${dstout} ${clusout} ${SeedID} ${userflag} ${clus_option}

rm -f ${dstout}

# g2ana/g2anaKL/g4ana/g6ana
g6anaout="${DecayMode}_Accidental_${SeedID}.root"
#/e14osg/AnalysisCode/g6ana/bin/g6ana ${clusout} ${g6anaout} ${userflag}

rm -f ${clusout}

#Basic Cuts
cut_input=${g6anaout}
cut_output="${DecayMode}_BasicVetoAndCuts_Accidental_${SeedID}.root"
cut_exec=basicvetoandcuts

${cut_exec} ${cut_input} ${cut_output}

rm -rf ${g6anaout}
rm -rf external
rm -rf common.tar.gz

# what is left?
ls -lh


