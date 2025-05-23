#%%
# Qualitative plots for presentationas
import os
os.environ['CUDA_VISIBLE_DEVICES'] = '3'
# os.environ['CUDA_VISIBLE_DEVICES'] = '1'

from typing import Dict, List, Any
from datetime import datetime
from pytz import timezone

from matplotlib import pyplot as plt
import numpy as np
import seaborn as sns
import torch
import lightning.pytorch as pl

from sklearn.metrics import r2_score

from context_general_bci.model import transfer_model, BrainBertInterface
from context_general_bci.dataset import SpikingDataset
from context_general_bci.config import RootConfig, ModelTask, Metric, Output, DataKey, MetaKey, BatchKey

from context_general_bci.utils import wandb_query_latest
from context_general_bci.analyze_utils import (
    stack_batch,
    rolling_time_since_student,
    get_dataloader,
)
from context_general_bci.plotting import prep_plt, data_label_to_target
from context_general_bci.inference import load_wandb_run


data_label = 'indy'
data_label = 'miller'
target = data_label_to_target(data_label)
queries = [
    # 'data_indy-jt456lfs',
    'data_jango-eqkrqixy',
    'data_min-ni4qut2z', # Wait, I thought this worked, why is this broken now
    # 'data_monkey-kvoi7ytu',
    # 'neural_data_monkey-pitt-i2maes5i',
]

trainer = pl.Trainer(
    accelerator='gpu', devices=1, default_root_dir='./data/tmp',
    precision='bf16-mixed',
)

def prep_query(query):

    wandb_run = wandb_query_latest(query, allow_running=True, use_display=True)[0]
    print(wandb_run.id)

    src_model, cfg, old_data_attrs = load_wandb_run(wandb_run, tag='val_loss')
    # Hotfix position: check if wandb run is older than oct 15, 10:00am
    wandb_datetime_utc = datetime.fromisoformat(wandb_run.created_at).replace(tzinfo=timezone('UTC'))
    est = timezone('US/Eastern')
    wandb_datetime_est = wandb_datetime_utc.astimezone(est)

    # Create a datetime object for Oct 15, 2023, 10AM EST
    target_datetime_est = est.localize(datetime(2023, 10, 15, 10, 0, 0))

    if wandb_datetime_est < target_datetime_est:
        cfg.model.eval.offset_kin_hotfix = 1

    cfg.model.task.outputs = [Output.behavior, Output.behavior_pred]
    # Note: This won't preserve train val split, try to make sure eval datasets were held out
    cfg.dataset.datasets = target
    cfg.dataset.exclude_datasets = []
    cfg.dataset.eval_datasets = []
    dataset = SpikingDataset(cfg.dataset)
    pl.seed_everything(1) # Qualitative on 0 is just atrocious.
    print("Eval length: ", len(dataset))
    data_attrs = dataset.get_data_attrs()
    print(data_attrs)

    model = transfer_model(src_model, cfg.model, data_attrs)
    model.cfg.eval.teacher_timesteps = int(50 * 1.) # 0.5s
    model.cfg.eval.student_gap = int(50 * 1.)

    dataloader = get_dataloader(dataset)
    heldin_outputs = stack_batch(trainer.predict(model, dataloader))

    return (
        heldin_outputs,
        model,
        cfg,
        dataset,
    )

MODEL_LABELS = {
    'data_indy-jt456lfs': 'Expert',
    'data_jango-eqkrqixy': 'Expert',
    'data_min-ni4qut2z': 'Multitask',
    'data_monkey-kvoi7ytu': '70 Hour',
    'neural_data_monkey-pitt-i2maes5i': '700 Hour',
}
outputs = []
model_labels = []
models = []
cfgs = []

for query in queries:
    out = prep_query(query)
    outputs.append(out[0])
    model_labels.append(MODEL_LABELS[query])
    models.append(out[1])
    cfgs.append(out[2])


#%%
def compute_r2s(
        pred_payload: Dict[Output, torch.Tensor], model: BrainBertInterface,
        plot=False, label=None, color=None,
):
    print(f'Pred points: {pred_payload[Output.behavior_pred].shape}')
    # print(pred_payload[Output.behavior].shape)

    prediction = pred_payload[Output.behavior_pred]
    target = pred_payload[Output.behavior]
    is_student = pred_payload[Output.behavior_query_mask]

    r2_net = r2_score(target, prediction)
    is_student_rolling, trial_change_points = rolling_time_since_student(is_student)
    valid = is_student_rolling > model.cfg.eval.student_gap
    # Compute R2
    # mse = torch.mean((target[valid] - prediction[valid])**2, dim=0)
    r2_student = r2_score(target[valid], prediction[valid])
    # print(f'R2_net: {r2:.4f}')
    print(f'R2 Student: {r2_student:.4f}')
    print(model.cfg.eval)

    if plot:
        f = plt.figure(figsize=(10, 10))
        ax = prep_plt(f.gca(), big=True)
        palette = sns.color_palette(n_colors=2)
        colors = [palette[0] if is_student[i] else palette[1] for i in range(len(is_student))]
        ax.scatter(target, prediction, s=3, alpha=0.4, color=colors)
        target_student = target[is_student]
        prediction_student = prediction[is_student]
        target_student = target_student[prediction_student.abs() < 0.8]
        prediction_student = prediction_student[prediction_student.abs() < 0.8]
        robust_r2_student = r2_score(target_student, prediction_student)
        ax.set_xlabel('True')
        ax.set_ylabel('Pred')
        ax.set_title(f'{query} {data_label} R2 Student: {r2_student:.2f}, Robust: {robust_r2_student:.2f} ')
    return r2_student

model_r2s = [
    compute_r2s(
        outputs[i],
        models[i],
        plot=False,
    ) for i in range(len(queries))
]
#%%
palette = sns.color_palette(n_colors=len(queries))
camera_label = {
    'x': 'Vel X',
    'y': 'Vel Y',
    'z': 'Vel Z',
    'EMG_FCU': 'FCU',
    'EMG_ECRl': 'ECRl',
    'EMG_FDP': 'FDP',
    'EMG_FCR': 'FCR',
    'EMG_ECRb': 'ECRb',
    'EMG_EDCr': 'EDCr',
}
xlim = [0, 250]
xlim = [1500, 2000]
subset_cov = []
if data_label == 'miller':
    subset_cov = ['EMG_FCU', 'EMG_ECRl', 'EMG_FCR']

def plot_prediction_spans(ax, is_student, prediction, color, model_label):
    # Convert boolean tensor to numpy for easier manipulation
    is_student_np = is_student.cpu().numpy()

    # Find the changes in the boolean array
    change_points = np.where(is_student_np[:-1] != is_student_np[1:])[0] + 1

    # Include the start and end points for complete spans
    change_points = np.concatenate(([0], change_points, [len(is_student_np)]))

    # Initialize a variable to keep track of whether the first line is plotted
    first_line = True

    # Plot the lines
    for start, end in zip(change_points[:-1], change_points[1:]):
        if is_student_np[start]:  # Check if the span is True
            label = model_label if first_line else None  # Label only the first line
            ax.plot(
                np.arange(start, end),
                prediction[start:end],
                color=color,
                label=label,
                alpha=0.8,
                linestyle='-',
                linewidth=2,
            )
            first_line = False  # Update the flag as the first line is plotted

def plot_target_pred_overlay(
    output_payloads,
    label,
    r2s: List[int],
    cfgs: List[RootConfig],
    model_labels=["Pred"],
    ax: plt.Axes | None = None,
    palette=palette,
    plot_xlabel=False,
    xlim=None,
):
    ax = prep_plt(ax, big=True)

    if xlim:
        payloads = [{
            k: v[xlim[0]:xlim[1]] for k, v in payload.items()
        } for payload in output_payloads]
    else:
        payloads = output_payloads

    target = payloads[0][Output.behavior]
    assert all([torch.allclose(target, payload[Output.behavior]) for payload in payloads])

    ax.plot(target, label=f'True', linestyle='-', alpha=0.2, color='k')
    print(model_labels, r2s)
    for i in range(len(payloads)):
        plot_prediction_spans(
            ax,
            payloads[i][Output.behavior_query_mask],
            payloads[i][Output.behavior_pred],
            palette[i],
            f'{model_labels[i]} ({r2s[i]:.2f})',
        )

    xticks = ax.get_xticks()
    ax.set_xticks(xticks)
    ax.set_xticklabels(xticks * cfgs[0].dataset.bin_size_ms / 1000)
    ax.set_xlim([0 + 1e-5, xlim[1] - xlim[0]])
    if plot_xlabel:
        ax.set_xlabel('Time (s)')
        # legend = ax.legend(
        #     # loc='lower center',  # Positions the legend at the top center
        #     # bbox_to_anchor=(0.8, 1.1),  # Adjusts the box anchor to the top center
        #     # ncol=len(palette) + 1,  # Sets the number of columns equal to the length of the palette to display horizontally
        #     frameon=False,
        #     fontsize=16
        # )
        # # Make text in legend colored accordingly
        # for color, text in zip(palette, legend.get_texts()[1:]):
        #     text.set_color(color)


    # Set minor y-ticks
    # ax.set_yticks(np.arange(-1, 1.1, 0.25), minor=True)
    # Enable minor grid lines
    # ax.grid(which='minor', linestyle=':', linewidth='0.5', color='gray', alpha=0.3)

    ax.set_yticks([]) # Y ticks distracting, kill
    ax.spines['left'].set_visible(False)
    # Remove y axis entirely
    cov_text = camera_label.get(label, label)
    # ax.set_ylabel(f'{camera_label.get(label, label)} (au)')
    # Instead of using a ylabel, annotate
    ax.annotate(
        cov_text,
        xy=(0.25, 0.8),
        xycoords='axes fraction',
        xytext=(-ax.yaxis.labelpad - 5, 0),
        textcoords='offset points',
        fontsize=24,
        # ha='right',
        # va='center',
    )

    # ax.get_legend().remove()

cov_labels = DIMS[data_label]
num_dims = len(cov_labels)
if subset_cov:
    subset_dims = [i for i in range(num_dims) if cov_labels[i] in subset_cov]
    cov_labels = [cov_labels[i] for i in subset_dims]
else:
    subset_dims = range(num_dims)

fig, axs = plt.subplots(
    len(subset_dims), 1, figsize=(8, 2.5 * len(subset_dims)),
    sharex=True, sharey=True
)

for i, dim in enumerate(subset_dims):
    print(outputs[0][Output.behavior_pred].shape)
    reduced_outputs = [
        {
            k: v[dim::num_dims] for k, v in payload.items() if k in [Output.behavior, Output.behavior_pred, Output.behavior_query_mask]
        } for payload in outputs
    ]
    plot_target_pred_overlay(
        reduced_outputs,
        label=cov_labels[i],
        ax=axs[i],
        r2s=model_r2s,
        cfgs=cfgs,
        model_labels=model_labels,
        xlim=xlim,
        plot_xlabel=dim == subset_dims[-1],
    )

plt.tight_layout()


data_label_camera = {
    'odoherty': "O'Doherty",
    'miller': 'IsoEMG',
}
# fig.suptitle(
#     f'{data_label_camera.get(data_label, data_label)} 0-Shot $R^2$ ($\\uparrow$)',
#     fontsize=20,
#     # offset
#     x=0.35,
#     y=0.99,
# )
# fig.suptitle(f'{query}: {data_label_camera.get(data_label, data_label)} Velocity $R^2$ ($\\uparrow$): {r2_student:.2f}')

#%%
# ICL_CROP = 2 * 50 * 2 # Quick hack to eval only a certain portion of data. 2s x 50 bins/s x 2 dims
# ICL_CROP = 3 * 50 * 2 # Quick hack to eval only a certain portion of data. 3s x 50 bins/s x 2 dims
# ICL_CROP = 0

# from context_general_bci.config import DEFAULT_KIN_LABELS
# pred = heldin_outputs[Output.behavior_pred]
# true = heldin_outputs[Output.behavior]
# positions = heldin_outputs[f'{DataKey.covariate_space}_target']
# padding = heldin_outputs[f'covariate_{DataKey.padding}_target']

# if ICL_CROP:
#     if isinstance(pred, torch.Tensor):
#         pred = pred[:, -ICL_CROP:]
#         true = true[:, -ICL_CROP:]
#         positions = positions[:,-ICL_CROP:]
#         padding = padding[:, -ICL_CROP:]
#     else:
#         print(pred[0].shape)
#         pred = [p[-ICL_CROP:] for p in pred]
#         print(pred[0].shape)
#         true = [t[-ICL_CROP:] for t in true]
#         positions = [p[-ICL_CROP:] for p in positions]
#         padding = [p[-ICL_CROP:] for p in padding]

# # print(heldin_outputs[f'{DataKey.covariate_space}_target'].unique())
# # print(heldin_outputs[DataKey.covariate_labels])

# def flatten(arr):
#     return np.concatenate(arr) if isinstance(arr, list) else arr.flatten()
# flat_padding = flatten(padding)

# if model.data_attrs.semantic_covariates:
#     flat_space = flatten(positions)
#     flat_space = flat_space[~flat_padding]
#     coords = [DEFAULT_KIN_LABELS[i] for i in flat_space]
# else:
#     # remap position to global space
#     coords = []
#     labels = heldin_outputs[DataKey.covariate_labels]
#     for i, trial_position in enumerate(positions):
#         coords.extend(np.array(labels[i])[trial_position])
#     coords = np.array(coords)
#     coords = coords[~flat_padding]

# df = pd.DataFrame({
#     'pred': flatten(pred)[~flat_padding].flatten(), # Extra flatten - in list of tensors path, there's an extra singleton dimension
#     'true': flatten(true)[~flat_padding].flatten(),
#     'coord': coords,
# })
# # plot marginals
# subdf = df
# # subdf = df[df['coord'].isin(['y'])]

# g = sns.jointplot(x='true', y='pred', hue='coord', data=subdf, s=3, alpha=0.4)
# # Recompute R2 between pred / true
# from sklearn.metrics import r2_score
# r2 = r2_score(subdf['true'], subdf['pred'])
# mse = np.mean((subdf['true'] - subdf['pred'])**2)
# # set title
# g.fig.suptitle(f'{query} {mode} {str(target)[:20]} Velocity R2: {r2:.2f}, MSE: {mse:.4f}')

#%%
# f = plt.figure(figsize=(10, 10))
# ax = prep_plt(f.gca(), big=True)
# trials = 4
# trials = 1
# trials = min(trials, len(heldin_outputs[Output.behavior_pred]))
# trials = range(trials)

# colors = sns.color_palette('colorblind', df.coord.nunique())
# label_unique = list(df.coord.unique())
# # print(label_unique)
# def plot_trial(trial, ax, color, label=False):
#     vel_true = heldin_outputs[Output.behavior][trial]
#     vel_pred = heldin_outputs[Output.behavior_pred][trial]
#     dims = heldin_outputs[f'{DataKey.covariate_space}_target'][trial]
#     pad = heldin_outputs[f'covariate_{DataKey.padding}_target'][trial]
#     vel_true = vel_true[~pad]
#     vel_pred = vel_pred[~pad]
#     dims = dims[~pad]
#     for i, dim in enumerate(dims.unique()):
#         dim_mask = dims == dim
#         true_dim = vel_true[dim_mask]
#         pred_dim = vel_pred[dim_mask]
#         dim_label = DEFAULT_KIN_LABELS[dim] if model.data_attrs.semantic_covariates else heldin_outputs[DataKey.covariate_labels][trial][dim]
#         if dim_label != 'f':
#             true_dim = true_dim.cumsum(0)
#             pred_dim = pred_dim.cumsum(0)
#         color = colors[label_unique.index(dim_label)]
#         ax.plot(true_dim, label=f'{dim_label} true' if label else None, linestyle='-', color=color)
#         ax.plot(pred_dim, label=f'{dim_label} pred' if label else None, linestyle='--', color=color)

#     # ax.plot(pos_true[:,0], pos_true[:,1], label='true' if label else '', linestyle='-', color=color)
#     # ax.plot(pos_pred[:,0], pos_pred[:,1], label='pred' if label else '', linestyle='--', color=color)
#     # ax.set_xlabel('X-pos')
#     # ax.set_ylabel('Y-pos')
#     # make limits square
#     # ax.set_aspect('equal', 'box')


# for i, trial in enumerate(trials):
#     plot_trial(trial, ax, colors[i], label=i==0)
# ax.legend()
# ax.set_title(f'{mode} {str(target)[:20]} Trajectories')
# # ax.set_ylabel(f'Force (minmax normalized)')
# # xticks - 1 bin is 20ms. Express in seconds
# ax.set_xticklabels(ax.get_xticks() * cfg.dataset.bin_size_ms / 1000)
# # express in seconds
# ax.set_xlabel('Time (s)')

# #%%
# # Look for the raw data
# from pathlib import Path
# from context_general_bci.tasks.rtt import ODohertyRTTLoader
# mins = []
# maxes = []
# raw_mins = []
# raw_maxes = []
# bhvr_vels = []
# bhvr_pos = []
# for i in dataset.meta_df[MetaKey.session].unique():
#     # sample a trial
#     trial = dataset.meta_df[dataset.meta_df[MetaKey.session] == i].iloc[0]
#     print(trial.path)
#     # Open the processed payload, print minmax
#     payload = torch.load(trial.path)
#     print(payload['cov_min'])
#     print(payload['cov_max'])
#     # append and plot
#     mins.extend(payload['cov_min'].numpy())
#     maxes.extend(payload['cov_max'].numpy())
#     # open the original payload
#     path_pieces = Path(trial.path).parts
#     og_path = Path(path_pieces[0], *path_pieces[2:-1])
#     spike_arr, bhvr_raw, _ = ODohertyRTTLoader.load_raw(og_path, cfg.dataset, ['Indy-M1', 'Loco-M1'])
#     bhvr_vel = bhvr_raw[DataKey.bhvr_vel].flatten()
#     bhvr_vels.append(bhvr_vel)
#     # bhvr_pos.append(bhvr_raw['position'])
#     raw_mins.append(bhvr_vel.min().item())
#     raw_maxes.append(bhvr_vel.max().item())
# ax = prep_plt()
# ax.set_title(f'{query} Raw MinMax bounds')
# ax.scatter(mins, maxes)
# ax.scatter(raw_mins, raw_maxes)
# ax.set_xlabel('Min')
# ax.set_ylabel('Max')
# # ax.plot(mins, label='min')
# # ax.plot(maxes, label='max')
# # ax.legend()
# #%%
# print(bhvr_pos[0][:,1:3].shape)
# # plt.plot(bhvr_pos[0][:, 1:3])
# # plt.plot(bhvr_vels[3])
# # plt.plot(bhvr_vels[2])
# # plt.plot(bhvr_vels[1])
# # plt.plot(bhvr_vels[0])
# import scipy.signal as signal
# def resample(data):
#     covariate_rate = cfg.dataset.odoherty_rtt.covariate_sampling_rate
#     base_rate = int(1000 / cfg.dataset.bin_size_ms)
#     # print(base_rate, covariate_rate, base_rate / covariate_rate)
#     return torch.tensor(
#         # signal.resample(data, int(len(data) / cfg.dataset.odoherty_rtt.covariate_sampling_rate / (cfg.dataset.bin_size_ms / 1000))) # This produces an edge artifact
#         signal.resample_poly(data, base_rate, covariate_rate, padtype='line')
#     )
# # 250=Hz to 5Hz - > 2000
# # plt.plot(bhvr_pos[0][:, 1:3])
# plt.plot(resample(bhvr_pos[0][:, 1:3]))
