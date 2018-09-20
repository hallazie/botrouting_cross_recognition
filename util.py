#coding:utf-8

from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageEnhance
from matplotlib import pyplot as plt

import numpy as np
import os
import cv2
import math
import random

batch_size = 32
size_1 = (256, 256)
size_2 = (32, 32)


def init_data():
	for _,_,fs in os.walk('crop/data'):
		random.shuffle(fs)
		data, label = np.zeros((len(fs),1,size_1[1],size_1[0]), dtype='float32'), np.zeros((len(fs),1,size_2[1],size_2[0]), dtype='float32')
		for i, f in enumerate(fs):
			img = Image.open('crop/data/'+f)
			if random.randint(0,10)>3:
				angle = random.randint(-45,45)
				img = np.array(img.rotate(angle, resample=Image.BICUBIC))
				data[i] = img
				lbl = np.array(Image.open('crop/label_dot/'+f).resize((size_2[0],size_2[1]), resample=Image.BICUBIC).rotate(angle, resample=Image.BICUBIC))
				lbl[lbl>0] = 255
				label[i] = lbl
			else:
				img = np.array(img)
				data[i] = img
				lbl = np.array(Image.open('crop/label_dot/'+f).resize((size_2[0],size_2[1]), resample=Image.BICUBIC))
				lbl[lbl>0] = 255
				label[i] = lbl		
	data = (data-data.mean())/data.std()
	from matplotlib import pyplot as plt
	plt.subplot(221)
	plt.imshow(data[0][0])
	plt.subplot(222)
	plt.imshow(label[0][0])
	plt.subplot(223)
	plt.imshow(data[1][0])
	plt.subplot(224)
	plt.imshow(label[1][0])
	plt.show()

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

def binarize(arr):
	return (arr>max(arr.mean(),64))*255

def enhance(arr):
	arr = np.ma.clip(arr * (255 / (np.amax(arr) - np.amin(arr))),0,255)
	arr = np.ma.clip(1 / (np.ones(arr.shape) * (1 / 485.0) + np.exp( - 0.045 * arr)),0,255)
	arr = np.ma.clip(arr * (255 / (np.amax(arr) - np.amin(arr))),0,255)
	return arr.astype('uint8')

def fitline(arr):
	ret, thresh = cv2.threshold(arr, 127, 255, cv2.THRESH_BINARY)
	_, contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
	cnt = contours[0]
	[vx,vy,x,y] = cv2.fitLine(cnt, cv2.DIST_L2,0,0.01,0.01)
	lefty = int((-x*vy/vx) + y)
	righty = int(((arr.shape[1]-x)*vy/vx)+y)
	cv2.line(arr,(arr.shape[1]-1,righty),(0,lefty),255,2)
	return arr

def angle(line):
	x1,y1,x2,y2 = line
	sin = float(abs(y1-y2))/math.sqrt((x1-x2)**2+(y1-y2)**2)
	arc = math.asin(sin)*(180/math.pi)
	# return arc if arc<90 else arc-90
	return arc

def find_cross():
	for _,_,fs in os.walk('val/mask/'):
		for f in fs:
			if 'ret' in f:
				continue
			img = Image.open('val/mask/'+f)
			img = img.filter(ImageFilter.SMOOTH_MORE)
			# img = img.filter(ImageFilter.GaussianBlur(2))

			enh_con = ImageEnhance.Contrast(img)
			contrast = 2
			img = enh_con.enhance(contrast)

			# img = img.filter(ImageFilter.EDGE_ENHANCE)
			# img = img.filter(ImageFilter.GaussianBlur(1))
			img = img.filter(ImageFilter.SMOOTH_MORE)

			arr = np.array(img, dtype='float32')
			arr = enhance(arr)
			arr = binarize(arr.astype('float32'))

			img = np.array(img.convert('RGB'))

			# lines = cv2.HoughLines(arr.astype('uint8'),1,np.pi/180,200)
			# for line in lines:
			# 	for rho,theta in line:
			# 	    a = np.cos(theta)
			# 	    b = np.sin(theta)
			# 	    x0 = a*rho
			# 	    y0 = b*rho
			# 	    x1 = int(x0 + 1000*(-b))
			# 	    y1 = int(y0 + 1000*(a))
			# 	    x2 = int(x0 - 1000*(-b))
			# 	    y2 = int(y0 - 1000*(a))
			# 	    cv2.line(img,(x1,y1),(x2,y2),(0,0,255),2)

			minLineLength = 1000
			maxLineGap = 10
			lines = cv2.HoughLinesP(arr.astype('uint8'),1,np.pi/180,100,minLineLength,maxLineGap)
			lines = sorted(lines, key=lambda x:(x[0][0]-x[0][2])**2+(x[0][1]-x[0][3])**2, reverse=True)
			prev_a = angle(lines[0][0])
			cv2.line(img,(lines[0][0][0],lines[0][0][1]),(lines[0][0][2],lines[0][0][3]),(0,0,255),2)
			for line in lines:
				x1,y1,x2,y2 = line[0]
				if math.sqrt((x1-x2)**2+(y1-y2)**2) < 20:
					continue
				curr_a = angle(line[0])
				if abs(prev_a-curr_a)>80:
					cv2.line(img,(x1,y1),(x2,y2),(255,0,0),2)
					print abs(prev_a-curr_a)
					break
				else:
					continue

			Image.fromarray(img.astype('uint8')).save('val/mask/'+f.split('.')[0]+'_ret.png')
			print '%s finished'%f

def contrast(img):
	enh_con = ImageEnhance.Contrast(img)
	contrast = 1.5
	return enh_con.enhance(contrast)

def vis():
	img = Image.open('0.bmp').resize((80,60), resample=Image.LANCZOS).rotate(40, resample=Image.BICUBIC)
	arr = np.array(img)

	img = Image.fromarray(arr.astype('uint8'))

	kernel = np.ones((5,5))*-1
	kernel[2,:] = 1
	kernel[:,2] = 1
	kernel = kernel.reshape(5*5)

	img = img.filter(ImageFilter.SMOOTH_MORE)
	img = img.filter(ImageFilter.DETAIL)
	img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
	img = img.filter(ImageFilter.SMOOTH_MORE)
	img = img.filter(ImageFilter.ModeFilter(3))
	# img = img.filter(ImageFilter.Kernel((5,5), tuple(kernel)))

	arr = np.array(img)
	hist1 = list(arr.sum(axis=0))
	hist2 = list(arr.sum(axis=1))

	plt.plot(hist1)
	plt.plot(hist2)

	# plt.imshow(img)
	plt.show()
	img.save('res.png')

if __name__ == '__main__':
	init_data()