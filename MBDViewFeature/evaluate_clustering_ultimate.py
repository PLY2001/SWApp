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

from model_ultimate import UltimateFusionModel
from model_transformer_fusion import TransformerFusionModel as TransformerEncoderModel
from jvlei import classify_to_coarse_type

import matplotlib.ticker as mticker
from matplotlib.legend import Legend # CRITICAL IMPORT for this solution


def _run_clustering_and_evaluation(all_features, true_labels, coarse_labels, title_suffix, plot_filename):
    """
    辅助函数：执行聚类、评估和可视化（通过为每行创建独立的图例对象实现真正的文本流效果，并进行精细调整）。
    """
    PLOT_FONT_SIZE = 30
    # ... (Steps 1, 2, 3: Clustering and Metrics remain unchanged) ...
    unique_coarse_types = sorted(list(set(coarse_labels)))
    coarse_label_map = {label: idx for idx, label in enumerate(unique_coarse_types)}
    coarse_label_indices = [coarse_label_map[label] for label in coarse_labels]
    n_clusters = len(unique_coarse_types)
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(all_features)
    ari_score = adjusted_rand_score(coarse_label_indices, cluster_labels)
    nmi_score = normalized_mutual_info_score(coarse_label_indices, cluster_labels)
    silhouette_avg = silhouette_score(all_features, cluster_labels)
    print(f"  Clustering results: ARI={ari_score:.4f}, NMI={nmi_score:.4f}, Silhouette={silhouette_avg:.4f}")
    # ... (Step 4: Visualization setup remains unchanged) ...
    print("  Generating t-SNE plot...")
    plt.rcParams['font.family'] = 'Times New Roman'
    plt.rcParams['axes.unicode_minus'] = True
    plt.rcParams['font.size'] = PLOT_FONT_SIZE
    tsne = TSNE(n_components=2, random_state=42, perplexity=min(30, len(all_features) - 1))
    features_2d = tsne.fit_transform(all_features)
    fig, ax1 = plt.subplots(1, 1, figsize=(10, 10))
    # ... (Plot drawing part remains unchanged) ...
    x_min, x_max = features_2d[:, 0].min(), features_2d[:, 0].max()
    y_min, y_max = features_2d[:, 1].min(), features_2d[:, 1].max()
    max_range = max(x_max - x_min, y_max - y_min)
    margin = max_range * 0.05
    x_center = (x_min + x_max) / 2
    y_center = (y_min + y_max) / 2
    ax1.set_xlim(x_center - max_range / 2 - margin, x_center + max_range / 2 + margin)
    ax1.set_ylim(y_center - max_range / 2 - margin, y_center + max_range / 2 + margin)
    markers = ['o', 's', 'v', '^', '<', '>', 'p', '*', 'h', 'H', 'D', 'd', 'P', 'X']
    colors_true = plt.cm.get_cmap('nipy_spectral', len(unique_coarse_types))
    for i, coarse_type in enumerate(unique_coarse_types):
        mask = np.array(coarse_labels) == coarse_type
        ax1.scatter(features_2d[mask, 0], features_2d[mask, 1],
                    color=colors_true(i), marker=markers[i % len(markers)], label=coarse_type,
                    alpha=0.8, s=100, edgecolors='k', linewidths=0.5)
    # ... (Axis setup remains unchanged) ...
    #ax1.set_title(f'Ground Truth (t-SNE): {title_suffix}', fontsize=PLOT_FONT_SIZE, pad=20)
    ax1.grid(False)
    ax1.set_aspect('equal', adjustable='box')
    for spine in ax1.spines.values(): spine.set_linewidth(1.5)
    ax1.tick_params(axis='both', which='major', direction='in', length=6, width=1.5)
    ax1.xaxis.set_major_locator(mticker.MaxNLocator(nbins=5, prune='both'))
    ax1.yaxis.set_major_locator(mticker.MaxNLocator(nbins=5, prune='both'))

    # --- MODIFIED (v7): Fine-Tuning the "Multiple Legends" Layout ---
    handles, labels = ax1.get_legend_handles_labels()

    # === PARAMETER TUNING SECTION ===
    items_per_row = 6
    legend_title = ''

    # 1. To move the whole legend block down, DECREASE these values.
    title_y_pos = -0.2  # Vertical position of the title (was 0.2)
    first_row_y_pos = -0.2  # Vertical position of the first legend row (was 0.15)

    # 2. To INCREASE vertical space between rows, INCREASE this value.
    row_height = 0.1  # Height to step down for each new row (was 0.05)

    # 3. To DECREASE horizontal space between items, DECREASE this value.
    horizontal_spacing = 0.0  # `columnspacing` value (was 0.8)
    # ================================

    # 1. Add the main title manually
    fig.text(0.5, title_y_pos, legend_title,
             ha='center', va='center', fontsize=PLOT_FONT_SIZE, family='Times New Roman')

    # 2. Process and add each row as a separate legend
    y_offset = first_row_y_pos
    for i in range(0, len(handles), items_per_row):
        handle_chunk = handles[i:i + items_per_row]
        label_chunk = labels[i:i + items_per_row]

        formatted_labels = []
        for j, label in enumerate(label_chunk):
            global_index = i + j

            # Add a semicolon if it is NOT the very last item in the entire legend
            if global_index < len(handles) - 1:
                formatted_labels.append(f"{label};")
            else:
                formatted_labels.append(label)

        row_legend = Legend(ax1, handle_chunk, formatted_labels,
                            loc='upper center',
                            bbox_to_anchor=(0.5, y_offset),
                            ncol=len(handle_chunk),
                            frameon=False,
                            fontsize=PLOT_FONT_SIZE,
                            handletextpad=0.5,
                            columnspacing=horizontal_spacing,  # Using the new tuned value
                            )

        fig.add_artist(row_legend)
        y_offset -= row_height  # Using the new tuned value

    # 3. Adjust layout to reserve space for the legend.
    # You may need to increase this if you add more rows or increase row_height.
    fig.subplots_adjust(bottom=0.25)

    plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
    print(f"  Plot saved to {plot_filename}")
    plt.close()

    return {'ari': ari_score, 'nmi': nmi_score, 'silhouette': silhouette_avg}


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
            
            # Load all 6 views for type A
            views_A = []
            for view_dir in range(6):
                img_path = f"{base_path_model}_{view_dir}_0_0.bmp"
                img = Image.open(img_path).convert('RGB') if os.path.exists(img_path) else Image.new('RGB', (224, 224), 'black')
                views_A.append(data_transform(img))
            
            views_A_tensor = torch.stack(views_A).unsqueeze(0).to(device) # Add batch dimension
            
            # Get the fused embedding directly from the model
            # In eval mode, UltimateFusionModel returns the embedding
            # MODIFIED: The model returns a tuple, get the first element for features.
            final_feature = net_A(views_A_tensor).squeeze()

            all_features.append(final_feature.cpu().numpy())
            true_labels.append(model_info['class_id'])
            coarse_labels.append(classify_to_coarse_type(class_name, False))

    all_features = np.array(all_features)

    return _run_clustering_and_evaluation(
        all_features,
        true_labels,
        coarse_labels,
        title_suffix="Coarse-Grained Geometric (net_A, Ultimate)",
        plot_filename="clustering_ultimate_coarse_geometric.png"
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

            # Load all 6 views for type B
            views_B = []
            for view_dir in range(6):
                img_path = f"{base_path_model}_{view_dir}_1_0.bmp"
                img = Image.open(img_path).convert('RGB') if os.path.exists(img_path) else Image.new('RGB', (224, 224), 'black')
                views_B.append(data_transform(img))

            views_B_tensor = torch.stack(views_B).unsqueeze(0).to(device)
            
            # Get the fused embedding from net_B
            final_feature = net_B(views_B_tensor).squeeze()

            all_features.append(final_feature.cpu().numpy())
            true_labels.append(model_info['class_id'])
            coarse_labels.append(classify_to_coarse_type(class_name, False))

    all_features = np.array(all_features)

    return _run_clustering_and_evaluation(
        all_features,
        true_labels,
        coarse_labels,
        title_suffix="Fine-Grained Geometric (net_B, Ultimate)",
        plot_filename="clustering_ultimate_fine_geometric.png"
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

            # Get fused feature from net_A
            views_A = []
            for view_dir in range(6):
                img_path = f"{base_path_model}_{view_dir}_0_0.bmp"
                img = Image.open(img_path).convert('RGB') if os.path.exists(img_path) else Image.new('RGB', (224, 224), 'black')
                views_A.append(data_transform(img))
            views_A_tensor = torch.stack(views_A).unsqueeze(0).to(device)
            feature_A = net_A(views_A_tensor)[0].squeeze()

            # Get fused feature from net_B
            views_B = []
            for view_dir in range(6):
                img_path = f"{base_path_model}_{view_dir}_1_0.bmp"
                img = Image.open(img_path).convert('RGB') if os.path.exists(img_path) else Image.new('RGB', (224, 224), 'black')
                views_B.append(data_transform(img))
            views_B_tensor = torch.stack(views_B).unsqueeze(0).to(device)
            feature_B = net_B(views_B_tensor).squeeze()

            # Combine features with equal weight
            final_feature = 0.4 * feature_A + 0.6 * feature_B

            all_features.append(final_feature.cpu().numpy())
            true_labels.append(model_info['class_id'])
            coarse_labels.append(classify_to_coarse_type(class_name, False))

    all_features = np.array(all_features)

    return _run_clustering_and_evaluation(
        all_features,
        true_labels,
        coarse_labels,
        title_suffix="Multi-Grained Geometric (net_A + net_B, Ultimate)",
        plot_filename="clustering_ultimate_multi_geometric.png"
    )


def evaluate_coarse_grained_semantic(net_C1, model_ids, device):
    """
    验证任务: 纯语义粗粒度的聚类 (使用 net_C1)
    """
    print("\n" + "=" * 50)
    print("  Running: Coarse-Grained Semantic Clustering (net_C1)")
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
        for model_info in tqdm(model_ids, desc="Processing models (Coarse Sem)"):
            class_name = model_info['class_name']
            model_name = model_info['model_name']
            base_path_model = f"./MBDViewDataset_noMBD/validation/{class_name}/{model_name}"
            
            # Load all 6 views for type C1
            views_C1 = []
            for view_dir in range(6):
                img_path = f"{base_path_model}_{view_dir}_0_1.bmp" # Changed from _0_0 to _0_1
                img = Image.open(img_path).convert('RGB') if os.path.exists(img_path) else Image.new('RGB', (224, 224), 'black')
                views_C1.append(data_transform(img))
            
            views_C1_tensor = torch.stack(views_C1).unsqueeze(0).to(device)
            
            final_feature = net_C1(views_C1_tensor).squeeze()

            all_features.append(final_feature.cpu().numpy())
            true_labels.append(model_info['class_id'])
            coarse_labels.append(classify_to_coarse_type(class_name, False))

    all_features = np.array(all_features)

    return _run_clustering_and_evaluation(
        all_features,
        true_labels,
        coarse_labels,
        title_suffix="Coarse-Grained Semantic (net_C1, Ultimate)",
        plot_filename="clustering_ultimate_coarse_semantic.png"
    )


def evaluate_fine_grained_semantic(net_C2, model_ids, device):
    """
    验证任务: 纯语义细粒度的聚类 (使用 net_C2)
    """
    print("\n" + "=" * 50)
    print("  Running: Fine-Grained Semantic Clustering (net_C2)")
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
        for model_info in tqdm(model_ids, desc="Processing models (Fine Sem)"):
            class_name = model_info['class_name']
            model_name = model_info['model_name']
            base_path_model = f"./MBDViewDataset_noMBD/validation/{class_name}/{model_name}"

            # Load all 6 views for type C2
            views_C2 = []
            for view_dir in range(6):
                img_path = f"{base_path_model}_{view_dir}_1_1.bmp" # Changed from _1_0 to _1_1
                img = Image.open(img_path).convert('RGB') if os.path.exists(img_path) else Image.new('RGB', (224, 224), 'black')
                views_C2.append(data_transform(img))

            views_C2_tensor = torch.stack(views_C2).unsqueeze(0).to(device)
            
            final_feature = net_C2(views_C2_tensor).squeeze()

            all_features.append(final_feature.cpu().numpy())
            true_labels.append(model_info['class_id'])
            coarse_labels.append(classify_to_coarse_type(class_name, False))

    all_features = np.array(all_features)

    return _run_clustering_and_evaluation(
        all_features,
        true_labels,
        coarse_labels,
        title_suffix="Fine-Grained Semantic (net_C2, Ultimate)",
        plot_filename="clustering_ultimate_fine_semantic.png"
    )


def evaluate_multi_grained_semantic(net_C1, net_C2, model_ids, device):
    """
    验证任务: 纯语义多粒度融合的聚类 (使用 net_C1 和 net_C2)
    """
    print("\n" + "=" * 50)
    print("  Running: Multi-Grained Semantic Clustering (net_C1 + net_C2)")
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
        for model_info in tqdm(model_ids, desc="Processing models (Multi Sem)"):
            class_name = model_info['class_name']
            model_name = model_info['model_name']
            base_path_model = f"./MBDViewDataset_noMBD/validation/{class_name}/{model_name}"

            # Get fused feature from net_C1
            views_C1 = []
            for view_dir in range(6):
                img_path = f"{base_path_model}_{view_dir}_0_1.bmp" # Changed from _0_0 to _0_1
                img = Image.open(img_path).convert('RGB') if os.path.exists(img_path) else Image.new('RGB', (224, 224), 'black')
                views_C1.append(data_transform(img))
            views_C1_tensor = torch.stack(views_C1).unsqueeze(0).to(device)
            feature_C1 = net_C1(views_C1_tensor)[0].squeeze()

            # Get fused feature from net_C2
            views_C2 = []
            for view_dir in range(6):
                img_path = f"{base_path_model}_{view_dir}_1_1.bmp" # Changed from _1_0 to _1_1
                img = Image.open(img_path).convert('RGB') if os.path.exists(img_path) else Image.new('RGB', (224, 224), 'black')
                views_C2.append(data_transform(img))
            views_C2_tensor = torch.stack(views_C2).unsqueeze(0).to(device)
            feature_C2 = net_C2(views_C2_tensor).squeeze()

            # Combine features with same weight as geometric
            final_feature = 0.4 * feature_C1 + 0.6 * feature_C2

            all_features.append(final_feature.cpu().numpy())
            true_labels.append(model_info['class_id'])
            coarse_labels.append(classify_to_coarse_type(class_name, False))

    all_features = np.array(all_features)

    return _run_clustering_and_evaluation(
        all_features,
        true_labels,
        coarse_labels,
        title_suffix="Multi-Grained Semantic (net_C1 + net_C2, Ultimate)",
        plot_filename="clustering_ultimate_multi_semantic.png"
    )


def evaluate_multi_level_multi_grained(net_A, net_B, net_C1, net_C2, model_ids, device, w_geo_coarse=0.4, w_geo_fine=0.6, w_sem_coarse=0.4, w_sem_fine=0.6, w_sem_vs_geo=0.5):
    """
    验证任务: 多层次多粒度融合聚类 (几何 + 语义)
    """
    print("\n" + "=" * 50)
    print("  Running: Multi-Level & Multi-Grained Clustering")
    print(f"  Weights: Geo(c:{w_geo_coarse}, f:{w_geo_fine}), Sem(c:{w_sem_coarse}, f:{w_sem_fine}), Sem-vs-Geo:{w_sem_vs_geo}")
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
        for model_info in tqdm(model_ids, desc="Processing models (Multi-Level)"):
            class_name = model_info['class_name']
            model_name = model_info['model_name']
            base_path_model = f"./MBDViewDataset_noMBD/validation/{class_name}/{model_name}"

            # --- Geometric Features ---
            views_A = []
            for view_dir in range(6):
                img_path = f"{base_path_model}_{view_dir}_0_0.bmp"
                img = Image.open(img_path).convert('RGB') if os.path.exists(img_path) else Image.new('RGB', (224, 224), 'black')
                views_A.append(data_transform(img))
            feature_A = net_A(torch.stack(views_A).unsqueeze(0).to(device))[0].squeeze()

            views_B = []
            for view_dir in range(6):
                img_path = f"{base_path_model}_{view_dir}_1_0.bmp"
                img = Image.open(img_path).convert('RGB') if os.path.exists(img_path) else Image.new('RGB', (224, 224), 'black')
                views_B.append(data_transform(img))
            feature_B = net_B(torch.stack(views_B).unsqueeze(0).to(device)).squeeze()
            
            feature_geometric_fused = (1 - w_geo_fine) * feature_A + w_geo_fine * feature_B

            # --- Semantic Features ---
            views_C1 = []
            for view_dir in range(6):
                img_path = f"{base_path_model}_{view_dir}_0_1.bmp"
                img = Image.open(img_path).convert('RGB') if os.path.exists(img_path) else Image.new('RGB', (224, 224), 'black')
                views_C1.append(data_transform(img))
            feature_C1 = net_C1(torch.stack(views_C1).unsqueeze(0).to(device))[0].squeeze()

            views_C2 = []
            for view_dir in range(6):
                img_path = f"{base_path_model}_{view_dir}_1_1.bmp"
                img = Image.open(img_path).convert('RGB') if os.path.exists(img_path) else Image.new('RGB', (224, 224), 'black')
                views_C2.append(data_transform(img))
            feature_C2 = net_C2(torch.stack(views_C2).unsqueeze(0).to(device)).squeeze()

            feature_semantic_fused = (1- w_sem_fine) * feature_C1 + w_sem_fine * feature_C2

            # --- Final Fusion ---
            final_feature = (1 - w_sem_vs_geo) * feature_geometric_fused + w_sem_vs_geo * feature_semantic_fused

            all_features.append(final_feature.cpu().numpy())
            true_labels.append(model_info['class_id'])
            coarse_labels.append(classify_to_coarse_type(class_name, False))

    all_features = np.array(all_features)

    return _run_clustering_and_evaluation(
        all_features,
        true_labels,
        coarse_labels,
        title_suffix=f"Multi-Level Fusion (w_sem={w_sem_vs_geo})",
        plot_filename=f"clustering_ultimate_multi_level_fusion_w_sem_{w_sem_vs_geo}.png"
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
    ax.set_title('Comparison of Clustering Evaluation Metrics (Ultimate Model)')
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
    plt.savefig('clustering_summary_ultimate.png', dpi=300)
    print("  Summary plot saved to clustering_summary_ultimate.png")
    plt.close()


def main():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"Using {device} device.")

    # --- Determine num_classes from dataset ---
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
    print("Loading ultimate models...")
    net_A = UltimateFusionModel(num_classes=num_classes).to(device)
    net_B = TransformerEncoderModel(num_classes=None).to(device)
    net_C1 = UltimateFusionModel(num_classes=num_classes).to(device)
    net_C2 = TransformerEncoderModel(num_classes=None).to(device)
    
    path_A = "./MBDNet34_ultimate_A.pth"
    path_B = "./MBDNet34_ultimate_B.pth"
    path_C1 = "./MBDNet34_ultimate_C1.pth"
    path_C2 = "./MBDNet34_ultimate_C2.pth"

    if not all(os.path.exists(p) for p in [path_A, path_B, path_C1, path_C2]):
        print(f"Error: One or more model weights not found. Please ensure all .pth files exist.")
        return

    net_A.load_state_dict(torch.load(path_A, map_location=device))
    net_B.load_state_dict(torch.load(path_B, map_location=device))
    net_C1.load_state_dict(torch.load(path_C1, map_location=device))
    net_C2.load_state_dict(torch.load(path_C2, map_location=device))
    
    net_A.eval()
    net_B.eval()
    net_C1.eval()
    net_C2.eval()
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
    
    results['coarse_sem'] = evaluate_coarse_grained_semantic(net_C1, model_ids, device)
    results['fine_sem'] = evaluate_fine_grained_semantic(net_C2, model_ids, device)
    results['multi_sem'] = evaluate_multi_grained_semantic(net_C1, net_C2, model_ids, device)

    results['multi_level'] = evaluate_multi_level_multi_grained(net_A, net_B, net_C1, net_C2, model_ids, device)

    # --- Plot Final Comparison ---
    plot_summary_results(results)

    print("\nAll evaluations complete.")


if __name__ == '__main__':
    main()
