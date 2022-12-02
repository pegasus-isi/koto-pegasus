# koto-pegasus

[The Pegasus project](https://pegasus.isi.edu) encompasses a set
of technologies that help workflow-based applications execute in a
number of different environments including desktops, campus clusters,
grids, and clouds. Pegasus bridges the scientific domain and the
execution environment by automatically mapping high-level workflow
descriptions onto distributed resources. It automatically locates the
necessary input data and computational resources necessary for workflow
execution. Pegasus enables scientists to construct workflows in abstract
terms without worrying about the details of the underlying execution
environment or the particulars of the low-level specifications required
by the middleware. Some of the advantages of using Pegasus include:

   * **Portability / Reuse** - User created workflows can easily be
     run in different environments without alteration. Pegasus currently
     runs workflows on compute systems scheduled via HTCondor, including the
     OSPool, and other other systems or via other schedulers (e.g. ACCESS
     resources, Amazon EC2, Google Cloud, and many campus clusters). The same
     workflow can run on a single system or across a heterogeneous set of
     resources.

   * **Performance** - The Pegasus mapper can reorder, group, and prioritize
     tasks in order to increase the overall workflow performance.

   * **Scalability** - Pegasus can easily scale both the size of the
     workflow, and the resources that the workflow is distributed over.
     Pegasus runs workflows ranging from just a few computational tasks up
     to 1 million tasks. The number of resources involved in executing a
     workflow can scale as needed without any impediments to performance.

   * **Provenance** - By default, all jobs in Pegasus are launched via
     the kickstart process that captures runtime provenance of the job and
     helps in debugging. The provenance data is collected in a database, and
     the data can be summarized with tools such as pegasus-statistics or
     directly with SQL queries.

   * **Data Management** - Pegasus handles replica selection, data
     transfers and output registrations in data catalogs. These tasks are
     added to a workflow as auxiliary jobs by the Pegasus planner.

   * **Reliability** - Jobs and data transfers are automatically retried
     in case of failures. Debugging tools such as pegasus-analyzer help the
     user to debug the workflow in case of non-recoverable failures.

   * **Error Recovery** - When errors occur, Pegasus tries to recover
     when possible by retrying tasks, retrying the entire workflow, providing
     workflow-level checkpointing, re-mapping portions of the workflow,
     trying alternative data sources for staging data, and, when all else
     fails, providing a rescue workflow containing a description of only the
     work that remains to be done. Pegasus keeps track of what has been done
     (provenance) including the locations of data used and produced, and
     which software was used with which parameters.

OSG has no read/write enabled shared file system across the resources.
Jobs are required to either bring inputs along with the job, or as
part of the job stage the inputs from a remote location. The following
examples highlight how Pegasus can be used to manage KOTO workloads in
such an environment by providing an abstraction layer around things
like data movements and job retries, enabling the users to run larger
workloads, spending less time developing job management tools and
babysitting their computations.

Pegasus workflows have 4 components:

  1. **Site Catalog** - Describes the execution environment in which
     the workflow will be executed.

  2. **Transformation Catalog** - Specifies locations of the executables
     used by the workflow.

  3. **Replica Catalog** - Specifies locations of the input data to the
     workflow.

  4. **Workflow Description** - An abstract workflow description
     containing compute steps and dependencies between the steps. We
     refer to this workflow as abstract because it does not contain data
     locations and available software.

When developing a Pegasus Workflow using the
[Python API](https://pegasus.isi.edu/documentation/reference-guide/api-reference.html),
all four components may be defined in the same file.

For details, please refer to the [Pegasus documentation](https://pegasus.isi.edu/documentation/).

### KOTO workflow example

The GitHub repo [https://github.com/pegasus-isi/koto-pegasus](https://github.com/pegasus-isi/koto-pegasus)
contains a sample Pegasus workflow for KOTO processing. It is a very
simple Monte Carlo example, containing just N independent jobs:

![fig 1](https://raw.githubusercontent.com/pegasus-isi/koto-pegasus/master/figures/KOTO-Workflow.png)

This example is using [OSG StashCache](https://derekweitzel.com/2018/09/26/stashcache-by-the-numbers/)
for data transfers. Credentials are transparant to the end users.

Additionally, this example uses a custom container to run jobs. This
ensures a consistent and complete environment for the jobs. Which 
container to use is defined in `workflow.py` with the
`+SingularityImage` attribute.

When invoked, the workflow script (`workflow.py`) does the following:

  1. Writes the file `pegasus.properties`. This file contains configuration settings
     used by Pegasus and HTCondor.

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

  2. Writes the file `sites.yml`. This file describes the execution environment in
     which the workflow will be run.

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

  3. Writes the file `transformations.yml`. This file specifies the executables used
     in the workflow and contains the locations where they are physically located.
     In this example, we only have `run_koto.sh`.

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

  4. Writes the file `replicas.yml`. This file specifies the physical locations of
     any input files used by the workflow. In this example, there is an entry for
     each file in the `inputs/` directory, and all files matching
     `/collab/project/KOTO/external/run87/accidental/64kW/**/*.root`

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
         
  5. Builds the wordfreq workflow and submits it for execution. When `wf.plan` is
     invoked, `pegasus.properties`, `sites.yml`, `transformations.yml`, and
     `replicas.yml` will be consumed as part of the workflow planning process. Note that
     in this step there is no mention of data movement and job details as these are
     added by Pegasus when the workflow is planned into an executable workflow. As
     part of the planning process, additional jobs which handle scratch directory
     creation, data staging, and data cleanup are added to the workflow.

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

Submit the workflow by executing `workflow.py`.

    $ ./workflow.py

Note that when Pegasus plans/submits a workflow, a workflow directory is created
and presented in the output. In the following example output, the workflow directory
is `/home/user/workflows/runs/pegasus/run0014`.

    2020.12.18 14:33:07.059 CST:   -----------------------------------------------------------------------
    2020.12.18 14:33:07.064 CST:   File for submitting this DAG to HTCondor           : koto-workflow-0.dag.condor.sub
    2020.12.18 14:33:07.070 CST:   Log of DAGMan debugging messages                 : koto-workflow-0.dag.dagman.out
    2020.12.18 14:33:07.075 CST:   Log of HTCondor library output                     : koto-workflow-0.dag.lib.out
    2020.12.18 14:33:07.080 CST:   Log of HTCondor library error messages             : koto-workflow-0.dag.lib.err
    2020.12.18 14:33:07.086 CST:   Log of the life of condor_dagman itself          : koto-workflow-0.dag.dagman.log
    2020.12.18 14:33:07.091 CST:
    2020.12.18 14:33:07.096 CST:   -no_submit given, not submitting DAG to HTCondor.  You can do this with:
    2020.12.18 14:33:07.107 CST:   -----------------------------------------------------------------------
    2020.12.18 14:33:11.352 CST:   Your database is compatible with Pegasus version: 5.1.0dev
    [WARNING]  Submitting to condor koto-workflow-0.dag.condor.sub
    2020.12.18 14:33:12.060 CST:   Time taken to execute is 5.818 seconds

    Your workflow has been started and is running in the base directory:

    /home/ryantanaka/workflows/runs/ryantanaka/pegasus/koto-workflow/run0014

    *** To monitor the workflow you can run ***

    pegasus-status -l /home/ryantanaka/workflows/runs/ryantanaka/pegasus/koto-workflow/run0014


    *** To remove your workflow run ***

    pegasus-remove /home/ryantanaka/workflows/runs/ryantanaka/pegasus/koto-workflow/run0014

This directory is the handle to the workflow instance
and is used by Pegasus command line tools. Some useful tools to know about:

* `pegasus-status -v [wfdir]`
     Provides status on a currently running workflow. ([more](https://pegasus.isi.edu/documentation/manpages/pegasus-status.html))
* `pegasus-analyzer [wfdir]`
     Provides debugging clues why a workflow failed. Run this after a workflow has failed. ([more](https://pegasus.isi.edu/documentation/manpages/pegasus-analyzer.html))
* `pegasus-statistics [wfdir]`
     Provides statistics, such as walltimes, on a workflow after it has completed. ([more](https://pegasus.isi.edu/documentation/manpages/pegasus-statistics.html))
* `pegasus-remove [wfdir]`
     Removes a workflow from the system. ([more](https://pegasus.isi.edu/documentation/manpages/pegasus-remove.html)) 
