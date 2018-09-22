#coding:utf-8

from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageEnhance
from matplotlib import pyplot as plt
from progressbar import *

import numpy as np
import os
import cv2
import math
import random

kernel_size = 75

def clip(arr):
	arr = 254*(arr-np.min(arr))/(np.max(arr)-np.min(arr))
	return arr

def gen_kernel(degree, case):
	val_1, val_2, val_3 = 128, 64, 0
	kernel = np.ones((kernel_size,kernel_size))*val_3

	if case == 0:
		kernel[kernel_size//2-2:kernel_size//2+3,:] = val_1
		kernel[:,kernel_size//2-2:kernel_size//2+3] = val_1
	elif case == 2:
		kernel[kernel_size//2-2:kernel_size//2+3,:] = val_1
	else:
		kernel[:,kernel_size//2-2:kernel_size//2+3] = val_1

	kerimg = Image.fromarray(kernel.astype('uint8'))
	kerimg = kerimg.rotate(degree, resample=Image.NEAREST)
	kerarr = np.array(kerimg).astype('float32')
	kerarr[kerarr==0]=0
	kerarr[kerarr==128]=1
	return kerarr

def indicate_point(img, coord):
	coord = [int(e) for e in coord]
	draw = ImageDraw.Draw(img)
	draw.arc([coord[0]-5,coord[1]-5,coord[0]+5,coord[1]+5], 0, 360, 'red')
	return img

def indicate_line(img, coords):
	draw = ImageDraw.Draw(img)
	draw.line([coords[0][0],coords[0][1],coords[1][0],coords[1][1]], 'red')
	draw.line([coords[2][0],coords[2][1],coords[3][0],coords[3][1]], 'red')
	return img

def conv(vec1, vec2):
	return np.dot(vec1.flatten(), vec2.flatten())

def norm(mat):
	return (mat-mat.mean())/mat.std()

def angle(line):
	x1,y1,x2,y2 = line
	sin = float(abs(y1-y2))/math.sqrt((x1-x2)**2+(y1-y2)**2)
	arc = math.asin(sin)*(180/math.pi)
	return arc

def border(arr, width):
	w,h = arr.shape
	arr[:width,:] = 0
	arr[w-width:,:] = 0
	arr[:,:width] = 0
	arr[:,h-width:] = 0
	return arr

def enhance(arr):
	arr = arr - arr.min()
	arr = np.exp(arr)
	arr[arr>255] = 255
	return arr

def activation(arr, kernel):
	pad_x, pad_y = arr.shape[0]+kernel.shape[0]-1, arr.shape[1]+kernel.shape[1]-1
	padded = np.ones((pad_x, pad_y))*255
	padded[kernel_size//2:pad_x-kernel_size//2, kernel_size//2:pad_y-kernel_size//2] = arr
	active = np.zeros(arr.shape)
	steps_x, steps_y = arr.shape[0], arr.shape[1]
	for i in range(steps_x):
		for j in range(steps_y):
			c = conv(padded[i:i+kernel_size,j:j+kernel_size], kernel)
			active[i,j] = c
	img = Image.fromarray(clip(active).astype('uint8'))
	img = img.filter(ImageFilter.GaussianBlur(2))
	img = img.filter(ImageFilter.FIND_EDGES)
	img = img.filter(ImageFilter.SMOOTH_MORE)
	active = np.array(img).astype('float32')

	active = enhance(border(active, 5))
	img = Image.fromarray(active.astype('uint8'))
	img = img.filter(ImageFilter.SMOOTH_MORE)
	img = img.filter(ImageFilter.GaussianBlur(2))
	active = np.array(img)

	return active

def find_lines(arr):
	minLineLength = 1000
	maxLineGap = 10
	lines = cv2.HoughLinesP(arr.astype('uint8'),1,np.pi/180,100,minLineLength,maxLineGap)
	prev_a = angle(lines[0][0])
	for line in lines:
		x1,y1,x2,y2 = line[0]
		if math.sqrt((x1-x2)**2+(y1-y2)**2) < 20:
			continue
		cv2.line(arr,(x1,y1),(x2,y2),(0,0,255),2)
	return arr

def find_coords(arr):
	x_axis = list(arr.sum(axis=0))
	y_axis = list(arr.sum(axis=1))
	return (x_axis.index(max(x_axis[20:-20])), y_axis.index(max(y_axis[20:-20])))

def find_endpoints(coord, rot):
	rot = rot if rot>45 else -1*rot
	c1 = rotate_coord(coord[0]-50, coord[1], rot, coord[0], coord[1])
	c2 = rotate_coord(coord[0]+50, coord[1], rot, coord[0], coord[1])
	c3 = rotate_coord(coord[0], coord[1]-50, rot, coord[0], coord[1])
	c4 = rotate_coord(coord[0], coord[1]+50, rot, coord[0], coord[1])
	return c1, c2, c3, c4	

def rotate_coord(x,y,theta,c1,c2):
	x -= c1
	y -= c2
	y *= -1
	# theta = 90-theta
	return x*math.cos(math.radians(theta))-y*math.sin(math.radians(theta))+c1, y*math.cos(math.radians(theta))+x*math.sin(math.radians(theta))+c2

def vis():
	degree = 0
	kernel_cros = gen_kernel(degree+7, 0)
	kernel_vert = gen_kernel(degree+17, 0)
	kernel_horz = gen_kernel(degree+27, 0)
	raw = Image.open('5.png').resize((320,240), resample=Image.LANCZOS).rotate(degree, resample=Image.BICUBIC)
	arr = np.array(raw)

	img = Image.fromarray(arr.astype('uint8'))

	img = img.filter(ImageFilter.SMOOTH_MORE)
	img = img.filter(ImageFilter.EMBOSS)
	img = img.filter(ImageFilter.SMOOTH_MORE)
	img = img.filter(ImageFilter.FIND_EDGES)
	img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
	img = img.filter(ImageFilter.SMOOTH_MORE)

	arr = np.array(img)
	w, h = arr.shape

	plt.subplot(221)
	plt.title('mask map')
	plt.imshow(arr)

	arr = np.array(img)
	act_cros = activation(arr, kernel_cros)
	print act_cros[40:w-40, 40:h-40].mean()
	plt.subplot(222)
	plt.title('7 degree, avg activation: %s'%round(act_cros[40:w-40, 40:h-40].mean(), 4))
	plt.imshow(act_cros)

	arr = np.array(img)
	act_vert = activation(arr, kernel_vert)
	print act_vert[40:w-40, 40:h-40].mean()
	plt.subplot(223)
	plt.title('17 degree, avg activation: %s'%round(act_vert[40:w-40, 40:h-40].mean(), 4))
	plt.imshow(act_vert)

	arr = np.array(img)
	act_horz = activation(arr, kernel_horz)
	plt.subplot(224)
	print act_horz[40:w-40, 40:h-40].mean()
	plt.title('27 degree, avg activation: %s'%round(act_horz[40:w-40, 40:h-40].mean(), 4))
	plt.imshow(act_horz)

	plt.show()

	# deglst = []
	# for deg in range(0,90):
	# 	arr = np.array(img)
	# 	kernel = gen_kernel(deg, 0)
	# 	act = activation(arr, kernel)
	# 	w,h = act.shape
	# 	metric = act[40:w-40, 40:h-40].mean()
	# 	print '%s:%s'%(deg, metric)
	# 	deglst.append(metric)
	# rot = deglst.index(max(deglst))

	# print rot

	# gmi = img.rotate(-rot)
	# plt.subplot(221)
	# kernel = gen_kernel(rot, 0)
	# act = activation(arr, kernel)
	# plt.imshow(act)

	# plt.subplot(222)
	# plt.plot(np.array(gmi).sum(axis=0))
	# plt.subplot(224)
	# plt.plot(np.array(gmi).sum(axis=1))

	# center = find_coords(np.array(gmi))
	# coord = rotate_coord(center[0], center[1], rot, 160, 120)
	# endpoints = find_endpoints(coord, rot-90)

	# img = indicate_point(raw.convert('RGB'), coord)
	# img = indicate_line(img, endpoints)

	# plt.subplot(223)
	# plt.imshow(np.array(img))
	# plt.show()
	# img.save('9_ret.png')

def predict(f):
	msk = Image.open('val/res/mask/'+f).resize((320,240), resample=Image.LANCZOS)
	arr = np.array(msk)

	img = Image.fromarray(arr.astype('uint8'))

	img = img.filter(ImageFilter.SMOOTH_MORE)
	img = img.filter(ImageFilter.EMBOSS)
	img = img.filter(ImageFilter.SMOOTH_MORE)
	img = img.filter(ImageFilter.FIND_EDGES)
	img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
	img = img.filter(ImageFilter.SMOOTH_MORE)

	arr = np.array(img)
	w, h = arr.shape


	pbar = ProgressBar(maxval=100, widgets=[Bar('=', '[', ']'), ' ', Percentage()]).start()

	deglst = []
	for deg in range(0,90):
		arr = np.array(img)
		kernel = gen_kernel(deg, 0)
		act = activation(arr, kernel)
		w,h = act.shape
		metric = act[40:w-40, 40:h-40].mean()
		deglst.append(metric)
		pbar.update(int((float(deg) / (90 - 1)) * 100))
	rot = deglst.index(max(deglst))
	print rot

	gmi = img.rotate(-rot)
	kernel = gen_kernel(rot, 0)
	act = activation(arr, kernel)

	center = find_coords(np.array(gmi))
	coord = rotate_coord(center[0], center[1], (90-rot)+90, 160, 120)
	endpoints = find_endpoints(coord, rot-90)

	raw = Image.open('val/res/raw/'+f.split('_')[0]+'_raw.png').resize((320,240), resample=Image.LANCZOS)
	raw = indicate_point(raw.convert('RGB'), coord)
	raw = indicate_line(raw, endpoints)
	raw.save('val/res/out/'+f.split('_')[0]+'_%s_out.png'%rot)

	pbar.finish()

	print '%s finished'%f

def main():
	for _,_, fs in os.walk('val/res/mask'):
		for f in fs:
			predict(f)

def show():
	for _,_,fs in os.walk('val/res/out/'):
		for f in fs:
			# raw = Image.open('val/res/raw/'+f.split('_')[0]+'_raw.png').convert('RGB')
			mask = Image.open('val/res/mask/'+f.split('_')[0]+'_mask.png')
			out = Image.open('val/res/out/'+f)
			# plt.subplot(212)
			# plt.title('raw input')
			# plt.imshow(np.array(raw))
			plt.subplot(121)
			plt.title('cnn mask output')
			plt.imshow(np.array(mask))
			plt.subplot(122)
			plt.title('cross detection')
			plt.imshow(np.array(out))
			plt.savefig('val/res/fig/'+f.split('_')[0]+'_fig.png', dpi=128)
			print '%s finished'%f
			# return

if __name__ == '__main__':
	# predict('287,33000,9000,270_mask.png')
	vis()