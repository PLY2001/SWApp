import os
import time  # 新增：导入时间模块
import trimesh
import numpy as np
from PIL import Image


def render_thickness_from_stls(folder_path, voxel_size, output_image_path):
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

    # 3. 体素化与实体识别
    print(f"正在按体素大小 {voxel_size} 进行体素化处理 (这可能需要一些时间)...")
    # pitch 定义了体素的边长，voxelized() 首先生成表面体素
    surface_voxels = combined_mesh.voxelized(pitch=voxel_size)

    # fill() 方法通过形态学/射线检测填充内部空间，从而识别出"实体部分"
    solid_voxels = surface_voxels.fill()

    # 获取 3D 布尔矩阵 (形状为: [Nx, Ny, Nz])
    # 矩阵中的 True 代表该位置存在实体体素，False 代表为空白
    matrix = solid_voxels.matrix

    # 4. 从 X 轴正方向正交投影
    print("正在进行X轴正交投影与厚度计算...")
    # 从 +x 看向原点，视线平行于 x 轴。
    # 我们沿着 X 轴 (axis=0) 对布尔矩阵进行累加，得到每个 (y, z) 坐标上的体素数量
    voxel_count_yz = np.sum(matrix, axis=0)  # 形状变为 (Ny, Nz)

    # 累计厚度 = 体素数量 * 体素大小
    thickness_yz = voxel_count_yz * float(voxel_size)

    # 5. 转换为灰度图
    print("正在生成渲染图像...")
    max_thickness = np.max(thickness_yz)

    if max_thickness > 0:
        # 修改点1：取消了 255- 的反相操作，使厚度越大值越接近255（越白）
        intensity = (thickness_yz / max_thickness * 255).astype(np.uint8)
    else:
        intensity = np.zeros_like(thickness_yz, dtype=np.uint8)

        # 修改点2：生成 Alpha (透明度) 通道。厚度为0的地方透明(0)，大于0的地方不透明(255)
    alpha = np.where(thickness_yz > 0, 255, 0).astype(np.uint8)

    # 修改点3：将 R, G, B, A 四个通道组合在一起 (对于灰度效果，RGB三个通道的值是一样的)
    rgba_matrix = np.stack((intensity, intensity, intensity, alpha), axis=-1)

    # 修改点4：针对三维数组 (Ny, Nz, 4) 的转置和翻转处理
    # 交换前两个维度，对应原来的 .T 操作
    image_data = np.transpose(rgba_matrix, (1, 0, 2))
    # 上下翻转
    image_data = np.flipud(image_data)

    # 修改点5：模式改为 RGBA
    img = Image.fromarray(image_data, mode='RGBA')

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

    # 6. 保存带有 300 DPI 信息的图像 (PNG 格式原生支持透明通道)
    img.save(output_image_path, dpi=(300, 300))
    print(f"渲染完成！最大厚度为: {max_thickness:.2f} (单位: 与STL一致)")
    print(f"高分辨率图像(300 DPI)已保存至: {output_image_path}")


if __name__ == "__main__":
    # ================= 参数配置区 =================

    # 1. 你的STL文件夹路径 (请修改为实际路径，可使用绝对路径或相对路径)
    TARGET_FOLDER = r"C:\Users\PLY\Desktop\Files\Projects\SWApp\SolidWorks Temp\CMB carter"

    # 2. 体素大小 (单位与你的STL模型单位一致。值越小精度越高，但内存和计算时间消耗越大)
    VOXEL_SIZE = 0.5

    # 3. 输出图像的文件名
    OUTPUT_IMAGE = "x_axis_thickness_projection.png"

    # ==============================================

    if not os.path.exists(TARGET_FOLDER):
        print(f"提示：未找到文件夹 '{TARGET_FOLDER}'，请确保路径正确。")
    else:
        # 新增：记录开始时间
        start_time = time.perf_counter()

        render_thickness_from_stls(TARGET_FOLDER, VOXEL_SIZE, OUTPUT_IMAGE)

        # 新增：记录结束时间并计算差值
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time

        print("-" * 40)
        # 如果耗时超过60秒，同时换算成分钟显示以便于阅读
        if elapsed_time > 60:
            minutes = int(elapsed_time // 60)
            seconds = elapsed_time % 60
            print(f"⏱️ 总流程耗时: {minutes} 分 {seconds:.2f} 秒")
        else:
            print(f"⏱️ 总流程耗时: {elapsed_time:.2f} 秒")
        print("-" * 40)