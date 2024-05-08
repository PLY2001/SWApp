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

#from tqdm import tqdm
import torch.nn.functional as F

import numpy as np
import re

def main(inputName,hasMBD,modelCount):
    os.chdir("C:/Users/PLY/Desktop/Files/Projects/Pycharm Projects/MBDViewFeature")
    # hasMBD = "y" #input("是否考虑MBD？ y/n:")
    dataset = "MBDViewDataset" if hasMBD == 1 else "MBDViewDataset_noMBD"
    #modelCount = 8
    viewCount = 12
    featureSize = 128
    picturesType = []

    viewDirCount = 3
    viewTypeCount = 2
    cullModeCount = 2
    for i in range(viewDirCount):
        for j in range(viewTypeCount):
            for k in range(cullModeCount):
                picturesType.append([i,j,k])

    #matplotlib.use("TKAgg")
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    data_transform = transforms.Compose(
        [transforms.Resize(224),
         # transforms.CenterCrop(224),
         transforms.ToTensor(),
         transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])

    plt.figure(figsize=(10, 8))

    # load image
    # inputName = input("检索目标名称:")
    img_list = []
    CADmodelName = "./" + dataset + "/photos/" + inputName
    for i in range(viewCount):
        img_path = CADmodelName + "_" + str(picturesType[i][0]) + "_" + str(picturesType[i][1]) + "_" + str(picturesType[i][2]) + ".bmp"  # 搜索这张图
        assert os.path.exists(img_path), "file: '{}' dose not exist.".format(img_path)
        img = Image.open(img_path)
        img = data_transform(img)
        torchvision.utils.save_image(img, 'out.jpg')
        # expand batch dimension
        img = torch.unsqueeze(img, dim=0)
        img_list.append(img)

    img_path = "MBDViewModelPicture/" + inputName + "_.bmp" # 搜索这张图
    assert os.path.exists(img_path), "file: '{}' dose not exist.".format(img_path)
    img = Image.open(img_path)

    plt.subplot(231)
    plt.axis('off')
    plt.imshow(img)
    plt.rcParams['font.size'] = 20
    hasMBDtitle = "(含MBD信息)" if hasMBD == "y" else "(不含MBD信息)"
    plt.title(f"[检索目标]\n{inputName}\n{hasMBDtitle}")

    # read dataset
    json_path = "./" + dataset + ".json"
    assert os.path.exists(json_path), "file: '{}' dose not exist.".format(json_path)

    # with open(json_path, "r") as f:
    #     data_list = json.load(f)

    file = open(json_path, 'r')
    views = np.ones((viewCount, featureSize),dtype=np.float32)
    CADmodel_list = np.empty((modelCount, viewCount, featureSize), dtype=np.float32)
    view_list = []
    #load_bar = tqdm(file.readlines(), file=sys.stdout)
    load_bar = file.readlines()
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
                views = np.ones((viewCount, featureSize),dtype=np.float32)
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

        #load_bar.desc = "加载数据库中"



    CADmodel_tensor = torch.tensor(CADmodel_list).to(device) #pan1在pan之前
    # create model
    model = resnet34().to(device)

    # load model weights
    weights_path = "./MBDNet34.pth"
    assert os.path.exists(weights_path), "file: '{}' dose not exist.".format(weights_path)
    model.load_state_dict(torch.load(weights_path, map_location=device))

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
        #predict_bar = tqdm(range(len(CADmodel_tensor)), file=sys.stdout)
        predict_bar = range(len(CADmodel_tensor))
        for i in predict_bar:
            index = torch.tensor([i]).to(device)
            views = torch.index_select(CADmodel_tensor, 0, index)
            views = torch.squeeze(views, dim=0)
            # views = F.normalize(views, p=2, dim=2)
            similarity = torch.mm(output_tensor, views.t())
            # similarity = (output@view.t()).item()
            sim = 0
            for j in range (viewCount) :
                sim = sim + similarity[j][j]/viewCount
            sim_dic[i] = sim
            # if similarity > best_similarity:
            #     best_similarity = similarity
            #     best_index = i
            #predict_bar.desc = "检索中"
    sim_order = sorted(sim_dic.items(), key=lambda x: x[1], reverse=True)

    # print(f"best_similarity = {best_similarity}")

    # load image
    fileList = os.listdir('./MBDViewModelPicture')
    fileList.sort()
    FileNameList = []
    SimList = []
    for i in range(5 if 5 < len(CADmodel_list) else len(CADmodel_list)):
        thisindex = sim_order[i][0]
        Target_img_path = "./MBDViewModelPicture/"+fileList[thisindex]
        img1 = Image.open(Target_img_path)
        plt.subplot(232+i)
        plt.axis('off')
        plt.imshow(img1)
        plt.rcParams['font.size'] = 20
        plt.title(f"【检索结果 {i+1}】\n{fileList[thisindex][:-5]}\n相似度：{round(sim_order[i][1].item()*100,1)}%")
        FileNameList.append(fileList[thisindex])
        SimList.append(sim_order[i][1].tolist())

    if (os.path.isfile("./Results/FileNameList.json")):
        os.remove("./Results/FileNameList.json")
    if (os.path.isfile("./Results/SimList.json")):
        os.remove("./Results/SimList.json")

    json_str = json.dumps(FileNameList, indent=0, ensure_ascii=False)
    with open('./Results/FileNameList.json', 'a') as json_file:
        json_file.write(json_str)
    json_str = json.dumps(SimList, indent=0)
    with open('./Results/SimList.json', 'a') as json_file:
        json_file.write(json_str)


    # plt.subplots_adjust(left=None, bottom=None, right=None, top=0.75, wspace=0.5, hspace=1.0)
    # plt.rcParams['font.sans-serif'] = ['SimHei']
    # plt.rcParams['font.size'] = 30
    # plt.suptitle("三维检索系统")
    # plt.show()

    return 1