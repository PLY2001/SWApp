import os
from PIL import Image

json_dir = r"C:\\Users\\PLY\\Desktop\\Files\\bmp"
label_names = os.listdir(json_dir)
label_dir = []
for filename in label_names:
    label_dir.append(os.path.join(json_dir, filename))

for i, filename in enumerate(label_dir):
    im = Image.open(filename)  # open ppm file

    newname = label_names[i].split('.')[0] + '.png'  # new name for png file
    im.save(os.path.join(json_dir, newname))