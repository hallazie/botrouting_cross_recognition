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
			# suf.line([label_x, label_y-50, label_x, label_y+50], 'white', width=5)
			# suf.line([label_x-50, label_y, label_x+50, label_y], 'white', width=5)			
			suf.line([label_x, 0, label_x, h], 'white', width=5)
			suf.line([0, label_y, w, label_y], 'white', width=5)
			res = np.array(ret)
			# res[res>230] = 190
			ret = Image.fromarray(res.astype('uint8'))
			if i<300:
				ret.save('train/data/%s.png'%(i))
				# ret.save('train/data/%s_%s_%s.png'%(i, label_x, label_y))
				lbl.save('train/label/%s.png'%(i))
			else:
				ret.save('test/data/%s.png'%(i))
				# ret.save('test/data/%s_%s_%s.png'%(i, label_x, label_y))
				lbl.save('test/label/%s.png'%(i))				
			print '%s finished'%(f)

def fum():
	center_dict = {
		'56,19000,2000,90':(580,240),
		'93,19000,3000,90':(546,240),
		'128,19000,4000,90':(515,240),
	}
	for _,_,fs in os.walk('raw'):
		for i,f in enumerate(fs):
			img = Image.open('raw/'+f)
			w, h = img.size
			lbl = Image.new('L', (w, h), (0))
			suf = ImageDraw.Draw(lbl)
			# suf.rectangle([label_x-1, label_y-1, label_x+1, label_y+1], 'white', 'white')
			# suf.line([label_x, label_y-50, label_x, label_y+50], 'white', width=5)
			# suf.line([label_x-50, label_y, label_x+50, label_y], 'white', width=5)
			if not f.split('.')[0] in center_dict.keys():		
				suf.line([320, 0, 320, h], 'white', width=5)
				suf.line([0, 240, w, 240], 'white', width=5)				
			else:
				cent = center_dict[f.split('.')[0]]
				suf.line([cent[0], 0, cent[0], h], 'white', width=5)
				suf.line([0, 240, w, 240], 'white', width=5)			
			res = np.array(img)
			ret = Image.fromarray(res.astype('uint8'))
			if i<300:
				ret.save('train/data/%s.png'%(i))
				# ret.save('train/data/%s_%s_%s.png'%(i, label_x, label_y))
				lbl.save('train/label/%s.png'%(i))
			else:
				ret.save('test/data/%s.png'%(i))
				# ret.save('test/data/%s_%s_%s.png'%(i, label_x, label_y))
				lbl.save('test/label/%s.png'%(i))				
			print '%s finished'%(f)

def dot():
	for _,_,fs in os.walk('prep'):
		for i,f in enumerate(fs):
			img = Image.open('prep/'+f)
			w, h = img.size
			dot = Image.new('L', (size, size), (0))
			lin = Image.new('L', (size, size), (0))

			shift_x, shift_y = random.randint(-rd_size,rd_size), random.randint(-rd_size,rd_size)
			label_x, label_y = half-shift_x, half-shift_y
			ret = img.crop([center[0]+shift_x-half, center[1]+shift_y-half, center[0]+shift_x+half, center[1]+shift_y+half])
			
			suf_dot = ImageDraw.Draw(dot)
			suf_dot.rectangle([label_x-2, label_y-2, label_x+2, label_y+2], 'white', 'white')

			suf_lin = ImageDraw.Draw(lin)			
			suf_lin.line([label_x, 0, label_x, h], 'white', width=5)
			suf_lin.line([0, label_y, w, label_y], 'white', width=5)

			ret.save('crop/data/%s.png'%(i))
			dot.save('crop/label_dot/%s.png'%(i))			
			lin.save('crop/label_line/%s.png'%(i))			
			print '%s finished'%(f)


# def white2gray():
# 	sam = np.array(Image.open('sample.png'))
# 	avg = sam.sum()/(size**2)
# 	print avg

def foo():
	pass

if __name__ == '__main__':
	dot()