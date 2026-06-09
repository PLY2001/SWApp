import matplotlib.pyplot as plt

# 节点1的坐标
center1 = (-1459.74, 1010)
min1 = (-1482.19, 987.55)
max1 = (-1437.29, 1032.45)

# 节点2的坐标
center2 = (-1467.98, 1001.34)
min2 = (-1482.38, 986.94)
max2 = (-1453.58, 1015.74)

# 节点3的坐标
center3 = (-1459.47, 1011.09)
min3 = (-1485.41, 985.15)
max3 = (-1433.53, 1037.03)

# 创建一个图形和一个子图
fig, ax = plt.subplots()

# 绘制节点1的矩形
rect1 = plt.Rectangle(min1, max1[0] - min1[0], max1[1] - min1[1], edgecolor='r', facecolor='none')
ax.add_patch(rect1)

# 绘制节点2的矩形
rect2 = plt.Rectangle(min2, max2[0] - min2[0], max2[1] - min2[1], edgecolor='g', facecolor='none')
ax.add_patch(rect2)

# 绘制节点3的矩形
rect3 = plt.Rectangle(min3, max3[0] - min3[0], max3[1] - min3[1], edgecolor='b', facecolor='none')
ax.add_patch(rect3)

# 设置坐标轴的范围
ax.set_xlim(min(min1[0], min2[0], min3[0]) - 10, max(max1[0], max2[0], max3[0]) + 10)
ax.set_ylim(min(min1[1], min2[1], min3[1]) - 10, max(max1[1], max2[1], max3[1]) + 10)

# 显示图形
plt.show()
