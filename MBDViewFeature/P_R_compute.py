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

def last_main(input_weight):
    simWeight = [input_weight[0] * 4, input_weight[1] / 2 * 4, input_weight[2] * 4, input_weight[1] / 2 * 4,
                 input_weight[0] * 4, input_weight[1] / 2 * 4, input_weight[2] * 4, input_weight[1] / 2 * 4,
                 input_weight[0] * 4, input_weight[1] / 2 * 4, input_weight[2] * 4, input_weight[1] / 2 * 4]
    dataset = "MBDViewDataset_noMBD"
    modelCount = 2131
    viewCount = 12
    featureSize = 128
    picturesType = []

    viewDirCount = 3
    viewTypeCount = 2
    cullModeCount = 2
    for i in range(viewDirCount):
        for j in range(viewTypeCount):
            for k in range(cullModeCount):
                picturesType.append([i, j, k])

    # matplotlib.use("TKAgg")
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    data_transform = transforms.Compose(
        [transforms.Resize(224),
         # transforms.CenterCrop(224),
         transforms.ToTensor(),
         transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])

    # read dataset
    json_path = "./" + dataset + ".json"
    assert os.path.exists(json_path), "file: '{}' dose not exist.".format(json_path)

    # with open(json_path, "r") as f:
    #     data_list = json.load(f)

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

    # create model
    model = resnet34().to(device)

    # load model weights
    weights_path = "./MBDNet34.pth"
    assert os.path.exists(weights_path), "file: '{}' dose not exist.".format(weights_path)
    model.load_state_dict(torch.load(weights_path, map_location=device))

    # P R
    k = 20
    precision = [0 for index in range(k)]
    P = [0 for index in range(k)]
    recall = [0 for index in range(k)]
    R = [0 for index in range(k)]
    nn = 0
    NN = 0
    ft = 0
    FT = 0
    st = 0
    ST = 0
    avgdcg = [0 for index in range(k)]
    avgDCG = [0 for index in range(k)]
    avgndcg = [0 for index in range(k)]
    avgNDCG = [0 for index in range(k)]
    thisModelCount = 0
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
            # 绘图大小
            # plt.figure(figsize=(10, 28))

            inputClass = classList[classIndex]
            inputName = modelList[modelIndex][:-10]

            # 读取该模型的视图
            img_list = []
            CADmodelName = "./" + dataset + "/photos/" + inputClass + "/" + inputName
            for i_view in range(viewCount):
                img_path = CADmodelName + "_" + str(picturesType[i_view][0]) + "_" + str(
                    picturesType[i_view][1]) + "_" + str(
                    picturesType[i_view][2]) + ".bmp"  # 搜索这张图
                assert os.path.exists(img_path), "file: '{}' dose not exist.".format(img_path)
                img = Image.open(img_path)
                img = data_transform(img)
                # expand batch dimension
                img = torch.unsqueeze(img, dim=0)
                img_list.append(img)

            img_path = "MBDViewModelPicture/" + inputClass + "/" + inputName + "_3_2_0.bmp"  # 搜索这张图
            assert os.path.exists(img_path), "file: '{}' dose not exist.".format(img_path)
            img = Image.open(img_path)

            # plt.subplot(7, 3, 1)
            # plt.axis('off')
            # plt.imshow(img)
            # plt.rcParams['font.size'] = 20
            # plt.title(f"[检索目标]\n{inputClass}\n{inputName}")

            # prediction
            output_list = []
            model.eval()
            with torch.no_grad():
                for img in img_list:
                    output = model(img.to(device))
                    # output = F.normalize(output, p=2, dim=1)
                    output_list.append(output)
                output_tensor = torch.cat((output_list[:]), 0).to(device)

                sim_dic = {}
                # predict_bar = tqdm(range(len(CADmodel_tensor)), file=sys.stdout)
                for i_predict in range(len(CADmodel_tensor)):
                    index = torch.tensor([i_predict]).to(device)
                    views = torch.index_select(CADmodel_tensor, 0, index)
                    views = torch.squeeze(views, dim=0)
                    # views = F.normalize(views, p=2, dim=2)
                    similarity = torch.mm(output_tensor, views.t())
                    # similarity = (output@view.t()).item()
                    sim = 0
                    for j_view in range(viewCount):
                        sim = sim + similarity[j_view][j_view] / viewCount * simWeight[j_view]
                    sim_dic[i_predict] = sim
                    # if similarity > best_similarity:
                    #     best_similarity = similarity
                    #     best_index = i
                    # predict_bar.desc = "检索中"
            sim_order = sorted(sim_dic.items(), key=lambda x: x[1], reverse=True)

            # 显示检索结果
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
                Target_img_path = "./MBDViewModelPicture/" + classList[thisclassIndex] + "/" + fileList[indexInClass]
                img1 = Image.open(Target_img_path)
                # plt.subplot(7, 3, 2 + i)
                # plt.axis('off')
                # plt.imshow(img1)
                # plt.rcParams['font.size'] = 20
                # plt.title(
                #     f"【检索结果 {i + 1}】\n{classList[thisclassIndex]}\n{fileList[indexInClass][:-10]}\n相似度：{round(sim_order[i][1].item() * 100, 1)}%")

                # 计算P R
                if thisclassIndex == classIndex:
                    exactCount = exactCount + 1
                    DCG = DCG + math.log(2) / math.log(i_result + 2)
                if i_result < k:
                    precision[i_result] = precision[i_result] + exactCount / (i_result + 1)
                    recall[i_result] = recall[i_result] + exactCount / len(modelList)
                    avgDCG[i_result] = avgDCG[i_result] + DCG
                    avgNDCG[i_result] = avgNDCG[i_result] + DCG / IDCG
                if i_result == 1:
                    NN = NN + exactCount - 1
                if i_result == T - 1:
                    FT = FT + exactCount / T
                if i_result == 2 * T - 1:
                    ST = ST + exactCount / T

            # plt.subplots_adjust(left=None, bottom=None, right=None, top=0.75, wspace=0.5, hspace=1.0)
            # plt.rcParams['font.sans-serif'] = ['SimHei']
            # plt.rcParams['font.size'] = 30
            # plt.suptitle("三维检索系统")
            # plt.show()

        for p in range(k):
            P[p] = precision[p] / thisModelCount
            R[p] = recall[p] / thisModelCount
            avgdcg[p] = avgDCG[p] / thisModelCount
            avgndcg[p] = avgNDCG[p] / thisModelCount

        nn = NN / thisModelCount
        ft = FT / thisModelCount
        st = ST / thisModelCount
        f = 2 * P[4] * R[4] / (P[4] + R[4])

        # print(P)
        # print(R)
        # print(nn)
        # print(ft)
        # print(st)
        # print(f)
        # print(avgdcg)
        # print(avgndcg)
        #
        # plt.plot(R, P)
        # plt.show()
        #return P, R, nn, ft, st, f, avgdcg, avgndcg

    for p in range(k):
        P[p] = precision[p] / modelCount
        R[p] = recall[p] / modelCount
        avgDCG[p] = avgDCG[p] / modelCount
        avgNDCG[p] = avgNDCG[p] / modelCount

    NN = NN / modelCount
    FT = FT / modelCount
    ST = ST / modelCount
    F = 2 * P[4] * R[4] / (P[4] + R[4])

    print(P)
    print(R)
    print(NN)
    print(FT)
    print(ST)
    print(F)
    print(avgDCG)
    print(avgNDCG)

    #plt.plot(R, P)
    #plt.show()

    return P,R,NN,FT,ST,F,avgDCG,avgNDCG
def main():
    input_weight = [1.0, 0.0, 0.0]
    P_list = []
    P = []
    R_list = []
    R = []
    NN_list = []
    NN = 0
    FT_list = []
    FT = 0
    ST_list = []
    ST = 0
    F_lsit = []
    F = 0
    avgDCG = []
    avgDCG_list = []
    avgNDCG = []
    avgNDCG_list = []
    maxPoint_y = [0,0,0,0,0,0]
    maxPoint_x = [0,0,0,0,0,0]
    legend_list_PR = ['0','1','2','3','4','5','6','7','8','9','10']
    legend_list_other = ['NN','FT','ST','F','avgDCG','avgNDCG']
    color_list_point = ['r','g','b','c','y','k']
    for i in range(11):
        P,R,NN,FT,ST,F,avgDCG,avgNDCG = last_main(input_weight)
        input_weight[0] -= 0.1
        input_weight[2] += 0.1
        P_list.append(P)
        R_list.append(R)
        NN_list.append(NN)
        FT_list.append(FT)
        ST_list.append(ST)
        F_lsit.append(F)
        avgDCG_list.append(avgDCG[-1]*0.1)
        avgNDCG_list.append(avgNDCG[-1]*0.1)

        if NN > maxPoint_y[0]:
            maxPoint_y[0] = NN
            maxPoint_x[0] = i
        if FT > maxPoint_y[1]:
            maxPoint_y[1] = FT
            maxPoint_x[1] = i
        if ST > maxPoint_y[2]:
            maxPoint_y[2] = ST
            maxPoint_x[2] = i
        if F > maxPoint_y[3]:
            maxPoint_y[3] = F
            maxPoint_x[3] = i
        if avgDCG[-1]*0.1 > maxPoint_y[4]:
            maxPoint_y[4] = avgDCG[-1]*0.1
            maxPoint_x[4] = i
        if avgNDCG[-1]*0.1 > maxPoint_y[5]:
            maxPoint_y[5] = avgNDCG[-1]*0.1
            maxPoint_x[5] = i

        for j in range(i+1):
            plt.plot(R_list[j], P_list[j])
        plt.legend(legend_list_PR[0:i+1], loc='upper right')
        plt.xlabel('R')
        plt.ylabel('P')
        plt.show()

        plt.plot(NN_list,color=color_list_point[0])
        plt.plot(FT_list,color=color_list_point[1])
        plt.plot(ST_list,color=color_list_point[2])
        plt.plot(F_lsit,color=color_list_point[3])
        plt.plot(avgDCG_list,color=color_list_point[4])
        plt.plot(avgNDCG_list,color=color_list_point[5])
        for k in range(6):
            plt.scatter(maxPoint_x[k], maxPoint_y[k], color=color_list_point[k])
        plt.legend(legend_list_other, loc='upper right')
        plt.show()





if __name__ == '__main__':
    main()
