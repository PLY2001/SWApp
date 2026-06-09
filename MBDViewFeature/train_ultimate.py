import os
import sys
import numpy as np
from tqdm import tqdm
from PIL import Image
from collections import defaultdict

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

class UltimateDataset(Dataset):
    """
    Dataset for the ultimate training scheme.
    Returns all 6 views for type A and B for a given model.
    Also returns class_id and a unique model_id integer.
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
        self.model_keys = {name: i for i, name in enumerate(self.models)}
        self.indices_A = [i * 4 for i in range(6)]
        self.indices_B = [i * 4 + 2 for i in range(6)]

    def __getitem__(self, index):
        model_name = self.models[index]
        class_id = self.model_to_label[model_name]
        model_id_int = self.model_keys[model_name]

        def get_all_views_for_type(indices):
            img_paths = self.model_to_images[model_name]
            paths_to_load = [img_paths[i] for i in indices]
            views = []
            for p in paths_to_load:
                img = Image.open(p).convert('RGB') if p and os.path.exists(p) else Image.new('RGB', (224, 224), 'black')
                if self.transform:
                    img = self.transform(img)
                views.append(img)
            return torch.stack(views)

        views_A = get_all_views_for_type(self.indices_A)
        views_B = get_all_views_for_type(self.indices_B)
            
        return views_A, views_B, class_id, model_id_int

    def __len__(self):
        return len(self.models)

def main():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"Using {device} device.")

    # --- Hyperparameters ---
    lambda_intra = 0.05 # Lower the weight of the contrastive loss
    lr_backbone = 1e-5
    lr_head = 1e-4
    weight_decay = 5e-4 # Increased weight decay for stronger regularization
    epochs = 100
    batch_size = 4 # Smaller batch size for two large models

    # --- Data Loading ---
    data_transform = {
        "train": transforms.Compose([
            transforms.Resize(224),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(15),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            transforms.RandomErasing(p=0.5, scale=(0.02, 0.33), ratio=(0.3, 3.3), value='random') # Added RandomErasing
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

    train_dataset = UltimateDataset(root_dir=train_image_path, transform=data_transform["train"])
    val_dataset = UltimateDataset(root_dir=val_image_path, transform=data_transform["val"])
    
    num_classes = len(train_dataset.class_names)
    print(f"Dataset has {num_classes} classes.")

    nw = min([os.cpu_count(), batch_size if batch_size > 1 else 0, 8])
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=nw)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=nw)

    # --- Models, Losses, Optimizer ---
    net_A = UltimateFusionModel(num_classes=num_classes).to(device)
    net_B = TransformerEncoderModel(num_classes=None).to(device)

    model_weight_path = "./resnet34-pre.pth"
    if os.path.exists(model_weight_path):
        net_A.backbone.load_state_dict(torch.load(model_weight_path, map_location='cpu'), strict=False)
        net_B.backbone.load_state_dict(torch.load(model_weight_path, map_location='cpu'), strict=False)

    loss_arcface = nn.CrossEntropyLoss(label_smoothing=0.1) # Added Label Smoothing
    cosine_sim_func = nn.CosineSimilarity(dim=1)

    # --- Optimizer with Differential Learning Rates (Corrected) ---
    # Group parameters to avoid overlap
    param_groups = [
        {'params': net_A.backbone.parameters(), 'lr': lr_backbone},
        {'params': net_A.pos_encoder.parameters(), 'lr': lr_head},
        {'params': net_A.transformer_encoder.parameters(), 'lr': lr_head},
        {'params': net_A.arcface_head.parameters(), 'lr': lr_head},
        
        {'params': net_B.backbone.parameters(), 'lr': lr_backbone},
        {'params': net_B.pos_encoder.parameters(), 'lr': lr_head},
        {'params': net_B.transformer_encoder.parameters(), 'lr': lr_head},
    ]
    optimizer = optim.Adam(param_groups, weight_decay=weight_decay)
    
    warmup_epochs = 5
    warmup_scheduler = torch.optim.lr_scheduler.LinearLR(optimizer, start_factor=0.1, total_iters=warmup_epochs)
    # Using CosineAnnealingLR for smoother learning rate decay
    main_scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs - warmup_epochs, eta_min=1e-7)
    scheduler = torch.optim.lr_scheduler.SequentialLR(optimizer, schedulers=[warmup_scheduler, main_scheduler], milestones=[warmup_epochs])

    best_val_loss = float('inf')
    save_path_A = './MBDNet34_ultimate_A.pth'
    save_path_B = './MBDNet34_ultimate_B.pth'

    train_loss_list, val_loss_list = [], []
    epoch_list = []

    for epoch in range(epochs):
        net_A.train()
        net_B.train()
        run_loss, run_loss_A, run_loss_B = 0.0, 0.0, 0.0
        
        train_bar = tqdm(train_loader, file=sys.stdout, desc=f"Train E[{epoch+1}]")
        for views_A, views_B, class_ids, model_ids_int in train_bar:
            views_A, views_B, class_ids = views_A.to(device), views_B.to(device), class_ids.to(device)
            
            optimizer.zero_grad()
            
            # --- Train net_A (ArcFace) ---
            logits = net_A(views_A, class_ids)
            loss_A = loss_arcface(logits, class_ids)
            
            # --- Train net_B (Contrastive) ---
            embeddings_B = net_B(views_B)
            mask_negative = model_ids_int.unsqueeze(1) != model_ids_int.unsqueeze(0)
            if not mask_negative.any(): # Skip if all items in batch are the same model
                loss_B = torch.tensor(0.0, device=device)
            else:
                # embeddings_B is already normalized. Dot product is cosine similarity.
                sim_matrix = torch.matmul(embeddings_B, embeddings_B.T)
                # Select similarity of negative pairs
                negative_pairs_sim = sim_matrix[mask_negative]
                # Loss: we want similarity to be -1, so (1+sim)/2 should be 0.
                loss_B = (1 + negative_pairs_sim).mean() / 2
            
            total_loss = loss_A + lambda_intra * loss_B
            
            total_loss.backward()
            optimizer.step()

            run_loss += total_loss.item()
            run_loss_A += loss_A.item()
            run_loss_B += loss_B.item()
            train_bar.set_postfix(L=f"{total_loss.item():.3f}", A=f"{loss_A.item():.3f}", B=f"{loss_B.item():.3f}")

        scheduler.step()
        
        train_loss = run_loss / len(train_loader)
        print(f"[Epoch {epoch+1}] Train Loss: {train_loss:.4f} (ArcFace: {run_loss_A/len(train_loader):.4f}, Contrastive: {run_loss_B/len(train_loader):.4f})")

        # --- Validation ---
        net_A.eval()
        net_B.eval()
        val_run_loss = 0.0
        with torch.no_grad():
            val_bar = tqdm(val_loader, file=sys.stdout, desc=f"Val E[{epoch+1}]")
            for views_A, views_B, class_ids, model_ids_int in val_bar:
                views_A, views_B, class_ids = views_A.to(device), views_B.to(device), class_ids.to(device)
                
                net_A.train() # Temporarily set to train to get logits
                logits = net_A(views_A, class_ids)
                net_A.eval()
                loss_A = loss_arcface(logits, class_ids)
                
                embeddings_B = net_B(views_B)
                mask_negative = model_ids_int.unsqueeze(1) != model_ids_int.unsqueeze(0)
                if not mask_negative.any():
                    loss_B = torch.tensor(0.0, device=device)
                else:
                    sim_matrix = torch.matmul(embeddings_B, embeddings_B.T)
                    negative_pairs_sim = sim_matrix[mask_negative]
                    loss_B = (1 + negative_pairs_sim).mean() / 2
                
                total_loss = loss_A + lambda_intra * loss_B
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
