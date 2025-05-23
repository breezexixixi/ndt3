import os
import socket
from typing import Tuple
from .loader import loadmat, cast_struct, get_struct_or_dict
from .halton import generate_search
from .grid_search import grid_search
from .baselines import *
import math
import torch

from einops import rearrange


def suppress_default_registry():
    os.environ['NDT_SUPPRESS_DEFAULT_REGISTRY'] = '1'

def enum_backport(old_inst, new_enum_cls):
    # We run many enum checks but also migrated class modules at some point -- python doesn't recognize them as equal
    # so we add a cast
    return new_enum_cls[old_inst.name]

def sort_A_by_B(A: torch.Tensor, B: torch.Tensor, indices: torch.Tensor | None = None) -> Tuple[torch.Tensor, torch.Tensor | None]:
    # Generally expecting Batch T * dimensions
    # Sort B along the Time dimension (dim=1) and get the sorting indices
    _, indices = torch.sort(B, dim=1)
    # Sort A using the sorting indices obtained from B
    if indices.ndim != A.ndim:
        indices = indices.unsqueeze(-1).expand(-1, -1, A.shape[-1])
    A_sorted = torch.gather(A, 1, indices)
    return A_sorted, indices

def unflatten(
    flat_data: torch.Tensor,
    time: torch.Tensor,
    position: torch.Tensor,
    default_value=-100,
) -> torch.Tensor:
    r"""
        Unflatten data into (time, position) space
        Args:
            flat_data: (batch, flat ~= time*position, token_chan, ...)
            time: (batch, flat_time (len time*position))
            position: (batch, flat_position (len time * position))
        Returns:
            assembled: (batch, time, channel)
    """
    b, _, token_chan, *rest = flat_data.size()
    time_min, time_max = time.min(), time.max()
    position_min, position_max = position.min(), position.max()
    assembled = torch.full(
        (b, time_max - time_min + 1, position_max - position_min + 1, token_chan, *rest),
        default_value,
        device=flat_data.device,
        dtype=flat_data.dtype,
    )
    assembled[ # no scatter needed, merely need to select the specified indices
        torch.arange(b, device=flat_data.device)[:, None],
        time - time_min,
        position - position_min,
    ] = flat_data
    assembled = assembled.flatten(start_dim=2)
    return assembled

def simple_unflatten(src: torch.Tensor, ref: torch.Tensor, batch: bool = False):
    if batch:
        return rearrange(src, 'b (time space) ... -> b time space ...', space=len(ref.unique()))
    return rearrange(src, '(time space) ... -> time space ...', space=len(ref.unique()))

def cosine_schedule(time: torch.Tensor | int, T: int, start: float = 0.9, end: float = 0.0) -> torch.Tensor:
    r"""
        Cosine schedule
        Args:
            time: (batch, time)
            T: int
            start: float
            end: float
        Returns:
            schedule: (batch, time)
    """
    assert T > 0
    assert 0.0 <= start <= 1.0
    assert 0.0 <= end <= 1.0
    assert start != end
    # assert time.max() <= T
    # assert time.min() >= 0
    schedule = end + (start - end) * (1 + torch.cos(time * math.pi / T)) / 2
    return schedule

def to_device(batch, device):
    r" in place "
    for k, v in batch.items():
        if isinstance(v, torch.Tensor):
            batch[k] = v.to(device)
    return batch


def get_simple_host(): # find shared FS identity for evals run on different locations. Important as we don't want to override
    hostname = socket.gethostname()
    if 'nid' in hostname: # nersc
        hostname = 'nid'
    elif 'crc' in hostname:
        hostname = 'crc'
    elif 'mind' in hostname:
        hostname = 'mind'
    elif 'WS106l' in hostname:
        hostname = 'rnel-n0'
    return hostname

def get_scratch_path() -> str:
    hostname = get_simple_host()
    if hostname == 'crc':
        # scratch_path = os.environ.get("SLURM_SCRATCH") # flash
        scratch_path = '/ix3/rgaunt/joy47' # 5tb global flash
    elif hostname == 'nid':
        scratch_path = os.environ.get("SCRATCH")
    else:
        raise NotImplementedError("Don't know scratch path for this host")
    return scratch_path

# Has dependencies on typedefs in Config but hopefully that's not a huge issue.
from .ckpts_and_wandb_helpers import *