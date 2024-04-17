import os
import json
import sys

import matplotlib
import torch
from PIL import Image
from torchvision import transforms
import matplotlib.pyplot as plt
import  torchvision
from model import resnet34

from tqdm import tqdm
import torch.nn.functional as F

import numpy as np
import re

a = torch.tensor([[1, 2], [3, 4]])
b = torch.tensor([[5, 6], [7, 8]])

result = torch.mm(a, b.t())
print(result)