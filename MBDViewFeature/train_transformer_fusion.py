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

# Import the new Transformer-based fusion model
from model_transformer_fusion import TransformerFusionModel

class MultiViewPoolingDataset(Dataset):
    """
    Dataset that loads all 6 views for a given model type (A or B) at once.
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
        anchor_model_id = self.models[index]
        anchor_label = self.model_to_label[anchor_model_id]

        positive_model_id = anchor_model_id
        if len(self.label_to_models[anchor_label]) > 1:
            while positive_model_id == anchor_model_id:
                positive_model_id = np.random.choice(self.label_to_models[anchor_label])
        positive_label = self.model_to_label[positive_model_id]
        
        negative_label = np.random.choice(list(self.labels_set - {anchor_label}))
        negative_model_id = np.random.choice(self.label_to_models[negative_label])

        def get_all_views_for_type(model_id, indices):
            img_paths = self.model_to_images[model_id]
            paths_to_load = [img_paths[i] for i in indices]
            views = []
            for p in paths_to_load:
                # Use a black image placeholder if a view is missing
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
        
        return (anchor_views_A, anchor_views_B, 
                positive_views_A, positive_views_B, 
                negative_views_A), \
               torch.tensor([anchor_label, positive_label, negative_label])

    def __len__(self):
        return len(self.models)


def main():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"Using {device} device.")

    # --- Hyperparameters ---
    gamma_classification = 0.5
    lambda_intra = 0.5
    margin_inter = 1.0
    lr_backbone = 1e-5      # Smaller learning rate for the pre-trained backbone
    lr_head = 1e-4          # Larger learning rate for the new Transformer layers
    weight_decay = 1e-4
    epochs = 100
    batch_size = 2 # Keep batch size small

    # --- Data Loading ---
    data_transform = {
        "train": transforms.Compose([transforms.Resize(224), transforms.RandomHorizontalFlip(), transforms.ToTensor(), transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])]),
        "val": transforms.Compose([transforms.Resize(224), transforms.ToTensor(), transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
    }
    data_root = os.getcwd()
    train_image_path = os.path.join(data_root, "MBDViewDataset_noMBD/train")
    val_image_path = os.path.join(data_root, "MBDViewDataset_noMBD/validation")

    train_dataset = MultiViewPoolingDataset(root_dir=train_image_path, transform=data_transform["train"])
    val_dataset = MultiViewPoolingDataset(root_dir=val_image_path, transform=data_transform["val"])
    
    num_classes = len(train_dataset.class_names)
    print(f"Dataset has {num_classes} classes.")

    nw = min([os.cpu_count(), batch_size if batch_size > 1 else 0, 8])
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=nw)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=nw)

    # --- Model, Loss, Optimizer ---
    # Both networks now use the powerful Transformer fusion architecture
    net_A = TransformerFusionModel(num_classes=num_classes).to(device)
    net_B = TransformerFusionModel(num_classes=None).to(device) # No classifier head for net_B

    model_weight_path = "./resnet34-pre.pth"
    if os.path.exists(model_weight_path):
        # Load pretrained weights into the backbone of each model
        net_A.backbone.load_state_dict(torch.load(model_weight_path, map_location='cpu'), strict=False)
        net_B.backbone.load_state_dict(torch.load(model_weight_path, map_location='cpu'), strict=False)

    triplet_loss_func = nn.TripletMarginLoss(margin=margin_inter, p=2)
    classification_loss_func = nn.CrossEntropyLoss()
    cosine_sim_func = nn.CosineSimilarity(dim=1)

    # --- Optimizer with Differential Learning Rates ---
    param_groups = [
        {'params': net_A.backbone.parameters(), 'lr': lr_backbone},
        {'params': net_A.pos_encoder.parameters(), 'lr': lr_head},
        {'params': net_A.transformer_encoder.parameters(), 'lr': lr_head},
        {'params': net_A.classifier_head.parameters(), 'lr': lr_head},
        {'params': net_B.backbone.parameters(), 'lr': lr_backbone},
        {'params': net_B.pos_encoder.parameters(), 'lr': lr_head},
        {'params': net_B.transformer_encoder.parameters(), 'lr': lr_head},
    ]
    optimizer = optim.Adam(param_groups, weight_decay=weight_decay)
    
    # --- Scheduler with Warmup ---
    # Warmup for the first 5 epochs, then StepLR
    warmup_epochs = 5
    warmup_scheduler = torch.optim.lr_scheduler.LinearLR(optimizer, start_factor=0.1, total_iters=warmup_epochs)
    main_scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=30, gamma=0.1)
    scheduler = torch.optim.lr_scheduler.SequentialLR(optimizer, schedulers=[warmup_scheduler, main_scheduler], milestones=[warmup_epochs])

    best_val_loss = float('inf')
    save_path_net_A = './MBDNet34_transformer_A.pth'
    save_path_net_B = './MBDNet34_transformer_B.pth'

    # --- Plotting Setup ---
    train_loss_list, val_loss_list = [], []
    epoch_list = []

    for epoch in range(epochs):
        net_A.train()
        net_B.train()
        run_loss = 0.0
        
        train_bar = tqdm(train_loader, file=sys.stdout, desc=f"Train E[{epoch+1}]")
        for views, labels in train_bar:
            anchor_vA, anchor_vB, pos_vA, pos_vB, neg_vA = views
            labels = labels.to(device)
            anchor_lbl, positive_lbl, negative_lbl = labels[:, 0], labels[:, 1], labels[:, 2]

            optimizer.zero_grad()
            
            # --- Train net_A (Transformer Fusion) ---
            emb_anchor_A, logit_anchor_A = net_A(anchor_vA.to(device))
            emb_positive_A, logit_positive_A = net_A(pos_vA.to(device))
            emb_negative_A, logit_negative_A = net_A(neg_vA.to(device))
            
            loss_triplet = triplet_loss_func(emb_anchor_A, emb_positive_A, emb_negative_A)
            
            all_logits = torch.cat([logit_anchor_A, logit_positive_A, logit_negative_A], dim=0)
            all_labels = torch.cat([anchor_lbl, positive_lbl, negative_lbl], dim=0)
            loss_class = classification_loss_func(all_logits, all_labels)
            
            loss_A = loss_triplet + gamma_classification * loss_class

            # --- Train net_B (Transformer Fusion) ---
            emb_anchor_B = net_B(anchor_vB.to(device))
            emb_positive_B = net_B(pos_vB.to(device))
            similarity = cosine_sim_func(emb_anchor_B, emb_positive_B)
            loss_intra = (1 + similarity).mean() / 2

            total_loss = loss_A + lambda_intra * loss_intra
            
            total_loss.backward()
            optimizer.step()

            run_loss += total_loss.item()
            train_bar.set_postfix(L=f"{total_loss.item():.3f}")

        train_loss = run_loss / len(train_loader)
        print(f"[Epoch {epoch+1}] Train Loss: {train_loss:.4f}")

        # --- Validation ---
        net_A.eval()
        net_B.eval()
        val_run_loss = 0.0
        with torch.no_grad():
            val_bar = tqdm(val_loader, file=sys.stdout, desc=f"Val E[{epoch+1}]")
            for views, labels in val_bar:
                anchor_vA, anchor_vB, pos_vA, pos_vB, neg_vA = views
                labels = labels.to(device)
                anchor_lbl, positive_lbl, negative_lbl = labels[:, 0], labels[:, 1], labels[:, 2]

                emb_anchor_A, logit_anchor_A = net_A(anchor_vA.to(device))
                emb_positive_A, logit_positive_A = net_A(pos_vA.to(device))
                emb_negative_A, logit_negative_A = net_A(neg_vA.to(device))
                loss_triplet = triplet_loss_func(emb_anchor_A, emb_positive_A, emb_negative_A)
                all_logits = torch.cat([logit_anchor_A, logit_positive_A, logit_negative_A], dim=0)
                all_labels = torch.cat([anchor_lbl, positive_lbl, negative_lbl], dim=0)
                loss_class = classification_loss_func(all_logits, all_labels)
                loss_A = loss_triplet + gamma_classification * loss_class

                emb_anchor_B = net_B(anchor_vB.to(device))
                emb_positive_B = net_B(pos_vB.to(device))
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

        # --- Update and Save Plot ---
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
        plt.savefig(f'loss_curve_transformer_fusion.png')
        plt.show()

    print('Finished Training')

if __name__ == '__main__':
    main()
