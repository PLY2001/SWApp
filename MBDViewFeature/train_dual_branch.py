import os
import sys
import numpy as np
from tqdm import tqdm
from PIL import Image

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, datasets
import matplotlib.pyplot as plt

from model import resnet34

class MultiViewTripletDataset(Dataset):
    def __init__(self, root_dir, transform=None):
        self.root_dir = root_dir
        self.transform = transform
        self.image_folder = datasets.ImageFolder(root_dir)
        self.labels = np.array(self.image_folder.targets)
        self.class_names = self.image_folder.classes
        
        self.model_to_images = {}
        self.model_to_label = {}
        for img_path, label_idx in self.image_folder.imgs:
            model_id = "_".join(os.path.basename(img_path).split('_')[:-3])
            class_name = self.class_names[label_idx]
            full_model_id = f"{class_name}/{model_id}"

            if full_model_id not in self.model_to_images:
                self.model_to_images[full_model_id] = [None] * 24
                self.model_to_label[full_model_id] = label_idx
            
            try:
                view_dir = int(os.path.basename(img_path).split('_')[-3])
                view_type = int(os.path.basename(img_path).split('_')[-2])
                cull_mode = int(os.path.basename(img_path).split('_')[-1].split('.')[0])
                view_index = view_dir * 4 + view_type * 2 + cull_mode
                self.model_to_images[full_model_id][view_index] = img_path
            except (ValueError, IndexError):
                print(f"Warning: Could not parse view info from {img_path}. Skipping.")
                continue

        self.models = list(self.model_to_images.keys())
        self.labels_set = set(self.model_to_label.values())
        self.label_to_models = {label: [m for m in self.models if self.model_to_label[m] == label]
                                for label in self.labels_set}
        
        self.indices_A = [i * 4 for i in range(6)]
        self.indices_B = [i * 4 + 2 for i in range(6)]

    def __getitem__(self, index):
        view_direction_idx = np.random.randint(0, 6)
        view_idx_A = self.indices_A[view_direction_idx]
        view_idx_B = self.indices_B[view_direction_idx]

        anchor_model_id = self.models[index]
        anchor_label = self.model_to_label[anchor_model_id]

        positive_model_id = anchor_model_id
        if len(self.label_to_models[anchor_label]) > 1:
            while positive_model_id == anchor_model_id:
                positive_model_id = np.random.choice(self.label_to_models[anchor_label])
        
        negative_label = np.random.choice(list(self.labels_set - {anchor_label}))
        negative_model_id = np.random.choice(self.label_to_models[negative_label])

        def get_sampled_views(model_id):
            img_paths = self.model_to_images[model_id]
            paths_to_load = [img_paths[view_idx_A], img_paths[view_idx_B]]
            views = []
            for img_path in paths_to_load:
                if img_path and os.path.exists(img_path):
                    img = Image.open(img_path).convert('RGB')
                    if self.transform:
                        img = self.transform(img)
                    views.append(img)
                else:
                    views.append(torch.zeros(3, 224, 224))
            return torch.stack(views)

        anchor_views = get_sampled_views(anchor_model_id)
        positive_views = get_sampled_views(positive_model_id)
        negative_views = get_sampled_views(negative_model_id)

        return anchor_views, positive_views, negative_views, anchor_label

    def __len__(self):
        return len(self.models)

def main():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"Using {device} device.")

    # --- Hyperparameters ---
    lambda_intra = 0.5 # Weight for the intra-class loss
    margin_inter = 1.0
    learning_rate = 1e-5
    weight_decay = 1e-4
    epochs = 50
    batch_size = 4

    # --- Data Loading ---
    data_transform = {
        "train": transforms.Compose([
            transforms.Resize(256),
            transforms.RandomResizedCrop(224),
            transforms.RandomHorizontalFlip(),
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

    train_dataset = MultiViewTripletDataset(root_dir=train_image_path, transform=data_transform["train"])
    val_dataset = MultiViewTripletDataset(root_dir=val_image_path, transform=data_transform["val"])

    nw = min([os.cpu_count(), batch_size if batch_size > 1 else 0, 8])
    print(f'Using {nw} dataloader workers every process')

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=nw)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=nw)

    print(f"Training on {len(train_dataset)} models, validating on {len(val_dataset)} models.")

    # --- Model, Loss, Optimizer ---
    # Initialize two separate networks
    net_A = resnet34().to(device) # For global, inter-class features
    net_B = resnet34().to(device) # For local, intra-class features

    # Load pretrained weights if available
    model_weight_path = "./resnet34-pre.pth"
    if os.path.exists(model_weight_path):
        net_A.load_state_dict(torch.load(model_weight_path, map_location='cpu'), strict=False)
        net_B.load_state_dict(torch.load(model_weight_path, map_location='cpu'), strict=False)

    # Define separate loss functions
    triplet_loss_func = nn.TripletMarginLoss(margin=margin_inter, p=2)
    cosine_sim_func = nn.CosineSimilarity(dim=1)

    # Combine parameters of both networks for the optimizer
    optimizer = optim.Adam(list(net_A.parameters()) + list(net_B.parameters()), lr=learning_rate, weight_decay=weight_decay)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=20, gamma=0.1)

    best_val_loss = float('inf')
    save_path_net_A = './MBDNet34_dual_A.pth'
    save_path_net_B = './MBDNet34_dual_B.pth'

    # --- Plotting Setup ---
    train_loss_list = []
    val_loss_list = []
    epoch_list = []

    # --- Training & Validation Loop ---
    for epoch in range(epochs):
        # Training
        net_A.train()
        net_B.train()
        running_loss, running_loss_inter, running_loss_intra = 0.0, 0.0, 0.0
        train_bar = tqdm(train_loader, file=sys.stdout)
        
        for anchor_views, positive_views, negative_views, _ in train_bar:
            # anchor_views is [batch, 2, 3, 224, 224]
            # Separate views for each network
            anchor_A, anchor_B = anchor_views[:, 0], anchor_views[:, 1]
            positive_A, positive_B = positive_views[:, 0], positive_views[:, 1]
            negative_A, _ = negative_views[:, 0], negative_views[:, 1] # negative_B is not used

            anchor_A, positive_A, negative_A = anchor_A.to(device), positive_A.to(device), negative_A.to(device)
            anchor_B, positive_B = anchor_B.to(device), positive_B.to(device)

            optimizer.zero_grad()
            
            # --- Inter-Class Training (net_A) ---
            feat_anchor_A = net_A(anchor_A)
            feat_positive_A = net_A(positive_A)
            feat_negative_A = net_A(negative_A)
            loss_inter = triplet_loss_func(feat_anchor_A, feat_positive_A, feat_negative_A)

            # --- Intra-Class Training (net_B) ---
            feat_anchor_B = net_B(anchor_B)
            feat_positive_B = net_B(positive_B)
            # We want to maximize distance, so minimize similarity. Loss = (1-sim) is not good.
            # Loss = 1 - sim is in [0, 2]. We want to push sim to -1.
            # Let's use (1 + sim) / 2. If sim=-1, loss=0. If sim=1, loss=1.
            similarity = cosine_sim_func(feat_anchor_B, feat_positive_B)
            loss_intra = (1 + similarity).mean() / 2

            # --- Total Loss ---
            total_loss = loss_inter + lambda_intra * loss_intra
            
            total_loss.backward()
            optimizer.step()

            running_loss += total_loss.item()
            running_loss_inter += loss_inter.item()
            running_loss_intra += loss_intra.item()
            train_bar.set_description(f"Train E[{epoch+1}] L:{total_loss.item():.3f} (Inter:{loss_inter.item():.3f}, Intra:{loss_intra.item():.3f})")

        scheduler.step()
        train_loss = running_loss / len(train_loader)
        train_loss_inter = running_loss_inter / len(train_loader)
        train_loss_intra = running_loss_intra / len(train_loader)
        print(f"[Epoch {epoch+1}] Train Loss: {train_loss:.4f} (Inter: {train_loss_inter:.4f}, Intra: {train_loss_intra:.4f})")

        # Validation
        net_A.eval()
        net_B.eval()
        val_loss, val_loss_inter, val_loss_intra = 0.0, 0.0, 0.0
        with torch.no_grad():
            val_bar = tqdm(val_loader, file=sys.stdout)
            for anchor_views, positive_views, negative_views, _ in val_bar:
                anchor_A, anchor_B = anchor_views[:, 0], anchor_views[:, 1]
                positive_A, positive_B = positive_views[:, 0], positive_views[:, 1]
                negative_A, _ = negative_views[:, 0], negative_views[:, 1]

                anchor_A, positive_A, negative_A = anchor_A.to(device), positive_A.to(device), negative_A.to(device)
                anchor_B, positive_B = anchor_B.to(device), positive_B.to(device)

                feat_anchor_A = net_A(anchor_A)
                feat_positive_A = net_A(positive_A)
                feat_negative_A = net_A(negative_A)
                loss_inter = triplet_loss_func(feat_anchor_A, feat_positive_A, feat_negative_A)

                feat_anchor_B = net_B(anchor_B)
                feat_positive_B = net_B(positive_B)
                similarity = cosine_sim_func(feat_anchor_B, feat_positive_B)
                loss_intra = (1 + similarity).mean() / 2
                
                total_loss = loss_inter + lambda_intra * loss_intra
                
                val_loss += total_loss.item()
                val_loss_inter += loss_inter.item()
                val_loss_intra += loss_intra.item()
                val_bar.set_description(f"Val E[{epoch+1}]")

        val_loss /= len(val_loader)
        val_loss_inter /= len(val_loader)
        val_loss_intra /= len(val_loader)
        print(f"[Epoch {epoch+1}] Val Loss: {val_loss:.4f} (Inter: {val_loss_inter:.4f}, Intra: {val_loss_intra:.4f})")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(net_A.state_dict(), save_path_net_A)
            torch.save(net_B.state_dict(), save_path_net_B)
            print(f"New best models saved to {save_path_net_A} and {save_path_net_B}")

        # --- Update Plot ---
        train_loss_list.append(train_loss)
        val_loss_list.append(val_loss)
        epoch_list.append(epoch + 1)
        
        plt.figure(figsize=(10, 6))
        plt.plot(epoch_list, train_loss_list, 'b-', label='Train Loss')
        plt.plot(epoch_list, val_loss_list, 'r-', label='Validation Loss')
        plt.xlabel('Epoch')
        plt.ylabel('Loss')
        plt.title(f'Loss Curve up to Epoch {epoch+1}')
        plt.legend()
        plt.grid(True)
        plt.show() # This will block until the window is closed

if __name__ == '__main__':
    main()
