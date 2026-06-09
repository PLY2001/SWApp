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
    modelCount = 88#2131
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
                img_path = CADmodelName + "_" + str(picturesType[i_view][0]) + "_" + \
                           str(picturesType[i_view][1]) + "_" + str(picturesType[i_view][2]) + ".bmp"
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

def main():
    # 分析两种权重设置
    weight_settings = [
        ([1.0, 0.0, 0.0], "input_weight[0]=1"),
        ([0.0, 0.0, 1.0], "input_weight[2]=1")
    ]
    for weight, weight_name in weight_settings:
        print(f"\n=== 分析 {weight_name} 时三角面数与准确率指标的关系 ===")
        triangle_results = last_main(weight)
        # 按三角面数排序
        sorted_triangles = sorted(triangle_results.keys())
        # 提取指标数据用于绘图
        triangle_counts = []
        NN_values = []
        FT_values = []
        ST_values = []
        F_values = []
        avgDCG_values = []
        avgNDCG_values = []
        print(f"三角面数\t模型数量\tNN\tFT\tST\tF\tavgDCG\tavgNDCG")
        print("-" * 80)
        for triangle_count in sorted_triangles:
            metrics = triangle_results[triangle_count]
            triangle_counts.append(triangle_count)
            NN_values.append(metrics['NN'])
            FT_values.append(metrics['FT'])
            ST_values.append(metrics['ST'])
            F_values.append(metrics['F'])
            avgDCG_values.append(metrics['avgDCG'][-1])
            avgNDCG_values.append(metrics['avgNDCG'][-1])
            print(f"{triangle_count}\t{metrics['count']}\t{metrics['NN']:.4f}\t{metrics['FT']:.4f}\t{metrics['ST']:.4f}\t{metrics['F']:.4f}\t{metrics['avgDCG'][-1]:.4f}\t{metrics['avgNDCG'][-1]:.4f}")

        # 绘制图表
        plt.figure(figsize=(15, 10))
        # 第一个子图
        plt.subplot(2, 2, 1)
        plt.plot(triangle_counts, NN_values, 'r-o', label='NN', linewidth=2)
        plt.plot(triangle_counts, FT_values, 'g-s', label='FT', linewidth=2)
        plt.plot(triangle_counts, ST_values, 'b-^', label='ST', linewidth=2)
        plt.plot(triangle_counts, F_values, 'c-d', label='F', linewidth=2)
        plt.xlabel('三角面数')
        plt.ylabel('准确率指标')
        plt.title(f'{weight_name} - 准确率指标随三角面数变化')
        plt.legend()
        plt.grid(True, alpha=0.3)
        # 第二个子图
        plt.subplot(2, 2, 2)
        plt.plot(triangle_counts, avgDCG_values, 'y-o', label='avgDCG', linewidth=2)
        plt.plot(triangle_counts, avgNDCG_values, 'k-s', label='avgNDCG', linewidth=2)
        plt.xlabel('三角面数')
        plt.ylabel('DCG/NDCG指标')
        plt.title(f'{weight_name} - DCG/NDCG指标随三角面数变化')
        plt.legend()
        plt.grid(True, alpha=0.3)
        # 第三个子图
        plt.subplot(2, 2, 3)
        representative_triangles = sorted_triangles[::max(1, len(sorted_triangles) // 5)]
        for triangle_count in representative_triangles:
            metrics = triangle_results[triangle_count]
            plt.plot(metrics['R'], metrics['P'], label=f'{triangle_count}面')
        plt.xlabel('Recall')
        plt.ylabel('Precision')
        plt.title(f'{weight_name} - P-R曲线')
        plt.legend()
        plt.grid(True, alpha=0.3)
        # 第四个子图
        plt.subplot(2, 2, 4)
        model_counts = [triangle_results[tc]['count'] for tc in sorted_triangles]
        plt.bar(range(len(triangle_counts)), model_counts, alpha=0.7)
        plt.xlabel('三角面数索引')
        plt.ylabel('模型数量')
        plt.title(f'{weight_name} - 不同三角面数的模型数量分布')
        plt.xticks(
            range(0, len(triangle_counts), max(1, len(triangle_counts) // 10)),
            [str(triangle_counts[i]) for i in range(0, len(triangle_counts), max(1, len(triangle_counts) // 10))],
            rotation=45
        )
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(f'triangle_analysis_{weight_name.replace("=", "_").replace("[", "").replace("]", "")}.png', dpi=300, bbox_inches='tight')
        plt.show()
        # 找到最优三角面数
        max_metrics = {
            'NN': (max(NN_values), triangle_counts[NN_values.index(max(NN_values))]),
            'FT': (max(FT_values), triangle_counts[FT_values.index(max(FT_values))]),
            'ST': (max(ST_values), triangle_counts[ST_values.index(max(ST_values))]),
            'F': (max(F_values), triangle_counts[F_values.index(max(F_values))]),
            'avgDCG': (max(avgDCG_values), triangle_counts[avgDCG_values.index(max(avgDCG_values))]),
            'avgNDCG': (max(avgNDCG_values), triangle_counts[avgNDCG_values.index(max(avgNDCG_values))])
        }
        print(f"\n{weight_name} 最优三角面数：")
        for metric, (value, triangle_count) in max_metrics.items():
            print(f"{metric}: {triangle_count}面 (值: {value:.4f})")
        print("=" * 80)

if __name__ == '__main__':
    main()