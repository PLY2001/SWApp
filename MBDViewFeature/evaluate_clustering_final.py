import os
import numpy as np
import torch
from torchvision import transforms
from PIL import Image
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score, silhouette_score
from sklearn.manifold import TSNE
from tqdm import tqdm

from model import resnet34
from model_dual_output import resnet34_dual_output
from jvlei import classify_to_coarse_type


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

    tsne = TSNE(n_components=2, random_state=42, perplexity=min(30, len(all_features) - 1))
    features_2d = tsne.fit_transform(all_features)

    fig, ax1 = plt.subplots(1, 1, figsize=(12, 10))
    markers = ['o', 's', 'v', '^', '<', '>', 'p', '*', 'h', 'H', 'D', 'd', 'P', 'X']
    num_markers = len(markers)

    colors_true = plt.cm.get_cmap('nipy_spectral', len(unique_coarse_types))
    for i, coarse_type in enumerate(unique_coarse_types):
        mask = np.array(coarse_labels) == coarse_type
        marker = markers[i % num_markers]
        ax1.scatter(features_2d[mask, 0], features_2d[mask, 1],
                    color=colors_true(i),
                    marker=marker,
                    label=coarse_type,
                    alpha=0.8,
                    s=50,
                    edgecolors='k',
                    linewidths=0.5)
    ax1.set_title(f'Ground Truth (t-SNE): {title_suffix}')
    ax1.grid(True, which='both', linestyle='--', linewidth=0.5)
    handles1, labels1 = ax1.get_legend_handles_labels()
    ax1.legend(handles1, labels1, title='Ground Truth', bbox_to_anchor=(1.05, 1), loc='upper left', borderaxespad=0.)

    plt.subplots_adjust(right=0.7)
    plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
    print(f"  Plot saved to {plot_filename}")
    plt.close()

    return {
        'ari': ari_score,
        'nmi': nmi_score,
        'silhouette': silhouette_avg,
    }


def evaluate_coarse_grained_geometric(net_A, model_ids, device):
    """
    验证任务1: 纯几何粗粒度的聚类 (使用 net_A)
    """
    print("\n" + "=" * 50)
    print("  Running: Coarse-Grained Geometric Clustering (net_A)")
    print("=" * 50)

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
            base_path_model = f"./MBDViewDataset_noMBD/validation/{class_name}/{model_name}"
            
            # Load and average features from all 6 views for type A
            model_features = []
            for view_dir in range(6):
                img_path = f"{base_path_model}_{view_dir}_0_0.bmp"
                if os.path.exists(img_path):
                    img = Image.open(img_path).convert('RGB')
                    img_tensor = data_transform(img).unsqueeze(0).to(device)
                    # net_A returns (embedding, logits), we need the embedding
                    feature = net_A(img_tensor)[0].squeeze()
                    model_features.append(feature)
            
            if not model_features:
                continue
            
            # Average the features
            final_feature = torch.stack(model_features).mean(dim=0)

            all_features.append(final_feature.cpu().numpy())
            true_labels.append(model_info['class_id'])
            coarse_labels.append(classify_to_coarse_type(class_name, False))

    all_features = np.array(all_features)

    return _run_clustering_and_evaluation(
        all_features,
        true_labels,
        coarse_labels,
        title_suffix="Coarse-Grained Geometric (net_A, Final)",
        plot_filename="clustering_final_coarse_geometric.png"
    )


def evaluate_fine_grained_geometric(net_B, model_ids, device):
    """
    验证任务2: 纯几何细粒度的聚类 (使用 net_B)
    """
    print("\n" + "=" * 50)
    print("  Running: Fine-Grained Geometric Clustering (net_B)")
    print("=" * 50)

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
            base_path_model = f"./MBDViewDataset_noMBD/validation/{class_name}/{model_name}"

            # Load and average features from all 6 views for type B
            model_features = []
            for view_dir in range(6):
                img_path = f"{base_path_model}_{view_dir}_1_0.bmp"
                if os.path.exists(img_path):
                    img = Image.open(img_path).convert('RGB')
                    img_tensor = data_transform(img).unsqueeze(0).to(device)
                    feature = net_B(img_tensor).squeeze()
                    model_features.append(feature)

            if not model_features:
                continue
            
            # Average the features
            final_feature = torch.stack(model_features).mean(dim=0)

            all_features.append(final_feature.cpu().numpy())
            true_labels.append(model_info['class_id'])
            coarse_labels.append(classify_to_coarse_type(class_name, False))

    all_features = np.array(all_features)

    return _run_clustering_and_evaluation(
        all_features,
        true_labels,
        coarse_labels,
        title_suffix="Fine-Grained Geometric (net_B, Final)",
        plot_filename="clustering_final_fine_geometric.png"
    )


def evaluate_multi_grained_geometric(net_A, net_B, model_ids, device):
    """
    验证任务3: 纯几何多粒度融合的聚类 (使用 net_A 和 net_B)
    """
    print("\n" + "=" * 50)
    print("  Running: Multi-Grained Geometric Clustering (net_A + net_B)")
    print("=" * 50)

    data_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])

    all_features = []
    true_labels = []
    coarse_labels = []

    with torch.no_grad():
        for model_info in tqdm(model_ids, desc="Processing models (Multi Geo)"):
            class_name = model_info['class_name']
            model_name = model_info['model_name']
            base_path_model = f"./MBDViewDataset_noMBD/validation/{class_name}/{model_name}"

            # Load and average features for type A (orthographic) -> net_A
            features_A = []
            for view_dir in range(6):
                img_path = f"{base_path_model}_{view_dir}_0_0.bmp"
                if os.path.exists(img_path):
                    img = Image.open(img_path).convert('RGB')
                    img_tensor = data_transform(img).unsqueeze(0).to(device)
                    features_A.append(net_A(img_tensor)[0].squeeze())
            
            # Load and average features for type B (perspective) -> net_B
            features_B = []
            for view_dir in range(6):
                img_path = f"{base_path_model}_{view_dir}_1_0.bmp"
                if os.path.exists(img_path):
                    img = Image.open(img_path).convert('RGB')
                    img_tensor = data_transform(img).unsqueeze(0).to(device)
                    features_B.append(net_B(img_tensor).squeeze())

            if not features_A or not features_B:
                continue

            feature_A = torch.stack(features_A).mean(dim=0)
            feature_B = torch.stack(features_B).mean(dim=0)

            # Combine features with equal weight
            final_feature = 0.5 * feature_A + 0.5 * feature_B

            all_features.append(final_feature.cpu().numpy())
            true_labels.append(model_info['class_id'])
            coarse_labels.append(classify_to_coarse_type(class_name, False))

    all_features = np.array(all_features)

    return _run_clustering_and_evaluation(
        all_features,
        true_labels,
        coarse_labels,
        title_suffix="Multi-Grained Geometric (net_A + net_B, Final)",
        plot_filename="clustering_final_multi_geometric.png"
    )


def evaluate_coarse_grained_semantic(net_A, net_B, model_ids, device, w_C=0.3):
    """
    验证任务4: 结合几何与语义的细粒度聚类
    """
    print("\n" + "=" * 50)
    print("  Running: Coarse-Grained Semantic-Enhanced Clustering Evaluation")
    print(f"  Semantic Weight (wC): {w_C}")
    print("=" * 50)

    data_transform = transforms.Compose([
        transforms.Resize((224, 224)),
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
            base_path_model = f"./MBDViewDataset_noMBD/validation/{class_name}/{model_name}"

            # Geo-Coarse feature from net_A on ortho views (average)
            features_A = []
            for view_dir in range(6):
                img_path = f"{base_path_model}_{view_dir}_0_0.bmp"
                if os.path.exists(img_path):
                    img = Image.open(img_path).convert('RGB')
                    img_tensor = data_transform(img).unsqueeze(0).to(device)
                    features_A.append(net_A(img_tensor)[0].squeeze())

            # Geo-Fine feature from net_B on perspective views (average)
            features_B = []
            for view_dir in range(6):
                img_path = f"{base_path_model}_{view_dir}_1_0.bmp"
                if os.path.exists(img_path):
                    img = Image.open(img_path).convert('RGB')
                    img_tensor = data_transform(img).unsqueeze(0).to(device)
                    features_B.append(net_B(img_tensor).squeeze())

            # Semantic feature from net_A on ortho, back-cull views (average)
            features_C = []
            for view_dir in range(6):
                img_path = f"{base_path_model}_{view_dir}_0_1.bmp"
                if os.path.exists(img_path):
                    img = Image.open(img_path).convert('RGB')
                    img_tensor = data_transform(img).unsqueeze(0).to(device)
                    features_C.append(net_A(img_tensor)[0].squeeze())

            if not features_A or not features_B or not features_C:
                continue

            feature_A = torch.stack(features_A).mean(dim=0)
            feature_B = torch.stack(features_B).mean(dim=0)
            feature_C = torch.stack(features_C).mean(dim=0)

            # Combine features using the specified weights
            w_A_raw = 0.715
            w_B_raw = 0.285
            
            feature_geometric = w_A_raw * feature_A + w_B_raw * feature_B
            final_feature = (1 - w_C) * feature_geometric + w_C * feature_C

            all_features.append(final_feature.cpu().numpy())
            true_labels.append(model_info['class_id'])
            coarse_labels.append(classify_to_coarse_type(class_name, False))

    all_features = np.array(all_features)

    return _run_clustering_and_evaluation(
        all_features,
        true_labels,
        coarse_labels,
        title_suffix=f"Coarse-Grained Semantic-Geo (w_C={w_C}, Final)",
        plot_filename=f"clustering_final_coarse_semantic_wc_{w_C}.png"
    )


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

    ax.set_ylabel('Scores')
    ax.set_title('Comparison of Clustering Evaluation Metrics (Final Model)')
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.legend()
    ax.grid(axis='y', linestyle='--', alpha=0.7)

    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height:.3f}',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom')

    autolabel(rects1)
    autolabel(rects2)
    autolabel(rects3)

    fig.tight_layout()
    plt.savefig('clustering_summary_final.png', dpi=300)
    print("  Summary plot saved to clustering_summary_final.png")
    plt.close()


def main():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"Using {device} device.")

    # --- Determine num_classes from dataset ---
    # This is needed to initialize the model correctly.
    data_dir_for_classes = './MBDViewDataset_noMBD/train'
    if not os.path.exists(data_dir_for_classes):
        print(f"Warning: Training directory not found at '{data_dir_for_classes}'. Falling back to validation dir.")
        data_dir_for_classes = './MBDViewDataset_noMBD/validation'
        if not os.path.exists(data_dir_for_classes):
            print(f"Error: Neither train nor validation directory found to determine class count.")
            return
            
    class_names_for_model = sorted([d for d in os.listdir(data_dir_for_classes) if os.path.isdir(os.path.join(data_dir_for_classes, d))])
    num_classes = len(class_names_for_model)
    if num_classes == 0:
        print("Error: No classes found in the dataset directory.")
        return
    print(f"Found {num_classes} classes. Initializing models...")

    # --- Load Models ---
    print("Loading final models...")
    net_A = resnet34_dual_output(num_classes=num_classes).to(device)
    net_B = resnet34(num_classes=num_classes).to(device)
    
    path_A = "./MBDNet34_final_A.pth"
    path_B = "./MBDNet34_final_B.pth"

    if not os.path.exists(path_A) or not os.path.exists(path_B):
        print(f"Error: Model weights not found. Please ensure '{path_A}' and '{path_B}' exist.")
        return

    net_A.load_state_dict(torch.load(path_A, map_location=device))
    net_B.load_state_dict(torch.load(path_B, map_location=device))
    net_A.eval()
    net_B.eval()
    print("Models loaded successfully.")

    # --- Load Model Info ---
    print("Loading model info from validation directory...")
    data_dir = './MBDViewDataset_noMBD/V'
    model_ids = []
    class_names = sorted([d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d))])
    class_to_id = {name: i for i, name in enumerate(class_names)}

    for class_name in class_names:
        class_id = class_to_id[class_name]
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
            model_ids.append({
                'class_name': class_name,
                'model_name': model_name,
                'class_id': class_id
            })

    print(f"Loaded info for {len(model_ids)} models from {len(class_names)} classes.")

    # --- Run Evaluations ---
    results = {}
    results['coarse_geo'] = evaluate_coarse_grained_geometric(net_A, model_ids, device)
    results['fine_geo'] = evaluate_fine_grained_geometric(net_B, model_ids, device)
    results['multi_geo'] = evaluate_multi_grained_geometric(net_A, net_B, model_ids, device)
    results['coarse_sem'] = evaluate_coarse_grained_semantic(net_A, net_B, model_ids, device)

    # --- Plot Final Comparison ---
    plot_summary_results(results)

    print("\nAll evaluations complete.")


if __name__ == '__main__':
    main()
