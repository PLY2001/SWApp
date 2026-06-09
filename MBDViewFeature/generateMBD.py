import os
import shutil
from PIL import Image


def hex_to_rgb(hex_color):
    """将十六进制颜色字符串转换为RGB元组。"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


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
            [f for f in os.listdir(type_folder_path) if f.lower().endswith(('.jpg', '.bmp'))])
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


def _process_directory(directory_path, palette_map, predefined_palettes, palette_index_ref):
    """
    处理指定目录（train或validation）中的所有类型文件夹。
    """
    if not os.path.exists(directory_path):
        print(f"错误: 文件夹 '{directory_path}' 不存在。请确认路径是否正确。")
        return

    print(f"\n开始处理文件夹: {directory_path}")

    # 视图文件命名模式
    c1_patterns = ["_0_0_1.bmp", "_1_0_1.bmp", "_2_0_1.bmp", "_3_0_1.bmp", "_4_0_1.bmp", "_5_0_1.bmp"]
    c2_patterns = ["_0_1_1.bmp", "_1_1_1.bmp", "_2_1_1.bmp", "_3_1_1.bmp", "_4_1_1.bmp", "_5_1_1.bmp"]

    type_folders = sorted([d for d in os.listdir(directory_path) if os.path.isdir(os.path.join(directory_path, d))])
    
    for type_folder_name in type_folders:
        type_folder_path = os.path.join(directory_path, type_folder_name)
        print(f"\n处理类型文件夹: {type_folder_name}")

        # 为当前类型文件夹分配一个专属调色板（如果尚未分配）
        if type_folder_name not in palette_map:
            if palette_index_ref[0] < len(predefined_palettes):
                palette_map[type_folder_name] = predefined_palettes[palette_index_ref[0]]
                palette_index_ref[0] += 1
            else:
                print(f"  警告: 调色板池不足，将从头开始复用。")
                palette_map[type_folder_name] = predefined_palettes[0]
        
        palette_hex = palette_map[type_folder_name]
        c1_color_rgb = hex_to_rgb(palette_hex[0])
        c2_colors_rgb = [hex_to_rgb(c) for c in palette_hex[1:]]
        print(f"  为类型 '{type_folder_name}' 指定调色板: c1={palette_hex[0]}, c2={palette_hex[1:]}")

        # 按模型ID对图片进行分组
        all_images_in_type_folder = [f for f in os.listdir(type_folder_path) if f.lower().endswith(('.jpg', '.bmp'))]
        models = {}
        for image_name in all_images_in_type_folder:
            model_id = image_name.split('_')[0]
            if model_id not in models:
                models[model_id] = []
            models[model_id].append(image_name)
        
        if not models:
            print(f"  类型 '{type_folder_name}' 中没有发现任何图片文件。")
            continue

        sorted_model_ids = sorted(models.keys())
        print(f"  在类型 '{type_folder_name}' 中发现 {len(sorted_model_ids)} 个模型。")

        processed_count = 0
        for model_idx, model_id in enumerate(sorted_model_ids):
            # 为当前模型确定c2视图的颜色
            c2_model_color_rgb = c2_colors_rgb[model_idx % 3]
            
            for image_name in models[model_id]:
                target_color_rgb = None
                # 判断图片是c1还是c2视图，并分配相应颜色
                if any(image_name.endswith(p) for p in c1_patterns):
                    target_color_rgb = c1_color_rgb
                elif any(image_name.endswith(p) for p in c2_patterns):
                    target_color_rgb = c2_model_color_rgb
                else:
                    continue  # 如果不是c1或c2视图，则跳过

                image_path = os.path.join(type_folder_path, image_name)
                try:
                    with Image.open(image_path) as img:
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                        pixels = img.load()
                        width, height = img.size
                        has_changed = False
                        for x in range(width):
                            for y in range(height):
                                r, g, b = pixels[x, y]
                                if not (r > 240 and g > 240 and b > 240):
                                    pixels[x, y] = target_color_rgb
                                    has_changed = True
                        
                        if has_changed:
                            img.save(image_path)
                            processed_count += 1
                except Exception as e:
                    print(f"    处理图片 '{image_name}' 失败: {e}")
        
        if processed_count > 0:
            print(f"  总共处理了 {processed_count} 张符合条件的图片。")
        else:
            print(f"  在类型 '{type_folder_name}' 中没有找到符合条件的图片或无需处理。")

    print(f"\n文件夹 {directory_path} 处理完成！")


def run_color_processing(base_path="MBDViewDataset_noMBD"):
    """
    对 'train' 和 'validation' 文件夹执行颜色处理。
    使用共享的调色板映射以确保数据一致性。
    """
    # 预定义调色板列表。每个调色板包含4种颜色:
    # [c1_基准色, c2_相似色1, c2_相似色2, c2_相似色3]
    # 扩充至70组，以确保69种类型都有独立的颜色方案。
    predefined_palettes = [
        ["#8B0000", "#DC143C", "#FF4500", "#FF6347"],  # 1. Red-ish
        ["#006400", "#228B22", "#32CD32", "#ADFF2F"],  # 2. Green-ish
        ["#00008B", "#4169E1", "#4682B4", "#87CEEB"],  # 3. Blue-ish
        ["#8B4513", "#A0522D", "#CD853F", "#D2B48C"],  # 4. Brown-ish
        ["#4B0082", "#8A2BE2", "#9932CC", "#BA55D3"],  # 5. Purple-ish
        ["#FF8C00", "#FFA500", "#FFD700", "#FFFF00"],  # 6. Orange/Yellow-ish
        ["#008B8B", "#20B2AA", "#48D1CC", "#AFEEEE"],  # 7. Teal/Cyan-ish
        ["#FF1493", "#FF69B4", "#FFB6C1", "#FFC0CB"],  # 8. Pink-ish
        ["#696969", "#808080", "#A9A9A9", "#C0C0C0"],  # 9. Gray-ish
        ["#556B2F", "#6B8E23", "#9ACD32", "#BDB76B"],  # 10. Olive-ish
        ["#800080", "#9400D3", "#DA70D6", "#EE82EE"],  # 11. Magenta/Violet-ish
        ["#B22222", "#CD5C5C", "#E9967A", "#FA8072"],  # 12. Firebrick/Salmon-ish
        ["#191970", "#0000CD", "#6495ED", "#B0C4DE"],  # 13. Midnight/Cornflower Blue-ish
        ["#808000", "#B8860B", "#DAA520", "#F0E68C"],  # 14. Olive/Gold-ish
        ["#483D8B", "#6A5ACD", "#7B68EE", "#9370DB"],  # 15. Dark/Medium SlateBlue-ish
        ["#2F4F4F", "#008080", "#00CED1", "#40E0D0"],  # 16. DarkSlateGray/Teal/Turquoise-ish
        ["#D2691E", "#CD853F", "#F4A460", "#FFDEAD"],  # 17. Chocolate/Peru/SandyBrown-ish
        ["#C71585", "#DB7093", "#D8BFD8", "#E6E6FA"],  # 18. MediumVioletRed/PaleVioletRed-ish
        ["#A52A2A", "#F08080", "#FFA07A", "#FFE4E1"],  # 19. Brown/LightCoral-ish
        ["#000000", "#2F4F4F", "#708090", "#778899"],  # 20. Black/SlateGray-ish
        ["#7FFF00", "#7CFC00", "#98FB98", "#90EE90"],  # 21. Chartreuse/LawnGreen-ish
        ["#DC143C", "#FF0000", "#FF6347", "#FF7F50"],  # 22. Crimson/Red-ish
        ["#00BFFF", "#1E90FF", "#87CEFA", "#ADD8E6"],  # 23. DeepSkyBlue/DodgerBlue-ish
        ["#BDB76B", "#EEE8AA", "#F0E68C", "#FAFAD2"],  # 24. Khaki-ish
        ["#FFFAF0", "#FFF8DC", "#FFFACD", "#FFFFE0"],  # 25. Floral/Lemon-ish
        ["#DCDCDC", "#D3D3D3", "#C0C0C0", "#B0C4DE"],  # 26. Light Grays
        ["#F5F5DC", "#F5DEB3", "#FFE4B5", "#FFDAB9"],  # 27. Beige/Wheat-ish
        ["#FFE4C4", "#FFDEAD", "#F5DEB3", "#DEB887"],  # 28. Bisque/Navajo-ish
        ["#F0FFF0", "#F5FFFA", "#F0FFFF", "#E0FFFF"],  # 29. Mint/Azure-ish
        ["#E6E6FA", "#D8BFD8", "#DDA0DD", "#DA70D6"],  # 30. Lavender/Plum-ish
        ["#FDF5E6", "#FAF0E6", "#FAEBD7", "#FFEFD5"],  # 31. OldLace/Linen-ish
        ["#8A2BE2", "#9370DB", "#9966CC", "#A020F0"],  # 32. BlueViolet-ish
        ["#CD5C5C", "#BC8F8F", "#E9967A", "#F08080"],  # 33. IndianRed-ish
        ["#4682B4", "#5F9EA0", "#6495ED", "#708090"],  # 34. SteelBlue/CadetBlue-ish
        ["#3CB371", "#2E8B57", "#66CDAA", "#8FBC8F"],  # 35. MediumSeaGreen-ish
        ["#BA55D3", "#C71585", "#DB7093", "#CC3399"],  # 36. MediumOrchid/VioletRed-ish
        ["#F0E68C", "#FFD700", "#FFEC8B", "#EEE8AA"],  # 37. Khaki/Gold-ish
        ["#C0C0C0", "#A9A9A9", "#808080", "#696969"],  # 38. Silver/Gray-ish
        ["#ADFF2F", "#9ACD32", "#6B8E23", "#556B2F"],  # 39. GreenYellow/OliveDrab-ish
        ["#40E0D0", "#48D1CC", "#00CED1", "#20B2AA"],  # 40. Turquoise-ish
        ["#FA8072", "#E9967A", "#F08080", "#CD5C5C"],  # 41. Salmon-ish
        ["#DAA520", "#B8860B", "#CD853F", "#D2691E"],  # 42. Goldenrod/Peru-ish
        ["#B0E0E6", "#ADD8E6", "#87CEEB", "#87CEFA"],  # 43. PowderBlue/SkyBlue-ish
        ["#FF69B4", "#FF1493", "#C71585", "#DB7093"],  # 44. HotPink/DeepPink-ish
        ["#7B68EE", "#6A5ACD", "#483D8B", "#191970"],  # 45. MediumSlateBlue-ish
        ["#F5DEB3", "#FFE4B5", "#FFDAB9", "#FFEBCD"],  # 46. Wheat/Moccasin-ish
        ["#AFEEEE", "#E0FFFF", "#F0FFFF", "#F5FFFA"],  # 47. PaleTurquoise/Azure-ish
        ["#DB7093", "#C71585", "#FF1493", "#FF00FF"],  # 48. PaleVioletRed/Magenta-ish
        ["#6B8E23", "#808000", "#556B2F", "#808069"],  # 49. OliveDrab-ish
        ["#2E8B57", "#3CB371", "#20B2AA", "#008B8B"],  # 50. SeaGreen-ish
        ["#D2B48C", "#BC8F8F", "#CD853F", "#A0522D"],  # 51. Tan/RosyBrown-ish
        ["#9370DB", "#8A2BE2", "#9400D3", "#8B008B"],  # 52. MediumPurple/DarkViolet-ish
        ["#FF7F50", "#FF6347", "#FF4500", "#FF8C00"],  # 53. Coral/Tomato-ish
        ["#32CD32", "#228B22", "#008000", "#006400"],  # 54. LimeGreen/ForestGreen-ish
        ["#4169E1", "#0000CD", "#00008B", "#191970"],  # 55. RoyalBlue/Navy-ish
        ["#F4A460", "#D2691E", "#A0522D", "#8B4513"],  # 56. SandyBrown/Sienna-ish
        ["#DA70D6", "#EE82EE", "#DDA0DD", "#BA55D3"],  # 57. Orchid/Violet-ish
        ["#BDB76B", "#F0E68C", "#EEE8AA", "#FFFFE0"],  # 58. DarkKhaki/LightYellow-ish
        ["#778899", "#708090", "#696969", "#2F4F4F"],  # 59. Light/Dark SlateGray-ish
        ["#98FB98", "#90EE90", "#32CD32", "#2E8B57"],  # 60. PaleGreen/LimeGreen-ish
        ["#FFC0CB", "#FFB6C1", "#FF69B4", "#FF1493"],  # 61. Pink/HotPink-ish
        ["#B0C4DE", "#6495ED", "#4682B4", "#4169E1"],  # 62. LightSteelBlue/Cornflower-ish
        ["#CD853F", "#D2691E", "#A0522D", "#800000"],  # 63. Peru/SaddleBrown-ish
        ["#9932CC", "#9400D3", "#8A2BE2", "#4B0082"],  # 64. DarkOrchid/Indigo-ish
        ["#F08080", "#CD5C5C", "#B22222", "#8B0000"],  # 65. LightCoral/Firebrick-ish
        ["#66CDAA", "#3CB371", "#2E8B57", "#006400"],  # 66. MediumAquaMarine/SeaGreen-ish
        ["#87CEFA", "#87CEEB", "#00BFFF", "#1E90FF"],  # 67. LightSkyBlue/DeepSkyBlue-ish
        ["#FFDAB9", "#FFE4B5", "#FFDEAD", "#F5DEB3"],  # 68. PeachPuff/Moccasin-ish
        ["#D8BFD8", "#DDA0DD", "#DA70D6", "#EE82EE"],  # 69. Thistle/Plum-ish
        ["#F5F5F5", "#DCDCDC", "#D3D3D3", "#A9A9A9"],  # 70. WhiteSmoke/Gainsboro-ish
    ]
    
    # 共享的调色板映射和索引
    palette_map = {}
    palette_index_ref = [0]  # 使用列表作为可变引用

    # 依次处理 validation 和 train 文件夹
    validation_path = os.path.join(base_path, "validation")
    _process_directory(validation_path, palette_map, predefined_palettes, palette_index_ref)
    
    train_path = os.path.join(base_path, "train")
    _process_directory(train_path, palette_map, predefined_palettes, palette_index_ref)

    print("\n所有文件夹处理完成！")
    print("注意: train和validation文件夹中的c1和c2视图已根据新的颜色方案进行着色。")


# 当文件存在时，可以调用此函数来执行操作
if __name__ == "__main__":
    # 您可以选择执行原始的 V 文件夹处理函数，或新的颜色处理函数
    # keep_first_view_for_each_model_in_V_folder() # 如果需要执行原始任务，请取消注释
    run_color_processing()
