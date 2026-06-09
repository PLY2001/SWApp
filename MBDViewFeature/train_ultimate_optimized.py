import os
import sys
import numpy as np
from tqdm import tqdm
from PIL import Image
from collections import defaultdict
import random

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, datasets
import matplotlib.pyplot as plt

from model_ultimate import UltimateFusionModel
from model_transformer_fusion import TransformerFusionModel as TransformerEncoderModel # For net_B

def default_list_factory():
    """Helper function for defaultdict to be pickle-able."""
    return [None] * 24

class UltimateTripletDataset(Dataset):
    """
    Dataset for the ultimate training scheme, modified to return triplets.
    For each anchor, it finds a positive (same class, different model) and a negative (different class).
    """
    def __init__(self, root_dir, transform=None):
        self.root_dir = root_dir
        self.transform = transform
        self.image_folder = datasets.ImageFolder(root_dir)
        self.class_names = self.image_folder.classes
        
        self.model_to_images = defaultdict(default_list_factory)
        self.model_to_label = {}
        for img_path, label_idx in self.image_folder.imgs:
            model_id_str = "_".join(os.path.basename(img_path).split('_')[:-3])
            class_name = self.class_names[label_idx]
            full_model_id = f"{class_name}/{model_id_str}"
            self.model_to_label[full_model_id] = label_idx
            try:
                view_dir = int(os.path.basename(img_path).split('_')[-3])
                view_type = int(os.path.basename(img_path).split('_')[-2])
                cull_mode = int(os.path.basename(img_path).split('_')[-1].split('.')[0])
                view_index = view_dir * 4 + view_type * 2 + cull_mode
                self.model_to_images[full_model_id][view_index] = img_path
            except (ValueError, IndexError):
                continue

        self.models = list(self.model_to_images.keys())
        self.labels_set = set(self.model_to_label.values())
        self.label_to_models = {label: [m for m in self.models if self.model_to_label[m] == label]
                                for label in self.labels_set}

        self.indices_A = [i * 4 for i in range(6)]
        self.indices_B = [i * 4 + 2 for i in range(6)]

    def __getitem__(self, index):
        anchor_model_id = self.models[index]
        anchor_label = self.model_to_label[anchor_model_id]

        # Find a positive model
        positive_list = self.label_to_models[anchor_label]
        if len(positive_list) > 1:
            positive_model_id = random.choice([m for m in positive_list if m != anchor_model_id])
        else:
            positive_model_id = anchor_model_id # Fallback to anchor if no other model in class

        # Find a negative model
        negative_label = random.choice(list(self.labels_set - {anchor_label}))
        negative_model_id = random.choice(self.label_to_models[negative_label])

        def get_all_views_for_type(model_name, indices):
            img_paths = self.model_to_images[model_name]
            paths_to_load = [img_paths[i] for i in indices]
            views = []
            for p in paths_to_load:
                img = Image.open(p).convert('RGB') if p and os.path.exists(p) else Image.new('RGB', (224, 224), 'black')
                if self.transform:
                    img = self.transform(img)
                views.append(img)
            return torch.stack(views)

        anchor_views_A = get_all_views_for_type(anchor_model_id, self.indices_A)
        anchor_views_B = get_all_views_for_type(anchor_model_id, self.indices_B)
        
        positive_views_A = get_all_views_for_type(positive_model_id, self.indices_A)
        positive_views_B = get_all_views_for_type(positive_model_id, self.indices_B)

        negative_views_A = get_all_views_for_type(negative_model_id, self.indices_A)
        negative_views_B = get_all_views_for_type(negative_model_id, self.indices_B)
            
        positive_label = anchor_label # Positive is same class as anchor
        return (anchor_views_A, positive_views_A, negative_views_A, 
                anchor_views_B, positive_views_B, negative_views_B,
                torch.tensor([anchor_label, positive_label, negative_label]))

    def __len__(self):
        return len(self.models)

def main():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"Using {device} device.")

    # --- TASK-ALIGNED HYPERPARAMETERS ---
    # Loss weights
    gamma_classification = 0.5 # Weight for the ArcFace classification loss on net_A
    lambda_contrastive = 0.2   # Weight for the fine-grained contrastive loss on net_B
    margin_triplet = 1.0       # Margin for the main triplet loss on net_A
    
    # Learning rates
    lr_backbone = 1e-5
    lr_head = 1e-4
    
    # Training settings
    weight_decay = 1e-4
    epochs = 100
    # AMP allows us to potentially double the physical batch size without increasing memory usage
    physical_batch_size = 8
    gradient_accumulation_steps = 2 # Adjust accumulation steps to keep effective batch size the same
    effective_batch_size = physical_batch_size * gradient_accumulation_steps
    print(f"Using Automatic Mixed Precision (AMP).")
    print(f"Physical Batch Size: {physical_batch_size}, Grad Accumulation Steps: {gradient_accumulation_steps}, Effective Batch Size: {effective_batch_size}")

    # --- Data Loading ---
    data_transform = {
        "train": transforms.Compose([
            transforms.Resize(224),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(15),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ]),
        "val": transforms.Compose([
            transforms.Resize(224),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
    }
    data_root = os.getcwd()
    train_image_path = os.path.join(data_root, "MBDViewDataset_noMBD/train")
    val_image_path = os.path.join(data_root, "MBDViewDataset_noMBD/validation")

    # Use the new Triplet Dataset
    train_dataset = UltimateTripletDataset(root_dir=train_image_path, transform=data_transform["train"])
    val_dataset = UltimateTripletDataset(root_dir=val_image_path, transform=data_transform["val"])
    
    num_classes = len(train_dataset.class_names)
    print(f"Dataset has {num_classes} classes.")

    nw = min([os.cpu_count(), physical_batch_size if physical_batch_size > 1 else 0, 8])
    train_loader = DataLoader(train_dataset, batch_size=physical_batch_size, shuffle=True, num_workers=nw)
    val_loader = DataLoader(val_dataset, batch_size=physical_batch_size, shuffle=False, num_workers=nw)

    # --- Models, Losses, Optimizer ---
    net_A = UltimateFusionModel(num_classes=num_classes).to(device)
    net_B = TransformerEncoderModel(num_classes=None).to(device)

    model_weight_path = "./resnet34-pre.pth"
    if os.path.exists(model_weight_path):
        net_A.backbone.load_state_dict(torch.load(model_weight_path, map_location='cpu'), strict=False)
        net_B.backbone.load_state_dict(torch.load(model_weight_path, map_location='cpu'), strict=False)

    # --- TASK-ALIGNED LOSS FUNCTIONS ---
    loss_arcface_func = nn.CrossEntropyLoss(label_smoothing=0.1)
    loss_triplet_func = nn.TripletMarginLoss(margin=margin_triplet, p=2)
    cosine_sim_func = nn.CosineSimilarity(dim=1)

    # --- Optimizer with Differential Learning Rates ---
    # Group parameters to avoid overlap and assign correct learning rates
    param_groups = [
        # net_A's backbone is shared, so we put it here
        {'params': net_A.backbone.parameters(), 'lr': lr_backbone},
        # net_A's head components
        {'params': net_A.pos_encoder.parameters(), 'lr': lr_head},
        {'params': net_A.transformer_encoder.parameters(), 'lr': lr_head},
        {'params': net_A.arcface_head.parameters(), 'lr': lr_head},
        # net_B uses the same backbone instance, so we only need to add its unique parts
        {'params': net_B.pos_encoder.parameters(), 'lr': lr_head},
        {'params': net_B.transformer_encoder.parameters(), 'lr': lr_head},
    ]
    # To avoid adding backbone parameters twice, we can link net_B's backbone to net_A's
    net_B.backbone = net_A.backbone
    optimizer = optim.AdamW(param_groups, weight_decay=weight_decay) # Use AdamW for better weight decay handling
    
    # OPTIMIZED SCHEDULER: Use CosineAnnealingLR
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-7)

    # AMP: Initialize Gradient Scaler
    scaler = torch.cuda.amp.GradScaler()

    best_val_loss = float('inf')
    save_path_A = './MBDNet34_ultimate_optimized_A.pth'
    save_path_B = './MBDNet34_ultimate_optimized_B.pth'

    train_loss_list, val_loss_list = [], []
    epoch_list = []

    for epoch in range(epochs):
        net_A.train()
        net_B.train()

        run_loss, run_loss_A_triplet, run_loss_A_class, run_loss_B_contrast = 0.0, 0.0, 0.0, 0.0
        
        train_bar = tqdm(train_loader, file=sys.stdout, desc=f"Train E[{epoch+1}]")
        for i, (anchor_A, pos_A, neg_A, anchor_B, pos_B, neg_B, labels) in enumerate(train_bar):
            # Move data to device
            anchor_A, pos_A, neg_A = anchor_A.to(device), pos_A.to(device), neg_A.to(device)
            anchor_B, pos_B = anchor_B.to(device), pos_B.to(device)
            labels = labels.to(device)
            anchor_lbl, pos_lbl, neg_lbl = labels[:, 0], labels[:, 1], labels[:, 2]

            # AMP: Enable autocasting for forward pass
            with torch.cuda.amp.autocast():
                # --- OPTIMIZED BATCHED FORWARD PASS ---
                # 1. Process net_A
                all_A_views = torch.cat([anchor_A, pos_A, neg_A], dim=0)
                all_A_labels = torch.cat([anchor_lbl, pos_lbl, neg_lbl], dim=0)
                all_A_embs, all_A_logits = net_A(all_A_views, all_A_labels)
                emb_A_anchor, emb_A_pos, emb_A_neg = torch.chunk(all_A_embs, 3, dim=0)

                # --- Loss for net_A (Coarse-grained Metric Learning) ---
                loss_A_triplet = loss_triplet_func(emb_A_anchor, emb_A_pos, emb_A_neg)
                loss_A_class = loss_arcface_func(all_A_logits, all_A_labels)
                
                # 2. Process net_B
                all_B_views = torch.cat([anchor_B, pos_B], dim=0)
                all_B_embs = net_B(all_B_views)
                emb_B_anchor, emb_B_pos = torch.chunk(all_B_embs, 2, dim=0)

                # --- Loss for net_B (Fine-grained Distinguishability) ---
                loss_B_contrastive = cosine_sim_func(emb_B_anchor, emb_B_pos).mean()

                # --- Total Loss ---
                total_loss = loss_A_triplet + gamma_classification * loss_A_class + lambda_contrastive * loss_B_contrastive
            
            # GRADIENT ACCUMULATION & SCALING
            total_loss = total_loss / gradient_accumulation_steps
            scaler.scale(total_loss).backward()

            if (i + 1) % gradient_accumulation_steps == 0:
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad()

            # Logging
            run_loss += total_loss.item() * gradient_accumulation_steps
            run_loss_A_triplet += loss_A_triplet.item()
            run_loss_A_class += loss_A_class.item()
            run_loss_B_contrast += loss_B_contrastive.item()
            train_bar.set_postfix(L=f"{total_loss.item() * gradient_accumulation_steps:.3f}", 
                                  T_A=f"{loss_A_triplet.item():.3f}", 
                                  C_A=f"{loss_A_class.item():.3f}", 
                                  C_B=f"{loss_B_contrastive.item():.3f}")

        scheduler.step()
        
        train_loss = run_loss / len(train_loader)
        print(f"[Epoch {epoch+1}] Train Loss: {train_loss:.4f} (A_Triplet: {run_loss_A_triplet/len(train_loader):.4f}, A_Class: {run_loss_A_class/len(train_loader):.4f}, B_Contrast: {run_loss_B_contrast/len(train_loader):.4f})")

        # --- Validation ---
        net_A.eval()
        net_B.eval()
        val_run_loss = 0.0
        with torch.no_grad():
            val_bar = tqdm(val_loader, file=sys.stdout, desc=f"Val E[{epoch+1}]")
            for anchor_A, pos_A, neg_A, anchor_B, pos_B, neg_B, labels in val_bar:
                # Move data to device
                anchor_A, pos_A, neg_A = anchor_A.to(device), pos_A.to(device), neg_A.to(device)
                anchor_B, pos_B = anchor_B.to(device), pos_B.to(device)
                labels = labels.to(device)
                anchor_lbl, pos_lbl, neg_lbl = labels[:, 0], labels[:, 1], labels[:, 2]

                # Enable autocast for validation
                with torch.cuda.amp.autocast():
                    # --- Batched forward pass for validation ---
                    all_A_views = torch.cat([anchor_A, pos_A, neg_A], dim=0)
                    all_A_labels = torch.cat([anchor_lbl, pos_lbl, neg_lbl], dim=0)
                    all_A_embs, all_A_logits = net_A(all_A_views, all_A_labels)
                    emb_A_anchor, emb_A_pos, emb_A_neg = torch.chunk(all_A_embs, 3, dim=0)

                    loss_A_triplet = loss_triplet_func(emb_A_anchor, emb_A_pos, emb_A_neg)
                    loss_A_class = loss_arcface_func(all_A_logits, all_A_labels)

                    # --- net_B validation loss ---
                    all_B_views = torch.cat([anchor_B, pos_B], dim=0)
                    all_B_embs = net_B(all_B_views)
                    emb_B_anchor, emb_B_pos = torch.chunk(all_B_embs, 2, dim=0)
                    loss_B_contrastive = cosine_sim_func(emb_B_anchor, emb_B_pos).mean()

                    total_loss = loss_A_triplet + gamma_classification * loss_A_class + lambda_contrastive * loss_B_contrastive
                val_run_loss += total_loss.item()
        
        val_loss = val_run_loss / len(val_loader)
        print(f"[Epoch {epoch+1}] Val Loss: {val_loss:.4f}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(net_A.state_dict(), save_path_A)
            torch.save(net_B.state_dict(), save_path_B)
            print(f"New best models saved to {save_path_A} and {save_path_B}")

        train_loss_list.append(train_loss)
        val_loss_list.append(val_loss)
        epoch_list.append(epoch + 1)
        
        plt.figure(figsize=(12, 7))
        plt.plot(epoch_list, train_loss_list, 'b-o', label='Train Loss')
        plt.plot(epoch_list, val_loss_list, 'r-o', label='Validation Loss')
        plt.xlabel('Epoch')
        plt.ylabel('Loss')
        plt.title(f'Loss Curve up to Epoch {epoch+1}')
        plt.legend()
        plt.grid(True)
        plt.show()

    print('Finished Training')

if __name__ == '__main__':
    main()
