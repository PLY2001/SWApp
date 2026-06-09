import os
import json
import numpy as np
import torch
from torchvision import transforms
from PIL import Image
from sklearn.cluster import KMeans
from tqdm import tqdm
from collections import Counter
import pandas as pd

from model import resnet34
from jvlei import classify_to_coarse_type # To get the number of clusters

def analyze_cluster_composition():
    """
    执行K-Means聚类并分析每个簇中细粒度类别的构成。
    """
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"Using {device} device.")

    # --- 1. 加载模型和数据 ---
    print("Loading feature extraction model (MBDNet34_hierarchical_sampling.pth)...")
    net = resnet34().to(device)
    net.load_state_dict(torch.load("./MBDNet34_hierarchical_sampling.pth", map_location=device))
    net.eval()

    print("Loading model info from ./MBDViewDataset_noMBD/V directory...")
    data_dir = './MBDViewDataset_noMBD/V'
    model_infos = []
    class_names = sorted([d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d))])

    for class_name in class_names:
        class_path = os.path.join(data_dir, class_name)
        unique_model_names = set()
        if os.path.isdir(class_path):
            for filename in os.listdir(class_path):
                if filename.endswith('.bmp'):
                    parts = filename.split('_')
                    if len(parts) > 3:
                        model_name = '_'.join(parts[:-3])
                        unique_model_names.add(model_name)
        for model_name in sorted(list(unique_model_names)):
            model_infos.append({'class_name': class_name, 'model_name': model_name})
    
    print(f"Loaded info for {len(model_infos)} models from {len(class_names)} classes.")

    # --- 2. 提取纯几何特征 (复用 evaluate_coarse_grained_geometric 的逻辑) ---
    data_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])

    all_features = []
    fine_grained_labels = [] # 我们需要这个来分析

    with torch.no_grad():
        for model_info in tqdm(model_infos, desc="Extracting Geometric Features"):
            class_name = model_info['class_name']
            model_name = model_info['model_name']
            
            features_A = []
            base_path_model = f"./MBDViewDataset_noMBD/validation/{class_name}/{model_name}"

            for view_dir in range(6):
                img_path = f"{base_path_model}_{view_dir}_0_0.bmp"
                if os.path.exists(img_path):
                    img = Image.open(img_path).convert('RGB')
                    img_tensor = data_transform(img).unsqueeze(0).to(device)
                    feature = net(img_tensor)
                    features_A.append(feature)

            if not features_A:
                continue

            avg_feature_A = torch.mean(torch.cat(features_A), dim=0)
            
            # 使用与 evaluate_coarse_grained_geometric 相同的特征
            final_feature = avg_feature_A 

            all_features.append(final_feature.cpu().numpy())
            fine_grained_labels.append(class_name)

    all_features = np.array(all_features)
    print(f"Extracted {len(all_features)} feature vectors.")

    # --- 3. 执行K-Means聚类 ---
    # 获取粗粒度类别的数量，以此作为K-Means的k值
    coarse_types = set()
    for fine_label in class_names:
        coarse_types.add(classify_to_coarse_type(fine_label, True))
    n_clusters = len(coarse_types)
    
    print(f"\nRunning KMeans with k={n_clusters}...")
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    cluster_assignments = kmeans.fit_predict(all_features)
    print("KMeans clustering complete.")

    # --- 4. 分析并报告每个簇的构成 ---
    print("\n" + "="*50)
    print("  Cluster Composition Analysis")
    print("="*50)

    cluster_composition = {i: [] for i in range(n_clusters)}
    for i, label in enumerate(fine_grained_labels):
        cluster_id = cluster_assignments[i]
        cluster_composition[cluster_id].append(label)

    # 使用pandas来更好地展示结果
    report_data = []
    for cluster_id, labels in sorted(cluster_composition.items()):
        count = Counter(labels)
        total_items = len(labels)
        # print(f"\n--- Cluster {cluster_id} (Total: {total_items} items) ---")
        for label, num in count.most_common():
            percentage = (num / total_items) * 100
            # print(f"  - {label}: {num} items ({percentage:.1f}%)")
            report_data.append({
                'Cluster ID': cluster_id,
                'Fine-Grained Class': label,
                'Count': num,
                'Percentage in Cluster': f"{percentage:.1f}%",
                'Cluster Total': total_items
            })
    
    df = pd.DataFrame(report_data)
    
    # 打印一个更紧凑的报告
    for cluster_id in sorted(df['Cluster ID'].unique()):
        cluster_df = df[df['Cluster ID'] == cluster_id].sort_values(by='Count', ascending=False)
        total_items = cluster_df['Cluster Total'].iloc
        print(f"\n--- Cluster {cluster_id} (Total: {total_items} items) ---")
        print(cluster_df[['Fine-Grained Class', 'Count', 'Percentage in Cluster']].to_string(index=False))

    # 保存详细报告到CSV
    output_csv_path = 'kmeans_geometric_cluster_analysis.csv'
    df.to_csv(output_csv_path, index=False, encoding='utf-8-sig')
    print(f"\nDetailed report saved to {output_csv_path}")


if __name__ == '__main__':
    analyze_cluster_composition()
