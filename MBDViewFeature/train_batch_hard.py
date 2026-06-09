import os
import sys
import numpy as np
from tqdm import tqdm
from PIL import Image

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, datasets
import matplotlib.pyplot as plt

# Import the original ResNet for net_B and the new dual-output ResNet for net_A
from model import resnet34
from model_dual_output import resnet34_dual_output

class MultiViewTripletDataset(Dataset):
    """
    Modified Dataset to return labels for anchor, positive, and negative samples.
    """
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
        positive_label = self.model_to_label[positive_model_id]
        
        negative_label = np.random.choice(list(self.labels_set - {anchor_label}))
        negative_model_id = np.random.choice(self.label_to_models[negative_label])

        def get_sampled_views(model_id):
            img_paths = self.model_to_images[model_id]
            paths_to_load = [img_paths[view_idx_A], img_paths[view_idx_B]]
            views = [Image.open(p).convert('RGB') if p and os.path.exists(p) else torch.zeros(3, 224, 224) for p in paths_to_load]
            if self.transform:
                views = [self.transform(v) if isinstance(v, Image.Image) else v for v in views]
            return torch.stack(views)

        anchor_views = get_sampled_views(anchor_model_id)
        positive_views = get_sampled_views(positive_model_id)
        negative_views = get_sampled_views(negative_model_id)

        return anchor_views, positive_views, negative_views, torch.tensor([anchor_label, positive_label, negative_label])

    def __len__(self):
        return len(self.models)

def main():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"Using {device} device.")

    # --- Hyperparameters ---
    gamma_classification = 0.5 # Weight for the classification loss on net_A
    lambda_intra = 0.5         # Weight for the intra-class loss from net_B
    margin_inter = 1.0
    learning_rate = 1e-4 # Increased learning rate for fine-tuning the head
    weight_decay = 1e-4
    epochs = 100
    batch_size = 4
    num_classes = 74 # Set this to the actual number of classes in your dataset

    # --- Data Loading ---
    data_transform = {
        "train": transforms.Compose([transforms.Resize(256), transforms.RandomResizedCrop(224), transforms.RandomHorizontalFlip(), transforms.ToTensor(), transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])]),
        "val": transforms.Compose([transforms.Resize(224), transforms.ToTensor(), transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
    }
    data_root = os.getcwd()
    train_image_path = os.path.join(data_root, "MBDViewDataset_noMBD/train")
    val_image_path = os.path.join(data_root, "MBDViewDataset_noMBD/validation")

    train_dataset = MultiViewTripletDataset(root_dir=train_image_path, transform=data_transform["train"])
    val_dataset = MultiViewTripletDataset(root_dir=val_image_path, transform=data_transform["val"])
    
    # Update num_classes based on the dataset
    num_classes = len(train_dataset.class_names)
    print(f"Dataset has {num_classes} classes.")

    nw = min([os.cpu_count(), batch_size if batch_size > 1 else 0, 8])
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=nw)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=nw)

    # --- Model, Loss, Optimizer ---
    net_A = resnet34_dual_output(num_classes=num_classes).to(device)
    net_B = resnet34(num_classes=num_classes).to(device)

    model_weight_path = "./resnet34-pre.pth"
    if os.path.exists(model_weight_path):
        net_A.load_state_dict(torch.load(model_weight_path, map_location='cpu'), strict=False)
        net_B.load_state_dict(torch.load(model_weight_path, map_location='cpu'), strict=False)

    # --- Fine-tuning Setup: Freeze backbone layers ---
    for name, param in net_A.named_parameters():
        if not any(head_name in name for head_name in ["Dense1", "Dense2", "BN", "classifier_head"]):
            param.requires_grad = False
    
    for name, param in net_B.named_parameters():
        if not any(head_name in name for head_name in ["Dense1", "Dense2", "BN"]):
            param.requires_grad = False

    # --- Define Loss Functions ---
    triplet_loss_func = nn.TripletMarginLoss(margin=margin_inter, p=2)
    classification_loss_func = nn.CrossEntropyLoss()
    cosine_sim_func = nn.CosineSimilarity(dim=1)

    # --- Optimizer: Pass only the parameters that require gradients ---
    params_to_update = []
    for net in [net_A, net_B]:
        for name, param in net.named_parameters():
            if param.requires_grad:
                params_to_update.append(param)
                print(f"Training parameter: {name}")

    optimizer = optim.Adam(params_to_update, lr=learning_rate, weight_decay=weight_decay)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=30, gamma=0.1)

    best_val_loss = float('inf')
    save_path_net_A = './MBDNet34_final_A.pth'
    save_path_net_B = './MBDNet34_final_B.pth'

    # --- Plotting Setup ---
    train_loss_list, val_loss_list = [], []
    epoch_list = []

    for epoch in range(epochs):
        # --- Training ---
        net_A.train()
        net_B.train()
        run_loss, run_l_triplet, run_l_class, run_l_intra = 0.0, 0.0, 0.0, 0.0
        
        train_bar = tqdm(train_loader, file=sys.stdout, desc=f"Train E[{epoch+1}]")
        for anchor_v, positive_v, negative_v, labels in train_bar:
            anchor_A, anchor_B = anchor_v[:, 0].to(device), anchor_v[:, 1].to(device)
            positive_A, positive_B = positive_v[:, 0].to(device), positive_v[:, 1].to(device)
            negative_A = negative_v[:, 0].to(device)
            
            labels = labels.to(device)
            anchor_lbl, positive_lbl, negative_lbl = labels[:, 0], labels[:, 1], labels[:, 2]

            optimizer.zero_grad()
            
            emb_anchor_A, logit_anchor_A = net_A(anchor_A)
            emb_positive_A, logit_positive_A = net_A(positive_A)
            emb_negative_A, logit_negative_A = net_A(negative_A)
            
            loss_triplet = triplet_loss_func(emb_anchor_A, emb_positive_A, emb_negative_A)
            
            all_logits = torch.cat([logit_anchor_A, logit_positive_A, logit_negative_A], dim=0)
            all_labels = torch.cat([anchor_lbl, positive_lbl, negative_lbl], dim=0)
            loss_class = classification_loss_func(all_logits, all_labels)
            
            loss_A = loss_triplet + gamma_classification * loss_class

            emb_anchor_B = net_B(anchor_B)
            emb_positive_B = net_B(positive_B)
            similarity = cosine_sim_func(emb_anchor_B, emb_positive_B)
            loss_intra = (1 + similarity).mean() / 2

            total_loss = loss_A + lambda_intra * loss_intra
            
            total_loss.backward()
            optimizer.step()

            run_loss += total_loss.item()
            run_l_triplet += loss_triplet.item()
            run_l_class += loss_class.item()
            run_l_intra += loss_intra.item()
            train_bar.set_postfix(L=f"{total_loss.item():.2f}", T=f"{loss_triplet.item():.2f}", C=f"{loss_class.item():.2f}", I=f"{loss_intra.item():.2f}")

        train_loss = run_loss / len(train_loader)
        print(f"[Epoch {epoch+1}] Train Loss: {train_loss:.4f} (Triplet: {run_l_triplet/len(train_loader):.4f}, Class: {run_l_class/len(train_loader):.4f}, Intra: {run_l_intra/len(train_loader):.4f})")

        # --- Validation ---
        net_A.eval()
        net_B.eval()
        val_run_loss = 0.0
        with torch.no_grad():
            val_bar = tqdm(val_loader, file=sys.stdout, desc=f"Val E[{epoch+1}]")
            for anchor_v, positive_v, negative_v, labels in val_bar:
                anchor_A, anchor_B = anchor_v[:, 0].to(device), anchor_v[:, 1].to(device)
                positive_A, positive_B = positive_v[:, 0].to(device), positive_v[:, 1].to(device)
                negative_A = negative_v[:, 0].to(device)
                labels = labels.to(device)
                anchor_lbl, positive_lbl, negative_lbl = labels[:, 0], labels[:, 1], labels[:, 2]

                emb_anchor_A, logit_anchor_A = net_A(anchor_A)
                emb_positive_A, _ = net_A(positive_A)
                emb_negative_A, _ = net_A(negative_A)
                loss_triplet = triplet_loss_func(emb_anchor_A, emb_positive_A, emb_negative_A)
                
                all_logits = torch.cat([logit_anchor_A, net_A(positive_A)[1], net_A(negative_A)[1]], dim=0)
                all_labels = torch.cat([anchor_lbl, positive_lbl, negative_lbl], dim=0)
                loss_class = classification_loss_func(all_logits, all_labels)
                loss_A = loss_triplet + gamma_classification * loss_class

                emb_anchor_B = net_B(anchor_B)
                emb_positive_B = net_B(positive_B)
                similarity = cosine_sim_func(emb_anchor_B, emb_positive_B)
                loss_intra = (1 + similarity).mean() / 2

                total_loss = loss_A + lambda_intra * loss_intra
                val_run_loss += total_loss.item()
        
        val_loss = val_run_loss / len(val_loader)
        print(f"[Epoch {epoch+1}] Val Loss: {val_loss:.4f}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(net_A.state_dict(), save_path_net_A)
            torch.save(net_B.state_dict(), save_path_net_B)
            print(f"New best models saved to {save_path_net_A} and {save_path_net_B}")

        scheduler.step()

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
        plt.show()

    print('Finished Training')

if __name__ == '__main__':
    main()
