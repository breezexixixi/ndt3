r"""
    Miller/Limb lab data under XDS format e.g.
    https://datadryad.org/stash/dataset/doi:10.5061/dryad.cvdncjt7n (Jango, force isometric, 20 sessions, 95 days)
    Data proc libs:
    - https://github.com/limblab/xds
    - https://github.com/limblab/adversarial_BCI/blob/main/xds_tutorial.ipynb
    JY updated the xds repo into a package, clone here: https://github.com/joel99/xds/

    Features EMG data and abundance of isometric tasks.
    No fine-grained analysis - just cropped data for pretraining.
"""
from typing import List
from pathlib import Path
import logging
logger = logging.getLogger(__name__)

import numpy as np
import pandas as pd
import torch
try:
    import xds_python as xds
except:
    logging.info("XDS not installed, please install from https://github.com/joel99/xds/. Import will fail")
    xds = None

from einops import reduce, rearrange

from context_general_bci.config import DataKey, DatasetConfig, REACH_DEFAULT_KIN_LABELS, EMG_CANON_LABELS
from context_general_bci.subjects import SubjectInfo, SubjectArrayRegistry, create_spike_payload
from context_general_bci.tasks import ExperimentalTask, ExperimentalTaskLoader, ExperimentalTaskRegistry
from context_general_bci.tasks.preproc_utils import get_minmax_norm, heuristic_sanitize_payload

MILLER_LABELS = [*REACH_DEFAULT_KIN_LABELS, *EMG_CANON_LABELS]
# No sanitation needed implemented at the moment, only using curated data
# TODO add guards
# Angular conditions
CONDITION_MAP = {
    0.: 0,
    45.: 1,
    90.: 2,
    135.: 3,
    180.: 4,
    -135.: 5,
    -90.: 6,
    -45.: 7, 
}

@ExperimentalTaskRegistry.register
class MillerLoader(ExperimentalTaskLoader):
    name = ExperimentalTask.miller

    @classmethod
    def load(
        cls,
        datapath: Path,
        cfg: DatasetConfig,
        cache_root: Path,
        subject: SubjectInfo,
        context_arrays: List[str],
        dataset_alias: str,
        **kwargs,
    ):
        my_xds = xds.lab_data(str(datapath.parent), str(datapath.name)) # Load the data using the lab_data class in xds.py
        assert cfg.bin_size_ms % (my_xds.bin_width * 1000) == 0, "bin_size_ms must divide bin_size in the data"
        # We do resizing using xds native utilities, not our chopping mechanisms
        my_xds.update_bin_data(cfg.bin_size_ms / 1000) # rebin to 20ms

        meta_payload = {}
        meta_payload['path'] = []
        global_args = {}

        if cfg.tokenize_covariates:
            canonical_labels = []
            if my_xds.has_cursor:
                canonical_labels.extend(REACH_DEFAULT_KIN_LABELS)
            if my_xds.has_EMG:
                # Use muscle labels
                canonical_labels.extend(my_xds.EMG_names)
                # for i, label in enumerate(my_xds.EMG_names):
                    # assert label in EMG_CANON_LABELS, f"EMG label {label} not in canonical labels, please regiser in `config_base` for bookkeeping."
            if my_xds.has_force:
                # Cursor, EMG (we don't include manipulandum force, mostly to stay under 10 dims for now)
                logger.info('Force data found but not loaded for now')

        # Print total active time etc
        all_trials = [*my_xds.get_trial_info('R'), *my_xds.get_trial_info('F')] # 'A' not included
        end_times = [trial['trial_end_time'] for trial in all_trials]
        start_times = [trial['trial_gocue_time'] for trial in all_trials]
        if isinstance(start_times[0], np.ndarray):
            start_times = [start[0] for start in start_times]
        # ? Does the end time indicate the sort of... bin count?
        total_time = sum([end - start for start, end in zip(start_times, end_times)])
        print(f'Total trial/active time: {total_time:.2f} / {(my_xds.time_frame[-1] - my_xds.time_frame[0])[0]:.2f}')
        def chop_vector(vec: torch.Tensor):
            # vec - already at target resolution, just needs chopping
            chops = round(cfg.miller.chop_size_ms / cfg.bin_size_ms)
            return rearrange(
                vec.unfold(0, chops, chops),
                'trial hidden time -> trial time hidden'
             ) # Trial x C x chop_size (time)
        vel_pieces = []
        if my_xds.has_cursor:
            vel_pieces.append(torch.as_tensor(my_xds.curs_v, dtype=torch.float))
        if my_xds.has_EMG:
            vel_pieces.append(torch.as_tensor(my_xds.EMG, dtype=torch.float))
        vel = torch.cat(vel_pieces, 1) # T x H
        if cfg.miller.explicit_labels:
            explicit_indices = []
            for i in cfg.miller.explicit_labels:
                if i in canonical_labels:
                    explicit_indices.append(canonical_labels.index(i))
            logger.info(f"Reducing discovered covariates to requested: ({len(canonical_labels)}) {canonical_labels} -> ({len(explicit_indices)}) {explicit_indices}")
            canonical_labels = [canonical_labels[i] for i in explicit_indices]
            vel = vel[:, explicit_indices]
        if cfg.miller.minmax:
            vel, payload_norm = get_minmax_norm(vel, center_mean=cfg.miller.center, quantile_thresh=cfg.miller.minmax_quantile)
            global_args.update(payload_norm)
        global_args[DataKey.covariate_labels] = canonical_labels
        

        spikes = my_xds.spike_counts
        if spikes.shape[0] == vel.shape[0] + 1:
            spikes = spikes[1:] # Off by 1s in velocity
        elif spikes.shape[0] == vel.shape[0] + 2:
            spikes = spikes[1:-1]
        else:
            raise ValueError("Spikes and velocity size mismatch")
        
        if cfg.miller.respect_trial_boundaries:
            start_bins = (my_xds.trial_start_time / my_xds.bin_width).astype(int)
            end_bins = (my_xds.trial_end_time / my_xds.bin_width).astype(int)
            vel = [vel[start:end] for start, end in zip(start_bins, end_bins)]
            full_spikes = [spikes[start:end] for start, end in zip(start_bins, end_bins)]
            # breakpoint()
            all_conditions = my_xds.trial_target_dir
            assert len(vel) == len(full_spikes) == len(all_conditions), "Trial size mismatch"
            conditions = []
            for i, cond in enumerate(all_conditions):
                filt_cond = np.around(cond, 1)
                if filt_cond not in CONDITION_MAP:
                    logger.warning(f"Condition {filt_cond} not in condition map, skipping")
                    conditions.append(-1)
                elif vel[i].size(0) > cfg.miller.outlier_bin_length:
                    logger.warning(f"Trial {i} too long, skipping")
                    conditions.append(-1)
                else:
                    conditions.append(CONDITION_MAP[filt_cond])
            vel = [v for i, v in enumerate(vel) if conditions[i] != -1]
            full_spikes = [s for i, s in enumerate(full_spikes) if conditions[i] != -1]
            conditions = [c for c in conditions if c != -1]
        else:
            vel = chop_vector(vel) # T x H
            full_spikes = chop_vector(torch.as_tensor(spikes, dtype=torch.float))
            assert full_spikes.size(0) == vel.size(0), "Chop size mismatch"
        for t in range(len(full_spikes)):
            single_payload = {
                DataKey.spikes: create_spike_payload(full_spikes[t], context_arrays),
                DataKey.bhvr_vel: vel[t].clone(), # T x H
                **global_args,
            }
            if not heuristic_sanitize_payload(single_payload):
                continue
            if cfg.miller.respect_trial_boundaries:
                single_payload[DataKey.condition] = conditions[t]
            single_path = cache_root / f'{t}.pth'
            meta_payload['path'].append(single_path)
            torch.save(single_payload, single_path)
        return pd.DataFrame(meta_payload)