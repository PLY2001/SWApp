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
import math
modelc = 5
train_steps = int(math.factorial(modelc)/(2*math.factorial(modelc-2)))
imagesIndex = []
for i in range(train_steps):
    j = i
    while j + 1<modelc:
        imagesIndex.append(i)
        imagesIndex.append(j + 1)
        j+=1
print(imagesIndex)