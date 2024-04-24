import os
import sys
import json

import torch
import torch.nn as nn
import torchvision.utils
from torchvision import transforms, datasets
import torch.optim as optim
#from tqdm import tqdm

from model import resnet34,Loss_mv_ms

def main():
    os.chdir("C:/Users/PLY/Desktop/Files/Projects/Pycharm Projects/MBDViewFeature")
    dataset1_num = 0
    viewCount = 18
    for i in range(2):
        hasMBD = i
        dataset = "MBDViewDataset" if hasMBD == 0 else "MBDViewDataset_noMBD"

        if (os.path.isfile(dataset + ".json")):
            os.remove(dataset + ".json")

        device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        # print("using {} device.".format(device))

        data_transform = transforms.Compose([transforms.Resize(224),  # 图片等比例缩放，使得最小的边长为256
                                             #transforms.CenterCrop(224),  # 从中心裁剪出224x224的图片
                                             transforms.ToTensor(),
                                             transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])

        data_root = os.getcwd()  # get data root path
        image_path = os.path.join(data_root, dataset)  # flower data set path
        assert os.path.exists(image_path), "{} path does not exist.".format(image_path)
        dataset1 = datasets.ImageFolder(root=image_path,
                                             transform=data_transform)
        dataset1_num = len(dataset1)



        batch_size = viewCount
        nw = 0 #min([os.cpu_count(), batch_size if batch_size > 1 else 0, 8])  # number of workers
        # print('Using {} dataloader workers every process'.format(nw))

        dataset1_loader = torch.utils.data.DataLoader(dataset1,
                                                   batch_size=batch_size, shuffle=False,
                                                   num_workers=nw)


        # print("using {} images.".format(dataset1_num))


        #######################载入预训练模型##########################
        net = resnet34()
        model_weight_path = "./MBDNet34.pth"  # 预训练好的模型参数
        assert os.path.exists(model_weight_path), "file {} does not exist.".format(model_weight_path)
        net.load_state_dict(torch.load(model_weight_path, map_location='cpu'))  # 加载预训练好的模型参数
        net.to(device)
        ##############################################################



        # dataset1
        net.eval()
        with torch.no_grad():
            #dataset1_bar = tqdm(dataset1_loader, file=sys.stdout)
            dataset1_bar = dataset1_loader
            for step, data in enumerate(dataset1_bar):
                images, labels = data
                # torchvision.utils.save_image(images,'out.jpg')
                outputs = net(images.to(device))
                json_str = json.dumps(outputs.tolist(), indent=4)
                with open(dataset + ".json", 'a') as json_file:
                    json_file.write(json_str)


        #print('Finished Building Dataset')

    modelCount = round(dataset1_num / viewCount)
    return modelCount
