#%%
import torch
import matplotlib.pyplot as plt
from context_general_bci.dataset import SpikingDataset
from context_general_bci.tasks.pitt_co import PittCOLoader
from context_general_bci.contexts import context_registry

test = context_registry.query(alias='odoherty_rtt.*')
print(test[0].alias)

#%%
test = torch.load('data/calib_pitt_calib_broad_norm.pt')
print(test)
# test = context_registry.query(alias='pitt_grasp')
# print(test[0].alias)
#%%

# Drop abnormal session 40 set 4
from pathlib import Path
target_dir = Path('data/eval/pitt_grasp')
# target_dir = Path('data/calib/pitt_grasp')
for i, payload_pth in enumerate(target_dir.glob('*.pth')):
    # print(payload_pth)
    # if i > 1:
        # break
    payload = torch.load(payload_pth)
    # print(payload['spikes'].shape, payload['force'].shape)
    if payload['force'].shape[0] > 10000:
        print(payload_pth.stem)
    # else:
    #     continue
    covariate_force  = payload['force']
    # plt.plot(payload['force'], label=payload_pth.stem)
    covariate_force = PittCOLoader.smooth(
        covariate_force,
        kernel=PittCOLoader.get_kin_kernel(
            100,
            sample_bin_ms=20
        )
    ) # Gary doesn't compute velocity, just absolute. We follow suit.
    nonzeros = torch.nonzero(covariate_force > 1)[:, 0]
    nonzero_start = nonzeros[0] - 50
    nonzero_end = nonzeros[-1] + 50
    plt.plot(covariate_force[nonzero_start:nonzero_end], label='smoothed')
    # if i > 10:
        # break
# plt.xlim(0, 500)
# plt.legend()
#%%

# Take a quick look at raw data
import pandas as pd
pd.read_csv('./data/eval_metrics/')
#%%

import numpy as np
def generate_lagged_matrix(input_matrix: np.ndarray, lag: int):
    """
    Generate a lagged version of an input matrix; i.e. include history in the input matrix.

    Parameters:
    input_matrix (np.ndarray): The input matrix. T x H
    lag (int): The number of lags to consider.
    zero_pad (bool): Whether to zero pad the lagged matrix to match input

    Returns:
    np.ndarray: The lagged matrix, shape T x (H * (lag + 1))
    """
    if lag == 0:
        return input_matrix
    # Initialize the lagged matrix
    lagged_matrix = np.zeros((input_matrix.shape[0], input_matrix.shape[1], lag + 1))
    lagged_matrix[:, :, 0] = input_matrix
    # Fill the lagged matrix
    for i in range(lag + 1):
        lag_entry = np.roll(input_matrix, i, axis=0)
        lag_entry[:i] = 0
        lagged_matrix[:, :, i] = lag_entry
    lagged_matrix = lagged_matrix.reshape(input_matrix.shape[0], input_matrix.shape[1] * (lag + 1))
    return lagged_matrix

test = np.random.randint(1, 5, (3, 2)) # 3 time steps, 2 channels
print(test)
print(generate_lagged_matrix(test, 2))

#%%
import wandb
api = wandb.Api()
tag = 'scratch_100-sweep-simple-scratch'
experiment_set = 'v4/tune/rtt'
other_overrides = {'config.'}
print(f'Checking for runs with tag: {tag}, exp: {experiment_set}, with: {other_overrides}')
# print(other_overrides)
if 'init_from_id' in other_overrides:
    del other_overrides['init_from_id'] # oh jeez... we've been rewriting this in run.py and doing redundant runs because we constantly query non-inits
runs = api.runs(
    f"{cfg.wandb_user}/{cfg.wandb_project}",
    filters={
        "config.experiment_set": experiment_set if experiment_set else cfg.experiment_set,
        "config.tag": tag if tag else cfg.tag,
        "state": {"$in": allowed_states},
        **other_overrides,
    }
)

from context_general_bci.contexts.context_registry import context_registry
#%%
from pathlib import Path

test = Path('./data/preprocessed/schwartz/MonkeyR')
# test = Path('./data/preprocessed/schwartz/MonkeyN')
total = 0
for subdir in test.iterdir():
    if list(subdir.glob('*.csv')) == []:
        continue
    print(subdir)
    total += 1
print(total)

#%%
from context_general_bci.config.presets import ScaleHistoryDatasetConfig
from context_general_bci.dataset import SpikingDataset

default_cfg = ScaleHistoryDatasetConfig()
default_cfg.datasets = ['odoherty_rtt.*']
dataset = SpikingDataset(default_cfg)
print(len(dataset))

#%%



from pathlib import Path
import torch
from torch import nn
from context_general_bci.task_io import symlog, unsymlog
import matplotlib.pyplot as plt


# old_root = Path('./data/preprocessed/P4Lab.data.00077/')
exp_root = Path('./data/preprocessed/closed_loop_tests_outpost/PTest.data.00064/')
# exp_root = Path('./data/preprocessed/closed_loop_tests/P4Lab.data.00077/')
for i in [6, 17]:
# for i in [1, 3, 5, 6, 8, 9, 10]:
    sample = torch.load(exp_root / f'PTest_session_64_set_{i}.mat' / f'closed_loop_outpost_pitt_co_PTest_64_{i}_0.pth')
    print("New")
    print(i, sample['cov_max'])
print(cmp['cov_max'].shape)
cmp = torch.load(exp_root / 'PTest_session_64_norm.pth')
# cmp = torch.load(exp_root / 'P4Lab_session_77_norm.pth')

print(sample['cov_max'])
print(cmp['cov_max'])

#%%
pld = torch.load('ablate.pth')
pred_ablate = pld['pred']
true_ablate = pld['true']
pld = torch.load('dense.pth')
pred_dense = pld['pred']
true_dense = pld['true']
import seaborn as sns
import matplotlib.pyplot as plt

plt.plot(pred_ablate.cpu().numpy()[::2], label='ablate')
plt.plot(pred_dense.cpu().numpy()[::2], label='dense')
plt.plot(true_ablate.cpu().numpy()[::2], label='true')


#%%
from rotary_embedding_torch import apply_rotary_emb, RotaryEmbedding, broadcat

pos_emb = RotaryEmbedding(
    dim = 32,
    freqs_for = 'pixel',
    max_freq = 256
)

# queries and keys for frequencies to be rotated into

q = torch.randn(1, 256, 256, 64)
k = torch.randn(1, 256, 256, 64)

# get frequencies for each axial
# -1 to 1 has been shown to be a good choice for images and audio

freqs_h = pos_emb(torch.linspace(-1, 1, steps = 256), cache_key = 256)
freqs_w = pos_emb(torch.linspace(-1, 1, steps = 256), cache_key = 256)

# concat the frequencies along each axial
# broadcat function makes this easy without a bunch of expands

freqs = broadcat((freqs_h[:, None, :], freqs_w[None, :, :]), dim = -1)
print(freqs.shape)
# rotate in frequencies

q = apply_rotary_emb(freqs, q)
k = apply_rotary_emb(freqs, k)

#%%
import math
import logging
import sys
logging.basicConfig(stream=sys.stdout, level=logging.INFO) # needed to get `logger` to print

import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import torch
from einops import rearrange
from context_general_bci.config import DatasetConfig, DataKey, MetaKey
from context_general_bci.analyze_utils import prep_plt
import pandas as pd
import lightning.pytorch as pl

#%%
def cosine_schedule(time: torch.Tensor, T: int, start: float = 0.9, end: float = 0.0) -> torch.Tensor:
    assert T > 0
    assert 0.0 <= start <= 1.0
    assert 0.0 <= end <= 1.0
    assert start != end
    assert time.max() <= T
    assert time.min() >= 0
    schedule = end + (start - end) * (1 + torch.cos(time * math.pi / T)) / 2
    return schedule

# Test and plot cosine
time = torch.arange(0, 100)
T = 100
schedule = cosine_schedule(time, T)
plt.plot(schedule)

#%%
test = pd.read_pickle('debug.df')
# print(test.vel.values)
valid_vel = np.concatenate(test.vel.values)
valid_vel = valid_vel[np.isfinite(valid_vel).any(axis=1)]
print(valid_vel.shape)
# sns.histplot(valid_vel.flatten())
print(np.quantile(valid_vel, 0.99, axis=0))
print(np.quantile(valid_vel, 0.01))

#%%
# Load BrainBertInterface and SpikingDataset to make some predictions
from context_general_bci.config import RootConfig, ModelConfig, ModelTask, Metric, Output, EmbedStrat, DataKey, MetaKey
from context_general_bci.dataset import SpikingDataset, DataAttrs
from context_general_bci.model import transfer_model, logger

from context_general_bci.analyze_utils import stack_batch, load_wandb_run
from context_general_bci.analyze_utils import prep_plt, get_dataloader
from context_general_bci.utils import wandb_query_experiment, get_wandb_run, wandb_query_latest

pl.seed_everything(0)

UNSORT = True
# UNSORT = False

DATASET_WHITELIST = [
    "odoherty_rtt-Indy-20160407_02",
    "odoherty_rtt-Indy-20170131_02",
    "odoherty_rtt-Indy-20160627_01",
]

EXPERIMENTS_KIN = [
    f'scale_decode',
]

queries = [
    'session_cross',
]

trainer = pl.Trainer(accelerator='gpu', devices=1, default_root_dir='./data/tmp')
runs_kin = wandb_query_experiment(EXPERIMENTS_KIN, order='created_at', **{
    "state": {"$in": ['finished']},
    "config.dataset.odoherty_rtt.include_sorted": not UNSORT,
})
runs_kin = [r for r in runs_kin if r.name.split('-')[0] in queries]
print(f'Found {len(runs_kin)} runs')
#%%

def get_evals(model, dataloader, runs=8, mode='nll'):
    evals = []
    for i in range(runs):
        pl.seed_everything(i)
        heldin_metrics = stack_batch(trainer.test(model, dataloader, verbose=False))
        if mode == 'nll':
            test = heldin_metrics['test_infill_loss'] if 'test_infill_loss' in heldin_metrics else heldin_metrics['test_shuffle_infill_loss']
        else:
            test = heldin_metrics['test_kinematic_r2']
        test = test.mean().item()
        evals.append({
            'seed': i,
            mode: test,
        })
    return pd.DataFrame(evals)[mode].mean()
    # return evals

def build_df(runs, mode='nll'):
    df = []
    seen_set = {}
    for run in runs:
        variant, _frag, *rest = run.name.split('-')
        src_model, cfg, data_attrs = load_wandb_run(run, tag='val_loss')
        dataset_name = cfg.dataset.datasets[0] # drop wandb ID
        dataset_name = "odoherty_rtt-Indy-20160627_01"
        if dataset_name not in DATASET_WHITELIST:
            continue
        experiment_set = run.config['experiment_set']
        if (variant, dataset_name, run.config['model']['lr_init'], experiment_set) in seen_set:
            continue
        dataset = SpikingDataset(cfg.dataset)
        set_limit = run.config['dataset']['scale_limit_per_eval_session']
        # if set_limit == 0:
            # train_dev_dataset = SpikingDataset(cfg.dataset)
            # train_dev_dataset.subset_split()
            # set_limit = len(train_dev_dataset)
        dataset.subset_split(splits=['eval'])
        dataset.build_context_index()
        data_attrs = dataset.get_data_attrs()
        model = transfer_model(src_model, cfg.model, data_attrs)

        dataloader = get_dataloader(dataset)
        payload = {
            'limit': set_limit,
            'variant': variant,
            'series': experiment_set,
            'dataset': dataset_name,
            'lr': run.config['model']['lr_init'], # swept
        }
        payload[mode] = get_evals(model, dataloader, mode=mode, runs=1 if mode != 'nll' else 8)
        df.append(payload)
        seen_set[(variant, dataset_name, run.config['model']['lr_init']), experiment_set] = True
    return pd.DataFrame(df)

kin_df = build_df(runs_kin, mode='kin_r2')
kin_df = kin_df.sort_values('kin_r2', ascending=False).drop_duplicates(['variant', 'dataset', 'series'])

df = kin_df


#%%

# Temperature stuff
palette = sns.color_palette('colorblind', 2)
from torch.distributions import poisson

lambdas = torch.arange(0, 30, 2)
def change_temp(probs, temperature):
    return (probs / temperature).exp()  / (probs / temperature).exp().sum()
for l in lambdas:
    dist = poisson.Poisson(l)
    plt.plot(dist.log_prob(torch.arange(0, 20)).exp(), color=palette[0])
    plt.plot(change_temp(dist.log_prob(torch.arange(0, 20)).exp(), 0.01), color=palette[1])

#%%
batch = torch.load('valid.pth')
# batch = torch.load('debug_batch.pth')

#%%
print(batch['tgt'].size())
sns.histplot(batch['tgt'].cpu().numpy().flatten())
#%%
print(batch[DataKey.spikes].size())
print(batch[DataKey.bhvr_vel].size())

trial = 0
# trial = 1
# trial = 2
# trial = 3
# trial = 4
# trial = 5

trial_vel = batch[DataKey.bhvr_vel][trial].cpu()
trial_spikes = batch[DataKey.spikes][trial].cpu()

def plot_vel(vel, ax):
    ax = prep_plt(ax=ax)
    ax.plot(vel)
def plot_raster(spikes, ax, vert_space=0.1, bin_size_ms=5):
    ax = prep_plt(ax)
    spikes = rearrange(spikes, 't a c h -> t (a c h)')
    sns.despine(ax=ax, left=True, bottom=False)
    spike_t, spike_c = np.where(spikes)
    # prep_plt(axes[_c], big=True)
    time = np.arange(spikes.shape[0])
    ax.scatter(
        time[spike_t], spike_c * vert_space,
        # c=colors,
        marker='|',
        s=10,
        alpha=0.9
        # alpha=0.3
    )
    time_lim = spikes.shape[0] * bin_size_ms
    ax.set_xticks(np.linspace(0, spikes.shape[0], 5))
    ax.set_xticklabels(np.linspace(0, time_lim, 5))
    # ax.set_title("Benchmark Maze (Sorted)")
    # ax.set_title(context.alias)
    ax.set_xlabel('Time (ms)')
    ax.set_yticks([])
    return ax


f = plt.figure(figsize=(10, 10))
plot_vel(trial_vel, f.add_subplot(2, 1, 1))
plot_raster(trial_spikes, f.add_subplot(2, 1, 2), bin_size_ms=20)



#%%
# Draw a 3d scatterplot of several random point clouds in space
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d import Axes3D

colors = sns.color_palette('colorblind', 10)
fig = plt.figure()
ax = fig.add_subplot(111)
# ax = fig.add_subplot(111, projection='3d')

# Generate random data
n = 100
xs = np.random.rand(n)
ys = np.random.rand(n)
zs = np.random.rand(n)

def plot_3d_cluster(mu, std, color):
    xs, ys, zs = generate_3d_cluster(mu, std)
    ax.scatter(xs, ys, zs, c=color, marker='o')

def generate_2d_cluster(mu, std):
    # Generate random vector for array inputs mu, std
    n = 100
    xs = np.random.normal(mu[0], std[0], n)
    ys = np.random.normal(mu[1], std[1], n)
    return xs, ys

def plot_2d_cluster(mu, std, color):
    xs, ys = generate_2d_cluster(mu, std)
    ax.scatter(xs, ys, c=color, marker='o')
# Plot the points
# ax.scatter(xs, ys, zs, c='b', marker='o')
mus = np.random.rand(2, 10) * 10
stds = np.random.rand(2, 10)
for i in range(5):
    plot_2d_cluster(mus[:, i], stds[:, i], color=colors[i])
