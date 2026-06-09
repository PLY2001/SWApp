import torch
import torch.nn as nn
import torch.nn.functional as F
from model import resnet34  # We'll use the original ResNet as the backbone

class PositionalEncoding(nn.Module):
    """Adds positional information to the input sequence."""
    def __init__(self, d_model, max_len=10):
        super(PositionalEncoding, self).__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-torch.log(torch.tensor(10000.0)) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)
        self.register_buffer('pe', pe)

    def forward(self, x):
        # x shape: [seq_len, batch_size, d_model]
        x = x + self.pe[:, :x.size(1), :].transpose(0, 1)
        return x

class TransformerFusionModel(nn.Module):
    """
    A model that uses a ResNet backbone to extract features from multiple views,
    then uses a Transformer Encoder to fuse these features, and finally pools them.
    Can optionally include a classification head.
    """
    def __init__(self, num_classes=None, d_model=128, nhead=4, num_encoder_layers=2, dim_feedforward=512, dropout=0.5):
        super(TransformerFusionModel, self).__init__()
        
        self.backbone = resnet34(include_top=True)
        self.pos_encoder = PositionalEncoding(d_model)
        encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead, dim_feedforward=dim_feedforward, dropout=dropout, batch_first=True)
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_encoder_layers)
        
        self.dropout = nn.Dropout(p=dropout)
        
        self.use_classifier = num_classes is not None
        if self.use_classifier:
            self.classifier_head = nn.Linear(d_model, num_classes)

    def forward(self, x):
        bs, num_views, C, H, W = x.shape
        x = x.view(-1, C, H, W)
        view_features = self.backbone(x)
        seq_features = view_features.view(bs, num_views, -1)
        
        # The positional encoding in the original code had a bug with batch handling.
        # Correct application for batch_first=True.
        seq_features = seq_features + self.pos_encoder.pe[:, :num_views, :]
        
        fused_features_seq = self.transformer_encoder(seq_features)
        pooled_features = torch.mean(fused_features_seq, dim=1)
        
        # Apply dropout for regularization
        pooled_features = self.dropout(pooled_features)
        
        if self.use_classifier:
            logits = self.classifier_head(pooled_features)
            return pooled_features, logits
        else:
            # When used as a feature extractor (like for net_B), normalize the final embedding
            return F.normalize(pooled_features, p=2, dim=1)

class SimpleResNet(nn.Module):
    """A simple ResNet wrapper for net_B, which doesn't need the fusion part."""
    def __init__(self):
        super(SimpleResNet, self).__init__()
        self.backbone = resnet34(include_top=True)

    def forward(self, x):
        # x shape: [batch_size * num_views, C, H, W]
        return self.backbone(x)
