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

def last_main(input_weight):
    simWeight = [input_weight[0] * 4, input_weight[1] / 2 * 4, input_weight[2] * 4, input_weight[1] / 2 * 4,
                 input_weight[0] * 4, input_weight[1] / 2 * 4, input_weight[2] * 4, input_weight[1] / 2 * 4,
                 input_weight[0] * 4, input_weight[1] / 2 * 4, input_weight[2] * 4, input_weight[1] / 2 * 4,
                 input_weight[0] * 4, input_weight[1] / 2 * 4, input_weight[2] * 4, input_weight[1] / 2 * 4,
                 input_weight[0] * 4, input_weight[1] / 2 * 4, input_weight[2] * 4, input_weight[1] / 2 * 4,
                 input_weight[0] * 4, input_weight[1] / 2 * 4, input_weight[2] * 4, input_weight[1] / 2 * 4]
    dataset = "MBDViewDataset_noMBD"
    modelCount = 2131
    viewCount = 24
    featureSize = 128
    picturesType = []
    viewDirCount = 6
    viewTypeCount = 2
    cullModeCount = 2
    for i in range(viewDirCount):
        for j in range(viewTypeCount):
            for k in range(cullModeCount):
                picturesType.append([i, j, k])

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    data_transform = transforms.Compose([
        transforms.Resize(224),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])

    json_path = "./" + dataset + ".json"
    assert os.path.exists(json_path), "file: '{}' does not exist.".format(json_path)
    file = open(json_path, 'r')

    views = np.ones((viewCount, featureSize), dtype=np.float32)
    CADmodel_list = np.empty((modelCount, viewCount, featureSize), dtype=np.float32)
    view_list = []
    load_bar = tqdm(file.readlines(), file=sys.stdout)
    viewStart = False
    viewStop = True
    viewIndex = 0
    modelIndex = 0
    for line in load_bar:
        if line == '    [\n' and viewStop:
            viewStart = True
            continue
        if line == '    ],\n' or line == '    ]\n' and viewStart:
            viewStop = True
            views[viewIndex, :] = view_list[:]
            if viewIndex == viewCount - 1:
                CADmodel_list[modelIndex] = views[:]
                views = np.ones((viewCount, featureSize), dtype=np.float32)
                modelIndex = modelIndex + 1
            viewIndex = (viewIndex + 1) % viewCount
            view_list.clear()
        if viewStart:
            pattern_0 = "[-]?[0-9]+[.]{1}[0-9]+[e]{1}[\\+|-]?[0-9]+"
            match = re.findall(pattern_0, line)
            if len(match) > 0:
                num = eval(match[0])
                view_list.append(num)
            else:
                pattern = "[-]?[0-9]+[.]{1}[0-9]*"
                match = re.findall(pattern, line)
                if len(match) > 0:
                    num = json.loads(match[0])
                    view_list.append(num)
        load_bar.desc = "加载数据库中"
    CADmodel_tensor = torch.tensor(CADmodel_list).to(device)  # pan1在pan之前

    model = resnet34().to(device)
    weights_path = "./MBDNet34.pth"
    assert os.path.exists(weights_path), "file: '{}' does not exist.".format(weights_path)
    model.load_state_dict(torch.load(weights_path, map_location=device))

    # P R
    k = 20
    precision = [0 for _ in range(k)]
    P = [0 for _ in range(k)]
    recall = [0 for _ in range(k)]
    R = [0 for _ in range(k)]
    nn = 0
    NN = 0
    ft = 0
    FT = 0
    st = 0
    ST = 0
    avgdcg = [0 for _ in range(k)]
    avgDCG = [0 for _ in range(k)]
    avgndcg = [0 for _ in range(k)]
    avgNDCG = [0 for _ in range(k)]
    thisModelCount = 0
    # 用于存储三角面数和对应的准确率指标
    triangle_metrics = defaultdict(lambda: {
        'precision': [0 for _ in range(k)],
        'recall': [0 for _ in range(k)],
        'nn': 0, 'ft': 0, 'st': 0,
        'avgdcg': [0 for _ in range(k)],
        'avgndcg': [0 for _ in range(k)],
        'count': 0
    })

    # 遍历检索
    classList = os.listdir('./MBDViewModelPicture')
    classList.sort()
    for classIndex in range(len(classList)):
        print(classList[classIndex])
        modelList = os.listdir('./MBDViewModelPicture/' + classList[classIndex] + '/')
        modelList.sort()
        T = len(modelList)
        thisModelCount = thisModelCount + T
        IDCG = 0
        for s in range(T):
            IDCG = IDCG + math.log(2) / math.log(s + 2)
        for modelIndex in range(len(modelList)):
            inputClass = classList[classIndex]
            inputName = modelList[modelIndex][:-10]
            # 从inputName提取三角面数
            triangle_count = None
            if '_' in inputName:
                parts = inputName.split('_')
                if len(parts) >= 2:
                    try:
                        triangle_count = int(parts[-1])
                    except ValueError:
                        print(f"Warning: Could not extract triangle count from {inputName}")
                        continue
            if triangle_count is None:
                continue
            # 读取该模型的视图
            img_list = []
            CADmodelName = "./" + dataset + "/photos/" + inputClass + "/" + inputName
            for i_view in range(viewCount):
                img_path = CADmodelName + "_" + str(picturesType[i_view][0]) + "_" + str(picturesType[i_view][1]) + "_" + str(picturesType[i_view][2]) + ".bmp"
                assert os.path.exists(img_path), "file: '{}' does not exist.".format(img_path)
                img = Image.open(img_path)
                img = data_transform(img)
                img = torch.unsqueeze(img, dim=0)
                img_list.append(img)
            # prediction
            output_list = []
            model.eval()
            with torch.no_grad():
                for img in img_list:
                    output = model(img.to(device))
                    output_list.append(output)
                output_tensor = torch.cat((output_list[:]), 0).to(device)

                sim_dic = {}
                for i_predict in range(len(CADmodel_tensor)):
                    index = torch.tensor([i_predict]).to(device)
                    views = torch.index_select(CADmodel_tensor, 0, index)
                    views = torch.squeeze(views, dim=0)
                    similarity = torch.mm(output_tensor, views.t())
                    sim = 0
                    for j_view in range(viewCount):
                        sim += similarity[j_view][j_view] / viewCount * simWeight[j_view]
                    sim_dic[i_predict] = sim
            sim_order = sorted(sim_dic.items(), key=lambda x: x[1], reverse=True)
            # 显示检索结果并计算指标
            exactCount = 0
            DCG = 0
            for i_result in range(k if k > 2 * T else 2 * T):
                thisindex = sim_order[i_result][0]
                thisclassIndex = 0
                indexCount = 0
                fileList = []
                while indexCount <= thisindex:
                    fileList = os.listdir('./MBDViewModelPicture/' + classList[thisclassIndex] + '/')
                    fileList.sort()
                    indexCount = indexCount + len(fileList)
                    thisclassIndex = thisclassIndex + 1
                thisclassIndex = thisclassIndex - 1
                indexInClass = thisindex - indexCount

                # 计算P R
                if thisclassIndex == classIndex:
                    exactCount = exactCount + 1
                    DCG = DCG + math.log(2) / math.log(i_result + 2)
                if i_result < k:
                    triangle_metrics[triangle_count]['precision'][i_result] += exactCount / (i_result + 1)
                    triangle_metrics[triangle_count]['recall'][i_result] += exactCount / len(modelList)
                    triangle_metrics[triangle_count]['avgdcg'][i_result] += DCG
                    triangle_metrics[triangle_count]['avgndcg'][i_result] += DCG / IDCG

                if i_result == 1:
                    triangle_metrics[triangle_count]['nn'] += exactCount - 1
                if i_result == T - 1:
                    triangle_metrics[triangle_count]['ft'] += exactCount / T
                if i_result == 2 * T - 1:
                    triangle_metrics[triangle_count]['st'] += exactCount / T

            triangle_metrics[triangle_count]['count'] += 1

    # 计算每个三角面数的平均指标
    triangle_results = {}
    for triangle_count, metrics in triangle_metrics.items():
        if metrics['count'] > 0:
            triangle_results[triangle_count] = {
                'P': [p / metrics['count'] for p in metrics['precision']],
                'R': [r / metrics['count'] for r in metrics['recall']],
                'NN': metrics['nn'] / metrics['count'],
                'FT': metrics['ft'] / metrics['count'],
                'ST': metrics['st'] / metrics['count'],
                'avgDCG': [dcg / metrics['count'] for dcg in metrics['avgdcg']],
                'avgNDCG': [ndcg / metrics['count'] for ndcg in metrics['avgndcg']],
                'count': metrics['count'],
            }
            # 计算F值
            if triangle_results[triangle_count]['P'][4] + triangle_results[triangle_count]['R'][4] > 0:
                triangle_results[triangle_count]['F'] = 2 * triangle_results[triangle_count]['P'][4] * triangle_results[triangle_count]['R'][4] / (triangle_results[triangle_count]['P'][4] + triangle_results[triangle_count]['R'][4])
            else:
                triangle_results[triangle_count]['F'] = 0

    return triangle_results


def aggregate_by_triangle_bins(data, bin_size=1000):
    """
    根据三角面数对数据进行分段，并计算每个分段内指标的平均值。
    对于P-R曲线，直接对相同召回率点上的Precision和Recall进行平均。

    Args:
        data (dict): 原始数据，键为三角面数，值为包含NN, FT, ST, F, avgDCG, avgNDCG, P, R和count的字典。
        bin_size (int): 每个分段的三角面数大小。

    Returns:
        dict: 聚合后的数据，键为分段的起始三角面数，值为包含平均NN, FT, ST, F, avgDCG, avgNDCG, avg_P_curve, avg_R_curve以及该分段模型数量的字典。
    """
    if not data:
        return {}

    aggregated_data = {}

    for triangle_count, metrics in data.items():
        bin_start = (triangle_count // bin_size) * bin_size

        if bin_start not in aggregated_data:
            aggregated_data[bin_start] = {
                'NN_sum': 0.0, 'FT_sum': 0.0, 'ST_sum': 0.0, 'F_sum': 0.0,
                'avgDCG_sum': [], 'avgNDCG_sum': [],
                'P_curves_to_avg': [],  # 存储P曲线列表
                'R_curves_to_avg': [],  # 存储R曲线列表
                'count': 0  # 记录这个bin的模型总数 (而非每个三角面数对应模型的数量)
            }

        # 累加指标值（按照每个原始模型的count进行加权平均）
        aggregated_data[bin_start]['NN_sum'] += metrics['NN'] * metrics['count']
        aggregated_data[bin_start]['FT_sum'] += metrics['FT'] * metrics['count']
        aggregated_data[bin_start]['ST_sum'] += metrics['ST'] * metrics['count']
        # 但为了通用性，我们还是按照多条R的列表处理。
        aggregated_data[bin_start]['F_sum'] += metrics['F'] * metrics['count']

        aggregated_data[bin_start]['avgDCG_sum'].append(metrics['avgDCG'][-1])
        aggregated_data[bin_start]['avgNDCG_sum'].append(metrics['avgNDCG'][-1])

        # 存储原始P-R曲线，供后续平均
        # 确保P和R都是非空列表，并且长度相同
        if metrics['R'] and metrics['P'] and len(metrics['R']) == len(metrics['P']):
            aggregated_data[bin_start]['P_curves_to_avg'].append(metrics['P'])
            aggregated_data[bin_start]['R_curves_to_avg'].append(metrics['R'])

        aggregated_data[bin_start]['count'] += metrics['count']

    final_aggregated_data = {}
    for bin_start, sums in aggregated_data.items():
        if sums['count'] > 0:
            final_aggregated_data[bin_start] = {
                'NN': sums['NN_sum'] / sums['count'],
                'FT': sums['FT_sum'] / sums['count'],
                'ST': sums['ST_sum'] / sums['count'],
                'F': sums['F_sum'] / sums['count'],
                'avgDCG': np.mean(sums['avgDCG_sum']) if sums['avgDCG_sum'] else 0.0,  # 避免空列表求平均报错
                'avgNDCG': np.mean(sums['avgNDCG_sum']) if sums['avgNDCG_sum'] else 0.0,
                'count': sums['count']
            }

            # 计算平均P-R曲线
            if sums['P_curves_to_avg'] and sums['R_curves_to_avg']:
                # 检查所有P-R曲线的长度是否一致
                pr_curve_lengths = [len(p_curve) for p_curve in sums['P_curves_to_avg']]
                if not all(length == pr_curve_lengths[0] for length in pr_curve_lengths):
                    print(
                        f"警告：分段 {bin_start}-{bin_start + bin_size - 1:.0f} 内P-R曲线长度不一致，无法直接平均。将跳过此P-R曲线。")
                    final_aggregated_data[bin_start]['avg_P_curve'] = []
                    final_aggregated_data[bin_start]['avg_R_curve'] = []
                else:
                    # 将列表的列表转换为numpy数组，然后求平均
                    try:
                        avg_P_curve = np.mean(np.array(sums['P_curves_to_avg']), axis=0)
                        avg_R_curve = np.mean(np.array(sums['R_curves_to_avg']), axis=0)

                        final_aggregated_data[bin_start]['avg_P_curve'] = avg_P_curve.tolist()  # 转换回列表
                        final_aggregated_data[bin_start]['avg_R_curve'] = avg_R_curve.tolist()
                    except Exception as e:
                        print(f"处理分段 {bin_start}-{bin_start + bin_size - 1:.0f} 的P-R曲线时发生错误: {e}")
                        final_aggregated_data[bin_start]['avg_P_curve'] = []
                        final_aggregated_data[bin_start]['avg_R_curve'] = []
            else:
                final_aggregated_data[bin_start]['avg_P_curve'] = []
                final_aggregated_data[bin_start]['avg_R_curve'] = []
        else:
            # 如果该bin没有数据，则所有指标为0
            final_aggregated_data[bin_start] = {
                'NN': 0.0, 'FT': 0.0, 'ST': 0.0, 'F': 0.0,
                'avgDCG': 0.0, 'avgNDCG': 0.0,
                'avg_P_curve': [], 'avg_R_curve': [],
                'count': 0
            }

    return final_aggregated_data


def main():
    plt.rcParams['font.family'] = 'SimHei'  # 选择一个支持中文的字体
    # 分析两种权重设置
    weight_settings = [
        ([1.0, 0.0, 0.0], "input_weight[0]=1"),
        ([0.0, 0.0, 1.0], "input_weight[2]=1")
    ]

    bin_size = 1000  # 定义分段大小，例如每1000个三角面数一个分段

    for weight, weight_name in weight_settings:
        print(f"\n=== 分析 {weight_name} 时三角面数（按 {bin_size} 分段）与准确率指标的关系 ===")

        # 假设 last_main 返回原始的 triangle_results
        original_triangle_results = last_main(weight)

        # 调用新的聚合函数
        aggregated_results = aggregate_by_triangle_bins(original_triangle_results, bin_size=bin_size)

        # 按三角面数分段排序
        sorted_bin_starts = sorted(aggregated_results.keys())

        # 提取指标数据用于绘图
        bin_labels = []
        NN_values = []
        FT_values = []
        ST_values = []
        F_values = []
        avgDCG_values = []
        avgNDCG_values = []

        # 用于P-R曲线和模型数量分布图的原始数据
        all_P_values = []
        all_R_values = []
        model_counts_per_bin = []

        print(f"分段起始三角面数\t模型数量\tNN\tFT\tST\tF\tavgDCG\tavgNDCG\tR\tP")
        print("-" * 100)

        for bin_start in sorted_bin_starts:
            metrics = aggregated_results[bin_start]
            bin_labels.append(f"{bin_start}-{bin_start + bin_size - 1.0:.0f}")  # 标签显示范围
            NN_values.append(metrics['NN'])
            FT_values.append(metrics['FT'])
            ST_values.append(metrics['ST'])
            F_values.append(metrics['F'])
            avgDCG_values.append(metrics['avgDCG'])
            avgNDCG_values.append(metrics['avgNDCG'])
            model_counts_per_bin.append(metrics['count'])

            # 聚合P-R曲线数据
            # 这里需要从 original_triangle_results 中获取每个模型的所有P和R值
            for triangle_count, original_metrics in original_triangle_results.items():
                if (triangle_count // bin_size) * bin_size == bin_start:
                    all_P_values.extend(original_metrics['P'])
                    all_R_values.extend(original_metrics['R'])

            print(
                f"{bin_start}-{bin_start + bin_size - 1.0:.0f}\t{metrics['count']}\t{metrics['NN']:.4f}\t{metrics['FT']:.4f}\t{metrics['ST']:.4f}\t{metrics['F']:.4f}\t{metrics['avgDCG']:.4f}\t{metrics['avgNDCG']:.4f}")
            print(
                f"{bin_start}-{bin_start + bin_size - 1.0:.0f}\t{metrics['avg_R_curve']}")
            print(
                f"{bin_start}-{bin_start + bin_size - 1.0:.0f}\t{metrics['avg_P_curve']}")

        # 绘制图表
        plt.figure(figsize=(15, 10))

        # 第一个子图：准确率指标随三角面数分段变化
        plt.subplot(2, 2, 1)
        plt.plot(bin_labels, NN_values, 'r-o', label='NN', linewidth=2)
        plt.plot(bin_labels, FT_values, 'g-s', label='FT', linewidth=2)
        plt.plot(bin_labels, ST_values, 'b-^', label='ST', linewidth=2)
        plt.plot(bin_labels, F_values, 'c-d', label='F', linewidth=2)
        plt.xlabel('三角面数范围')
        plt.ylabel('平均准确率指标')
        plt.title(f'{weight_name} - 平均准确率指标随三角面数范围变化')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45, ha='right')

        # 第二个子图：DCG/NDCG指标随三角面数分段变化
        plt.subplot(2, 2, 2)
        plt.plot(bin_labels, avgDCG_values, 'y-o', label='avgDCG', linewidth=2)
        plt.plot(bin_labels, avgNDCG_values, 'k-s', label='avgNDCG', linewidth=2)
        plt.xlabel('三角面数范围')
        plt.ylabel('平均DCG/NDCG指标')
        plt.title(f'{weight_name} - 平均DCG/NDCG指标随三角面数范围变化')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45, ha='right')

        # 第三个子图：P-R曲线
        plt.subplot(2, 2, 3)
        # 为每个分段绘制一条平均P-R曲线
        for bin_start in sorted_bin_starts:
            metrics = aggregated_results[bin_start]
            if metrics['avg_R_curve'] and metrics['avg_P_curve']:
                plt.plot(metrics['avg_R_curve'], metrics['avg_P_curve'])

        plt.xlabel('Recall')
        plt.ylabel('Precision')
        plt.title(f'{weight_name} - 平均P-R曲线')
        plt.legend()
        plt.grid(True, alpha=0.3)

        # 第四个子图：模型数量分布
        plt.subplot(2, 2, 4)
        plt.bar(bin_labels, model_counts_per_bin, alpha=0.7)
        plt.xlabel('三角面数范围')
        plt.ylabel('模型数量')
        plt.title(f'{weight_name} - 不同三角面数范围的模型数量分布')
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45, ha='right')  # 旋转X轴标签，防止重叠

        plt.tight_layout()
        plt.savefig(
            f'triangle_analysis_binned_{weight_name.replace("=", "_").replace("[", "").replace("]", "")}_{bin_size}.png',
            dpi=300, bbox_inches='tight')
        plt.show()

        # 找到最优三角面数范围（基于平均指标）
        max_metrics_binned = {
            'NN': (max(NN_values), bin_labels[NN_values.index(max(NN_values))]),
            'FT': (max(FT_values), bin_labels[FT_values.index(max(FT_values))]),
            'ST': (max(ST_values), bin_labels[ST_values.index(max(ST_values))]),
            'F': (max(F_values), bin_labels[F_values.index(max(F_values))]),
            'avgDCG': (max(avgDCG_values), bin_labels[avgDCG_values.index(max(avgDCG_values))]),
            'avgNDCG': (max(avgNDCG_values), bin_labels[avgNDCG_values.index(max(avgNDCG_values))])
        }
        print(f"\n{weight_name} 最优三角面数范围（按 {bin_size} 分段）:")
        for metric, (value, bin_range) in max_metrics_binned.items():
            print(f"{metric}: {bin_range} (值: {value:.4f})")
        print("=" * 100)


if __name__ == '__main__':
    main()