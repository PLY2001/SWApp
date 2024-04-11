import os
import json
import sys

import matplotlib
import torch
from PIL import Image
from torchvision import transforms
import matplotlib.pyplot as plt
import  torchvision
from model import resnet34

from tqdm import tqdm
import torch.nn.functional as F

import re

def main():
    #matplotlib.use("TKAgg")
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    data_transform = transforms.Compose(
        [transforms.Resize(224),
         # transforms.CenterCrop(224),
         transforms.ToTensor(),
         transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])


    # load image
    img_path = "pan1_1_1_0.bmp"  # 搜索这张图
    assert os.path.exists(img_path), "file: '{}' dose not exist.".format(img_path)
    img = Image.open(img_path)
    plt.subplot(231)
    plt.imshow(img)
    plt.title("检索目标")
    # [N, C, H, W]
    img = data_transform(img)
    torchvision.utils.save_image(img, 'out.jpg')
    # expand batch dimension
    img = torch.unsqueeze(img, dim=0)

    # read dataset
    json_path = './MBDViewDataset.json'
    assert os.path.exists(json_path), "file: '{}' dose not exist.".format(json_path)

    # with open(json_path, "r") as f:
    #     data_list = json.load(f)

    file = open(json_path, 'r')
    data_list = []
    view_list = []
    load_bar = tqdm(file.readlines(), file=sys.stdout)
    viewStart = False
    viewStop = True
    for line in load_bar:
        if line == '    [\n' and viewStop:
            viewStart = True
            continue
        if line == '    ],\n' or line == '    ]\n' and viewStart:
            viewStop = True
            data_list.append(view_list[:])
            view_list.clear()
        if viewStart:
            pattern = "[-]?[0-9]+[.]{1}[0-9]*"
            match = re.findall(pattern, line)
            if len(match) > 0:
                num = json.loads(match[0])
                view_list.append(num)
        load_bar.desc = "加载数据库中"



    data_tensor = torch.tensor(data_list).to(device)
    # create model
    model = resnet34().to(device)

    # load model weights
    weights_path = "./MBDNet34.pth"
    assert os.path.exists(weights_path), "file: '{}' dose not exist.".format(weights_path)
    model.load_state_dict(torch.load(weights_path, map_location=device))

    # prediction
    model.eval()
    with torch.no_grad():
        # predict class
        output = model(img.to(device))
        output = F.normalize(output, p=2, dim=1)

        # best_similarity = -100.0

        sim_dic = {}
        predict_bar = tqdm(range(len(data_tensor)), file=sys.stdout)
        for i in predict_bar:
            index = torch.tensor([i]).to(device)
            view = torch.index_select(data_tensor, 0, index)
            view = F.normalize(view, p=2, dim=1)
            similarity = (output@view.t()).item()
            sim_dic[i] = similarity
            # if similarity > best_similarity:
            #     best_similarity = similarity
            #     best_index = i
            predict_bar.desc = "检索中"
    sim_order = sorted(sim_dic.items(), key=lambda x: x[1], reverse=True)

    # print(f"best_similarity = {best_similarity}")

    # load image
    fileList = os.listdir('./MBDViewDataset/photos')
    fileList.sort()
    FileNameList = []
    SimList = []
    for i in range(5 if 5 < len(data_list) else len(data_list)):
        thisindex = sim_order[i][0]
        Target_img_path = "MBDViewDataset/photos/"+fileList[thisindex]
        img1 = Image.open(Target_img_path)
        plt.subplot(232+i)
        plt.imshow(img1)
        plt.title(f"检索结果{i+1}\n{fileList[thisindex]}\n相似度：{sim_order[i][1]*100:.3f}%")
        FileNameList.append(fileList[thisindex])
        SimList.append(sim_order[i][1])

    # if (os.path.isfile("FileNameList.json")):
    #     os.remove("FileNameList.json")
    # if (os.path.isfile("SimList.json")):
    #     os.remove("SimList.json")
    #
    # json_str = json.dumps(FileNameList, indent=0)
    # with open('FileNameList.json', 'a') as json_file:
    #     json_file.write(json_str)
    # json_str = json.dumps(SimList, indent=0)
    # with open('SimList.json', 'a') as json_file:
    #     json_file.write(json_str)

    plt.subplots_adjust(left=None, bottom=None, right=None, top=0.75, wspace=1.8, hspace=1.5)
    plt.rcParams['font.sans-serif'] = ['FangSong']
    plt.rcParams['font.size'] = 15
    plt.suptitle("三维检索系统")
    plt.show()


if __name__ == '__main__':
    main()
