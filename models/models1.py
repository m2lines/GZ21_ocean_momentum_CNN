# -*- coding: utf-8 -*-
"""
Module of PyTorch ML models.

TODOs:
------
-Try some standard image classification network whose last layer you'll change
- change the color map of plots
- study different values of time indices
-  Log the data run that is used to create the dataset. Log any
   transformation applied to the data. Later we might want to allow from
   stream datasets.

BUGS
----
-when we run less than 100 epochs the figures from previous runs are
logged.
"""
import torch
from torch import nn
from torch.nn.modules.utils import _pair
from torch.nn.functional import pad

import numpy as np
from .base import DetectOutputSizeMixin


# TODO I can't see where this is used anywhere? Remove?  # AB
class Identity(nn.Module):
    """
    Definition of an Identity net that returns the input tensor unmodified.

    Methods
    -------
    forward
    """

    def __init__(self):
        super().__init__()

    def forward(self, input: torch.Tensor):
        return input


# TODO I can't see where this is used anywhere? Remove?  # AB
class ScaledModule(nn.Module):
    """
    Definition of a scalar net that returns the input tensor multiplied by a constant.

    Attributes
    ----------
    factor : float
        factor to scale input tensor by
    module : nn.Module
        description?  # AB

    Methods
    -------
    forward
    """

    def __init__(self, factor: float, module: nn.Module):
        super().__init__()
        self.factor = factor
        self.module = module

    def forward(self, input: torch.Tensor):
        return self.factor * self.module.forward(input)


# THIS IS THE MODEL USED IN THE FINAL PAPER
class FullyCNN(DetectOutputSizeMixin, nn.Sequential):
    """
    Fully Convolutional Neural Net used for modelling ocean momentum.

    Attributes
    ----------
    n_in_channels : int
        number of input chanels to model
    n_out_channels : int
        number of output channels from model
    padding : type?  # AB
        description?  # AB
    batch_norm : bool
        whether to normalise batches

    Methods
    -------
    final_transformation
    forward
    """

    def __init__(
        self,
        n_in_channels: int = 2,
        n_out_channels: int = 4,
        padding=None,
        batch_norm=False,
    ):
        if padding is None:
            padding_5 = 0
            padding_3 = 0
        elif padding == "same":
            padding_5 = 2
            padding_3 = 1
        else:
            raise ValueError("Unknow value for padding parameter.")

        self.n_in_channels = n_in_channels
        self.batch_norm = batch_norm
        conv1 = torch.nn.Conv2d(n_in_channels, 128, 5, padding=padding_5)
        block1 = self._make_subblock(conv1)
        conv2 = torch.nn.Conv2d(128, 64, 5, padding=padding_5)
        block2 = self._make_subblock(conv2)
        conv3 = torch.nn.Conv2d(64, 32, 3, padding=padding_3)
        block3 = self._make_subblock(conv3)
        conv4 = torch.nn.Conv2d(32, 32, 3, padding=padding_3)
        block4 = self._make_subblock(conv4)
        conv5 = torch.nn.Conv2d(32, 32, 3, padding=padding_3)
        block5 = self._make_subblock(conv5)
        conv6 = torch.nn.Conv2d(32, 32, 3, padding=padding_3)
        block6 = self._make_subblock(conv6)
        conv7 = torch.nn.Conv2d(32, 32, 3, padding=padding_3)
        block7 = self._make_subblock(conv7)
        conv8 = torch.nn.Conv2d(32, n_out_channels, 3, padding=padding_3)

        nn.Sequential.__init__(
            self, *block1, *block2, *block3, *block4, *block5, *block6, *block7, conv8
        )

    @property
    def final_transformation(self):
        """
        Return the final transformation of the model.

        Returns
        -------
        self._final_transformation : type?  # AB
            description?  # AB
        """
        return self._final_transformation

    @final_transformation.setter
    def final_transformation(self, transformation):
        """
        Setter method for the final_transformation attribute.

        Parameters
        ----------
        transformation : type?  # AB
            description?  # AB
        """
        self._final_transformation = transformation

    def forward(self, x):
        """
        Forward method for the model.

        Parameters
        ----------
        x : type?  # AB
            description?  # AB

        Returns
        -------
        self.final_transformation(x) : type?  # AB
            input with final_transformation operation performed
        """
        x = super().forward(x)
        return self.final_transformation(x)

    def _make_subblock(self, conv):
        """
        Function description?  # AB

        Parameters
        ----------
        conv : type?  # AB
            description?  # AB

        Returns
        -------
        subbloc : type?  # AB
            description?  # AB
        """
        subbloc = [conv, nn.ReLU()]
        if self.batch_norm:
            subbloc.append(nn.BatchNorm2d(conv.out_channels))
        return subbloc


# THIS IS NOT USED IN FINAL PAPER
class LocallyConnected2d(nn.Module):
    """
    Locally Connected ML model to do what?  # AB

    Attributes
    ----------
    input_h : type?  # AB
        description?  # AB
    input_w : type?  # AB
        description?  # AB
    in_channels : type?  # AB
        description?  # AB
    out_channels : type?  # AB
        description?  # AB
    kernel_size : type?  # AB
        description?  # AB
    padding : type?  # AB
        description?  # AB
    stride : type?  # AB
        description?  # AB
    bias : bool
        description?  # AB

    Methods
    -------
    forward
    calculate_output_size

    References
    ----------
    Based on the code provided on the following link:
    https://discuss.pytorch.org/t/locally-connected-layers/26979
    """

    def __init__(
        self,
        input_h,
        input_w,
        in_channels,
        out_channels,
        kernel_size,
        padding,
        stride,
        bias=False,
    ):
        super(LocallyConnected2d, self).__init__()
        self.kernel_size = _pair(kernel_size)
        self.stride = _pair(stride)
        self.padding = _pair(padding)

        def padding_extract(padding):
            new = []
            for el in padding:
                new.append(int(el))
                new.append(int(el))
            return tuple(new)

        self.padding_long = padding_extract(self.padding)
        output_size = self.calculate_output_size(
            input_h, input_w, self.kernel_size, self.padding, self.stride
        )
        self.weight = nn.Parameter(
            torch.randn(
                1,
                out_channels,
                in_channels,
                output_size[0],
                output_size[1],
                self.kernel_size[0] * self.kernel_size[1],
            )
        )
        # Scaling of the weight parameters according to number of inputs
        self.weight.data = self.weight / np.sqrt(
            in_channels * self.kernel_size[0] * self.kernel_size[1]
        )
        if bias:
            self.bias = nn.Parameter(
                torch.randn(1, out_channels, output_size[0], output_size[1])
            )
        else:
            self.register_parameter("bias", None)

    def forward(self, x):
        # I think the following line is redundant and can be removed?  # AB
        _, c, h, w = x.size()
        kh, kw = self.kernel_size
        dh, dw = self.stride
        x = pad(x, self.padding_long)
        x = x.unfold(2, kh, dh).unfold(3, kw, dw)
        x = x.contiguous().view(*x.size()[:-2], -1)
        # Sum in in_channel and kernel_size dims
        out = (x.unsqueeze(1) * self.weight).sum([2, -1])
        if self.bias is not None:
            out += self.bias
        return out

    @staticmethod
    def calculate_output_size(
        input_h: int,
        input_w: int,
        kernel_size: int,
        padding: int = None,
        stride: int = 1,
    ):
        # TODO add the stride bit. Right now it assumes 1.
        output_h = int(input_h - (kernel_size[0] - 1) / 2 + padding[0])
        output_w = int(input_w - (kernel_size[1] - 1) / 2 + padding[1])
        return output_h, output_w


# THIS IS NOT USED IN FINAL PAPER
class Divergence2d(nn.Module):
    """
    Fixed Layer model to generate divergence of input.

    Defines a fixed layer that produces the divergence of the input field.
    Note that the padding is set to 2, hence the spatial dim of the output
    is larger than that of the input.

    Attributes
    ----------
    n_input_channels : int
        description?  # AB
    n_output_channels : int
        description?  # AB

    Methods
    -------
    forward
    """

    def __init__(self, n_input_channels: int, n_output_channels: int):
        super().__init__()

        device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        self.n_input_channels = n_input_channels
        self.n_output_channels = n_output_channels
        factor = n_input_channels // n_output_channels
        lambda_ = 1 / (factor * 2)
        shape = (1, n_input_channels // 4, 1, 1)

        self.lambdas1x = nn.Parameter(torch.ones(shape)) * lambda_
        self.lambdas2x = nn.Parameter(torch.ones(shape)) * lambda_
        self.lambdas1y = nn.Parameter(torch.ones(shape)) * lambda_
        self.lambdas2y = nn.Parameter(torch.ones(shape)) * lambda_
        self.lambdas1x = self.lambdas1x.to(device=device)
        self.lambdas2x = self.lambdas2x.to(device=device)
        self.lambdas1y = self.lambdas1y.to(device=device)
        self.lambdas2y = self.lambdas2y.to(device=device)

        x_derivative = torch.tensor([[[[0, 0, 0], [-1, 0, 1], [0, 0, 0]]]])
        x_derivative = x_derivative.expand(1, n_input_channels // 4, -1, -1)

        y_derivative = torch.tensor([[0, 1, 0], [0, 0, 0], [0, -1, 0]])
        y_derivative = y_derivative.expand(1, n_input_channels // 4, -1, -1)

        x_derivative = x_derivative.to(dtype=torch.float32, device=device)
        y_derivative = y_derivative.to(dtype=torch.float32, device=device)

        self.x_derivative = x_derivative
        self.y_derivative = y_derivative

    def forward(self, input: torch.Tensor):
        _, c, _, _ = input.size()
        # TODO: The following 3 lines are unused? Remove?  # AB
        y_derivative1 = self.y_derivative * self.lambdas1y
        x_derivative2 = self.x_derivative * self.lambdas2x
        y_derivative2 = self.y_derivative * self.lambdas2y

        output11 = nn.functional.conv2d(
            input[:, : c // 4, :, :], self.x_derivative * self.lambdas1x, padding=2
        )
        output12 = nn.functional.conv2d(
            input[:, c // 4 : c // 2, :, :], self.y_derivative, padding=2
        )
        output1 = output11 + output12
        output21 = nn.functional.conv2d(
            input[:, c // 2 : c // 2 + c // 4, :, :], self.x_derivative, padding=2
        )
        output22 = nn.functional.conv2d(
            input[:, c // 2 + c // 4 :, :, :], self.y_derivative, padding=2
        )
        output2 = output21 + output22
        res = torch.stack((output1, output2), dim=1)
        res = res[:, :, 0, :, :]
        return res


# THIS IS NOT USED IN FINAL PAPER
class MixedModel(nn.Module):
    """
    Fixed Layer model to generate divergence of input.

    Defines a fixed layer that produces the divergence of the input field.
    Note that the padding is set to 2, hence the spatial dim of the output
    is larger than that of the input.

    Attributes
    ----------
    *args :  # AB
        description?  # AB
    **kwargs :  # AB
        description?  # AB

    Methods
    -------
    forward
    crop_like

    """

    net_cls = FullyCNN

    def __init__(self, *args, **kwargs):
        if "n_in_channels" in kwargs:
            kwargs["n_in_channels"] -= 2
        args = list(args)
        if len(args) > 0:
            args[0] -= 2
        args = tuple(args)
        self.net = self.net_cls(*args, **kwargs)
        self.n_in_channels = self.net.n_in_channels + 2

    def forward(self, x):
        uv = x[:, :2, ...]
        equations = x[:, 2:, ...]
        out = self.net.forward(uv)
        equations = self.crop_like(equations, out)
        out[:, 0, ...] = (out[:, 0, ...]) * equations[:, 0, ...]
        out[:, 1, ...] = (out[:, 1, ...]) * equations[:, 1, ...]
        return out

    def crop_like(self, x, y):
        shape_x = x.shape
        shape_y = y.shape
        m = (shape_x[-2] - shape_y[-2]) // 2
        n = (shape_x[-1] - shape_y[-1]) // 2
        return x[..., m : shape_x[-2] - m, n : shape_x[-1] - n]

    def __getattr__(self, attr_name):
        return getattr(self.net, attr_name)

    def __setattr__(self, key, value):
        if key in ("net", "n_in_channels"):
            self.__dict__[key] = value
        else:
            setattr(self.net, key, value)

    def __repr__(self):
        return self.net.__repr__()


if __name__ == "__main__":
    net = FullyCNN()
    net._final_transformation = lambda x: x
    input_ = torch.randint(0, 10, (17, 2, 35, 30)).to(dtype=torch.float)
    input_[0, 0, 0, 0] = np.nan
    output = net(input_)