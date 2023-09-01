# Stochastic-Deep Learning Parameterization of Ocean Momentum Forcing
[gz21-paper-code-zenodo]: https://zenodo.org/record/5076046#.ZF4ulezMLy8
[gz21-paper-agupubs]: https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2021MS002534

This repository provides a subgrid model of ocean momentum forcing, based on a
convolutional neural network (CNN) trained on high-resolution surface velocity
data from CM2.6. This model can then be coupled into larger GCMs, e.g., at
coarser granularity to provide high-fidelity parameterization of ocean momentum
forcing. The parameterization output by the CNN consists of a Gaussian
distribution specified by 2 parameters (mean and standard deviation), which
allows for stochastic implementations in online models.

The model is based on the paper [Arthur P. Guillaumin, Laure Zanna (2021).
Stochastic-deep learning parameterization of ocean momentum
forcing][gz21-paper-agupubs]. The exact version of the code used to produce said
paper can be found on [Zenodo][gz21-paper-code-zenodo]. The present repository
provides a version of this model which is designed for others to reproduce,
replicate, and reuse.

_This repository is currently work-in-progress following a process of
refreshing the code and making it available for easy reuse by others._

## Architecture
The model is written in Python, using PyTorch for the CNN. We provide 3 separate
"steps", which are run using different commands and arguments:

* data processing: downloads part of CM2.6 dataset and processes
* model training: train model on processed data
* model testing: tests the trained model on an unseen region

For more details on each of the steps, see the [`docs`](docs/) directory.

## Usage
### Dependencies
Python 3.9 or newer is required. We primarily test on Python 3.11.

To avoid any conflicts with local packages, we recommend using a virtual
environment. In the root directory:

    python -m venv venv

or using [virtualenv](https://virtualenv.pypa.io/en/latest/):

    virtualenv venv

Then load with `source venv/bin/activate`.

With `pip` installed, run the following in the root directory:

    pip install -e .

*(An alternate `pyproject.toml` file is provided for building with
[Poetry](https://python-poetry.org/). To use, rename `pyproject-poetry.toml` to
`pyproject.toml` (overwriting the existing file) and use Poetry as normal. Note
that the Poetry build is not actively supported-- if it fails, check that the
dependencies are up-to-date with the setuptools `pyproject.toml`.)*

### Running unit tests
There are a handful of unit tests using pytest, in the [`tests`](tests/)
directory. These assert some operations and methods used in the steps. They may
be run in the regular method:

    pytest

### Running steps
Execute these commands from the repository root.

See [`docs`](docs/) directory for more details.

For command-line option explanation, run the appropriate step with `--help` e.g.
`python src/gz21_ocean_momentum/cli/data.py --help`.

#### MLflow specifics
MLflow parameters:

* `experiment-name`: "tag" to use for MLflow experiment. Used to share artifacts
  between steps, i.e. you should run the training step with a name you used to
  run the data processing step.
* `exp_id`: TODO: one way MLflow distinguishes runs. May need to set to share
  artifacts between steps...?
* `run_id`: TODO: one way MLflow distinguishes runs. May need to set to share
  artifacts between steps...?

For MLflow versions older than 1.25.0, replace the `--env-manager=local` flag
with `--no-conda`.

When invoking steps with `mlflow run`, you may need to control the path used for
`mlruns` (which stores outputs of runs). You may set the `MLFLOW_TRACKING_URI`
environment variable to achieve this. In Linux:

    export MLFLOW_TRACKING_URI="/path/to/data/dir"

In a Jupyter Notebook:

    %env MLFLOW_TRACKING_URI /path/to/data/dir

In Python:

```python
import os
os.environ['MLFLOW_TRACKING_URI'] = '/path/to/data/dir'
```

#### Data processing
The CLI into the data processing step is at
[`cli/data.py`](src/gz21_ocean_momentum/cli/data.py). It generates coarse
surface velocities and diagnosed forcings from the CM2.6 dataset and saves them
to disk. You may configure certain parameters such as bounds (lat/lon) and CO2
level.

**You must configure GCP credentials to download the CM2.6 dataset used.**
See [`docs/data.md`](docs/data.md) for more details.

Direct call (without MLflow) example:

    python src/gz21_ocean_momentum/cmip26.py \
    --lat-min -80 --lat-max 80 --long-min -280 --long-max 80 \
    --factor 4 --ntimes 100 --co2-increase

Some preprocessed data is hosted on HuggingFace at
[datasets/M2LInES/gfdl-cmip26-gz21-ocean-forcing](https://huggingface.co/datasets/M2LInES/gfdl-cmip26-gz21-ocean-forcing).

#### Training
The [`trainScript.py`](src/gz21_ocean_momentum/trainScript.py) script runs the
model training step. You may configure various training parameters through
command-line arguments, such as number of training epochs, loss functions, and
training data. (You will want to select the output from a data processing step
for the latter.)

MLflow call example:

```
mlflow run . --experiment-name <name> -e train --env-manager=local \
-P run_id=<run id> \
-P learning_rate=0/5e-4/15/5e-5/30/5e-6 -P n_epochs=200 -P weight_decay=0.00 -P train_split=0.8 \
-P test_split=0.85 -P model_module_name=models.models1 -P model_cls_name=FullyCNN -P batchsize=4 \
-P transformation_cls_name=SoftPlusTransform -P submodel=transform3 \
-P loss_cls_name=HeteroskedasticGaussianLossV2
```

Relevant parameters:

* `exp_id`: id of the experiment containing the run that generated the forcing
  data.
* `run_id`: id of the run that generated the forcing data that will be used for
  training.
* `loss_cls_name`: name of the class that defines the loss. This class should be
  defined in train/losses.py in order for the script to find it. Currently, the
  main available options are:
  * `HeteroskedasticGaussianLossV2`: this corresponds to the loss used in the
    2021 paper
  * `BimodalGaussianLoss`: a Gaussian loss defined using two Gaussian modes
* `model_module_name`: name of the module that contains the class defining the
  NN used
* `model_cls_name`: name of the class defining the NN used, should be defined in
  the module specified by `model_module_name`
* `train_split`: use `0->N` percent of the dataset for training
* `test_split`: use `N->100` percent of the dataset for testing

Another important way to modify the way the script runs consists in modifying
the domains used for training. These are defined in
[`training_subdomains.yaml`](training_subdomains.yaml) in terms of their
coordinates. Note that at run time domains will be truncated to the size of the
smallest domain in terms of number of points.

*Note:* Ensure that the spatial subdomains defined in `training_subdomains.yaml`
are contained in the domain of the forcing data you use. If they aren't, you may
get a Python error along the lines of:

```
RuntimeError: Calculated padded input size per channel: <smaller than 5 x 5>.
Kernel size: (5 x 5). Kernel size can't be greater than actual input size
```

#### Inference
The [`inference/main.py`](src/gz21_ocean_momentum/inference/main.py) script runs the
model testing stage. This consists of running a trained model on a dataset. 
The model's output are then stored as an artefact. This step
should ideally be run with a GPU device available, to achieve a better speed.

In this step it is particularly important to set the environment variable `MLFLOW_TRACKING_URI`
in order for the data to be found and stored in a sensible place.

One can run the inference step by interactively
running the following in the project root directory:

    python3 -m gz21_ocean_momentum.inference.main --n_splits=40

with `n_splits` being the number of subsets which the dataset is split 
into for the processing, before being put back together for the final output.
This is done in order to avoid memory issues for large datasets.
Other useful arguments for this call would be 
- `to_experiment`: the name of the mlflow experiment used for this run (default is "test").
- `batch_size`: the batch size used in running the neural network on the data.


After the script has started running, it will first require
the user to select an experiment and a run corresponding to a 
training step run previously. 
The user will then be required to select an experiment and a run
corresponding to a data step previously run.

The inference step should then start.

### Jupyter Notebooks
The [examples/jupyter-notebooks](examples/jupyter-notebooks/) folder stores
notebooks developed during early project development, some of which were used to
generate figures used in the 2021 paper. See the readme in the folder for
details.

### Dev Branch
The `dev` branch contains ongoing refactoring work which removes the necessity to use
mlflow. Currently, the code has been refactored into a clearer structure and easier
use through a command line interface for the data step, and the training step
is in progress. Further work is needed for the inference step, and to adapt the Jupyter
notebooks.

## Data on Huggingface
There is GZ21 Ocean Momentum data available on [Huggingface](https://huggingface.co/):
- [the output of the data step](https://huggingface.co/datasets/M2LInES/gfdl-cmip26-gz21-ocean-forcing)
and
- [the trained model](https://huggingface.co/M2LInES/gz21-ocean-momentum) 

## Contributing
We are not currently accepting contributions outside of the M2LInES and ICCS
projects until we have reached a code release milestone.

## License
This repository is provided under the MIT license. See [`LICENSE`](LICENSE) for
license text and copyright information.

## Citing this software
See `CITATION.cff` for citation metadata for this software. *(For further
details on usage, see https://citation-file-format.github.io/ .)*
