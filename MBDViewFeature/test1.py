import os
import cv2


def corp_margin(img):
    img2 = img.sum(axis=2)
    (row, col) = img2.shape
    row_top = 0
    row_down = 0
    col_top = 0
    col_down = 0
    for r in range(1, row, 10):
        print(img2.sum(axis=1)[r], 765 * col, col,
              file=open('cut.txt', 'a'))  # 图片也就是个三维数组，如果空白是白色的，也就是（255，255，255）255*3=765
    for r in range(1, row, 10):
        if img2.sum(axis=1)[r] < 765 * col:
            row_top = r
            break
    for r in range(row - 1, 0, -10):
        if img2.sum(axis=1)[r] < 765 * col:
            row_down = r
            break
    for c in range(0, col, 10):
        if img2.sum(axis=0)[c] < 765 * row:
            col_top = c
            break
    for c in range(col - 1, 0, -10):
        if img2.sum(axis=0)[c] < 765 * row:
            col_down = c
            break
    new_img = img[row_top-5:row_down + 11, col_top-5:col_down + 5, 0:3] #
    return new_img


# 遍历指定目录，显示目录下的所有文件名
def CropImage4File(filepath, destpath):
    pathDir = os.listdir(filepath)  # 列出文件路径中的所有路径或文件
    for allDir in pathDir:
        child = os.path.join(filepath, allDir)
        dest = os.path.join(destpath, allDir)
        if os.path.isfile(child):
            image = cv2.imread(child)
            img_re = corp_margin(image)
            cv2.imwrite(dest, img_re)  # 写入图像路径


if __name__ == '__main__':
    filepath = 'C:\\Users\\PLY\\Desktop\\Files\\gg'  # 源图像
    destpath = 'C:\\Users\\PLY\\Desktop\\Files\\gg_resize'  # resized images saved here
    CropImage4File(filepath, destpath)
