import os, json, time, glob 
from radical.entk import Pipeline, Stage, Task, AppManager

# ------------------------------------------------------------------------------
# Set default verbosity

if os.environ.get('RADICAL_ENTK_VERBOSE') is None:
    os.environ['RADICAL_ENTK_REPORT'] = 'True'

# Assumptions:
# - # of MD steps: 2
# - Each MD step runtime: 15 minutes
# - Summit's scheduling policy [1]
#
# Resource rquest:
# - 4 <= nodes with 2h walltime.
#
# Workflow [2]
#
# [1] https://www.olcf.ornl.gov/for-users/system-user-guides/summit/summit-user-guide/scheduling-policy
# [2] https://docs.google.com/document/d/1XFgg4rlh7Y2nckH0fkiZTxfauadZn_zSn3sh51kNyKE/
#
'''
export RMQ_HOSTNAME=two.radical-project.org 
export RMQ_PORT=33239
export RADICAL_PROFILE=True
export RADICAL_PILOT_PROFILE=True
export RADICAL_ENTK_PROFILE=True
'''
#

base_path = os.path.abspath('.') 

md_path = os.path.join(base_path, 'MD_exps/adrp') 
agg_path = os.path.join(base_path, 'MD_to_CVAE') 
cvae_path = os.path.join(base_path, 'CVAE_exps') 
param_path = os.path.join(base_path, 'Parameters') 
outlier_path = os.path.join(base_path, 'Outlier_search') 

input_path = sorted(glob.glob(os.path.join(param_path, 'input_*')))
input_prot_path = [path for path in input_path if 'rank' not in path] 
input_comp_path = [path for path in input_path if 'rank' in path]
n_comp = len(input_comp_path) 


N_jobs_MD = 120 
N_jobs_ML = 12

hrs_wt = 24
queue = 'v100'
proj_id = 'FTA-Jha'

CUR_STAGE=0
MAX_STAGE= 2
RETRAIN_FREQ = 5

LEN_initial = 100 # 100
LEN_iter = 10 

batch_size = 256


TASK_PRE_EXEC_MODULES = [
    'module load cuda/10.1',
    'export OMPI_LD_PRELOAD_POSTPEND_DISTRO=/opt/ibm/spectrum_mpi/lib/libpami_cudahook.so',
    'export LD_PRELOAD="/opt/ibm/spectrum_mpi/lib/pami_noib/libpami.so $OMPI_LD_PRELOAD_POSTPEND_DISTRO $LD_PRELOAD"']

TASK_PRE_EXEC_ENV = [
    "export TACC_SPECTRUM_ENV=`/usr/local/bin/build_env.pl | sed -e's/\(\S\S*\)=\S\S* / -x \\1/g'`"]

def generate_training_pipeline():
    """
    Function to generate the CVAE_MD pipeline
    """

    def generate_MD_stage(num_MD=1): 
        """
        Function to generate MD stage. 
        """
        s1 = Stage()
        s1.name = 'MD'
        initial_MD = True 
        outlier_filepath = '%s/restart_points.json' % outlier_path

        if os.path.exists(outlier_filepath): 
            initial_MD = False 
            outlier_file = open(outlier_filepath, 'r') 
            outlier_list = json.load(outlier_file) 
            outlier_file.close() 

        # MD tasks
        time_stamp = int(time.time())
        for i in range(num_MD):
            t1 = Task()
            # https://github.com/radical-collaboration/hyperspace/blob/MD/microscope/experiments/MD_exps/fs-pep/run_openmm.py

            t1.pre_exec = TASK_PRE_EXEC_MODULES[:]
            t1.pre_exec += ['export' + \
                    ' PYTHONPATH=%s/MD_exps:%s/MD_exps/MD_utils:$PYTHONPATH' %
                    (base_path, base_path)] 
            t1.pre_exec += ['cd %s' % md_path] 
            t1.executable = ['$TACC_SPECTRUM_ENV python']  # run_openmm.py
            t1.arguments = ['%s/run_openmm.py' % md_path] 

            # specify the pdb_file and top_file for each run  
            # pick initial point of simulation 
            if initial_MD or i >= len(outlier_list): 
                if i % 2 == 0: 
                    pdb_file = os.path.join(input_prot_path[0], 'prot.pdb') 
                    top_file = os.path.join(input_prot_path[0], 'prot.prmtop') 
                else: 
                    pdb_file = os.path.join(input_comp_path[i//2%n_comp], 'comp.pdb') 
                    top_file = os.path.join(input_comp_path[i//2%n_comp], 'comp.prmtop') 
            # Outlier situation with restarting simulation from pdb file 
            elif outlier_list[i].endswith('pdb'): 
                pdb_file = outlier_list[i]
                sim_path = os.path.join(md_path, os.path.basename(pdb_file)[:-11])   
                top_file = glob.glob(sim_path + '/*top')[0] 
            # Restarting simulation with check point 
            elif outlier_list[i].endswith('chk'): 
                check_point = outlier_list[i]
                t1.arguments += ['-c', check_point] 
                sim_path = os.path.join(md_path, os.path.basename(check_point)[:-4])
                pdb_file = glob.glob(sim_path + '/*pdb')[0]
                top_file = glob.glob(sim_path + '/*top')[0]
            
            # add pdb_file and top_file to simulation 
            ## identify the topology label 
            top_dirname = os.path.basename(os.path.dirname(top_file))
            if 'omm_runs' in top_dirname: 
                top_label = top_dirname.split('_')[2]
            elif 'input' in top_dirname: 
                top_label = top_dirname.split('_')[1]
            else: 
                raise Exception('Unknow topology file...') 

            # make a copy of everything at local dir 
            work_dirname = 'omm_runs_%s_%d' % (top_label,  time_stamp+i)
            t1.pre_exec += ['mkdir -p {0} && cd {0}'.format(work_dirname)]
            t1.pre_exec += ['cp %s ./' % pdb_file] 
            t1.pre_exec += ['cp %s ./' % top_file] 
            if '-c' in t1.arguments: 
                t1.pre_exec += ['cp %s ./' % check_point]
            t1.pre_exec += TASK_PRE_EXEC_ENV[:]

            # addd file to simulation 
            t1.arguments += ['--pdb_file', pdb_file] 
            t1.arguments += ['--topol', top_file] 
            
            # how long to run the simulation 
            if initial_MD: 
                t1.arguments += ['--length', LEN_initial] 
            else: 
                t1.arguments += ['--length', LEN_iter]

            # assign hardware the task 
            t1.cpu_reqs = {'processes': 1,
                           'process_type': None,
                           'threads_per_process': 4,
                           'thread_type': 'OpenMP'
                          }
            t1.gpu_reqs = {'processes': 1,
                           'process_type': None,
                           'threads_per_process': 1,
                           'thread_type': 'CUDA'
                          }
                              
            # Add the MD task to the simulating stage
            s1.add_tasks(t1)
        return s1 


    def generate_aggregating_stage(): 
        """ 
        Function to concatenate the MD trajectory (h5 contact map) 
        """ 
        s2 = Stage()
        s2.name = 'aggregating'

        # Aggregation task
        t2 = Task()
        # https://github.com/radical-collaboration/hyperspace/blob/MD/microscope/experiments/MD_to_CVAE/MD_to_CVAE.py
        t2.pre_exec = [] 
        t2.pre_exec += ['cd %s' % agg_path]
        t2.executable = ['python']  # MD_to_CVAE.py
        t2.arguments = ['%s/MD_to_CVAE.py' % agg_path, 
                '--sim_path', md_path, 
                '--pad', 4]

        # Add the aggregation task to the aggreagating stage
        s2.add_tasks(t2)
        return s2 


    def generate_ML_stage(num_ML=1): 
        """
        Function to generate the learning stage
        """
        s3 = Stage()
        s3.name = 'learning'

        # learn task
        time_stamp = int(time.time())
        for i in range(num_ML): 
            t3 = Task()
            # https://github.com/radical-collaboration/hyperspace/blob/MD/microscope/experiments/CVAE_exps/train_cvae.py
            t3.pre_exec = TASK_PRE_EXEC_MODULES[:]

            t3.pre_exec += ['export ' + \
                    'PYTHONPATH=%s/CVAE_exps:%s/CVAE_exps/cvae:$PYTHONPATH' %
                    (base_path, base_path)]
            t3.pre_exec += ['cd %s' % cvae_path]
            dim = i + 3 
            cvae_dir = 'cvae_runs_%.2d_%d' % (dim, time_stamp+i) 
            t3.pre_exec += ['mkdir -p {0} && cd {0}'.format(cvae_dir)]
            t3.pre_exec += TASK_PRE_EXEC_ENV[:]
            t3.executable = ['$TACC_SPECTRUM_ENV python']  #
            t3.arguments = ['%s/train_cvae.py' % cvae_path, 
                    '--h5_file', '%s/cvae_input.h5' % agg_path, 
                    '--dim', dim, 
                    '--batch', batch_size] 
            
            t3.cpu_reqs = {'processes': 1,
                           'process_type': None,
                    'threads_per_process': 4,
                    'thread_type': 'OpenMP'
                    }
            t3.gpu_reqs = {'processes': 1,
                           'process_type': None,
                    'threads_per_process': 1,
                    'thread_type': 'CUDA'
                    }
        
            # Add the learn task to the learning stage
            s3.add_tasks(t3)

        return s3 


    def generate_interfacing_stage(): 
        s4 = Stage()
        s4.name = 'scanning'

        # Scaning for outliers and prepare the next stage of MDs 
        t4 = Task() 
        t4.pre_exec = [] 
        t4.pre_exec = TASK_PRE_EXEC_MODULES[:]

        t4.pre_exec += ['export ' + \
                'PYTHONPATH=%s/CVAE_exps:%s/CVAE_exps/cvae:$PYTHONPATH' %
                (base_path, base_path)] 
        t4.pre_exec += ['cd %s/Outlier_search' % base_path] 
        t4.pre_exec += TASK_PRE_EXEC_ENV[:]
        t4.executable = ['$TACC_SPECTRUM_ENV python']
        t4.arguments = ['outlier_locator.py', 
                '--md',  md_path, 
                '--cvae', cvae_path, 
                ]

        t4.cpu_reqs = {'processes': 1,
                           'process_type': None,
                'threads_per_process': 12,
                'thread_type': 'OpenMP'
                }
        t4.gpu_reqs = {'processes': 1,
                           'process_type': None,
                'threads_per_process': 1,
                'thread_type': 'CUDA'
                }
        s4.add_tasks(t4) 
        s4.post_exec = func_condition 
        
        return s4


    def func_condition(): 
        global CUR_STAGE, MAX_STAGE 
        if CUR_STAGE < MAX_STAGE: 
            func_on_true()
        else:
            func_on_false()

    def func_on_true(): 
        global CUR_STAGE, MAX_STAGE
        
        #if CUR_STAGE != 0: 
        # --------------------------
        # MD stage
        s1 = generate_MD_stage(num_MD=N_jobs_MD)
        # Add simulating stage to the training pipeline
        p.add_stages(s1)

        if CUR_STAGE % RETRAIN_FREQ == 0: 
            # --------------------------
            # Aggregate stage
            s2 = generate_aggregating_stage() 
            # Add the aggregating stage to the training pipeline
            p.add_stages(s2)

            # --------------------------
            # Learning stage
            s3 = generate_ML_stage(num_ML=N_jobs_ML) 
            # Add the learning stage to the pipeline
            p.add_stages(s3)

        # --------------------------
        # Outlier identification stage
        s4 = generate_interfacing_stage() 
        p.add_stages(s4) 
        
        CUR_STAGE += 1

    def func_on_false(): 
        print('Done') 


    global CUR_STAGE

    p = Pipeline()
    p.name = 'MD_ML'

    func_on_true()
    
    return p




if __name__ == '__main__':

    # Create a dictionary to describe four mandatory keys:
    # resource, walltime, cores and project
    # resource is 'local.localhost' to execute locally
    res_dict = {
        'resource': 'local.longhorn',
        'project': proj_id,
        'queue': queue,
        'schema': 'local',
        'walltime': 60 * hrs_wt,
        'cpus': N_jobs_MD // 4 * 40
    }

    # Create Application Manager
    # appman = AppManager()
    appman = AppManager(hostname=os.environ.get('RMQ_HOSTNAME'), port=int(os.environ.get('RMQ_PORT')))
    appman.resource_desc = res_dict

    p1 = generate_training_pipeline()
    # p2 = generate_MDML_pipeline()

    pipelines = []
    pipelines.append(p1)
    # pipelines.append(p2)

    # Assign the workflow as a list of Pipelines to the Application Manager. In
    # this way, all the pipelines in the list will execute concurrently.
    appman.workflow = pipelines

    # Run the Application Manager
    appman.run()