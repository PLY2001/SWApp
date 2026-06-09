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



def main():
    hasMBD = input("是否考虑MBD？ y/n:")
    dataset = "MBDViewDataset" if hasMBD == "y" else "MBDViewDataset_noMBD"
    modelCount = 188
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
    inputName = input("检索目标名称:")
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

    X = output_tensor.cpu().numpy()
    A = np.arange(0, 100).reshape(10, 10)

    ax = plt.matshow(X)
    plt.colorbar(ax.colorbar, fraction=0.025)
    plt.axis('off')
    plt.title("matrix X");
    plt.show()


if __name__ == '__main__':
    main()
