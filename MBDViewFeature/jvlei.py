import os
import json
import sys
import matplotlib
import torch
from PIL import Image
from torchvision import transforms
import matplotlib.pyplot as plt
import torchvision
from model import resnet34
from tqdm import tqdm
import torch.nn.functional as F
import numpy as np
import re
import math
from collections import defaultdict
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score, silhouette_score
import seaborn as sns
from sklearn.manifold import TSNE
from sklearn.decomposition import PCA
def classify_to_coarse_type(class_name, culidu):
    """
    将具体的零件类型归类到粗粒度类型
    """
    # 转换为小写便于匹配
    name_lower = class_name.lower()

    if culidu is False:
        return name_lower

    # 管件 (Pipe Parts)
    pipe_parts = [
        'simple pipes',  # 直管
        'intersecting pipes',  # 交叉管道
        '90 degree elbows',  # 90度弯头
        'non-90 degree elbows',  # 非90度弯头
        'nozzle'  # 喷嘴
    ]

    for category in pipe_parts:
        if category in name_lower:
            return 'Pipe Parts'

    # 紧固件 - 螺钉螺栓销类 (Screws and Bolts)
    screws_bolts = [
        'screws and bolts with countersunk head',  # 沉头螺钉螺栓
        'screws and bolts with cylindrical head',  # 圆柱头螺钉螺栓
        'screws and bolts with hexagonal head',  # 六角头螺钉螺栓
        'setscrew',  # 紧定螺钉
        'tapping screws',  # 自攻螺钉
        'threaded rods',  # 螺杆
        'studs',  # 双头螺柱
        'eye screws',  # 吊环螺钉
        'articulations, eyelets and other articulated joints',  # 关节、吊环及其他铰接关节
        'bolt like parts',  # 螺栓类零件
        'socket',  # 插座
        'conventional rivets',  # 普通铆钉
        'bushes',  # 衬套
        'washer bolt'
    ]

    for category in screws_bolts:
        if category in name_lower:
            return 'Screws and Bolts'

    # 紧固件 - 销 (Pins)
    pins = [
        'cylindrical pins',  # 圆柱销
        'grooved pins',  # 开槽销
        'roll pins',  # 弹性圆柱销
        'split pins',  # 开口销
        'taper pins',  # 圆锥销
        'plain guidings',  # 滑动导向
        'posts'  # 柱销
    ]

    for category in pins:
        if category in name_lower:
            return 'Pins'

    # 紧固件 - 螺母类 (Nuts)
    nuts = [
        'cap nuts',  # 盖型螺母
        'castle nuts',  # 槽型螺母
        'flange nut',  # 法兰螺母
        'hexagonal nuts',  # 六角螺母
        'locknuts',  # 锁紧螺母
        'square nuts',  # 方螺母
        'collars',  # 轴环
        'rivet nut',  # 铆螺母
        'plugs',  # 塞子
        'slotted nuts'  # 开槽螺母

    ]

    for category in nuts:
        if category in name_lower:
            return 'Nuts'

    # 紧固件 - 垫圈类 (Washers)
    washers = [
        'convex washer',  # 凸形垫圈
        'lockwashers',  # 锁紧垫圈
        'spring washers',  # 弹簧垫圈
        'thrust washers',  # 推力垫圈
        'spacers',  # 垫片
        'bearing accessories',  # 轴承附件
        'snap rings'  # 卡簧
    ]

    for category in washers:
        if category in name_lower:
            return 'Washers'

    # 传动件 (Transmission Parts)
    transmission_parts = [
        'gear like parts',  # 齿轮类零件
        'pulleys',  # 滑轮
        'spoked wheels'  # 辐条轮
    ]

    for category in transmission_parts:
        if category in name_lower:
            return 'Transmission Parts'

    # 箱体壳体类 (Housings and Cases)
    housings = [
        'curved housings',  # 弯曲壳体
        'rectangular housings',  # 矩形壳体
        'motor bodies',  # 电机壳体
        'helical geared motors'  # 斜齿轮减速电机
    ]

    for category in housings:
        if category in name_lower:
            return 'Housings'

    # 板类零件 (Plate Parts)
    plates = [
        'machined plates',  # 机加工板
        'plates, circulate plates',  # 板材、循环板
        'thick plates',  # 厚板
        'thick slotted plates',  # 厚开槽板
        'back doors',  # 后门
        'bracket like parts',  # 支架类零件
        'contact switches',  # 接触开关
        'flanged block bearing',  # 法兰轴承座
        'oil pans'  # 油盘
    ]

    for category in plates:
        if category in name_lower:
            return 'Plates'

    # 块类零件 (Block Parts)
    blocks = [
        'keys and keyways, splines',  # 键和键槽、花键
        'bearing blocks',  # 轴承座
        'l blocks',  # L型块
        'machined blocks',  # 机加工块体
        'clamps'  # 夹具
    ]

    for category in blocks:
        if category in name_lower:
            return 'Blocks'

    # 操作控制件 (Control and Operation Parts)
    control_parts = [
        'handles',  # 手柄
        'lever',  # 杠杆
        'rocker arms'  # 摇臂
    ]

    for category in control_parts:
        if category in name_lower:
            return 'Control Parts'

    # 特殊零件 (Special Parts)
    special_parts = [
        't shaped parts',  # T型零件
        'u shaped parts'  # U型零件
    ]

    for category in special_parts:
        if category in name_lower:
            return 'Special Parts'

    return 'Unknown'
def coarse_grained_clustering_evaluation(input_weight=[0.4, 0.6, 0.0]):
    """
    粗粒度模型聚类效果评估
    """
    # 权重设置
    simWeight_0 = [input_weight[0], 0, 0, 0,
                   input_weight[0], 0, 0, 0,
                   input_weight[0], 0, 0, 0,
                   input_weight[0], 0, 0, 0,
                   input_weight[0], 0, 0, 0,
                   input_weight[0], 0, 0, 0]
    simWeight_1 = [0, input_weight[1] / 2, 0, input_weight[1] / 2,
                   0, input_weight[1] / 2, 0, input_weight[1] / 2,
                   0, input_weight[1] / 2, 0, input_weight[1] / 2,
                   0, input_weight[1] / 2, 0, input_weight[1] / 2,
                   0, input_weight[1] / 2, 0, input_weight[1] / 2,
                   0, input_weight[1] / 2, 0, input_weight[1] / 2]
    simWeight_2 = [0, 0, input_weight[2], 0,
                   0, 0, input_weight[2], 0,
                   0, 0, input_weight[2], 0,
                   0, 0, input_weight[2], 0,
                   0, 0, input_weight[2], 0,
                   0, 0, input_weight[2], 0]
    dataset = "MBDViewDataset_noMBD/validation"
    modelCount = 2131
    viewCount = 24
    featureSize = 128
    picturesType = []
    viewDirCount = 6
    viewTypeCount = 2
    cullModeCount = 2
    # 生成视图类型组合
    for i in range(viewDirCount):
        for j in range(viewTypeCount):
            for k in range(cullModeCount):
                picturesType.append([i, j, k])
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    # 4倍下采样的数据变换
    data_transform = transforms.Compose([
        transforms.Resize(56), # 224/4 = 56，实现4倍下采样
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    # 加载多个模型
    models = {}
    if input_weight[0] > 0:
        model_0 = resnet34().to(device)
        weights_path_0 = "./MBDNet34_0.pth"
        if os.path.exists(weights_path_0):
            model_0.load_state_dict(torch.load(weights_path_0, map_location=device))
            models['model_0'] = model_0
        else:
            print(f"Warning: {weights_path_0} not found, using default model")
            models['model_0'] = resnet34().to(device)
    if input_weight[1] > 0:
        model_1 = resnet34().to(device)
        weights_path_1 = "./MBDNet34_1.pth"
        if os.path.exists(weights_path_1):
            model_1.load_state_dict(torch.load(weights_path_1, map_location=device))
            models['model_1'] = model_1
        else:
            print(f"Warning: {weights_path_1} not found, using default model")
            models['model_1'] = resnet34().to(device)
    if input_weight[2] > 0:
        model_2 = resnet34().to(device)
        weights_path_2 = "./MBDNet34_0.pth"
        if os.path.exists(weights_path_2):
            model_2.load_state_dict(torch.load(weights_path_2, map_location=device))
            models['model_2'] = model_2
        else:
            print(f"Warning: {weights_path_2} not found, using default model")
            models['model_2'] = resnet34().to(device)
    # 存储特征和标签
    all_features = []
    true_labels = []
    coarse_labels = []
    model_names = []
    # 遍历所有类别和模型
    classList = os.listdir('./MBDViewDataset_noMBD/V')
    classList.sort()
    print("开始提取特征...")
    for classIndex, className in enumerate(classList):
        print(f"处理类别: {className}")
        # 获取粗粒度标签
        coarse_type = classify_to_coarse_type(className)
        modelList = os.listdir(f'./MBDViewDataset_noMBD/V/{className}/')
        modelList.sort()
        for modelIndex, modelName in enumerate(modelList):
            inputName = modelName[:-10] # 移除文件扩展名
            model_names.append(f"{className}_{inputName}")
            true_labels.append(classIndex)
            coarse_labels.append(coarse_type)
            # 读取该模型的视图
            img_list = []
            CADmodelName = f"./{dataset}/{className}/{inputName}"
            for i_view in range(viewCount):
                img_path = (CADmodelName + "_" +
                            str(picturesType[i_view][0]) + "_" +
                            str(picturesType[i_view][1]) + "_" +
                            str(picturesType[i_view][2]) + ".bmp")
                if os.path.exists(img_path):
                    img = Image.open(img_path)
                    img = data_transform(img)
                    img = torch.unsqueeze(img, dim=0)
                    img_list.append(img)
                else:
                    # 如果图片不存在，创建零图像
                    img_list.append(torch.zeros(1, 3, 56, 56))
            # 提取特征
            combined_features = []
            for model_key, model in models.items():
                model.eval()
                with torch.no_grad():
                    view_features = []
                    for img in img_list:
                        output = model(img.to(device))
                        view_features.append(output.cpu().numpy())
                # 将多视图特征按权重组合
                weighted_feature = np.zeros(featureSize)
                for j_view in range(viewCount):
                    if model_key == 'model_0':
                        weighted_feature += view_features[j_view].flatten() * simWeight_0[j_view] / viewCount
                    elif model_key == 'model_1':
                        weighted_feature += view_features[j_view].flatten() * simWeight_1[j_view] / viewCount
                    elif model_key == 'model_2':
                        weighted_feature += view_features[j_view].flatten() * simWeight_2[j_view] / viewCount
                if model_key == 'model_0':
                    combined_features.extend(weighted_feature * input_weight[0])
                elif model_key == 'model_1':
                    combined_features.extend(weighted_feature * input_weight[1])
                elif model_key == 'model_2':
                    combined_features.extend(weighted_feature * input_weight[2])
            all_features.append(combined_features)
    # 转换为numpy数组
    all_features = np.array(all_features)
    # 获取唯一的粗粒度类别
    unique_coarse_types = list(set(coarse_labels))
    coarse_label_map = {label: idx for idx, label in enumerate(unique_coarse_types)}
    coarse_label_indices = [coarse_label_map[label] for label in coarse_labels]
    print(f"发现的粗粒度类别: {unique_coarse_types}")
    print(f"每个类别的样本数量:")
    for coarse_type in unique_coarse_types:
        count = coarse_labels.count(coarse_type)
        print(f" {coarse_type}: {count}")
    # 执行聚类
    n_clusters = len(unique_coarse_types)
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(all_features)
    # 计算聚类评估指标
    ari_score = adjusted_rand_score(coarse_label_indices, cluster_labels)
    nmi_score = normalized_mutual_info_score(coarse_label_indices, cluster_labels)
    silhouette_avg = silhouette_score(all_features, cluster_labels)
    print(f"\n=== 聚类评估结果 ===")
    print(f"调整兰德系数 (ARI): {ari_score:.4f}")
    print(f"标准化互信息 (NMI): {nmi_score:.4f}")
    print(f"轮廓系数 (Silhouette): {silhouette_avg:.4f}")
    # 可视化结果
    plt.rcParams['font.family'] = 'SimHei'
    plt.rcParams['axes.unicode_minus'] = False  # 禁用 Unicode Minus
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    # 1. 使用t-SNE降维可视化聚类结果
    tsne = TSNE(n_components=2, random_state=42, perplexity=min(30, len(all_features)//4))
    features_2d = tsne.fit_transform(all_features)
    # 真实标签可视化
    ax1 = axes[0, 0]
    colors = plt.cm.Set3(np.linspace(0, 1, len(unique_coarse_types)))
    for i, coarse_type in enumerate(unique_coarse_types):
        mask = np.array(coarse_labels) == coarse_type
        ax1.scatter(features_2d[mask, 0], features_2d[mask, 1],
                    c=[colors[i]], label=coarse_type, alpha=0.7, s=30)
    ax1.set_title('真实粗粒度类别分布 (t-SNE)')
    ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax1.grid(True, alpha=0.3)
    # 聚类结果可视化
    ax2 = axes[0, 1]
    unique_clusters = np.unique(cluster_labels)
    cluster_colors = plt.cm.Set1(np.linspace(0, 1, len(unique_clusters)))
    for i, cluster_id in enumerate(unique_clusters):
        mask = cluster_labels == cluster_id
        ax2.scatter(features_2d[mask, 0], features_2d[mask, 1],
                    c=[cluster_colors[i]], label=f'Cluster {cluster_id}', alpha=0.7, s=30)
    ax2.set_title('聚类结果分布 (t-SNE)')
    ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax2.grid(True, alpha=0.3)
    # 2. 混淆矩阵热图
    ax3 = axes[1, 0]
    confusion_matrix = np.zeros((n_clusters, len(unique_coarse_types)))
    for i in range(len(cluster_labels)):
        confusion_matrix[cluster_labels[i], coarse_label_indices[i]] += 1
    sns.heatmap(confusion_matrix, annot=True, fmt='g', cmap='Blues', ax=ax3,
                xticklabels=unique_coarse_types, yticklabels=[f'Cluster {i}' for i in range(n_clusters)])
    ax3.set_title('聚类结果混淆矩阵')
    ax3.set_xlabel('真实粗粒度类别')
    ax3.set_ylabel('聚类标签')
    # 3. 评估指标柱状图
    ax4 = axes[1, 1]
    metrics = ['ARI', 'NMI', 'Silhouette']
    values = [ari_score, nmi_score, silhouette_avg]
    bars = ax4.bar(metrics, values, color=['skyblue', 'lightgreen', 'lightcoral'])
    ax4.set_title('聚类评估指标')
    ax4.set_ylabel('分数')
    ax4.set_ylim(0, 1)
    # 在柱状图上添加数值标签
    for bar, value in zip(bars, values):
        ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                 f'{value:.3f}', ha='center', va='bottom')
    ax4.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(f'coarse_grained_clustering_evaluation_weight_{input_weight[0]}_{input_weight[1]}_{input_weight[2]}.png',
                dpi=300, bbox_inches='tight')
    plt.show()
    # 详细分析每个粗粒度类别的聚类效果
    print(f"\n=== 各粗粒度类别聚类效果分析 ===")
    for i, coarse_type in enumerate(unique_coarse_types):
        mask = np.array(coarse_label_indices) == i
        assigned_clusters = cluster_labels[mask]
        cluster_counts = np.bincount(assigned_clusters, minlength=n_clusters)
        dominant_cluster = np.argmax(cluster_counts)
        purity = cluster_counts[dominant_cluster] / len(assigned_clusters)
        print(f"{coarse_type}:")
        print(f" 样本总数: {len(assigned_clusters)}")
        print(f" 主要分配到聚类 {dominant_cluster}: {cluster_counts[dominant_cluster]} 个样本")
        print(f" 纯度: {purity:.4f}")
        print(f" 分布: {cluster_counts}")
        print()
    return {
        'features': all_features,
        'true_labels': coarse_label_indices,
        'cluster_labels': cluster_labels,
        'coarse_types': unique_coarse_types,
        'ari_score': ari_score,
        'nmi_score': nmi_score,
        'silhouette_score': silhouette_avg,
        'model_names': model_names
    }
def main():
    """
    主函数：执行粗粒度聚类评估
    """
    print("开始粗粒度模型聚类效果评估")
    print("参数设置: input_weight = [0.4, 0.6, 0.0]")
    print("下采样倍数: 4倍 (224 -> 56)")
    # 执行评估
    results = coarse_grained_clustering_evaluation([0.08, 0.12, 0.8])
    if results:
        print("\n=== 评估完成 ===")
        print(f"最终聚类效果:")
        print(f" ARI: {results['ari_score']:.4f}")
        print(f" NMI: {results['nmi_score']:.4f}")
        print(f" Silhouette: {results['silhouette_score']:.4f}")
        # 可以在这里添加更多分析
        return results
    else:
        print("评估失败，请检查模型文件路径")
        return None
if __name__ == '__main__':
    results = main()