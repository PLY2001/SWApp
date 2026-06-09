import numpy as np

try:
    # 加载.npy文件，allow_pickle=True是必需的，因为里面存的是一个字典
    data = np.load('features_hierarchical_sampling.npy', allow_pickle=True)

    # 检查数据类型
    print(f"Data type: {type(data)}")

    # 如果数据是一个0维数组，其中包含一个字典，我们需要用.item()来提取它
    if data.shape == ():
        file_data = data.item()
        print(f"Data is a 0-d array containing a dict. Extracting item...")
    else:
        file_data = data
    
    print(f"Extracted data type: {type(file_data)}")

    # 打印字典的键
    if isinstance(file_data, dict):
        print(f"Keys: {list(file_data.keys())}")
        
        # 打印每个特征数组的形状
        print("\n--- Features Shape ---")
        if 'geometric' in file_data:
            print(f"Geometric: {file_data['geometric'].shape}")
        if 'semantic' in file_data:
            print(f"Semantic: {file_data['semantic'].shape}")
        if 'fused' in file_data:
            print(f"Fused: {file_data['fused'].shape}")
            
        # 打印标签列表的长度
        print("\n--- Labels and Metadata Length ---")
        if 'fine_grained_labels' in file_data:
            print(f"Fine Grained Labels: {len(file_data['fine_grained_labels'])}")
        if 'coarse_grained_labels' in file_data:
            print(f"Coarse Grained Labels: {len(file_data['coarse_grained_labels'])}")
        if 'model_names' in file_data:
            print(f"Model Names: {len(file_data['model_names'])}")

except Exception as e:
    print(f"An error occurred: {e}")
