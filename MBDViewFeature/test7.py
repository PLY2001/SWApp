import os
import shutil


def keep_first_view_for_each_model_in_V_folder(base_path="MBDViewDataset_noMBD"):
    """
    遍历指定路径下 'V' 文件夹中的每个类型文件夹。
    在每个类型文件夹内，将文件按照每24张视图一个模型进行分组，
    并对每个模型组只保留第一张视图，其余删除。
    :param base_path: 数据集的根目录，包含 'V' 文件夹。
    """
    v_folder_path = os.path.join(base_path, "V")
    views_per_model = 24  # 每个模型包含的视图数量

    if not os.path.exists(v_folder_path):
        print(f"错误: 文件夹 '{v_folder_path}' 不存在。请确认路径是否正确。")
        return

    print(f"开始处理文件夹: {v_folder_path}")

    # 遍历'V'文件夹中的所有子文件夹（即类型文件夹）
    for type_folder_name in os.listdir(v_folder_path):
        type_folder_path = os.path.join(v_folder_path, type_folder_name)

        if not os.path.isdir(type_folder_path):
            continue  # 跳过非文件夹项

        print(f"\n处理类型文件夹: {type_folder_name}")

        # 获取当前类型文件夹内所有的图片文件，并按名称排序
        all_views_in_type_folder = sorted(
            [f for f in os.listdir(type_folder_path) if f.endswith('.jpg') or f.endswith('.bmp')])

        if not all_views_in_type_folder:
            print(f"  类型 '{type_folder_name}' 中没有发现任何图片文件。")
            continue

        print(f"  在类型 '{type_folder_name}' 中发现 {len(all_views_in_type_folder)} 张视图。")

        # 将视图文件按照每 views_per_model 张作为一个模型进行分组
        models_views = []
        for i in range(0, len(all_views_in_type_folder), views_per_model):
            model_group = all_views_in_type_folder[i:i + views_per_model]
            if len(model_group) == views_per_model:  # 确保是完整的模型组
                models_views.append(model_group)
            else:
                print(
                    f"  警告: 类型 '{type_folder_name}' 中的文件数量不是 {views_per_model} 的倍数。跳过最后不完整的模型组。")

        if not models_views:
            print(f"  类型 '{type_folder_name}' 中没有发现完整的模型组。")
            continue

        print(f"  总共识别出 {len(models_views)} 个完整的模型。")

        # 遍历每个模型组，保留第一张视图，删除其余
        for model_idx, model_group in enumerate(models_views):
            print(f"  处理模型组 {model_idx + 1}/{len(models_views)} (包含 {len(model_group)} 张视图):")

            first_view_in_model = model_group[0]
            print(f"    保留第一张视图: {first_view_in_model}")

            for view_file_name in model_group:
                if view_file_name != first_view_in_model:
                    file_path_to_delete = os.path.join(type_folder_path, view_file_name)
                    try:
                        os.remove(file_path_to_delete)
                        print(f"    已删除: {view_file_name}")
                    except OSError as e:
                        print(f"    删除文件失败 {file_path_to_delete}: {e}")

    print("\n所有类型文件夹处理完成！")
    print("注意: 'V' 文件夹下每个模型的除了第一张以外的视图已被删除。")


# 当文件存在时，可以调用此函数来执行操作
if __name__ == "__main__":
    keep_first_view_for_each_model_in_V_folder()
