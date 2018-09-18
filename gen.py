#coding:utf-8

from PIL import Image, ImageDraw
import os
import random
import numpy as np

center = (320,240)
size = 256
half = size//2
rd_size = (size//2)-20

def fee():
	for _,_,fs in os.walk('prep'):
		for i,f in enumerate(fs):
			img = Image.open('prep/'+f)
			w, h = img.size
			lbl = Image.new('L', (size, size), (0))
			shift_x, shift_y = random.randint(-rd_size,rd_size), random.randint(-rd_size,rd_size)
			label_x, label_y = half-shift_x, half-shift_y
			ret = img.crop([center[0]+shift_x-half, center[1]+shift_y-half, center[0]+shift_x+half, center[1]+shift_y+half])
			suf = ImageDraw.Draw(lbl)
			suf.rectangle([label_x-1, label_y-1, label_x+1, label_y+1], 'white', 'white')
			suf.line([label_x-1, 0, label_x-1, h], 'white')
			suf.line([label_x, 0, label_x, h], 'white')
			suf.line([label_x+1, 0, label_x+1, h], 'white')
			suf.line([0, label_y-1, w, label_y-1], 'white')
			suf.line([0, label_y, w, label_y], 'white')
			suf.line([0, label_y+1, w, label_y+1], 'white')
			res = np.array(ret)
			# res[res>230] = 190
			ret = Image.fromarray(res.astype('uint8'))
			if i<300:
				ret.save('train/data/%s.png'%(i))
				lbl.save('train/label/%s.png'%(i))
			else:
				ret.save('test/data/%s.png'%(i))
				lbl.save('test/label/%s.png'%(i))				
			print '%s finished'%(f)

# def white2gray():
# 	sam = np.array(Image.open('sample.png'))
# 	avg = sam.sum()/(size**2)
# 	print avg

def foo():
	pass

if __name__ == '__main__':
	fee()