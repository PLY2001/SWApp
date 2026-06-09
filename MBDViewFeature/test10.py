import os
import numpy as np
import trimesh
from scipy.spatial.transform import Rotation as R


def get_rotation_matrix_to_y_axis(vector):
    """
    计算将 vector 旋转到对齐 y轴正方向 [0, 1, 0] 的旋转矩阵
    """
    vector = vector / np.linalg.norm(vector)
    target = np.array([0.0, 1.0, 0.0])

    # 如果已经平行于 y 轴
    if np.allclose(vector, target):
        return np.eye(3)
    if np.allclose(vector, -target):
        # 旋转 180 度，绕 x 轴
        return R.from_euler('x', 180, degrees=True).as_matrix()

    # 计算旋转轴和角度
    axis = np.cross(vector, target)
    axis_norm = np.linalg.norm(axis)
    axis = axis / axis_norm
    angle = np.arccos(np.clip(np.dot(vector, target), -1.0, 1.0))

    return R.from_rotvec(axis * angle).as_matrix()


def matrix_to_euler(matrix):
    """
    将旋转矩阵转换为欧拉角 (内旋 xyz，即先绕X，再绕Y，最后绕Z)
    """
    rot = R.from_matrix(matrix)
    # 'xyz' 代表内旋，对应的顺序也是通常理解的依次绕局部坐标系X, Y, Z旋转
    euler_angles = rot.as_euler('xyz', degrees=True)
    return euler_angles


def load_and_merge_stls(folder_path):
    """
    读取文件夹内的所有STL并合并为一个完整的Mesh
    """
    meshes = []
    for filename in os.listdir(folder_path):
        if filename.lower().endswith('.stl'):
            filepath = os.path.join(folder_path, filename)
            mesh = trimesh.load_mesh(filepath)
            meshes.append(mesh)

    if not meshes:
        raise ValueError("文件夹中没有找到STL文件！")

    # 合并所有网格
    merged_mesh = trimesh.util.concatenate(meshes)
    return merged_mesh


def align_by_vertex_pca(mesh):
    """
    方法1：顶点主成分分析
    """
    vertices = mesh.vertices
    # 计算协方差矩阵
    cov_matrix = np.cov(vertices.T)
    # 计算特征值和特征向量
    eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)

    # 获取最大特征值对应的特征向量作为主轴
    # np.linalg.eigh 返回的特征值是按从小到大排序的
    principal_axis = eigenvectors[:, np.argmax(eigenvalues)]

    # 统一主轴方向，使其指向较多顶点的一侧，保证唯一性（可选）

    rot_matrix = get_rotation_matrix_to_y_axis(principal_axis)
    return matrix_to_euler(rot_matrix)


def align_by_normal_pca(mesh):
    """
    方法2：法向量主成分分析
    """
    normals = mesh.face_normals
    areas = mesh.area_faces

    # 基于面积加权的法线散布矩阵
    # M = sum( Area * (n * n^T) )
    weighted_normals = normals * np.sqrt(areas[:, np.newaxis])
    scatter_matrix = np.dot(weighted_normals.T, weighted_normals)

    eigenvalues, eigenvectors = np.linalg.eigh(scatter_matrix)

    # 法线分布最少的方向通常就是柱状/条状物体的延伸方向（主轴）
    # 因此取最小特征值对应的特征向量
    principal_axis = eigenvectors[:, np.argmin(eigenvalues)]

    rot_matrix = get_rotation_matrix_to_y_axis(principal_axis)
    return matrix_to_euler(rot_matrix)


def align_by_max_normal_distribution(mesh):
    """
    方法3：最大法线分布
    """
    # Trimesh 的 facets 属性会自动将共面的面片组合起来
    # 我们找到总面积最大的共面组，它的法向量即为最大分布法向量
    if len(mesh.facets) > 0:
        largest_facet_idx = np.argmax(mesh.facets_area)
        dominant_normal = mesh.facets_normal[largest_facet_idx]
    else:
        # Fallback: 如果没有明显的共面(例如全是极小曲面)，则对法向量进行近似统计
        # 将法向量四舍五入到 1 位小数作为 Hash Key，统计面积极值
        normal_areas = {}
        for normal, area in zip(mesh.face_normals, mesh.area_faces):
            key = tuple(np.round(normal, 1))
            normal_areas[key] = normal_areas.get(key, 0) + area

        best_key = max(normal_areas, key=normal_areas.get)
        # 寻找最近似的原始法线
        best_normal = np.array(best_key)
        dominant_normal = best_normal / np.linalg.norm(best_normal)

    # 对于最大分布平面通常是"底面"或"顶面"
    # 我们将其法线对齐到 y 轴
    rot_matrix = get_rotation_matrix_to_y_axis(dominant_normal)
    return matrix_to_euler(rot_matrix)


def main():
    # =============== 配置区域 ===============
    # 在这里指定你的文件夹路径
    folder_path = r"C:\Users\PLY\Desktop\Files\Projects\SWApp\SolidWorks Temp\CMB carter"
    # ========================================

    print(f"正在读取文件夹: {folder_path}...")
    try:
        mesh = load_and_merge_stls(folder_path)
        print(f"成功合并模型，总顶点数: {len(mesh.vertices)}, 总面数: {len(mesh.faces)}\n")
    except Exception as e:
        print(f"读取模型失败: {e}")
        return

    # 1. 顶点主成分分析
    euler_1 = align_by_vertex_pca(mesh)
    print("【方法1：顶点主成分分析】")
    print(f"修正变换欧拉角 (内旋 XYZ, 顺序: 先绕X, 再绕Y, 最后绕Z):")
    print(f"绕 X 轴旋转: {euler_1[0]:.2f} 度")
    print(f"绕 Y 轴旋转: {euler_1[1]:.2f} 度")
    print(f"绕 Z 轴旋转: {euler_1[2]:.2f} 度\n")

    # 2. 法向量主成分分析
    euler_2 = align_by_normal_pca(mesh)
    print("【方法2：法向量主成分分析】")
    print(f"修正变换欧拉角 (内旋 XYZ, 顺序: 先绕X, 再绕Y, 最后绕Z):")
    print(f"绕 X 轴旋转: {euler_2[0]:.2f} 度")
    print(f"绕 Y 轴旋转: {euler_2[1]:.2f} 度")
    print(f"绕 Z 轴旋转: {euler_2[2]:.2f} 度\n")

    # 3. 最大法线分布
    euler_3 = align_by_max_normal_distribution(mesh)
    print("【方法3：最大法线分布】")
    print(f"修正变换欧拉角 (内旋 XYZ, 顺序: 先绕X, 再绕Y, 最后绕Z):")
    print(f"绕 X 轴旋转: {euler_3[0]:.2f} 度")
    print(f"绕 Y 轴旋转: {euler_3[1]:.2f} 度")
    print(f"绕 Z 轴旋转: {euler_3[2]:.2f} 度\n")


if __name__ == "__main__":
    main()