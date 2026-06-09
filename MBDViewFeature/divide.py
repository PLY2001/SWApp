import os
import shutil
import random


def split_dataset(base_path="MBDViewDataset_noMBD"):
    """
    将数据集划分为训练集和验证集（7:3），并剪切文件。

    :param base_path: 数据集的根目录，包含 'photos' 文件夹。
    """
    photos_path = os.path.join(base_path, "photos")
    train_path = os.path.join(base_path, "train")
    validation_path = os.path.join(base_path, "validation")
    views_per_part = 24  # 每个零件包含的视图数量

    # 确保目标训练集和验证集目录存在，如果存在则清空
    for path in [train_path, validation_path]:
        if os.path.exists(path):
            print(f"清空现有文件夹: {path}")
            shutil.rmtree(path)
        os.makedirs(path, exist_ok=True)
        print(f"创建目标文件夹: {path}")

    # 遍历每个种类文件夹
    for type_folder_name in os.listdir(photos_path):
        type_folder_path = os.path.join(photos_path, type_folder_name)

        if not os.path.isdir(type_folder_path):
            continue  # 跳过非文件夹项

        print(f"\n处理种类文件夹: {type_folder_name}")

        # 获取所有图片文件并按名称排序，以确保零件分组正确
        all_views = sorted([f for f in os.listdir(type_folder_path) if f.endswith('.jpg') or f.endswith('.bmp')])

        # 按照每24张视图一个零件进行分组
        parts = []
        for i in range(0, len(all_views), views_per_part):
            part_views = all_views[i:i + views_per_part]
            if len(part_views) == views_per_part:  # 确保是完整的零件
                parts.append(part_views)
            else:
                print(
                    f"  警告: 种类 '{type_folder_name}' 中的文件数量不是 {views_per_part} 的倍数。跳过最后不完整的零件。")

        if not parts:
            print(f"  种类 '{type_folder_name}' 中没有发现完整的零件。")
            continue

        # 打乱零件顺序
        random.shuffle(parts)

        # 计算训练集和验证集的零件数量
        total_parts = len(parts)
        train_parts_count = int(total_parts * 0.7)

        train_set_parts = parts[:train_parts_count]
        validation_set_parts = parts[train_parts_count:]

        print(f"  总零件数: {total_parts}")
        print(f"  训练集零件数: {len(train_set_parts)}")
        print(f"  验证集零件数: {len(validation_set_parts)}")

        # 创建训练集和验证集的目标子文件夹
        target_train_type_path = os.path.join(train_path, type_folder_name)
        target_validation_type_path = os.path.join(validation_path, type_folder_name)
        os.makedirs(target_train_type_path, exist_ok=True)
        os.makedirs(target_validation_type_path, exist_ok=True)

        # 剪切移动文件到训练集
        for part_idx, part_views in enumerate(train_set_parts):
            for view_file_name in part_views:
                src_path = os.path.join(type_folder_path, view_file_name)
                dst_path = os.path.join(target_train_type_path, view_file_name)
                try:
                    shutil.move(src_path, dst_path)
                except FileNotFoundError:
                    print(f"    文件未找到，跳过: {src_path}")
            print(f"  已移动 {len(part_views)} 个视图到训练集 (零件 {part_idx + 1}/{len(train_set_parts)})")

        # 剪切移动文件到验证集
        for part_idx, part_views in enumerate(validation_set_parts):
            for view_file_name in part_views:
                src_path = os.path.join(type_folder_path, view_file_name)
                dst_path = os.path.join(target_validation_type_path, view_file_name)
                try:
                    shutil.move(src_path, dst_path)
                except FileNotFoundError:
                    print(f"    文件未找到，跳过: {src_path}")
            print(f"  已移动 {len(part_views)} 个视图到验证集 (零件 {part_idx + 1}/{len(validation_set_parts)})")

    print("\n数据集划分并剪切完成！")
    print("注意: photos 文件夹下的原始数据已被移动。")


# 当文件存在时，可以调用此函数来执行划分
if __name__ == "__main__":
    split_dataset()
