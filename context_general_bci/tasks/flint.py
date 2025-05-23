r"""
From CRCNS DREAM - under Flint 2012. README below.
https://portal.nersc.gov/project/crcns/download/dream/data_sets/Flint_2012

Ben Walker, February 2013
ben-walker@northwestern.edu
__________________________________________
Experiment list
------------------------------------------
All are monkey C, center out
_e1: Same data as Stevenson_2011_e1, subject 1
_e2: Same day, subjects are different recording sessions
_e3: Same day, subjects are different recording sessions

_e4: Same day, subjects are different recording sessions
_e5: Same day, subjects are different recording sessions

__________________________________________
Data Comments:
------------------------------------------
The Neuron structure in the trial field has timestamps of nuerons that fire.
The EMG is for Biceps, Triceps, Anterior and Posterior Deltoids
LFPs are also present.

Subject 1 did not record EMGs.

File 2 was recorded on July 19, 2010.  File 3 was July 20.  File 4 was Aug 31.
File 5 was Sept 1.  I'm not sure when File 1 was recorded.
__________________________________________
Notes:
------------------------------------------
The first subject of data here is also the first subject for the
Stevenson_2011_e1 data set.  Each experiment is one day's worth of recording.
Each 'Subject' is a different recording session on the same day.

All the data is for one monkey, monkey C in the publication.

"Good" trials are ones that had a target off event.  They still might not
have a completed reach from target to target, however.

The target position was not recorded during the experiment.  It has been
estimated and added in.

Data format:
- Spike times, covariates at 100Hz
- Some EMG available, nahh
"""

from typing import List
from pathlib import Path
import logging
logger = logging.getLogger(__name__)

import numpy as np
import pandas as pd
import torch
from einops import reduce, rearrange
import scipy.signal as signal

from context_general_bci.utils import loadmat
from context_general_bci.config import DataKey, DatasetConfig, ExperimentalConfig, REACH_DEFAULT_KIN_LABELS
from context_general_bci.subjects import SubjectInfo, SubjectArrayRegistry, create_spike_payload
from context_general_bci.tasks import ExperimentalTask, ExperimentalTaskLoader, ExperimentalTaskRegistry
from context_general_bci.tasks.preproc_utils import (
    chop_vector, compress_vector, PackToChop, spike_times_to_dense, get_minmax_norm, heuristic_sanitize_payload
)

def flatten_single(channel_spikes, offsets): # offset in seconds
    # print(channel_spikes)
    filtered = [spike + offset for spike, offset in zip(channel_spikes, offsets) if spike is not None]
    filtered = [spike if len(spike.shape) > 0 else np.array([spike]) for spike in filtered]
    return np.concatenate(filtered)

@ExperimentalTaskRegistry.register
class FlintLoader(ExperimentalTaskLoader):
    name = ExperimentalTask.flint

    @classmethod
    def load(
        cls,
        datapath: Path,
        cfg: DatasetConfig,
        cache_root: Path,
        subject: SubjectInfo,
        context_arrays: List[str],
        dataset_alias: str,
        task: ExperimentalTask,
        **kwargs,
    ):
        r"""
            Unique to Flint:
            - Single day, multiple sortings. Classic. Process separate-ish.
            - They have a different number of Trials, indicating it's not multiple arrays or anything like that
        """
        exp_task_cfg: ExperimentalConfig = getattr(cfg, task.value)
        payload = loadmat(datapath)
        subject_payload = payload['Subject']
        if isinstance(subject_payload, dict):
            trial_datas = [subject_payload['Trial']]
        else:
            trial_datas = [f.Trial for f in subject_payload]
        if cfg.pack_dense:
            packer = PackToChop(exp_task_cfg.chop_size_ms // cfg.bin_size_ms, cache_root)
        meta_payload = {}
        meta_payload['path'] = []
        def get_mat_or_dict(obj, key):
            if isinstance(obj, dict):
                return obj[key]
            return getattr(obj, key)
        def proc_trial_data(chunk_data, prefix=''):
            all_vels = []
            all_spikes = []
            for trial_data in chunk_data: # trial_data may be dict or unconverted matlab struct
                trial_times = get_mat_or_dict(trial_data, 'Time') # in seconds
                trial_vel = np.array(get_mat_or_dict(trial_data, 'HandVel'))[:,:2] # Last dim is empty
                trial_vel = torch.tensor(
                    signal.resample_poly(trial_vel, 10, cfg.bin_size_ms, padtype='line', axis=0), # Default 100Hz
                    dtype=torch.float32
                ) # Time x Dim
                spike_times = [(np.array(get_mat_or_dict(t, 'Spike')) - trial_times[0]) * 1000 for t in get_mat_or_dict(trial_data, 'Neuron')] # List of channel spike times, in ms from trial start
                dense_spikes = spike_times_to_dense(spike_times, cfg.bin_size_ms, time_end=int((trial_times[-1] - trial_times[0]) * 1000) + 10, speculate_start=False) # Timebins x Channel x 1, at bin res
                # Crop trailing bin if needed - which is what we do for spikes
                if trial_vel.size(0) == dense_spikes.size(0) + 1:
                    trial_vel = trial_vel[:-1]
                elif trial_vel.size(0) != dense_spikes.size(0):
                    raise ValueError(f"Mismatched spike and velocity lengths: {trial_vel.size(0)} vs {dense_spikes.size(0)}")
                all_vels.append(trial_vel)
                all_spikes.append(dense_spikes)
            global_vel = torch.cat(all_vels) # Time x Dim, at bins
            global_spikes = torch.cat(all_spikes) # Timebins x Channel x 1, at bin res
            global_args = {}
            if cfg.tokenize_covariates:
                global_args[DataKey.covariate_labels] = REACH_DEFAULT_KIN_LABELS

            if exp_task_cfg.minmax:
                global_vel, norm_dict = get_minmax_norm(global_vel, center_mean=exp_task_cfg.center, quantile_thresh=exp_task_cfg.minmax_quantile)
                global_args.update(norm_dict)
            # Hm... hard to use packer individually since we normalize in external function

            # Directly chop trialized data as though continuous - borrowing from LM convention
            global_vel = chop_vector(global_vel, exp_task_cfg.chop_size_ms, cfg.bin_size_ms) # T x H
            global_spikes = chop_vector(global_spikes[..., 0], exp_task_cfg.chop_size_ms, cfg.bin_size_ms).unsqueeze(-1)
            assert global_spikes.size(0) == global_vel.size(0), "Chop size mismatch"
            for t in range(global_spikes.size(0)):
                single_payload = {
                    DataKey.spikes: create_spike_payload(global_spikes[t], context_arrays),
                    DataKey.bhvr_vel: global_vel[t].clone(), # T x H
                    **global_args,
                }
                if not heuristic_sanitize_payload(single_payload):
                    continue
                if cfg.pack_dense:
                    packer.prefix = prefix
                    packer.pack(single_payload)
                else:
                    single_path = cache_root / f'{prefix}{t}.pth'
                    meta_payload['path'].append(single_path)
                    torch.save(single_payload, single_path)
            if cfg.pack_dense:
                packer.flush()
        for i, chunk_data in enumerate(trial_datas):
            proc_trial_data(chunk_data, prefix=f'{i}_')
        meta_payload['path'] = packer.get_paths()
        return pd.DataFrame(meta_payload)