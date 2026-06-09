import torch
import torch.nn as nn
import torch.nn.functional as F
import math
from model import resnet34
from model_arcface import ArcFace # We can reuse the ArcFace layer

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
        # x shape: [batch_size, seq_len, d_model]
        x = x + self.pe[:, :x.size(1), :]
        return x

class UltimateFusionModel(nn.Module):
    """
    The ultimate model combining ResNet, Transformer, and ArcFace.
    """
    def __init__(self, num_classes, d_model=128, nhead=4, num_encoder_layers=2, dim_feedforward=512, dropout=0.5):
        super(UltimateFusionModel, self).__init__()
        
        # 1. Backbone Feature Extractor
        self.backbone = resnet34(include_top=True)
        
        # 2. Positional Encoding
        self.pos_encoder = PositionalEncoding(d_model)
        
        # 3. Transformer Encoder
        encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead, dim_feedforward=dim_feedforward, dropout=dropout, batch_first=True)
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_encoder_layers)
        
        # 4. Dropout Layer for regularization
        self.dropout = nn.Dropout(p=dropout)

        # 5. ArcFace Head
        self.arcface_head = ArcFace(in_features=d_model, out_features=num_classes)

    def forward(self, x, label=None):
        # x shape: [batch_size, num_views, C, H, W]
        bs, num_views, C, H, W = x.shape
        
        # --- Step 1: Feature Extraction ---
        x = x.view(-1, C, H, W)
        view_features = self.backbone(x)
        seq_features = view_features.view(bs, num_views, -1)
        
        # --- Step 2: Transformer Fusion ---
        seq_features = self.pos_encoder(seq_features)
        fused_features_seq = self.transformer_encoder(seq_features)
        
        # --- Step 3: Pooling ---
        pooled_features = torch.mean(fused_features_seq, dim=1) # -> [bs, 128]

        # --- Step 4: Dropout ---
        pooled_features = self.dropout(pooled_features)
        
        # --- Step 5: ArcFace Head ---
        # If label is not provided, return the feature embedding directly.
        if label is None:
            return pooled_features
            
        # The ArcFace head requires a label for training.
        logits = self.arcface_head(pooled_features, label)
            
        return logits
