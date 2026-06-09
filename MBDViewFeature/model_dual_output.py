import torch
import torch.nn as nn
import torch.nn.functional as F
from model import ResNet, BasicBlock # Import the base classes

class ResNetDualOutput(ResNet):
    """
    This ResNet version provides two outputs:
    1. A 128-dim embedding vector for metric learning (like the original).
    2. A num_classes-dim logit vector for classification learning.
    """
    def __init__(self, block, blocks_num, num_classes=1000, include_top=True, groups=1, width_per_group=64):
        # Call the parent's __init__
        super(ResNetDualOutput, self).__init__(block, blocks_num, num_classes, include_top, groups, width_per_group)
        
        # The original head for metric learning is already defined in the parent class.
        # We just need to add a new, separate head for classification.
        # This head takes the features right after the pooling layer.
        self.classifier_head = nn.Linear(512 * block.expansion, num_classes)

        # Initialize the weights for the new classifier head
        for m in self.classifier_head.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')

    def forward(self, x):
        # Backbone feature extraction (same as parent)
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)

        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)

        # Branching point
        if self.include_top:
            pooled_features = self.avgpool(x)
            flat_features = torch.flatten(pooled_features, 1)

            # --- Branch 1: Metric Learning Embedding ---
            embedding = self.Dense1(flat_features)
            embedding = self.BN(embedding)
            embedding = self.ReLU(embedding)
            embedding = self.Dense2(embedding)
            embedding = F.normalize(embedding, p=2, dim=1)

            # --- Branch 2: Classification Logits ---
            logits = self.classifier_head(flat_features)
            
            return embedding, logits
        else:
            # If not include_top, just return the feature map
            return x

def resnet34_dual_output(num_classes=1000, include_top=True):
    return ResNetDualOutput(BasicBlock, [3, 4, 6, 3], num_classes=num_classes, include_top=include_top)
