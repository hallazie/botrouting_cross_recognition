#coding:utf-8

from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageEnhance

import matplotlib.pyplot as plt
import numpy as np
import os
import cv2

def conv(vec1, vec2):
	pdct = [e[0]*e[1] for e in zip(vec1,vec2)]
	lent = len(pdct)//3
	if sum(pdct[lent:2*lent]) > (sum(pdct[:lent])+sum(pdct[2*lent:3*lent]))*0.75:
		return 0
	else:
		return reduce(lambda x,y:x+y, pdct) 

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
	folder = 'raw/'
	# folder = 'test/data/'
	for _,_, fs in os.walk(folder):
		fs = fs[:]
		for f in fs:
			raw = Image.open(folder+f)
			img = np.array(raw)
			img[img>220] = 220
			img = Image.fromarray(img.astype('uint8'))

			img = img.filter(ImageFilter.SMOOTH_MORE)

			enh_con = ImageEnhance.Contrast(img)
			contrast = 1.5
			img = enh_con.enhance(contrast)

			img = img.filter(ImageFilter.EDGE_ENHANCE)
			img = img.filter(ImageFilter.CONTOUR)
			img = img.filter(ImageFilter.GaussianBlur(2))
			img = img.filter(ImageFilter.SMOOTH_MORE)
			img = ImageOps.invert(img)

			enh_con = ImageEnhance.Contrast(img)
			contrast = 1.5
			img = enh_con.enhance(contrast)

			img.save('val/gen/'+f+'.png')

			# coord = percep(np.array(img), 'val/pred/'+f.split('.')[0]+'_plt.png')
			# raw = raw.convert('RGB')
			# w, h = raw.size
			# draw = ImageDraw.Draw(raw)
			# draw.arc([coord[0]-5,coord[1]-5,coord[0]+5,coord[1]+5], 0, 360, 'red')
			# draw.line([coord[0],0,coord[0],h], 'red')
			# draw.line([0,coord[1],w,coord[1]], 'red')
			# raw.save('val/pred/'+f)	
			# print '%s finished'%f	

if __name__ == '__main__':
	foo()