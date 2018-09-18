#coding:utf-8

from PIL import Image, ImageDraw, ImageFilter

import matplotlib.pyplot as plt
import numpy as np
import os
import cv2

def conv(vec1, vec2):
	return reduce(lambda x,y:x+y,[e[0]*e[1] for e in zip(vec1,vec2)]) 

def find_min(lst):
	cur_idx, cur_min, cur_gap, max_gap = 0, 1e7, 0, 0
	for i in range(20,len(lst)-20):
		e = lst[i]
		try:
			if e<lst[i-1] and e<lst[i-2] and e<lst[i+1] and lst[i+2] and abs(e-lst[i-2])>2500 and abs(e-lst[i+2])>2500:
				cur_gap = (abs(e-lst[i-2])+abs(e-lst[i+2]))/2
				if cur_gap > max_gap:
					cur_min = e
					cur_idx = i
					max_gap = cur_gap
		except Exception as err:
			print err
	return cur_idx, cur_min

'''def percep(img, fname):
	w, h = img.transpose().shape
	# arr = np.array(img)
	kernel_w = [255 for e in range(w)]
	kernel_h = [255 for e in range(h)]
	max_x, max_y = 0, 0

	loss_1, loss_2 = [], []

	min_conv = 1e7
	for i in range(h):
		cur_vec =[abs(e-255) for e in list(img[i,:])]
		cur_cov = conv(cur_vec, kernel_h)
		loss_1.append(abs(cur_cov-min_conv))
		if cur_cov < min_conv:
			min_conv = cur_cov
			max_x = i
	x, e_x = find_min(loss_1)
	if x == 0:
		x = max_x

	min_conv = 1e7
	for j in range(w):
		cur_vec = [abs(e-255) for e in list(img[:,j])]
		cur_cov = conv(cur_vec, kernel_w)
		loss_2.append(abs(cur_cov-min_conv))
		if cur_cov < min_conv:
			min_conv = cur_cov
			max_y = j
	y, e_y = find_min(loss_2)
	if y == 0:
		y = max_y

	idx_1 = [0 for e in range(len(loss_1))]
	idx_1[x] = e_x
	idx_2 = [0 for e in range(len(loss_2))]
	idx_2[y] = e_y'''

def percep(img, fname):
	w, h = img.transpose().shape
	kernel_w = [255 for e in range(w)]
	kernel_h = [255 for e in range(h)]
	max_x, max_y = 0, 0

	max_conv = 0
	for i in range(20,h-20):
		cur_vec =[e for e in list(img[i,:])]
		cur_cov = conv(cur_vec, kernel_h)
		if cur_cov > max_conv:
			max_conv = cur_cov
			max_x = i

	max_conv = 0
	for j in range(20,w-20):
		cur_vec = [e for e in list(img[:,j])]
		cur_cov = conv(cur_vec, kernel_w)
		if cur_cov > max_conv:
			max_conv = cur_cov
			max_y = j

	return (max_y, max_x)

def foo():
	folder = 'val/data/'
	# folder = 'test/data/'
	for _,_, fs in os.walk(folder):
		fs = fs[:]
		for f in fs:
			img = Image.open(folder+f)
			img = img.filter(ImageFilter.EDGE_ENHANCE)

			canny = np.array(img)
			canny[canny>230] = 190
			canny = cv2.GaussianBlur(canny,(3,3),0)
			factor = 20
			canny = cv2.Canny(canny, factor, factor*2.5)
			Image.fromarray(canny.astype('uint8')).save('val/pred/'+f+'.png')

			coord = percep(canny, 'val/pred/'+f.split('.')[0]+'_plt.png')
			img = img.convert('RGB')
			w, h = img.size
			draw = ImageDraw.Draw(img)
			draw.arc([coord[0]-5,coord[1]-5,coord[0]+5,coord[1]+5], 0, 360, 'red')
			draw.line([coord[0],0,coord[0],h], 'red')
			draw.line([0,coord[1],w,coord[1]], 'red')
			img.save('val/pred/'+f)	
			print '%s finished'%f	

if __name__ == '__main__':
	foo()