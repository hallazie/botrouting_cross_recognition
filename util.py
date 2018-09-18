#coding:utf-8

from PIL import Image, ImageDraw
from matplotlib import pyplot as plt

import numpy as np

def conv(vec1, vec2):
	return reduce(lambda x,y:x+y,[e[0]*e[1] for e in zip(vec1,vec2)]) 

def indicate_line(img, mask):
	mask = np.array(mask).transpose()
	h, w = mask.shape
	kernel_w = [255 for e in range(w)]
	kernel_h = [255 for e in range(h)]
	max_x, max_y = 0, 0
	max_conv = 0
	for i in range(20,h-20):
		cur_vec =[e for e in list(mask[i,:])]
		cur_cov = conv(cur_vec, kernel_h)
		if cur_cov > max_conv:
			max_conv = cur_cov
			max_x = i
	max_conv = 0
	for j in range(20,w-20):
		cur_vec = [e for e in list(mask[:,j])]
		cur_cov = conv(cur_vec, kernel_w)
		if cur_cov > max_conv:
			max_conv = cur_cov
			max_y = j
	coord = (max_x, max_y)
	mask = Image.fromarray(mask.astype('uint8').transpose())
	mask = mask.convert('RGB')
	draw = ImageDraw.Draw(mask)
	draw.arc([coord[0]-5,coord[1]-5,coord[0]+5,coord[1]+5], 0, 360, 'red')
	draw.line([coord[0],0,coord[0],h], 'red')
	draw.line([0,coord[1],w,coord[1]], 'red')
	return mask

def plot():
	with open('log2', 'r') as log_file:
		log = log_file.readlines()
		print log
		loss = []
		for line in log:
			if 'mse=' in line:
				loss.append(float(line.split('mse=')[-1]))
		plt.plot(loss)
		plt.show()

if __name__ == '__main__':
	plot()