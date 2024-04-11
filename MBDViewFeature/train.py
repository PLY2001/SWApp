import os
import sys
import json

import torch
import torch.nn as nn
from torchvision import transforms, datasets
import torch.optim as optim
from tqdm import tqdm
import matplotlib.pyplot as plt
from matplotlib.pyplot import MultipleLocator

from model import resnet34,Loss_mv_ms
import random
import numpy as np

def main():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print("using {} device.".format(device))

    # transforms.RandomVerticalFlip(),
    # transforms.ColorJitter(brightness=1, contrast=1, hue=0.5),
    # transforms.ColorJitter(brightness=1, contrast=1),
    # data_transform = {
    #     "train": transforms.Compose([transforms.RandomResizedCrop(224),
    #                                  transforms.RandomHorizontalFlip(),
    #                                  transforms.ToTensor(),
    #                                  transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])]),
    #     "val": transforms.Compose([transforms.Resize(256),  # 图片等比例缩放，使得最小的边长为256
    #                                transforms.CenterCrop(224),  # 从中心裁剪出224x224的图片
    #                                transforms.ToTensor(),
    #                                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])}

    # data_root = os.getcwd()  # get data root path
    # image_path = os.path.join(data_root, "Fmodelnet40v1")  # flower data set path
    # assert os.path.exists(image_path), "{} path does not exist.".format(image_path)
    # train_dataset = datasets.ImageFolder(root=os.path.join(image_path, "train"),
    #                                      transform=data_transform["train"])
    # train_num = len(train_dataset)


    # batch_size = 12
    # nw = 0 #min([os.cpu_count(), batch_size if batch_size > 1 else 0, 8])  # number of workers
    # print('Using {} dataloader workers every process'.format(nw))
    #
    # train_loader = torch.utils.data.DataLoader(train_dataset,
    #                                            batch_size=batch_size, shuffle=False,
    #                                            num_workers=nw)
    #
    # validate_dataset = datasets.ImageFolder(root=os.path.join(image_path, "val"),
    #                                         transform=data_transform["val"])
    # val_num = len(validate_dataset)
    # validate_loader = torch.utils.data.DataLoader(validate_dataset,
    #                                               batch_size=batch_size, shuffle=False,
    #                                               num_workers=nw)
    # print("using {} images for training, {} images for validation.".format(train_num,
    #                                                                        val_num))


    #######################载入预训练模型##########################
    net = resnet34()
    # load pretrain weights
    # download url: https://download.pytorch.org/models/resnet34-333f7ec4.pth
    model_weight_path = "./resnet34-pre.pth"  # 预训练好的模型参数
    assert os.path.exists(model_weight_path), "file {} does not exist.".format(model_weight_path)
    net.load_state_dict(torch.load(model_weight_path, map_location='cpu'), strict=False)  # 加载预训练好的模型参数
    # for param in net.parameters():
    #     param.requires_grad = False

    # change fc layer structure
    # in_channel = net.fc.in_features  # 获取模型的全连接层的输入特征数量in_features
    # net.fc = nn.Linear(in_channel, 40)  # 将模型的全连接层改为输出40个类别
    net.to(device)
    ##############################################################


    # loss_function = Loss_mv_ms(device=device,batch_size=batch_size)
    # construct an optimizer
    # params = [p for p in net.parameters() if p.requires_grad]
    # optimizer = optim.Adam(params, lr=0.0001)

    # torch.autograd.set_detect_anomaly(True)
    # with torch.autograd.set_detect_anomaly(True):
    # epochs = 100
    # best_valloss = 100.0
    save_path = './MBDNet34.pth'
    # train_steps = len(train_loader)
    # val_steps = len(validate_loader)
    # train_loss_y_list = []
    # train_loss_x_list = []
    # val_loss_y_list = []
    # val_loss_x_list = []
    #toContinue = 0
    torch.save(net.state_dict(), save_path)
    # imageslist = []
    # train_bar = tqdm(train_loader, file=sys.stdout)
    # for step, data in enumerate(train_bar):
    #     images, labels = data
    #     imageslist.append(images)
    #
    # if not imageslist:
    #     print("imageslist is empty")
    # else:
    #     print("imageslist is not empty")
    #
    # val_imageslist = []
    # val_bar = tqdm(validate_loader, file=sys.stdout)
    # for val_step, val_data in enumerate(val_bar):
    #     val_images, val_labels = val_data
    #     val_imageslist.append(val_images)
    #
    # if not val_imageslist:
    #     print("val_imageslist is empty")
    # else:
    #     print("val_imageslist is not empty")
    #
    # imagesIndex = list(range(train_steps))
    # val_imagesIndex = list(range(val_steps))

    '''
    for epoch in range(epochs):
        toContinue = 0
        running_loss = 0.0
        outputslist = []
        new_imagesIndex = np.random.permutation(imagesIndex)
        print(new_imagesIndex)
        new_val_imagesIndex = np.random.permutation(val_imagesIndex)




        for times in range(0, train_steps):
            #print(times)
            # train
            net.train()
            if (times + 1) % (12 / batch_size) != 0:  # 每两次算一次
                continue
            optimizer.zero_grad()
            outputs = net(imageslist[new_imagesIndex[times]].to(device))
            outputslist.append(outputs)

            if (times + 1) % (24 / batch_size) != 0:  # 每4次算一次
                continue
            loss = loss_function(outputslist[-2], outputslist[-1], 2)
            outputslist.clear()
            loss.backward()
            optimizer.step()
            # print statistics
            running_loss += loss.item()


        train_loss_y_list.append(running_loss / train_steps)
        train_loss_x_list.append(1 + epoch)
        print("train loss",train_loss_x_list[-1], train_loss_y_list[-1], sep=',')
            # train_bar.desc = "train epoch[{}/{}] loss:{:.3f}".format(epoch + 1,epochs,loss)

        # validate
        net.eval()
        valloss = 0.0  # accumulate accurate number / epoch
        valoutputslist = []

        with torch.no_grad():
            for times in range(0, val_steps):
                #print(times)
                if (times + 1) % (12 / batch_size) != 0:  # 每两次算一次
                    continue
                outputs = net(val_imageslist[new_val_imagesIndex[times]].to(device))
                valoutputslist.append(outputs)

                if (times + 1) % (24 / batch_size) != 0:  # 每4次算一次
                    continue

                loss = loss_function(valoutputslist[-2], valoutputslist[-1], 2)
                valoutputslist.clear()
                # predict_y = torch.max(outputs, dim=1)[1]
                # acc += torch.eq(predict_y, val_labels.to(device)).sum().item()
                valloss += loss.item()

        val_loss_y_list.append(valloss / val_steps)
        val_loss_x_list.append(1 + epoch)
        print("val loss",val_loss_x_list[-1], val_loss_y_list[-1], sep=',')



        valloss /= val_steps
        print('[epoch %d] train_loss: %.3f  val_loss: %.3f' %
              (epoch + 1, running_loss / train_steps, valloss))

        if valloss < best_valloss:
            best_valloss = valloss
            torch.save(net.state_dict(), save_path)

        #plt.gca().set_color_cycle(['red', 'blue'])
        plt.plot(train_loss_x_list, train_loss_y_list, color='red')
        plt.plot(val_loss_x_list, val_loss_y_list, color='blue')
        plt.legend(['train_loss', 'val_loss'], loc='upper right')
        plt.xlabel('Epoch')
        plt.ylabel('Loss')
        ax = plt.gca()
        # ax为两条坐标轴的实例
        ax.xaxis.set_major_locator(MultipleLocator(1))
        # 把x轴的主刻度设置为1的倍数
        plt.show()

        if (epoch+1)%5 == 0:
            while toContinue == 0:
                toContinue = int(input("输入1继续，输入2终止并保存"))
        if toContinue == 2:
            break
    print('Finished Training')
    '''




if __name__ == '__main__':
    main()
