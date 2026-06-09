import os
import time
import trimesh
import numpy as np
from PIL import Image


def render_thickness_ray_tracing(folder_path, ray_spacing, output_image_path):
    print(f"正在读取 {folder_path} 中的STL文件...")
    meshes = []

    # 1. 遍历文件夹并加载所有 STL 子模型
    for file_name in os.listdir(folder_path):
        if file_name.lower().endswith('.stl'):
            file_path = os.path.join(folder_path, file_name)
            try:
                mesh = trimesh.load_mesh(file_path)
                meshes.append(mesh)
                print(f" - 成功加载: {file_name}")
            except Exception as e:
                print(f" - 加载失败 {file_name}: {e}")

    if not meshes:
        print("错误：未能在指定文件夹中找到任何有效的STL文件。")
        return

    # 2. 合并为一个完整的网格模型
    print("正在合并所有子网格...")
    combined_mesh = trimesh.util.concatenate(meshes)

    # 获取模型的包围盒边界
    bounds = combined_mesh.bounds
    min_x, min_y, min_z = bounds[0]
    max_x, max_y, max_z = bounds[1]

    print(
        f"模型边界范围:\n X: {min_x:.2f} to {max_x:.2f}\n Y: {min_y:.2f} to {max_y:.2f}\n Z: {min_z:.2f} to {max_z:.2f}")

    # 3. 提前构建 BVH 树加速结构
    print("\n正在构建BVH树 (空间索引加速结构)...")
    start_bvh = time.perf_counter()
    # Trimesh 会在第一次调用射线功能时惰性初始化树结构。
    # 这里我们发射一根假射线来强制提前构建 BVH 树，以便单独统计构建时间。
    _ = combined_mesh.ray.intersects_id(np.array([[0, 0, 0]]), np.array([[1, 0, 0]]))
    end_bvh = time.perf_counter()
    print(f"✅ BVH树构建完成，耗时: {end_bvh - start_bvh:.4f} 秒")

    # 4. 设置射线网格 (代替体素化)
    # 我们在 Y-Z 平面上建立像素网格，每隔 ray_spacing 发射一条射线
    y_vals = np.arange(min_y, max_y, ray_spacing)
    z_vals = np.arange(min_z, max_z, ray_spacing)
    Ny, Nz = len(y_vals), len(z_vals)

    # indexing='ij' 确保输出形状为 (Ny, Nz)，与原代码体素矩阵切片一致
    Y, Z = np.meshgrid(y_vals, z_vals, indexing='ij')
    num_rays = Y.size
    print(f"\n射线网格分辨率: {Ny} x {Nz}，共需发射 {num_rays} 条射线")

    # 构造所有射线的起点和方向
    # 射线从包围盒 -X 侧外部一点出发，方向为正 X 轴
    ray_origins = np.zeros((num_rays, 3))
    ray_origins[:, 0] = min_x - 1.0
    ray_origins[:, 1] = Y.flatten()
    ray_origins[:, 2] = Z.flatten()

    ray_directions = np.zeros((num_rays, 3))
    ray_directions[:, 0] = 1.0  # (1, 0, 0) 指向 +X 方向

    # 5. 执行批量射线求交计算
    print("正在进行批量光线投射与三角面求交计算...")
    start_ray = time.perf_counter()
    # intersects_location 返回有交点的射线索引、面片索引和交点三维坐标
    locations, index_ray, index_tri = combined_mesh.ray.intersects_location(
        ray_origins=ray_origins, ray_directions=ray_directions
    )
    end_ray = time.perf_counter()
    print(f"✅ 求交计算完成，耗时: {end_ray - start_ray:.4f} 秒")

    # 6. 计算实体厚度
    print("正在计算每条射线的穿透厚度...")
    start_calc = time.perf_counter()

    thickness_flat = np.zeros(num_rays)

    if len(index_ray) > 0:
        # 提取交点的 X 坐标
        x_hits = locations[:, 0]

        # 按照射线索引对交点进行排序，以便将同一条射线的交点归组
        sort_idx = np.argsort(index_ray)
        sorted_ray_idx = index_ray[sort_idx]
        sorted_x_hits = x_hits[sort_idx]

        # 找到每条射线交点列表的分割点
        unique_rays, split_indices = np.unique(sorted_ray_idx, return_index=True)
        hit_groups = np.split(sorted_x_hits, split_indices[1:])

        # 遍历每一条有交点的射线
        for ray_id, hits in zip(unique_rays, hit_groups):
            if len(hits) > 1:
                hits.sort()  # 按 X 坐标从小到大排序

                # --- 新增：容差去重逻辑 ---
                unique_hits = [hits[0]]
                # 设置一个极小的容差值，通常 1e-5 就足够应对浮点误差了
                tolerance = 1e-1

                for h in hits[1:]:
                    # 如果当前交点与上一个有效交点的距离大于容差，才认为是新交点
                    if (h - unique_hits[-1]) > tolerance:
                        unique_hits.append(h)

                unique_hits = np.array(unique_hits)
                # --------------------------

                # 使用过滤后的交点进行配对计算
                n_pairs = len(unique_hits) // 2
                if n_pairs > 0:
                    # 累计厚度 = Sum(出点x - 进点x)
                    thickness = np.sum(unique_hits[1:2 * n_pairs:2] - unique_hits[0:2 * n_pairs:2])
                    thickness_flat[ray_id] = thickness

    # 将一维厚度数组重塑回 2D 网格形状 (Ny, Nz)
    thickness_yz = thickness_flat.reshape((Ny, Nz))
    end_calc = time.perf_counter()
    print(f"✅ 厚度统计完成，耗时: {end_calc - start_calc:.4f} 秒")

    # 7. 转换为 RGBA 图像渲染 (支持透明度和正确的灰度映射)
    print("\n正在生成渲染图像...")
    max_thickness = np.max(thickness_yz)

    # 先对二维厚度矩阵进行方向翻转，保持与原有视角一致
    thickness_img_data = thickness_yz.T  # 转置
    thickness_img_data = np.flipud(thickness_img_data)  # 上下翻转

    # 获取翻转后矩阵的宽和高
    h, w = thickness_img_data.shape

    # 创建一个空的 RGBA 图像矩阵 (高, 宽, 4个通道)
    rgba_matrix = np.zeros((h, w, 4), dtype=np.uint8)

    if max_thickness > 0:
        # 计算灰度值：厚度越大越接近255(白)，越小越接近0(黑)
        # 注意：这里去掉了原代码中的 `255 - ...`
        intensity = (thickness_img_data / max_thickness * 255).astype(np.uint8)
    else:
        intensity = np.zeros_like(thickness_img_data, dtype=np.uint8)

    # 填充 R, G, B 通道（RGB相同即为灰度）
    rgba_matrix[..., 0] = intensity  # Red
    rgba_matrix[..., 1] = intensity  # Green
    rgba_matrix[..., 2] = intensity  # Blue

    # 填充 Alpha (透明度) 通道：有厚度的地方不透明(255)，厚度为0的地方完全透明(0)
    rgba_matrix[..., 3] = np.where(thickness_img_data > 0, 255, 0).astype(np.uint8)

    # 从 RGBA 矩阵创建图像
    img = Image.fromarray(rgba_matrix, mode='RGBA')

    # ================= 高分辨率处理模块 =================
    TARGET_LONG_EDGE = 2500
    original_width, original_height = img.size
    max_edge = max(original_width, original_height)

    if max_edge < TARGET_LONG_EDGE:
        scale_factor = TARGET_LONG_EDGE / max_edge
        new_width = int(original_width * scale_factor)
        new_height = int(original_height * scale_factor)

        print(f"正在将图像分辨率从 {original_width}x{original_height} 放大至 {new_width}x{new_height}...")
        img = img.resize((new_width, new_height), resample=Image.Resampling.NEAREST)

    # 8. 保存带有 300 DPI 信息的图像
    img.save(output_image_path, dpi=(300, 300))
    print(f"渲染完成！最大厚度为: {max_thickness:.2f} (单位: 与STL一致)")
    print(f"高分辨率图像(300 DPI)已保存至: {output_image_path}")


if __name__ == "__main__":
    # ================= 参数配置区 =================

    # 1. 你的STL文件夹路径 (请修改为实际路径)
    TARGET_FOLDER = r"C:\Users\PLY\Desktop\Files\Projects\SWApp\SolidWorks Temp\CMB carter"

    # 2. 射线间距 (等同于原先的体素大小。值越小分辨率越高，计算耗时相对增加)
    RAY_SPACING = 0.15

    # 3. 输出图像的文件名
    OUTPUT_IMAGE = "x_axis_thickness_raytracing.png"

    # ==============================================

    if not os.path.exists(TARGET_FOLDER):
        print(f"提示：未找到文件夹 '{TARGET_FOLDER}'，请确保路径正确。")
    else:
        start_time = time.perf_counter()

        render_thickness_ray_tracing(TARGET_FOLDER, RAY_SPACING, OUTPUT_IMAGE)

        end_time = time.perf_counter()
        elapsed_time = end_time - start_time

        print("-" * 40)
        if elapsed_time > 60:
            minutes = int(elapsed_time // 60)
            seconds = elapsed_time % 60
            print(f"⏱️ 总流程耗时: {minutes} 分 {seconds:.2f} 秒")
        else:
            print(f"⏱️ 总流程耗时: {elapsed_time:.2f} 秒")
        print("-" * 40)