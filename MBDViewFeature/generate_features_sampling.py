import os
import json
import numpy as np
import torch
from torchvision import transforms, datasets
from torch.utils.data import Dataset, DataLoader
from tqdm import tqdm
from PIL import Image

from model import resnet34


class FullViewDataset(Dataset):
    """
    A dataset that loads all 24 views for each model.
    """

    def __init__(self, root_dir, transform=None):
        self.root_dir = root_dir
        self.transform = transform
        self.image_folder = datasets.ImageFolder(root_dir)
        self.class_names = self.image_folder.classes

        self.model_to_images = {}
        self.model_to_label_idx = {}
        for img_path, label_idx in self.image_folder.imgs:
            model_id = "_".join(os.path.basename(img_path).split('_')[:-3])
            class_name = self.class_names[label_idx]
            full_model_id = f"{class_name}/{model_id}"

            if full_model_id not in self.model_to_images:
                self.model_to_images[full_model_id] = [None] * 24
                self.model_to_label_idx[full_model_id] = label_idx

            try:
                view_dir = int(os.path.basename(img_path).split('_')[-3])
                view_type = int(os.path.basename(img_path).split('_')[-2])
                cull_mode = int(os.path.basename(img_path).split('_')[-1].split('.')[0])
                view_index = view_dir * 4 + view_type * 2 + cull_mode
                self.model_to_images[full_model_id][view_index] = img_path
            except (ValueError, IndexError):
                continue

        self.models = list(self.model_to_images.keys())

    def __getitem__(self, index):
        model_id = self.models[index]
        img_paths = self.model_to_images[model_id]

        views = []
        for img_path in img_paths:
            if img_path and os.path.exists(img_path):
                img = Image.open(img_path).convert('RGB')
                if self.transform:
                    img = self.transform(img)
                views.append(img)
            else:
                views.append(torch.zeros(3, 224, 224))

        return torch.stack(views), model_id

    def __len__(self):
        return len(self.models)


def main():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"Using {device} device.")

    # --- Load Model ---
    net = resnet34()
    weights_path = "./MBDNet34_hierarchical_sampling.pth"
    if not os.path.exists(weights_path):
        print(f"Error: Weights file not found at {weights_path}")
        return
    net.load_state_dict(torch.load(weights_path, map_location=device))
    net.to(device)
    net.eval()

    # --- Data ---
    data_transform = transforms.Compose([
        transforms.Resize(224),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])

    data_root = os.path.join(os.getcwd(), "MBDViewDataset_noMBD")
    # Combine train and validation datasets
    full_dataset = torch.utils.data.ConcatDataset([
        FullViewDataset(os.path.join(data_root, "train"), transform=data_transform),
        FullViewDataset(os.path.join(data_root, "validation"), transform=data_transform)
    ])

    data_loader = DataLoader(full_dataset, batch_size=16, shuffle=False, num_workers=4)

    # --- Feature Extraction ---
    all_features = []
    all_model_ids = []

    with torch.no_grad():
        for views, model_ids in tqdm(data_loader, desc="Extracting Features"):
            # views: [batch, 24, 3, 224, 224]
            batch_size = views.size(0)
            views = views.view(-1, 3, 224, 224).to(device)  # [batch*24, 3, 224, 224]

            features = net(views)  # [batch*24, 128]
            features = features.view(batch_size, 24, -1)  # [batch, 24, 128]

            all_features.append(features.cpu().numpy())
            all_model_ids.extend(model_ids)

    all_features = np.concatenate(all_features, axis=0)

    # --- Save Results ---
    output_features_path = 'features_hierarchical_sampling.npy'
    output_info_path = 'model_sampling_info.json'

    np.save(output_features_path, all_features)
    print(f"Saved feature database to {output_features_path}, shape: {all_features.shape}")

    with open(output_info_path, 'w') as f:
        json.dump(all_model_ids, f)
    print(f"Saved model info to {output_info_path}")


if __name__ == '__main__':
    main()
