import os
import sys
import numpy as np
from tqdm import tqdm
from PIL import Image
import random

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, datasets
import matplotlib.pyplot as plt

from model import resnet34

def classify_to_coarse_type(class_name):
    """
    将具体的零件类型归类到粗粒度类型
    """
    name_lower = class_name.lower()
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

class HierarchicalSamplingDataset(Dataset):
    def __init__(self, root_dir, transform=None):
        self.root_dir = root_dir
        self.transform = transform
        self.image_folder = datasets.ImageFolder(root_dir)
        
        self.fine_grained_classes = self.image_folder.classes
        self.fine_grained_labels = np.array(self.image_folder.targets)

        # --- Build Class Hierarchy ---
        self.fine_to_coarse_map = {fine_cls: classify_to_coarse_type(fine_cls) for fine_cls in self.fine_grained_classes}
        self.coarse_grained_classes = sorted(list(set(self.fine_to_coarse_map.values())))
        self.coarse_class_to_idx = {cls_name: i for i, cls_name in enumerate(self.coarse_grained_classes)}
        
        self.coarse_to_fine_map = {coarse_cls: [] for coarse_cls in self.coarse_grained_classes}
        for fine_idx, fine_cls in enumerate(self.fine_grained_classes):
            coarse_cls = self.fine_to_coarse_map[fine_cls]
            self.coarse_to_fine_map[coarse_cls].append(fine_idx)

        # --- Group images by model and class ---
        self.model_to_images = {}
        self.model_to_fine_label = {}
        self.model_to_coarse_label = {}
        
        for img_path, fine_label_idx in self.image_folder.imgs:
            model_id = "_".join(os.path.basename(img_path).split('_')[:-3])
            fine_class_name = self.fine_grained_classes[fine_label_idx]
            full_model_id = f"{fine_class_name}/{model_id}"

            if full_model_id not in self.model_to_images:
                self.model_to_images[full_model_id] = [None] * 24 # Corrected from 36 to 24
                self.model_to_fine_label[full_model_id] = fine_label_idx
                coarse_class_name = self.fine_to_coarse_map[fine_class_name]
                self.model_to_coarse_label[full_model_id] = self.coarse_class_to_idx[coarse_class_name]

            try:
                view_dir = int(os.path.basename(img_path).split('_')[-3])
                view_type = int(os.path.basename(img_path).split('_')[-2])
                cull_mode = int(os.path.basename(img_path).split('_')[-1].split('.')[0]) # Corrected parsing
                view_index = view_dir * 4 + view_type * 2 + cull_mode # Corrected formula
                self.model_to_images[full_model_id][view_index] = img_path
            except (ValueError, IndexError):
                continue

        self.models = list(self.model_to_images.keys())
        
        # --- Pre-calculate model lists for sampling ---
        self.fine_label_to_models = {i: [] for i in range(len(self.fine_grained_classes))}
        self.coarse_label_to_models = {i: [] for i in range(len(self.coarse_grained_classes))}
        for model_id in self.models:
            fine_label = self.model_to_fine_label[model_id]
            coarse_label = self.model_to_coarse_label[model_id]
            self.fine_label_to_models[fine_label].append(model_id)
            self.coarse_label_to_models[coarse_label].append(model_id)

        # View indices for coarse (a) and fine (b) views, assuming cull_mode=0
        # Coarse view (a) uses view_type=0
        # Fine view (b) uses view_type=1
        self.indices_coarse = [i * 4 + 0 * 2 + 0 for i in range(6)] # view_type=0
        self.indices_fine = [i * 4 + 1 * 2 + 0 for i in range(6)]   # view_type=1

    def __len__(self):
        return len(self.models)

    def __getitem__(self, index):
        anchor_model_id = self.models[index]
        anchor_fine_label = self.model_to_fine_label[anchor_model_id]
        anchor_coarse_label = self.model_to_coarse_label[anchor_model_id]

        # --- Coarse-grained Triplet Sampling (for view 'a') ---
        # Positive: same coarse class, different fine class if possible
        possible_pos_fine_labels = self.coarse_to_fine_map[self.coarse_grained_classes[anchor_coarse_label]]
        pos_fine_label_coarse = anchor_fine_label
        if len(possible_pos_fine_labels) > 1:
            while pos_fine_label_coarse == anchor_fine_label:
                pos_fine_label_coarse = random.choice(possible_pos_fine_labels)
        
        positive_model_pool_coarse = self.fine_label_to_models[pos_fine_label_coarse]
        positive_model_id_coarse = random.choice(positive_model_pool_coarse)

        # Negative: different coarse class
        neg_coarse_label = random.choice(list(set(self.coarse_label_to_models.keys()) - {anchor_coarse_label}))
        negative_model_id_coarse = random.choice(self.coarse_label_to_models[neg_coarse_label])

        # --- Fine-grained Triplet Sampling (for view 'b') ---
        # Positive: same fine class, different model
        positive_model_pool_fine = self.fine_label_to_models[anchor_fine_label]
        positive_model_id_fine = anchor_model_id
        if len(positive_model_pool_fine) > 1:
            while positive_model_id_fine == anchor_model_id:
                positive_model_id_fine = random.choice(positive_model_pool_fine)
        
        # Negative: different fine class
        neg_fine_label = random.choice(list(set(self.fine_label_to_models.keys()) - {anchor_fine_label}))
        negative_model_id_fine = random.choice(self.fine_label_to_models[neg_fine_label])

        # --- Load Views ---
        view_direction_idx = np.random.randint(0, 6)
        view_idx_coarse = self.indices_coarse[view_direction_idx]
        view_idx_fine = self.indices_fine[view_direction_idx]

        def get_view(model_id, view_idx):
            img_path = self.model_to_images[model_id][view_idx]
            if img_path and os.path.exists(img_path):
                img = Image.open(img_path).convert('RGB')
                if self.transform:
                    img = self.transform(img)
                return img
            return torch.zeros(3, 224, 224)

        anchor_view_a = get_view(anchor_model_id, view_idx_coarse)
        positive_view_a = get_view(positive_model_id_coarse, view_idx_coarse)
        negative_view_a = get_view(negative_model_id_coarse, view_idx_coarse)

        anchor_view_b = get_view(anchor_model_id, view_idx_fine)
        positive_view_b = get_view(positive_model_id_fine, view_idx_fine)
        negative_view_b = get_view(negative_model_id_fine, view_idx_fine)

        return (anchor_view_a, positive_view_a, negative_view_a, 
                anchor_view_b, positive_view_b, negative_view_b)


class HierarchicalSamplingTripletLoss(nn.Module):
    def __init__(self, margin=1.0):
        super(HierarchicalSamplingTripletLoss, self).__init__()
        self.margin = margin
        self.triplet_loss = nn.TripletMarginLoss(margin=margin, p=2)

    def forward(self, anchor_a, positive_a, negative_a, anchor_b, positive_b, negative_b):
        loss_a = self.triplet_loss(anchor_a, positive_a, negative_a)
        loss_b = self.triplet_loss(anchor_b, positive_b, negative_b)
        return loss_a + loss_b

def main():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"Using {device} device.")

    data_transform = {
        "train": transforms.Compose([
            transforms.Resize(256),
            transforms.RandomResizedCrop(224),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ]),
        "val": transforms.Compose([
            transforms.Resize(224),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
    }

    data_root = os.getcwd()
    train_image_path = os.path.join(data_root, "MBDViewDataset_noMBD/train")
    val_image_path = os.path.join(data_root, "MBDViewDataset_noMBD/validation")

    train_dataset = HierarchicalSamplingDataset(root_dir=train_image_path, transform=data_transform["train"])
    val_dataset = HierarchicalSamplingDataset(root_dir=val_image_path, transform=data_transform["val"])

    batch_size = 8
    nw = min([os.cpu_count(), batch_size if batch_size > 1 else 0, 8])
    print(f'Using {nw} dataloader workers every process')

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=nw)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=nw)

    print(f"Training on {len(train_dataset)} models, validating on {len(val_dataset)} models.")

    net = resnet34()
    model_weight_path = "./resnet34-pre.pth"
    if os.path.exists(model_weight_path):
        net.load_state_dict(torch.load(model_weight_path, map_location='cpu'), strict=False)
    net.to(device)

    loss_function = HierarchicalSamplingTripletLoss(margin=1.0).to(device)
    optimizer = optim.Adam(net.parameters(), lr=1e-5)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=20, gamma=0.1)

    epochs = 100
    best_val_loss = float('inf')
    save_path = './MBDNet34_hierarchical_sampling.pth'

    train_loss_list, val_loss_list, epoch_list = [], [], []

    for epoch in range(epochs):
        net.train()
        running_loss = 0.0
        train_bar = tqdm(train_loader, file=sys.stdout)
        for data in train_bar:
            anchor_a, pos_a, neg_a, anchor_b, pos_b, neg_b = [d.to(device) for d in data]
            
            optimizer.zero_grad()
            
            feat_anchor_a = net(anchor_a)
            feat_pos_a = net(pos_a)
            feat_neg_a = net(neg_a)
            
            feat_anchor_b = net(anchor_b)
            feat_pos_b = net(pos_b)
            feat_neg_b = net(neg_b)
            
            loss = loss_function(feat_anchor_a, feat_pos_a, feat_neg_a, feat_anchor_b, feat_pos_b, feat_neg_b)
            loss.backward()
            optimizer.step()

            running_loss += loss.item()
            train_bar.set_description(f"Train E[{epoch+1}] L:{loss.item():.3f}")

        scheduler.step()
        train_loss = running_loss / len(train_loader)
        train_loss_list.append(train_loss)
        epoch_list.append(epoch + 1)
        print(f"[Epoch {epoch+1}] Train Loss: {train_loss:.4f}")

        net.eval()
        val_loss = 0.0
        with torch.no_grad():
            val_bar = tqdm(val_loader, file=sys.stdout)
            for data in val_bar:
                anchor_a, pos_a, neg_a, anchor_b, pos_b, neg_b = [d.to(device) for d in data]
                feat_anchor_a, feat_pos_a, feat_neg_a = net(anchor_a), net(pos_a), net(neg_a)
                feat_anchor_b, feat_pos_b, feat_neg_b = net(anchor_b), net(pos_b), net(neg_b)
                loss = loss_function(feat_anchor_a, feat_pos_a, feat_neg_a, feat_anchor_b, feat_pos_b, feat_neg_b)
                val_loss += loss.item()
                val_bar.set_description(f"Val E[{epoch+1}]")

        val_loss /= len(val_loader)
        val_loss_list.append(val_loss)
        print(f"[Epoch {epoch+1}] Val Loss: {val_loss:.4f}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(net.state_dict(), save_path)
            print(f"New best model saved to {save_path}")

        plt.figure(figsize=(10, 6))
        plt.plot(epoch_list, train_loss_list, 'b-', label='Train Loss')
        plt.plot(epoch_list, val_loss_list, 'r-', label='Validation Loss')
        plt.xlabel('Epoch')
        plt.ylabel('Loss')
        plt.title(f'Loss Curve up to Epoch {epoch+1}')
        plt.legend()
        plt.grid(True)
        plt.show()

    print('Finished Training')

if __name__ == '__main__':
    main()
