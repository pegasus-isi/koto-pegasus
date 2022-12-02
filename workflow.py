#!/usr/bin/env python3

import getpass
import glob
import logging
import os
import random

from pathlib import Path
from Pegasus.api import *

logging.basicConfig(level=logging.INFO)

# --- Working Directory Setup --------------------------------------------------
# A good working directory for workflow runs and output files
WORK_DIR = Path("/scratch/{}/workflows".format(getpass.getuser()))
WORK_DIR.mkdir(exist_ok=True)

TOP_DIR = Path(__file__).resolve().parent

# --- Properties ---------------------------------------------------------------
props = Properties()
props["pegasus.data.configuration"] = "nonsharedfs"

# Provide a full kickstart record, including the environment, even for successful jobs
props["pegasus.gridstart.arguments"] = "-f"

# Limit the number of idle jobs for large workflows
props["dagman.maxidle"] = "1000"

# use timestamps for all our dirs - this make sure we have unique names in stash
props["pegasus.dir.useTimestamp"] = "true"

# seperate output dir for each workflow run
props["pegasus.dir.storage.deep"] = "true"

# Help Pegasus developers by sharing performance data (optional)
props["pegasus.monitord.encoding"] = "json"
props["pegasus.catalog.workflow.amqp.url"] = "amqp://friend:donatedata@msgs.pegasus.isi.edu:5672/prod/workflows"
props["pegasus.metrics.app"] = "KOTO"

# write properties file to ./pegasus.properties
props.write()

# --- Sites --------------------------------------------------------------------
sc = SiteCatalog()

# local site (submit machine)
local_site = Site(name="local")

local_shared_scratch = Directory(directory_type=Directory.SHARED_SCRATCH, path=WORK_DIR / "scratch")
local_shared_scratch.add_file_servers(FileServer(url="file://" + str(WORK_DIR / "scratch"), operation_type=Operation.ALL))
local_site.add_directories(local_shared_scratch)

local_storage = Directory(directory_type=Directory.LOCAL_STORAGE, path=WORK_DIR / "outputs")
local_storage.add_file_servers(FileServer(url="file://" + str(WORK_DIR / "outputs"), operation_type=Operation.ALL))
local_site.add_directories(local_storage)

local_site.add_env(PATH=os.environ["PATH"])
sc.add_sites(local_site)

# stash site (staging site, where intermediate data will be stored)
stash_site = Site(name="stash", arch=Arch.X86_64, os_type=OS.LINUX)
stash_staging_path = "/collab/user/{USER}/staging".format(USER=getpass.getuser())
stash_shared_scratch = Directory(directory_type=Directory.SHARED_SCRATCH, path=stash_staging_path)
stash_shared_scratch.add_file_servers(
    FileServer(
        url="stash:///osgconnect{STASH_STAGING_PATH}".format(STASH_STAGING_PATH=stash_staging_path), 
        operation_type=Operation.ALL)
)
stash_site.add_directories(stash_shared_scratch)
sc.add_sites(stash_site)

# condorpool (execution site)
condorpool_site = Site(name="condorpool", arch=Arch.X86_64, os_type=OS.LINUX)
condorpool_site.add_pegasus_profile(style="condor")
condorpool_site.add_condor_profile(
    universe="vanilla",
    requirements="HAS_SINGULARITY == True && HAS_AVX2 == True",
    request_cpus=1,
    request_memory="4 GB",
    request_disk="10 GB",
)
condorpool_site.add_profiles(
    Namespace.CONDOR, 
    key="+SingularityImage", 
    value='"/cvmfs/singularity.opensciencegrid.org/chiehlin0212/koto-dev:latest"'
)
condorpool_site.add_profiles(
    Namespace.CONDOR, 
    key="+ProjectName", 
    value='"collab.KOTO"'
)

sc.add_sites(condorpool_site)

# write SiteCatalog to ./sites.yml
sc.write()

# --- Transformations ----------------------------------------------------------
run_koto = Transformation(
               name="run_koto",
               site="local",
               pfn=TOP_DIR / "bin/run_koto.sh",
               is_stageable=True
           ).add_pegasus_profile(clusters_size=1)

tc = TransformationCatalog()
tc.add_transformations(run_koto)

# write TransformationCatalog to ./transformations.yml
tc.write()

# --- Replicas -----------------------------------------------------------------

rc = ReplicaCatalog()

input_files = []

# all files in the inputs/ dir
input_files = glob.glob(str(TOP_DIR / "inputs/*"))

for f in input_files:
    lfn = os.path.basename(f)    
    rc.add_replica(site="local", lfn=lfn, pfn=f)

# also add all wave files
wave_files = glob.glob("/collab/project/KOTO/external/run87/accidental/64kW/**/*.root", recursive=True)

for f in wave_files:
    lfn = os.path.basename(f)    
    rc.add_replica(site="local", lfn=lfn, pfn=f)

# write ReplicaCatalog to replicas.yml
rc.write()

# --- Workflow -----------------------------------------------------------------
wf = Workflow(name="koto")

random.seed()
for n in range(10):

    # arguments
    decay_mode = "KL3pi0"
    seed = str(random.randint(0, 10000))
    wave = os.path.basename(random.choice(wave_files))

    # TODO: check if we already have a job with the seed/wave combination
    print(" ... added mc job with wave={} / seed={}".format(wave, seed))

    out_root = File("{}_BasicVetoAndCuts_Accidental_{}.root".format(decay_mode, seed))
    job = Job(run_koto)\
             .add_args(decay_mode, seed, wave)\
             .add_outputs(out_root)

    # inputs, only use the lfn
    for inp in input_files + [wave]:
        job.add_inputs(os.path.basename(inp))

    wf.add_jobs(job)

# plan and run the workflow
wf.plan(
    dir=WORK_DIR / "runs",
    sites=["condorpool"],
    staging_sites={"condorpool": "stash"},
    output_sites=["local"],
    cluster=["horizontal"],
    submit=True
)

