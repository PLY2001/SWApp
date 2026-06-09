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
        
        # Group images by model
        self.model_to_images = {}
        self.model_to_label = {}
        for img_path, label_idx in self.image_folder.imgs:
            # e.g. './MBDViewDataset_noMBD/train/Hexagonal nuts/00000_0_0_0.bmp'
            model_id = "_".join(os.path.basename(img_path).split('_')[:-3]) # '00000'
            class_name = self.class_names[label_idx]
            full_model_id = f"{class_name}/{model_id}"

            if full_model_id not in self.model_to_images:
                self.model_to_images[full_model_id] = [None] * 24
                self.model_to_label[full_model_id] = label_idx
            
            try:
                view_dir = int(os.path.basename(img_path).split('_')[-3])
                view_type = int(os.path.basename(img_path).split('_')[-2])
                cull_mode = int(os.path.basename(img_path).split('_')[-1].split('.')[0])
                view_index = view_dir * 4 + view_type * 2 + cull_mode # Simplified index
                self.model_to_images[full_model_id][view_index] = img_path
            except (ValueError, IndexError):
                print(f"Warning: Could not parse view info from {img_path}. Skipping.")
                continue

        self.models = list(self.model_to_images.keys())
        self.labels_set = set(self.model_to_label.values())
        self.label_to_models = {label: [m for m in self.models if self.model_to_label[m] == label]
                                for label in self.labels_set}
        
        # Define view indices for A, B types for 6 directions
        self.indices_A = [i * 4 for i in range(6)]
        self.indices_B = [i * 4 + 2 for i in range(6)]

    def __getitem__(self, index):
        # 1. Randomly select one view direction for this triplet
        view_direction_idx = np.random.randint(0, 6)
        
        view_idx_A = self.indices_A[view_direction_idx]
        view_idx_B = self.indices_B[view_direction_idx]

        anchor_model_id = self.models[index]
        anchor_label = self.model_to_label[anchor_model_id]

        # 2. Get positive model
        positive_model_id = anchor_model_id
        # Ensure we get a different model of the same class
        if len(self.label_to_models[anchor_label]) > 1:
            while positive_model_id == anchor_model_id:
                positive_model_id = np.random.choice(self.label_to_models[anchor_label])
        else:
            # Handle case where a class has only one model (use itself as positive)
            positive_model_id = anchor_model_id
        
        # 3. Get negative model
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

class HierarchicalTripletLoss(nn.Module):
    def __init__(self, margin=1.0):
        super(HierarchicalTripletLoss, self).__init__()
        self.margin = margin
        self.distance_func = nn.CosineSimilarity(dim=1)
        
        # Attention network to learn w_A and w_B
        self.attention_net = nn.Sequential(
            nn.Linear(128 * 2, 64),
            nn.ReLU(),
            nn.Linear(64, 2),
            nn.Softmax(dim=1)
        )

    def forward(self, anchor_feats, positive_feats, negative_feats):
        # anchor_feats, positive_feats, negative_feats are [batch_size, 2, 128]
        # The 2 features are [view_A, view_B] from the same direction
        
        anchor_feat_A = anchor_feats[:, 0]
        anchor_feat_B = anchor_feats[:, 1]
        
        positive_feat_A = positive_feats[:, 0]
        positive_feat_B = positive_feats[:, 1]

        negative_feat_A = negative_feats[:, 0]
        negative_feat_B = negative_feats[:, 1]

        # --- Calculate Distances for each view type ---
        dist_ap_A = 1 - self.distance_func(anchor_feat_A, positive_feat_A)
        dist_ap_B = 1 - self.distance_func(anchor_feat_B, positive_feat_B)
        
        dist_an_A = 1 - self.distance_func(anchor_feat_A, negative_feat_A)
        dist_an_B = 1 - self.distance_func(anchor_feat_B, negative_feat_B)

        # --- Get Attention Weights ---
        # Use anchor's features of A and B to decide weights
        attention_input = torch.cat([anchor_feat_A, anchor_feat_B], dim=1)
        weights = self.attention_net(attention_input) # [batch_size, 2]
        w_A = weights[:, 0]
        w_B = weights[:, 1]

        # --- Calculate Final Weighted Distances ---
        d_ap = w_A * dist_ap_A + w_B * dist_ap_B
        d_an = w_A * dist_an_A + w_B * dist_an_B

        # --- Triplet Loss ---
        loss = F.relu(d_ap - d_an + self.margin).mean()
        
        return loss, w_A.mean(), w_B.mean()

def main():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"Using {device} device.")


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

    batch_size = 4 # Reduce batch size further to address CUDA error
    nw = min([os.cpu_count(), batch_size if batch_size > 1 else 0, 8])
    print(f'Using {nw} dataloader workers every process')

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=nw)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=nw)

    print(f"Training on {len(train_dataset)} models, validating on {len(val_dataset)} models.")

    # --- Model, Loss, Optimizer ---
    net = resnet34()
    model_weight_path = "./resnet34-pre.pth"
    if os.path.exists(model_weight_path):
        net.load_state_dict(torch.load(model_weight_path, map_location='cpu'), strict=False)
    net.to(device)

    loss_function = HierarchicalTripletLoss(margin=1.0).to(device)
    
    # Combine parameters of the model and the attention network in the loss function
    optimizer = optim.Adam(list(net.parameters()) + list(loss_function.parameters()), lr=1e-5)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=20, gamma=0.1)

    epochs = 200
    best_val_loss = float('inf')
    save_path_net = './MBDNet34_hierarchical.pth'
    save_path_loss = './HierarchicalLoss_attention.pth'

    # --- Plotting Setup ---
    train_loss_list = []
    val_loss_list = []
    epoch_list = []

    # --- Training & Validation Loop ---
    for epoch in range(epochs):
        # Training
        net.train()
        loss_function.train()
        running_loss = 0.0
        avg_w_A, avg_w_B = 0.0, 0.0
        train_bar = tqdm(train_loader, file=sys.stdout)
        for anchor_views, positive_views, negative_views, _ in train_bar:
            # anchor_views is [batch, 24, 3, 224, 224]
            batch_size_current = anchor_views.size(0)
            
            # Reshape for model input
            # anchor_views is [batch, 2, 3, 224, 224]
            all_views = torch.cat([anchor_views, positive_views, negative_views], dim=0)
            # all_views is now [batch*3, 2, 3, 224, 224]
            all_views = all_views.view(-1, 3, 224, 224).to(device) # Reshape to [batch*3*2, 3, 224, 224]

            optimizer.zero_grad()
            
            # Get features for all views
            all_features = net(all_views)
            # all_features is [batch*3*2, 128]
            all_features = all_features.view(batch_size_current * 3, 2, -1) # Reshape to [batch*3, 2, 128]
            
            anchor_feats = all_features[0:batch_size_current]
            positive_feats = all_features[batch_size_current:batch_size_current*2]
            negative_feats = all_features[batch_size_current*2:batch_size_current*3]

            loss, w_A, w_B = loss_function(anchor_feats, positive_feats, negative_feats)
            
            loss.backward()
            optimizer.step()

            running_loss += loss.item()
            avg_w_A += w_A.item()
            avg_w_B += w_B.item()
            train_bar.set_description(f"Train E[{epoch+1}] L:{loss.item():.3f} wA:{w_A:.2f} wB:{w_B:.2f}")

        scheduler.step()
        train_loss = running_loss / len(train_loader)
        avg_w_A /= len(train_loader)
        avg_w_B /= len(train_loader)
        print(f"[Epoch {epoch+1}] Train Loss: {train_loss:.4f}, Avg w_A: {avg_w_A:.3f}, Avg w_B: {avg_w_B:.3f}")

        # Validation
        net.eval()
        loss_function.eval()
        val_loss = 0.0
        with torch.no_grad():
            val_bar = tqdm(val_loader, file=sys.stdout)
            for anchor_views, positive_views, negative_views, _ in val_bar:
                batch_size_current = anchor_views.size(0)
                all_views = torch.cat([anchor_views, positive_views, negative_views], dim=0)
                all_views = all_views.view(-1, 3, 224, 224).to(device)
                all_features = net(all_views)
                all_features = all_features.view(batch_size_current * 3, 2, -1)
                anchor_feats, positive_feats, negative_feats = all_features.chunk(3, dim=0)
                loss, _, _ = loss_function(anchor_feats, positive_feats, negative_feats)
                val_loss += loss.item()
                val_bar.set_description(f"Val E[{epoch+1}]")

        val_loss /= len(val_loader)
        print(f"[Epoch {epoch+1}] Val Loss: {val_loss:.4f}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(net.state_dict(), save_path_net)
            torch.save(loss_function.state_dict(), save_path_loss)
            print(f"New best model saved to {save_path_net} and {save_path_loss}")

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

    print('Finished Training')

if __name__ == '__main__':
    main()
