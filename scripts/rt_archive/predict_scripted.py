#%%
# Autoregressive inference procedure, for generalist model
import os
import argparse
from pprint import pprint
import logging
from datetime import datetime
from pytz import timezone

import torch
torch.set_float32_matmul_precision('medium') # we don't care about precision really..

from sklearn.metrics import r2_score

from torch.utils.data import DataLoader
import lightning.pytorch as pl

from context_general_bci.model import transfer_model
from context_general_bci.dataset import SpikingDataset
from context_general_bci.config import RootConfig, ModelConfig, ModelTask, Metric, Output, DataKey, MetaKey

from context_general_bci.analyze_utils import (
    stack_batch,
    rolling_time_since_student,
)
from context_general_bci.plotting import prep_plt, data_label_to_target
from context_general_bci.inference import load_wandb_run

from context_general_bci.utils import wandb_query_latest

def main(
    student: bool,
    temperature: float,
    id: int,
    student_prob: float,
    data_label: str,
    gap: int,
    eval_tail_s: int,
    # gpu: int,
    cue: float,
    limit: float,
    trials: int,
    maskout_last_n: int,
    batch_size: int,
):
    logging.getLogger("lightning.pytorch").setLevel(logging.ERROR)
    print("Starting eval")
    print(f"ID: {id}")
    print(f"Data label: {data_label}")
    wandb_run = wandb_query_latest(id, allow_running=True, use_display=True)[0]
    print(wandb_run.id)
    src_model, cfg, old_data_attrs = load_wandb_run(wandb_run, tag='val_loss')
    # cfg.model.task.metrics = [Metric.kinematic_r2]
    cfg.model.task.outputs = [Output.behavior, Output.behavior_pred]
    cfg.dataset.exclude_datasets = []
    cfg.dataset.eval_datasets = []
    cfg.model.eval.teacher_timesteps = round(cue * 1000 // cfg.dataset.bin_size_ms) # 0.5s
    cfg.model.eval.limit_timesteps = round(limit * 1000 // cfg.dataset.bin_size_ms) # up to 4s
    cfg.model.eval.temperature = temperature
    cfg.model.eval.use_student = student
    cfg.model.eval.student_prob = student_prob
    cfg.model.eval.maskout_last_n = maskout_last_n

    # Hotfix position: check if wandb run is older than oct 15, 10:00am
    wandb_datetime_utc = datetime.fromisoformat(wandb_run.created_at).replace(tzinfo=timezone('UTC'))
    est = timezone('US/Eastern')
    wandb_datetime_est = wandb_datetime_utc.astimezone(est)

    # Create a datetime object for Oct 15, 2023, 10AM EST
    target_datetime_est = est.localize(datetime(2023, 10, 15, 10, 0, 0))

    if wandb_datetime_est < target_datetime_est:
        cfg.model.eval.offset_kin_hotfix = 1

    if eval_tail_s:
        if data_label not in ['robust', 'eval', 'indy', 'miller'] and not cfg.dataset.pack_dense:
            raise ValueError("Eval tail only supported for continuous datasets")
        print(f"Eval tail: {eval_tail_s}")
        # Compute gap based on total timebins - eval tail bins - teacher timesteps
        # Hm,... I need to update this script.
        total_bins = round(cfg.dataset.odoherty_rtt.chop_size_ms // cfg.dataset.bin_size_ms)
        eval_bins = round(eval_tail_s * 1000 // cfg.dataset.bin_size_ms)
        teacher_bins = cfg.model.eval.teacher_timesteps
        gap = total_bins - eval_bins - teacher_bins
    cfg.model.eval.student_gap = gap

    trainer = pl.Trainer(
        accelerator='gpu',
        devices=1 if torch.cuda.is_available() else 0,
        # devices=torch.cuda.device_count() if torch.cuda.is_available() else 0,
        default_root_dir='./data/tmp',
        precision='bf16-mixed',
    )
    if data_label == "eval":
        for sub_label in ['dyer', 'indy', 'miller']: # TODO infer from eval_datasets
            icl_eval(src_model, cfg, sub_label, trials, batch_size, trainer)
    else:
        return icl_eval(src_model, cfg, data_label, trials, batch_size, trainer)

def icl_eval(
    src_model: pl.LightningModule,
    cfg: RootConfig,
    data_label: str,
    trials: int,
    batch_size: int,
    trainer: pl.Trainer,
):
    # Note: This won't preserve train val split, try to make sure eval datasets were held out
    cfg.dataset.datasets = data_label_to_target(data_label)
    dataset = SpikingDataset(cfg.dataset)
    pl.seed_everything(0)
    print(f"START Data label: {data_label}")
    # Quick cheese - IDR how to subset by length, so use "val" to get 20% quickly
    if trials > 0:
        dataset.subset_scale(limit_per_session=trials)
    print("Eval length: ", len(dataset))
    data_attrs = dataset.get_data_attrs()
    # print(data_attrs)

    model = transfer_model(src_model, cfg.model, data_attrs)

    pprint(model.cfg.eval)

    def get_dataloader(dataset: SpikingDataset, batch_size=batch_size, num_workers=8, **kwargs) -> DataLoader:
        return DataLoader(dataset,
            batch_size=batch_size,
            num_workers=num_workers,
            persistent_workers=num_workers > 0,
            collate_fn=dataset.tokenized_collater,
        )

    dataloader = get_dataloader(dataset)
    outputs = stack_batch(trainer.predict(model, dataloader))

    prediction = outputs[Output.behavior_pred]
    target = outputs[Output.behavior]
    is_student = outputs[Output.behavior_query_mask]
    is_student_rolling, trial_change_points = rolling_time_since_student(is_student)
    valid = is_student_rolling > model.cfg.eval.student_gap * len(outputs[DataKey.covariate_labels.name])
    print(f"Computing metrics over {valid.sum()} samples")
    # Compute R2
    # r2 = r2_score(target, prediction)
    mse = torch.mean((target[valid] - prediction[valid])**2, dim=0)
    r2_student = r2_score(target[valid], prediction[valid])
    # print(f'R2: {r2:.4f}')
    print(f'MSE: {mse:.4f}')
    print(f'R2 Student: {r2_student:.4f}')
    pprint(model.cfg.eval)
    print(f"END Data label: {data_label}")
    # print(query)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluation script.")

    parser.add_argument("-s", "--student", action="store_true", help="Flag indicating if the subject is a student.")
    parser.add_argument("-t", "--temperature", type=float, default=0., help="Temperature value.")
    parser.add_argument("-i", "--id", type=str, required=True, help="ID number.")
    parser.add_argument("-p", "--student_prob", type=float, default=1., help="Probability of student.")
    parser.add_argument("-d", "--data_label", type=str, required=True, help="Data label.")
    # parser.add_argument("-g", "--gpu", type=int, default=0, help="GPU index.")
    parser.add_argument('-g', '--gap', type=int, default=0, help="Gap for student.")
    parser.add_argument("-c", "--cue", type=float, default=0.5, help="Cue context length (s)" )
    parser.add_argument("-l", "--limit", type=float, default=0., help="Limit eval length (s)")
    parser.add_argument("-e", "--eval_tail_s", type=int, default=1., help="Eval tail length (s)")
    parser.add_argument("--trials", type=int, default=0, help="Number of trials per session to evaluate. 0 for no subset")
    parser.add_argument("-b", "--batch_size", type=int, default=48, help="Batch size.")
    parser.add_argument("-m", "--maskout_last_n", type=int, default=0, help="Mask out last N timesteps.")
    args = parser.parse_args()
    main(**vars(args))
