import os
import json
import numpy as np
import torch
import torch.nn as nn
from torchvision import transforms
from PIL import Image
import matplotlib.pyplot as plt
from tqdm import tqdm

from model import resnet34
from train_triplet import HierarchicalTripletLoss

def calculate_hierarchical_similarity(target_feats, db_feats, attention_net, device):
    """
    Calculates similarity based on the hierarchical, attention-weighted method.
    target_feats: [24, 128] tensor for the single target model.
    db_feats: [N, 24, 128] tensor for all models in the database.
    attention_net: The trained attention network.
    """
    # Ensure models are on the correct device
    target_feats = target_feats.to(device)
    db_feats = db_feats.to(device)
    attention_net = attention_net.to(device)

    # Define view indices for A, B types
    indices_A = [i * 4 for i in range(6)]
    indices_B = [i * 4 + 2 for i in range(6)]

    # --- Get Attention Weights for the target model ---
    target_mean_A = target_feats[indices_A].mean(dim=0)
    target_mean_B = target_feats[indices_B].mean(dim=0)
    attention_input = torch.cat([target_mean_A, target_mean_B], dim=0).unsqueeze(0)
    
    with torch.no_grad():
        weights = attention_net(attention_input).squeeze(0) # [2]
    w_A = weights[0]
    w_B = weights[1]
    
    print(f"Calculated Weights -> w_A: {w_A:.4f}, w_B: {w_B:.4f}")

    # --- Calculate Similarities ---
    # Expand target_feats to match the shape of db_feats for batch calculation
    target_feats_expanded = target_feats.unsqueeze(0).expand_as(db_feats)
    
    # Cosine similarity is equivalent to dot product for normalized vectors
    # We calculate similarity, so no (1 - sim)
    sim_func = nn.CosineSimilarity(dim=2)
    
    sim_A = sim_func(target_feats_expanded[:, indices_A], db_feats[:, indices_A]).mean(dim=1)
    sim_B = sim_func(target_feats_expanded[:, indices_B], db_feats[:, indices_B]).mean(dim=1)

    # --- Final Weighted Similarity ---
    final_sim = w_A * sim_A + w_B * sim_B
    
    return final_sim.cpu().numpy()


def main():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"Using {device} device.")

    # --- Load Models and Data ---
    # 1. Feature Extractor
    net = resnet34().to(device)
    net.load_state_dict(torch.load("./MBDNet34_hierarchical.pth", map_location=device))
    net.eval()

    # 2. Attention Network (from HierarchicalTripletLoss)
    loss_module = HierarchicalTripletLoss()
    loss_module.load_state_dict(torch.load("./HierarchicalLoss_attention.pth", map_location=device))
    attention_net = loss_module.attention_net.to(device)
    attention_net.eval()

    # 3. Feature Database
    features_db = torch.from_numpy(np.load('features_hierarchical.npy'))
    with open('model_info.json', 'r') as f:
        model_ids = json.load(f)
    
    print(f"Loaded feature database with {len(model_ids)} models.")

    # --- Target Model ---
    input_full_id = '90 degree elbows/1476618.stl_10846' # Example target
    #input_full_id = 'Bushes/00013769.stl_448' # Example target

    try:
        target_idx = model_ids.index(input_full_id)
    except ValueError:
        print(f"Error: Target model '{input_full_id}' not found in database.")
        return

    # --- Get Target Features (real-time calculation) ---
    data_transform = transforms.Compose([
        transforms.Resize(224),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    
    target_views = []
    train_base_path = "./MBDViewDataset_noMBD/train"
    val_base_path = "./MBDViewDataset_noMBD/validation"
    class_name, model_name = input_full_id.split('/')

    for i in range(6): # view_dir
        for j in range(2): # view_type (a,b)
             for k in range(2): # cull_mode
                view_filename = f"{model_name}_{i}_{j}_{k}.bmp"
                
                # Robustly find the image path in either train or validation set
                img_path_train = os.path.join(train_base_path, class_name, view_filename)
                img_path_val = os.path.join(val_base_path, class_name, view_filename)

                final_img_path = None
                if os.path.exists(img_path_train):
                    final_img_path = img_path_train
                elif os.path.exists(img_path_val):
                    final_img_path = img_path_val

                if final_img_path:
                    img = Image.open(final_img_path).convert('RGB')
                    target_views.append(data_transform(img))
                else:
                    # If any view is missing, we still append a placeholder
                    target_views.append(torch.zeros(3, 224, 224))

    target_views = torch.stack(target_views).to(device)
    
    with torch.no_grad():
        target_features = net(target_views) # [24, 128]

    # --- Perform Retrieval ---
    similarities = calculate_hierarchical_similarity(target_features, features_db, attention_net, device)
    
    # Sort results (descending)
    sorted_indices = np.argsort(similarities)[::-1]

    # --- Display Results ---
    plt.figure(figsize=(10, 16))
    plt.suptitle("Hierarchical Retrieval System", fontsize=30)

    # Display target image (using one of its views from the dedicated preview folder)
    preview_base_path = "./MBDViewModelPicture"
    target_display_path = os.path.join(preview_base_path, class_name, f"{model_name}_6_2_0.bmp")
    if os.path.exists(target_display_path):
        img = Image.open(target_display_path)
        plt.subplot(4, 3, 1)
        plt.axis('off')
        plt.imshow(img)
        plt.title(f"[Target]\n{input_full_id}", fontsize=12)

    # Display top results
    for i in range(min(11, len(sorted_indices))):
        retrieved_idx = sorted_indices[i]
        retrieved_id = model_ids[retrieved_idx]
        retrieved_sim = similarities[retrieved_idx]
        
        retrieved_class, retrieved_name = retrieved_id.split('/')
        
        # Display one view of the retrieved model from the dedicated preview folder
        retrieved_display_path = os.path.join(preview_base_path, retrieved_class, f"{retrieved_name}_6_2_0.bmp")
        
        plt.subplot(4, 3, 2 + i)
        plt.axis('off')
        if os.path.exists(retrieved_display_path):
            img = Image.open(retrieved_display_path)
            plt.imshow(img)
        
        plt.title(f"[{i+1}] {retrieved_id}\nSim: {retrieved_sim:.4f}", fontsize=10)

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.show()


if __name__ == '__main__':
    main()
