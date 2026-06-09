import os
import json
import numpy as np
import torch
from torchvision import transforms
from PIL import Image
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score, silhouette_score
from sklearn.manifold import TSNE
from tqdm import tqdm

from model import resnet34
from train_triplet import HierarchicalTripletLoss
from jvlei import classify_to_coarse_type  # We can reuse this handy function


def _run_clustering_and_evaluation(all_features, true_labels, coarse_labels, title_suffix, plot_filename):
    """
    辅助函数：执行聚类、评估和可视化。
    """
    # 1. 处理标签
    unique_coarse_types = sorted(list(set(coarse_labels)))
    coarse_label_map = {label: idx for idx, label in enumerate(unique_coarse_types)}
    coarse_label_indices = [coarse_label_map[label] for label in coarse_labels]

    print("  Clustering...")
    # 2. 执行KMeans聚类
    n_clusters = len(unique_coarse_types)
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(all_features)

    # 3. 计算评估指标
    ari_score = adjusted_rand_score(coarse_label_indices, cluster_labels)
    nmi_score = normalized_mutual_info_score(coarse_label_indices, cluster_labels)
    silhouette_avg = silhouette_score(all_features, cluster_labels)

    print(f"  Adjusted Rand Index (ARI): {ari_score:.4f}")
    print(f"  Normalized Mutual Info (NMI): {nmi_score:.4f}")
    print(f"  Silhouette Score: {silhouette_avg:.4f}")

    # 4. 可视化
    print("  Generating t-SNE plot...")
    plt.rcParams['font.family'] = 'SimHei'
    plt.rcParams['axes.unicode_minus'] = False

    # t-SNE 降维
    tsne = TSNE(n_components=2, random_state=42, perplexity=min(30, len(all_features) - 1))
    features_2d = tsne.fit_transform(all_features)

    # 创建画布
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8))
    fig.suptitle(f'Clustering Evaluation: {title_suffix}', fontsize=16)

    # 图1: 真实标签
    colors_true = plt.cm.get_cmap('tab20', len(unique_coarse_types))
    for i, coarse_type in enumerate(unique_coarse_types):
        mask = np.array(coarse_labels) == coarse_type
        ax1.scatter(features_2d[mask, 0], features_2d[mask, 1], color=colors_true(i), label=coarse_type, alpha=0.8,
                    s=40)
    ax1.set_title('Ground Truth (t-SNE)')
    ax1.grid(True, which='both', linestyle='--', linewidth=0.5)
    # 将图例放在图的右侧外部
    handles1, labels1 = ax1.get_legend_handles_labels()
    ax1.legend(handles1, labels1, title='Ground Truth', bbox_to_anchor=(1.05, 1), loc='upper left', borderaxespad=0.)

    # 图2: 聚类结果
    colors_pred = plt.cm.get_cmap('tab20', n_clusters)
    for i in range(n_clusters):
        mask = cluster_labels == i
        ax2.scatter(features_2d[mask, 0], features_2d[mask, 1], color=colors_pred(i), label=f'Cluster {i}', alpha=0.8,
                    s=40)
    ax2.set_title('KMeans Clustering (t-SNE)')
    ax2.grid(True, which='both', linestyle='--', linewidth=0.5)
    # 将图例放在图的右侧外部
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax2.legend(handles2, labels2, title='KMeans Clusters', bbox_to_anchor=(1.05, 1), loc='upper left', borderaxespad=0.)

    # 调整布局为图例腾出空间
    plt.subplots_adjust(right=0.75)
    plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
    print(f"  Plot saved to {plot_filename}")
    plt.close()

    return {
        'ari': ari_score,
        'nmi': nmi_score,
        'silhouette': silhouette_avg,
    }


def evaluate_coarse_grained_geometric(net, model_ids, attention_net, device):
    """
    验证任务1: 纯几何粗粒度的聚类 (w_C = 0) - 使用全分辨率图像
    """
    print("\n" + "=" * 50)
    print("  Running: Coarse-Grained Geometric Clustering Evaluation")
    print("  Downsample Factor: 1x (No downsampling), Semantic Weight (wC): 0.0")
    print("=" * 50)

    # 使用全分辨率图像以获得最佳特征
    data_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])

    all_features = []
    true_labels = []
    coarse_labels = []

    with torch.no_grad():
        for model_info in tqdm(model_ids, desc="Processing models (Coarse Geo)"):
            class_name = model_info['class_name']
            model_name = model_info['model_name']

            features_A, features_B = [], []
            # Corrected path to use the 'validation' set with full views
            base_path_model = f"./MBDViewDataset_noMBD/validation/{class_name}/{model_name}"

            # Load views for type A (orthographic, front-cull)
            for view_dir in range(6):
                # Filename format: {model_id}_{view_dir}_{view_type}_{cull_mode}.bmp
                img_path = f"{base_path_model}_{view_dir}_0_0.bmp"
                if os.path.exists(img_path):
                    img = Image.open(img_path).convert('RGB')
                    img_tensor = data_transform(img).unsqueeze(0).to(device)
                    feature = net(img_tensor)
                    features_A.append(feature)

            # Load views for type B (perspective, front-cull)
            for view_dir in range(6):
                img_path = f"{base_path_model}_{view_dir}_1_0.bmp"
                if os.path.exists(img_path):
                    img = Image.open(img_path).convert('RGB')
                    img_tensor = data_transform(img).unsqueeze(0).to(device)
                    feature = net(img_tensor)
                    features_B.append(feature)

            if not features_A or not features_B:
                continue

            avg_feature_A = torch.mean(torch.cat(features_A), dim=0)
            avg_feature_B = torch.mean(torch.cat(features_B), dim=0)

            attention_input = torch.cat((avg_feature_A, avg_feature_B)).unsqueeze(0)
            w_A, w_B = attention_net(attention_input).squeeze(0)

            final_feature = w_A * avg_feature_A + w_B * avg_feature_B

            all_features.append(final_feature.cpu().numpy())
            true_labels.append(model_info['class_id'])
            coarse_labels.append(classify_to_coarse_type(class_name, False))

    all_features = np.array(all_features)

    return _run_clustering_and_evaluation(
        all_features,
        true_labels,
        coarse_labels,
        title_suffix="Coarse-Grained Geometric (w_C=0)",
        plot_filename="clustering_coarse_geometric.png"
    )


def evaluate_fine_grained_geometric(net, model_ids, attention_net, device):
    """
    验证任务2: 纯几何细粒度的聚类 (w_C = 0)
    """
    print("\n" + "=" * 50)
    print("  Running: Fine-Grained Geometric Clustering Evaluation")
    print("  Downsample Factor: 1x (No downsampling), Semantic Weight (wC): 0.0")
    print("=" * 50)

    # No downsampling for fine-grained features
    data_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])

    all_features = []
    true_labels = []
    coarse_labels = []

    with torch.no_grad():
        for model_info in tqdm(model_ids, desc="Processing models (Fine Geo)"):
            class_name = model_info['class_name']
            model_name = model_info['model_name']

            features_A, features_B = [], []
            # Corrected path to use the 'validation' set with full views
            base_path_model = f"./MBDViewDataset_noMBD/validation/{class_name}/{model_name}"

            # Load views for type A (orthographic, front-cull)
            for view_dir in range(6):
                # Filename format: {model_id}_{view_dir}_{view_type}_{cull_mode}.bmp
                img_path = f"{base_path_model}_{view_dir}_0_0.bmp"
                if os.path.exists(img_path):
                    img = Image.open(img_path).convert('RGB')
                    img_tensor = data_transform(img).unsqueeze(0).to(device)
                    feature = net(img_tensor)
                    features_A.append(feature)

            # Load views for type B (perspective, front-cull)
            for view_dir in range(6):
                img_path = f"{base_path_model}_{view_dir}_1_0.bmp"
                if os.path.exists(img_path):
                    img = Image.open(img_path).convert('RGB')
                    img_tensor = data_transform(img).unsqueeze(0).to(device)
                    feature = net(img_tensor)
                    features_B.append(feature)

            if not features_A or not features_B:
                continue

            avg_feature_A = torch.mean(torch.cat(features_A), dim=0)
            avg_feature_B = torch.mean(torch.cat(features_B), dim=0)

            attention_input = torch.cat((avg_feature_A, avg_feature_B)).unsqueeze(0)
            w_A, w_B = attention_net(attention_input).squeeze(0)

            final_feature = w_A * avg_feature_A + w_B * avg_feature_B

            all_features.append(final_feature.cpu().numpy())
            true_labels.append(model_info['class_id'])
            coarse_labels.append(classify_to_coarse_type(class_name, False))

    all_features = np.array(all_features)

    return _run_clustering_and_evaluation(
        all_features,
        true_labels,
        coarse_labels,
        title_suffix="Fine-Grained Geometric (w_C=0)",
        plot_filename="clustering_fine_geometric.png"
    )


def evaluate_coarse_grained_semantic(net, model_ids, attention_net, device, w_C=0.8, downsample_factor=4):
    """
    验证任务3: 结合几何与语义的粗粒度聚类
    """
    print("\n" + "=" * 50)
    print("  Running: Coarse-Grained Semantic-Enhanced Clustering Evaluation")
    print(f"  Downsample Factor: {downsample_factor}x, Semantic Weight (wC): {w_C}")
    print("=" * 50)

    img_size = 224 // downsample_factor
    data_transform = transforms.Compose([
        transforms.Resize((img_size, img_size)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])

    all_features = []
    true_labels = []
    coarse_labels = []

    with torch.no_grad():
        for model_info in tqdm(model_ids, desc="Processing models (Coarse Sem-Geo)"):
            class_name = model_info['class_name']
            model_name = model_info['model_name']

            # 1. Get Geometric Features (A and B)
            features_A, features_B, features_C = [], [], []
            # Corrected path to use the 'validation' set with full views
            base_path_model = f"./MBDViewDataset_noMBD/validation/{class_name}/{model_name}"

            # Load views for type A (orthographic, front-cull)
            for view_dir in range(6):
                # Filename format: {model_id}_{view_dir}_{view_type}_{cull_mode}.bmp
                img_path = f"{base_path_model}_{view_dir}_0_0.bmp"
                if os.path.exists(img_path):
                    img = Image.open(img_path).convert('RGB')
                    img_tensor = data_transform(img).unsqueeze(0).to(device)
                    feature = net(img_tensor)
                    features_A.append(feature)

            # Load views for type B (perspective, front-cull)
            for view_dir in range(6):
                img_path = f"{base_path_model}_{view_dir}_1_0.bmp"
                if os.path.exists(img_path):
                    img = Image.open(img_path).convert('RGB')
                    img_tensor = data_transform(img).unsqueeze(0).to(device)
                    feature = net(img_tensor)
                    features_B.append(feature)

            if not features_A or not features_B:
                continue

            avg_feature_A = torch.mean(torch.cat(features_A), dim=0)
            avg_feature_B = torch.mean(torch.cat(features_B), dim=0)

            # 2. Get Semantic Feature (C)
            for view_dir in range(6):
                img_path = f"{base_path_model}_{view_dir}_0_1.bmp"
                if os.path.exists(img_path):
                    img = Image.open(img_path).convert('RGB')
                    img_tensor = data_transform(img).unsqueeze(0).to(device)
                    feature = net(img_tensor)
                    features_C.append(feature)

            if not features_C:
                continue

            avg_feature_C = torch.mean(torch.cat(features_C), dim=0)

            # 3. Combine features
            attention_input = torch.cat((avg_feature_A, avg_feature_B)).unsqueeze(0)
            w_A_raw, w_B_raw = attention_net(attention_input).squeeze(0)

            # Scale geometric weights
            w_A = (1 - w_C) * w_A_raw
            w_B = (1 - w_C) * w_B_raw

            final_feature = (w_A * avg_feature_A) + (w_B * avg_feature_B) + (w_C * avg_feature_C)

            all_features.append(final_feature.cpu().numpy())
            true_labels.append(model_info['class_id'])
            coarse_labels.append(classify_to_coarse_type(class_name, False))

    all_features = np.array(all_features)

    return _run_clustering_and_evaluation(
        all_features,
        true_labels,
        coarse_labels,
        title_suffix=f"Coarse-Grained Semantic-Geo (w_C={w_C})",
        plot_filename=f"clustering_coarse_semantic_wc_{w_C}.png"
    )


def main():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"Using {device} device.")

    # --- Load Models and Data ---
    # 1. Feature Extractor
    print("Loading feature extraction model (MBDNet34_hierarchical.pth)...")
    net = resnet34().to(device)
    net.load_state_dict(torch.load("./MBDNet34_hierarchical.pth", map_location=device))
    net.eval()

    # 2. Attention Network
    print("Loading attention network (HierarchicalLoss_attention.pth)...")
    loss_module = HierarchicalTripletLoss()
    loss_module.load_state_dict(torch.load("./HierarchicalLoss_attention.pth", map_location=device))
    attention_net = loss_module.attention_net.to(device)
    attention_net.eval()

    # 3. Model Info
    print("Loading model info from ./MBDViewDataset_noMBD/V directory...")
    data_dir = './MBDViewDataset_noMBD/V'
    model_ids = []
    class_names = sorted([d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d))])
    class_to_id = {name: i for i, name in enumerate(class_names)}

    for class_name in class_names:
        class_id = class_to_id[class_name]
        class_path = os.path.join(data_dir, class_name)

        # Use a set to store unique model names for this class
        unique_model_names = set()

        if os.path.isdir(class_path):
            for filename in os.listdir(class_path):
                if filename.endswith('.bmp'):
                    # Extract model name, e.g., "1215744.STL_4482" from "1215744.STL_4482_0_0_0.bmp"
                    parts = filename.split('_')
                    if len(parts) > 3:
                        model_name = '_'.join(parts[:-3])
                        unique_model_names.add(model_name)

        # Add the unique models to our list
        for model_name in sorted(list(unique_model_names)):
            model_ids.append({
                'class_name': class_name,
                'model_name': model_name,
                'class_id': class_id
            })

    print(f"Loaded info for {len(model_ids)} models from {len(class_names)} classes.")

    # --- Run Evaluations ---
    results = {}

    # Task 1
    results['coarse_geo'] = evaluate_coarse_grained_geometric(net, model_ids, attention_net, device)

    # Task 2
    results['fine_geo'] = evaluate_fine_grained_geometric(net, model_ids, attention_net, device)

    # Task 3
    results['coarse_sem'] = evaluate_coarse_grained_semantic(net, model_ids, attention_net, device)

    # --- Plot Final Comparison ---
    plot_summary_results(results)

    print("\nAll evaluations complete.")


def plot_summary_results(results):
    """
    绘制一个条形图来总结和比较不同评估任务的结果。
    """
    print("\n" + "=" * 50)
    print("  Generating Final Summary Plot...")
    print("=" * 50)

    labels = list(results.keys())
    ari_scores = [res['ari'] for res in results.values()]
    nmi_scores = [res['nmi'] for res in results.values()]
    silhouette_scores = [res['silhouette'] for res in results.values()]

    x = np.arange(len(labels))
    width = 0.25

    fig, ax = plt.subplots(figsize=(14, 8))
    rects1 = ax.bar(x - width, ari_scores, width, label='ARI', color='skyblue')
    rects2 = ax.bar(x, nmi_scores, width, label='NMI', color='lightgreen')
    rects3 = ax.bar(x + width, silhouette_scores, width, label='Silhouette', color='salmon')

    # Add some text for labels, title and axes ticks
    ax.set_ylabel('Scores')
    ax.set_title('Comparison of Clustering Evaluation Metrics')
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.legend()
    ax.grid(axis='y', linestyle='--', alpha=0.7)

    def autolabel(rects):
        """Attach a text label above each bar in *rects*, displaying its height."""
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height:.3f}',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom')

    autolabel(rects1)
    autolabel(rects2)
    autolabel(rects3)

    fig.tight_layout()
    plt.savefig('clustering_summary_comparison.png', dpi=300)
    print("  Summary plot saved to clustering_summary_comparison.png")
    plt.close()


if __name__ == '__main__':
    main()