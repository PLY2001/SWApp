import torch.nn as nn
import torch
import torch.nn.functional as F


class BasicBlock(nn.Module):  # 定义18层、34层ResNet的残差结构块
    expansion = 1  # 对于18层、34层，残差结构块中有2个卷积层，每个卷积层的卷积核个数是一样的，即1倍，expansion = 1
                   # 对于50层、101层、152层，残差结构块中有3个卷积层，第三层卷积层的卷积核个数是第一层和第二层卷积层的4倍，expansion = 4

    def __init__(self, in_channel, out_channel, stride=1, downsample=None, **kwargs):  # downsample表示是否分支为虚线，即分支是否要经过一次下采样
                                                                                       # in_channel是输入结构块的通道数，out_channel是结构块中第一层的输出通道数，而第二层的输出通道数为out_channel*self.expansion
        super(BasicBlock, self).__init__()
        self.conv1 = nn.Conv2d(in_channels=in_channel, out_channels=out_channel,
                               kernel_size=3, stride=stride, padding=1, bias=False)  # 因为使用bn层，那么卷积层就没必要偏置，即bias=False
        self.bn1 = nn.BatchNorm2d(out_channel)  # 定义bn层，一般每次卷积层后都要bn一次
        self.relu = nn.ReLU()
        self.conv2 = nn.Conv2d(in_channels=out_channel, out_channels=out_channel*self.expansion,
                               kernel_size=3, stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_channel*self.expansion)
        self.downsample = downsample

    def forward(self, x):  # 定义18层、34层ResNet的残差结构块中的正向传播过程
        identity = x  # 分支输入
        if self.downsample is not None:
            identity = self.downsample(x)

        out = self.conv1(x)  # 主支输入
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)

        out += identity  # 主支和分支相加
        out = self.relu(out)

        return out


class Bottleneck(nn.Module):  # 定义50层、101层、152层ResNet的残差结构块
    """
    注意：原论文中，在虚线残差结构的主分支上，第一个1x1卷积层的步距是2，第二个3x3卷积层步距是1。
    但在pytorch官方实现过程中是第一个1x1卷积层的步距是1，第二个3x3卷积层步距是2，
    这么做的好处是能够在top1上提升大概0.5%的准确率。
    可参考Resnet v1.5 https://ngc.nvidia.com/catalog/model-scripts/nvidia:resnet_50_v1_5_for_pytorch
    """
    expansion = 4  # 对于18层、34层，残差结构块中有2个卷积层，每个卷积层的卷积核个数是一样的，即1倍，expansion = 1
                   # 对于50层、101层、152层，残差结构块中有3个卷积层，第三层卷积层的卷积核个数是第一层和第二层卷积层的4倍，expansion = 4

    def __init__(self, in_channel, out_channel, stride=1, downsample=None,  # downsample表示是否分支为虚线，即分支是否要经过一次下采样
                                                                            # in_channel是输入结构块的通道数，out_channel是结构块中前两层的输出通道数,而第三层的输出通道数为out_channel*self.expansion
                 groups=1, width_per_group=64):
        super(Bottleneck, self).__init__()

        width = int(out_channel * (width_per_group / 64.)) * groups  # 给输入特征矩阵按通道数分组后，width即全部组输出的通道数，width_per_group是每组采用的卷积核个数

        self.conv1 = nn.Conv2d(in_channels=in_channel, out_channels=width,
                               kernel_size=1, stride=1, bias=False)  # squeeze channels
        self.bn1 = nn.BatchNorm2d(width)
        # -----------------------------------------
        self.conv2 = nn.Conv2d(in_channels=width, out_channels=width, groups=groups,
                               kernel_size=3, stride=stride, bias=False, padding=1)  # group=groups表示该卷积层为组卷积层
        self.bn2 = nn.BatchNorm2d(width)
        # -----------------------------------------
        self.conv3 = nn.Conv2d(in_channels=width, out_channels=out_channel*self.expansion,
                               kernel_size=1, stride=1, bias=False)  # unsqueeze channels
        self.bn3 = nn.BatchNorm2d(out_channel*self.expansion)
        self.relu = nn.ReLU(inplace=True)
        self.downsample = downsample

    def forward(self, x):  # 定义50层、101层、152层ResNet的残差结构块中的正向传播过程
        identity = x  # 分支输入
        if self.downsample is not None:
            identity = self.downsample(x)

        out = self.conv1(x)  # 主支输入
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)
        out = self.relu(out)

        out = self.conv3(out)
        out = self.bn3(out)

        out += identity  # 主支和分支相加
        out = self.relu(out)

        return out


class ResNet(nn.Module):

    def __init__(self,
                 block,  # 残差结构块的类（不是实例）
                 blocks_num,  # 每个残差结构块的重复次数（列表）
                 num_classes=1000,
                 include_top=True,  # 是否在ResNet网络模型基础上搭建更加复杂的网络
                 groups=1,
                 width_per_group=64):
        super(ResNet, self).__init__()
        self.include_top = include_top
        self.in_channel = 64

        self.groups = groups
        self.width_per_group = width_per_group

        self.conv1 = nn.Conv2d(3, self.in_channel, kernel_size=7, stride=2,
                               padding=3, bias=False)
        self.bn1 = nn.BatchNorm2d(self.in_channel)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.layer1 = self._make_layer(block, 64, blocks_num[0])  # 定义第一个残差结构层，该层第一个结构块不需要虚线下采样
        self.layer2 = self._make_layer(block, 128, blocks_num[1], stride=2)  # 定义第二个残差结构
        self.layer3 = self._make_layer(block, 256, blocks_num[2], stride=2)  # 定义第三个残差结构
        self.layer4 = self._make_layer(block, 512, blocks_num[3], stride=2)  # 定义第四个残差结构
        if self.include_top:
            self.avgpool = nn.AdaptiveAvgPool2d((1, 1))  # output size = (1, 1)
            #self.fc = nn.Linear(512 * block.expansion, num_classes)
            self.Dense1 = nn.Linear(512 * block.expansion, 1024)
            self.BN = nn.BatchNorm1d(1024)
            self.ReLU = nn.ReLU(inplace=True)
            self.Dropout = nn.Dropout(p=0.5)
            self.Dense2 = nn.Linear(1024, 128)


        for m in self.modules():  # 卷积层权重初始化
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')

    def _make_layer(self, block, channel, block_num, stride=1):  # 定义残差结构层的函数
        downsample = None
        if stride != 1 or self.in_channel != channel * block.expansion:  # 当满足条件时，就说明该残差结构块的输入通道数和输出通道数不一样了，需要虚线的下采样
            downsample = nn.Sequential(                                  # 对于50层、101层、152层ResNet，4个残差结构都需要虚线下采样
                                                                         # 对于18层、34层ResNet，后3个残差结构才需要虚线下采样
                nn.Conv2d(self.in_channel, channel * block.expansion, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(channel * block.expansion))

        layers = []
        layers.append(block(self.in_channel,
                            channel,
                            downsample=downsample,
                            stride=stride,
                            groups=self.groups,
                            width_per_group=self.width_per_group))  # 残差结构层的第一个残差结构块，比较特殊（有可能要虚线下采样）
        self.in_channel = channel * block.expansion

        for _ in range(1, block_num):   # 定义完残差结构层的剩余残差结构块
            layers.append(block(self.in_channel,
                                channel,
                                groups=self.groups,
                                width_per_group=self.width_per_group))

        return nn.Sequential(*layers)  # 将列表拆散

    def forward(self, x):  # ResNet的正向传播
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)

        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)

        if self.include_top:
            x = self.avgpool(x)
            x = torch.flatten(x, 1)
            # x = self.fc(x)

            x = self.Dense1(x)
            x = self.BN(x)
            x = self.ReLU(x)
            # x = self.Dropout(x)
            x = self.Dense2(x)
            x = F.normalize(x, p=2, dim=1)

        return x


def resnet34(num_classes=1000, include_top=True):
    # https://download.pytorch.org/models/resnet34-333f7ec4.pth
    return ResNet(BasicBlock, [3, 4, 6, 3], num_classes=num_classes, include_top=include_top)


def resnet50(num_classes=1000, include_top=True):
    # https://download.pytorch.org/models/resnet50-19c8e357.pth
    return ResNet(Bottleneck, [3, 4, 6, 3], num_classes=num_classes, include_top=include_top)


def resnet101(num_classes=1000, include_top=True):
    # https://download.pytorch.org/models/resnet101-5d3b4d8f.pth
    return ResNet(Bottleneck, [3, 4, 23, 3], num_classes=num_classes, include_top=include_top)


def resnext50_32x4d(num_classes=1000, include_top=True):
    # https://download.pytorch.org/models/resnext50_32x4d-7cdf4587.pth
    groups = 32
    width_per_group = 4
    return ResNet(Bottleneck, [3, 4, 6, 3],
                  num_classes=num_classes,
                  include_top=include_top,
                  groups=groups,
                  width_per_group=width_per_group)


def resnext101_32x8d(num_classes=1000, include_top=True):
    # https://download.pytorch.org/models/resnext101_32x8d-8ba56ff5.pth
    groups = 32
    width_per_group = 8
    return ResNet(Bottleneck, [3, 4, 23, 3],
                  num_classes=num_classes,
                  include_top=include_top,
                  groups=groups,
                  width_per_group=width_per_group)




class Loss_mv_ms(nn.Module):
    def __init__(self, device, batch_size, alpha=1.5, beta=45, lamda=0.5):
        super(Loss_mv_ms, self).__init__()
        self.alpha = alpha
        self.beta = beta
        self.lamda = lamda
        self.device = device
        self.batch_size = batch_size

    def avgSVM(self, fi, fj):
        SVM = 0
        for i in range(self.batch_size):
            index1 = torch.tensor([i]).to(self.device)
            view1 = torch.index_select(fi, 0, index1)
            # alpha = 0
            alphalist = []
            for j in range(self.batch_size):
                index2 = torch.tensor([j]).to(self.device)
                view2 = torch.index_select(fj, 0, index2)
                tview2 = view2.t()
                alphalist.append(torch.exp(view1 @ tview2))
                # alpha = alpha + torch.exp((view1@view2).item)
            sumofalpha = sum(alphalist)
            newview2 = torch.zeros((1, 128)).to(self.device)
            for k in range(self.batch_size):
                newindex2 = torch.tensor([k]).to(self.device)
                newview2 += alphalist[k] / sumofalpha * torch.index_select(fj, 0, newindex2)  #还要L2归一化，不然最后算出的特征向量不是单位向量
            newview2 = F.normalize(newview2, p=2, dim=1)
            tnewview2 = newview2.t()
            SVM += view1 @ tnewview2
        SVM /= self.batch_size
        return SVM

    def forward(self, fi, fj, b):  # fi是模型i的随机t张视图的特征向量的集合，fj是剩余b-1个模型j的随机t张视图的特征向量的集合，b是这一批模型的个数
        loss = 0
        for i in range(1, b):
            SMM1 = self.avgSVM(fi, fi)  # 模型i的所有视图与模型i的相似度SVM求和再平均化
            SMM2sum = 0 # 模型i的所有视图与模型j的相似度SVM求和再平均化，而且模型j是共b-1个模型的总和
            sum = 0
            if b > 2:
                for j in range(1, b-1):
                    SMM2sum += self.avgSVM(fi, fj[j])
                    sum += torch.exp(self.beta*(SMM2sum-self.lamda))
            else:
                sum = torch.exp(self.beta * (self.avgSVM(fi, fj) - self.lamda))
            loss += 1/self.alpha*torch.log(1+torch.exp(-self.alpha*(SMM1-self.lamda)))+1/self.beta*torch.log(1+sum)
        return torch.squeeze(loss)