import torch
import torch.nn as nn
import torch.nn.functional as F
import math
from model import resnet34

class ArcFace(nn.Module):
    """
    Implementation of ArcFace loss.
    """
    def __init__(self, in_features, out_features, s=30.0, m=0.50):
        super(ArcFace, self).__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.s = s
        self.m = m
        self.weight = nn.Parameter(torch.FloatTensor(out_features, in_features))
        nn.init.xavier_uniform_(self.weight)

        self.cos_m = math.cos(m)
        self.sin_m = math.sin(m)
        self.th = math.cos(math.pi - m)
        self.mm = math.sin(math.pi - m) * m

    def forward(self, embedding, label):
        # The embedding is already L2-normalized
        cosine = F.linear(embedding, F.normalize(self.weight))
        sine = torch.sqrt((1.0 - torch.pow(cosine, 2)).clamp(0, 1))
        
        # cos(theta + m)
        phi = cosine * self.cos_m - sine * self.sin_m
        # Ensure the phi is monotonically decreasing
        phi = torch.where(cosine > self.th, phi, cosine - self.mm)
        
        # Convert label to one-hot
        one_hot = torch.zeros(cosine.size(), device=embedding.device)
        one_hot.scatter_(1, label.view(-1, 1).long(), 1)
        
        # Final output logits
        output = (one_hot * phi) + ((1.0 - one_hot) * cosine)
        output *= self.s
        
        return output

class ResNetWithArcFace(nn.Module):
    def __init__(self, num_classes):
        super(ResNetWithArcFace, self).__init__()
        # The original resnet34 model already outputs a 128-dim normalized embedding
        self.backbone = resnet34(include_top=True) 
        self.arcface_head = ArcFace(in_features=128, out_features=num_classes)

    def forward(self, x, label=None):
        embedding = self.backbone(x)
        # During training, we pass the label to get the logits for CrossEntropyLoss
        if self.training and label is not None:
            return self.arcface_head(embedding, label)
        # During inference, we just want the embedding
        return embedding
