#%%
from pathlib import Path
import numpy as np

from context_general_bci.utils import loadmat


# Unzipped https://figshare.com/articles/dataset/Processed_data_files_used_in_Schwartze_et_al_2023/23631951
# to ./data/rouse_precision and placed ./data_extracted at root.
data_dir = Path(
    # 'data/rouse_precision/monk_p/COT_SpikesCombined'
    'data/rouse/'
)

# for sample_file in data_dir.glob('*.mat'):
    # data = loadmat(sample_file)
    # print(f'{sample_file.stem} -- Num channels : {len(data["AllSpikeTimes"])}')
sample_file = data_dir.glob('*.mat').__next__()
data = loadmat(sample_file)


#%%
from scipy.io import loadmat
# from mat73 import loadmat
scipy_data = loadmat(sample_file, struct_as_record=False, squeeze_me=True)
#%%
print(data.keys())
# print(data['CursorPos'].shape)
# print(scipy_data['CursorPos'].shape)
# print(len(data['AllSpikeTimes']))
# print(len(scipy_data['AllSpikeTimes']))
print(data['AllSpikeTimes'][0].shape)
print(scipy_data['AllSpikeTimes'][0].shape)
#%%
print(data.keys())

covariate = data['JoystickPos_disp'] # pretty sure this is 100Hz. What's the alignment wrt the trial?
import scipy.signal as signal
import matplotlib.pyplot as plt
f = plt.figure(figsize=(20, 10))
ax = f.gca()

# ? Why do I suddenly have so many NaNs?
pos = covariate
vel = np.gradient(pos, axis=1)
def resample(data, covariate_rate=100):
    base_rate = int(1000 / 20)
    return (
        signal.resample_poly(data, base_rate, covariate_rate, padtype='line', axis=1)
    )

print(pos[0, :, 0])
ax.plot(np.arange(pos.shape[1]), pos[0,:,0] / 10) # For visual scaling
ax.plot(np.arange(pos.shape[1]), vel[0,:,0])
fake_vel = vel.copy()
fake_vel[np.isnan(fake_vel)] = 0
ax.plot(np.arange(0, pos.shape[1], 2), resample(fake_vel)[0, :, 0])
#%%
plt.plot(covariate[0,:,0])
plt.plot(covariate[0,:,1])
#%%
spikes = data['AllSpikeTimes']
spikes = [s[0] for s in spikes]
print(len(spikes))
# print(len(spikes[0]))
# print(len(spikes[1]))
# print(len(spikes[2]))
# print(len(spikes[3]))
# print(spikes[0])

#%%
print(data['TrialInfo'].keys())
print(len(data['TrialInfo']['trial_start_time']))
# print(data['TrialInfo'])
# print(data['TrialInfo']['align_samples'])
#%%
trial_spikes = data['SpikeTimes']
trial_spikes = [s[0] for s in trial_spikes]

#%%
print(len(trial_spikes))
print(len(trial_spikes[0]))
print(len(trial_spikes[1]))
# ? Are there spikes outside the main trial?
# print(trial_spikes[0])
def flatten_single(channel_spikes, offsets): # offset in seconds
    # print(channel_spikes)
    filtered = [spike + offset for spike, offset in zip(channel_spikes, offsets) if spike is not None]
    filtered = [spike if len(spike.shape) > 0 else np.array([spike]) for spike in filtered]
    return np.concatenate(filtered)
trial_spikes_cat = [flatten_single(channel, data['TrialInfo']['trial_start_time']) for channel in trial_spikes]
#%%
# print(trial_spikes_cat[0].shape)
# Check all trial spikes in spikes

for trial_channel, channel in zip(trial_spikes_cat, spikes):
    # channel is in s, trial_channel in s. round both to 0.001
    trial_channel = np.round(trial_channel, 3)
    channel = np.round(channel, 3)
    print(trial_channel[:10])
    print(channel[:10])
    # print the set diff
    print(np.setdiff1d(trial_channel, channel))
    assert np.all(np.isin(trial_channel, channel))

#%%
# Plot the both
import matplotlib.pyplot as plt
f = plt.figure(figsize=(20, 10))
ax = f.gca()
ax.scatter(spikes[0] / 1000, np.ones(len(spikes[0])), alpha=0.1)
ax.scatter(trial_spikes_cat[0], np.ones(len(trial_spikes_cat[0])) + 1, alpha=0.1)


#%%
# Covariates look fine
# * definitely trialized though. either I force concat (I think that's the plan), or I zero pad.