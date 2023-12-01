#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# TODO:
# * probably remove the map usage. seems non-Pythonic, clumsy over list comps

import gz21_ocean_momentum.common.cli as cli
import gz21_ocean_momentum.common.assorted as common
import gz21_ocean_momentum.common.bounding_box as bounding_box
import gz21_ocean_momentum.lib.model as lib
import gz21_ocean_momentum.models.submodels as submodels
import gz21_ocean_momentum.models.transforms as transforms
import gz21_ocean_momentum.models.models1 as model
import gz21_ocean_momentum.train.losses as loss
from gz21_ocean_momentum.train.base import Trainer
from gz21_ocean_momentum.inference.metrics import MSEMetric, MaxMetric
from gz21_ocean_momentum.data.datasets import Subset_, ConcatDataset_

import configargparse

import os

import xarray as xr
import numpy as np

import torch
from torch.utils.data import DataLoader, ConcatDataset
from torch import optim
from torch.optim.lr_scheduler import MultiStepLR

# TODO probably temporary
import tempfile

# TODO ideally temporary but probably not
import copy

_cli_desc = """
Train a Pytorch neural net to predict subgrid ocean momentum forcing from
ocean surface velocity.

Uses data generated by the GZ21 data step script.
"""

p = configargparse.ArgParser(description=_cli_desc)
p.add("--config-file", is_config_file=True, help="config file path")
p.add("--in-train-data-dir",         type=str,   required=True, help="training data in zarr format, containing ocean velocities and forcings")
p.add("--subdomains-file",           type=str,   required=True, help="YAML file describing subdomains to split input data into (see readme for format)")
p.add("--batch-size",                 type=int,   required=True, help="TODO")
p.add("--epochs",                    type=int,   required=True, help="number of epochs to train for")
p.add("--out-model",                 type=str,   required=True, help="save trained model to this path")
p.add("--initial-learning-rate",     type=float, required=True, help="initial learning rate for optimization algorithm")
p.add("--decay-factor",              type=float, required=True, help="learning rate decay factor, applied each time an epoch milestone is reached")
p.add("--decay-at-epoch-milestones", type=int, action="append", required=True, help="milestones to decay at. May specify multiple times. Must be strictly increasing with no duplicates")
p.add("--device",                    type=str, default="cuda:0", help="neural net device (e.g. cuda:0, cpu)")
p.add("--weight-decay",              type=float, default=0.0, help="Weight decay parameter for Adam loss function. Deprecated, default 0.")
p.add("--train-split-end",  type=float, required=True, help="0>=x>=1. Use 0->x of input dataset for training")
p.add("--test-split-start", type=float, required=True, help="0>=x>=1. Use x->end of input dataset for training. Must be greater than --train-split-start")
p.add("--printevery", type=int, default=20)
options = p.parse_args()

# TODO raehik 2023-11-13: parse, don't validate
if not common.list_is_strictly_increasing(options.decay_at_epoch_milestones):
    cli.fail(2, "epoch milestones list is not strictly increasing")

torch.autograd.set_detect_anomaly(True)

def _check_dir(dir_path):
    """
    Create directory if it does not already exist.

    Parameters
    ----------
    dir_path : str
        string of directory to check/make
    """
    if not os.path.exists(dir_path):
        os.mkdir(dir_path)

# Directories where temporary data will be saved
data_location = tempfile.mkdtemp()
print("Created temporary dir at  ", data_location)

FIGURES_DIRECTORY = "figures"
MODELS_DIRECTORY = "models"
MODEL_OUTPUT_DIR = "model_output"

for directory in [FIGURES_DIRECTORY, MODELS_DIRECTORY, MODEL_OUTPUT_DIR]:
    _check_dir(os.path.join(data_location, directory))

# load input training data, split into spatial domains via provided bounding
# boxes
ds = xr.open_zarr(options.in_train_data_dir)
f_bound_cm26 = lambda x: bounding_box.bound_dataset("yu_ocean", "xu_ocean", ds, x)
sd_dss_xr = list(map(f_bound_cm26, bounding_box.load_bounding_boxes_yaml(options.subdomains_file)))

# transform wrapper
def submodel_transform_and_to_torch(ds_xr):
    # TODO: we apparently have to deepcopy because it tracks if it's already
    # fitted the transform. ok I guess
    ds_xr = copy.deepcopy(submodels.transform3).fit_transform(ds_xr)
    ds_xr = ds_xr.compute()
    ds_torch = lib.gz21_train_data_subdomain_xr_to_torch(ds_xr)
    return ds_torch

datasets = list(map(submodel_transform_and_to_torch, sd_dss_xr))

train_dataset, test_dataset = prep_train_test(
        datasets,
        options.train_split_end, options.test_split_start,
        options.batchsize)
# split dataset according to requested lengths
train_range = lambda x: range(0, common.at_idx_pct(options.train_split_end,x))
test_range  = lambda x: range(common.at_idx_pct(options.test_split_start, x), len(x))
#train_datasets = [ Subset_(x, train_range(x)) for x in datasets ]
#test_datasets  = [ Subset_(x, test_range(x))  for x in datasets ]
train_datasets = datasets
test_datasets = datasets

# Concatenate datasets. This adds shape transforms to ensure that all
# regions produce fields of the same shape, hence should be called after
# saving the transformation so that when we're going to test on another
# region this does not occur.
print(f"len(train_datasets[0]):       {len(train_datasets[0])}")
print(f"len(train_datasets[0][0]):    {len(train_datasets[0][0])}")
print(f"len(train_datasets[0][0][0]): {len(train_datasets[0][0][0])}")
train_dataset = ConcatDataset(train_datasets)
test_dataset = ConcatDataset(test_datasets)

# Dataloaders
train_dataloader = DataLoader(
    train_dataset, batch_size=options.batch_size, shuffle=True, drop_last=True, num_workers=4
)
test_dataloader = DataLoader(
    test_dataset, batch_size=options.batch_size, shuffle=False, drop_last=True
)

# -------------------
# LOAD NEURAL NETWORK
# -------------------
# Load the loss class required in the script parameters
criterion = loss.HeteroskedasticGaussianLossV2(datasets[0].n_targets)
net = model.FullyCNN(datasets[0].n_features, criterion.n_required_channels)
transformation = transforms.SoftPlusTransform()
transformation.indices = criterion.precision_indices
net.final_transformation = transformation

# Log the text representation of the net into a txt artifact
with open(
    os.path.join(data_location, MODELS_DIRECTORY, "nn_architecture.txt"),
    "w",
    encoding="utf-8",
) as f:
    print("Writing neural net architecture into txt file.")
    f.write(str(net))

# Add transforms required by the model.
for dataset in datasets:
    dataset.add_transforms_from_model(net)


# -------------------
# TRAINING OF NETWORK
# -------------------
# Adam optimizer
# To GPU
net.to(options.device)

# Optimizer and learning rate scheduler
optimizer = optim.Adam(
        list(net.parameters()),
        lr=options.initial_learning_rate, weight_decay=options.weight_decay)
lr_scheduler = MultiStepLR(
        optimizer, options.decay_at_epoch_milestones,
        gamma=options.decay_factor)

trainer = Trainer(net, options.device)
trainer.criterion = criterion
trainer.print_loss_every = options.printevery

# metrics saved independently of the training criterion.
metrics = {"R2": MSEMetric(), "Inf Norm": MaxMetric()}
for metric_name, metric in metrics.items():
    metric.inv_transform = lambda x: test_dataset.inverse_transform_target(x)
    trainer.register_metric(metric_name, metric)

for i_epoch in range(options.epochs):
    print(f"Epoch number {i_epoch}.")
    # TODO remove clipping?
    train_loss = trainer.train_for_one_epoch(
        train_dataloader, optimizer, lr_scheduler, clip=1.0
    )
    test = trainer.test(test_dataloader)
    if test == "EARLY_STOPPING":
        print(test)
        break
    test_loss, metrics_results = test
    # Log the training loss
    print("Train loss for this epoch is ", train_loss)
    print("Test loss for this epoch is ", test_loss)

    for metric_name, metric_value in metrics_results.items():
        print(f"Test {metric_name} for this epoch is {metric_value}")

#net.cpu()
torch.save(net.state_dict(), options.out_model)
