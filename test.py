import torch.nn as nn
import torch

rnn = nn.LSTM(10, 20, 2)
input = torch.randn(5, 3, 10)
# h0 = torch.randn(2, 3, 20)
# c0 = torch.randn(2, 3, 20)
output, (hn, cn) = rnn(input)
print(output.shape)