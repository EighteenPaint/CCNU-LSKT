import torch.nn as nn
from torch.nn.utils import weight_norm


class Chomp1d(nn.Module):

    def __init__(self, chomp_size):
        # chomp_size = padding
        super(Chomp1d, self).__init__()
        self.chomp_size = chomp_size

    def forward(self, x):
        return x[:, :, :-self.chomp_size].contiguous()


class TemporalBlock(nn.Module):
    def __init__(self, n_inputs, n_outputs, kernel_size, stride, dilation, padding, dropout=0.2):
        super(TemporalBlock, self).__init__()
        self.kernel_size = kernel_size
        self.conv1 = weight_norm(nn.Conv1d(n_inputs, n_outputs, kernel_size,
                                           stride=stride, padding=padding, dilation=dilation))
        self.chomp1 = Chomp1d(padding)
        self.relu1 = nn.ReLU()
        self.dropout1 = nn.Dropout(dropout)

        self.conv2 = weight_norm(nn.Conv1d(n_outputs, n_outputs, kernel_size,
                                           stride=stride, padding=padding, dilation=dilation))
        self.chomp2 = Chomp1d(padding)
        self.relu2 = nn.ReLU()
        self.dropout2 = nn.Dropout(dropout)

        self.net = nn.Sequential(self.conv1, self.chomp1, self.relu1, self.dropout1,
                                 self.conv2, self.chomp2, self.relu2, self.dropout2)
        self.downsample = nn.Conv1d(n_inputs, n_outputs, 1) if n_inputs != n_outputs else None
        self.relu = nn.ReLU()
        self.init_weights()

    def init_weights(self):
        self.conv1.weight.data.normal_(0, 0.01)
        self.conv2.weight.data.normal_(0, 0.01)
        if self.downsample is not None:
            self.downsample.weight.data.normal_(0, 0.01)

    def forward(self, x):
        if self.kernel_size != 1:
            out = self.net(x)
            res = x if self.downsample is None else self.downsample(x)
            return self.relu(out + res)
        else:
            res = x if self.downsample is None else self.downsample(x)
            return res


class TemporalConvNetV4(nn.Module):
    """
    Thanks to:
	author = Shaojie Bai and J. Zico Kolter and Vladlen Koltun,
	title = An Empirical Evaluation of Generic Convolutional and Recurrent Networks for Sequence Modeling,
	year = 2018
    """

    def __init__(self, num_inputs, num_channels, kernel_size=2, dropout=0.2, model_type='lskt'):
        super(TemporalConvNetV4, self).__init__()
        self.layers = []
        self.init = kernel_size
        num_levels = len(num_channels)
        for i in range(num_levels):
            dilation_size = 1
            if model_type != 'lsktsk':
                kernel_size = self.init * 2 ** i
            else:
                kernel_size = self.init
            in_channels = num_inputs if i == 0 else num_channels[i - 1]
            out_channels = num_channels[i]
            self.layers += [TemporalBlock(in_channels, out_channels, kernel_size, stride=1, dilation=dilation_size,
                                          padding=(kernel_size - 1) * dilation_size, dropout=dropout)]

        self.network = nn.Sequential(*self.layers)

    def forward(self, x):
        x = x.permute(0, 2, 1)
        outs = []
        for layer in self.layers:
            x = layer(x)
            outs.append(x.permute(0, 2, 1))
        return outs
