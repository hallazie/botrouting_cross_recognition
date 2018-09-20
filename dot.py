#coding:utf-8

from PIL import Image, ImageDraw, ImageFilter
from collections import namedtuple

import mxnet as mx
import numpy as np
import os
import logging
import random

ctx = mx.gpu(0)
batch_size = 32
model_prefix = 'params/dot'
Batch = namedtuple('Batch', ['data'])
size_1 = (256, 256)
size_2 = (32, 32)

logging.getLogger().setLevel(logging.DEBUG)

def init_data(train):
	if train:
		for _,_,fs in os.walk('crop/data'):
			random.shuffle(fs)
			data, label = np.zeros((len(fs),1,size_1[1],size_1[0]), dtype='float32'), np.zeros((len(fs),1,size_2[1],size_2[0]), dtype='float32')
			for i, f in enumerate(fs):
				img = Image.open('crop/data/'+f)
				img = img.filter(ImageFilter.SMOOTH_MORE)
				img = img.filter(ImageFilter.DETAIL)
				img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
				img = img.filter(ImageFilter.SMOOTH_MORE)
				if random.randint(0,10)>3:
					angle = random.randint(-45,45)
					img = np.array(img.rotate(angle, resample=Image.BICUBIC))
					data[i] = img
					lbl = np.array(Image.open('crop/label_dot/'+f).resize((size_2[0],size_2[1]), resample=Image.BICUBIC).rotate(angle, resample=Image.BICUBIC))
					lbl[lbl>1] = 255
					label[i] = lbl
				else:
					img = np.array(img)
					data[i] = img
					lbl = np.array(Image.open('crop/label_dot/'+f).resize((size_2[0],size_2[1]), resample=Image.BICUBIC))
					lbl[lbl>1] = 255
					label[i] = lbl		
		data = (data-data.mean())/data.std()
		lbl = lbl/255.
		return mx.io.NDArrayIter(data=data, label=label, batch_size=batch_size, shuffle=True)
	else:
		data, label = mx.nd.zeros((1,1,size_1[1],size_1[0])), mx.nd.zeros((1,1,size_2[0],size_2[1]))
		return mx.io.NDArrayIter(data=data, label=label, batch_size=1, shuffle=True)

def indicate(img, mask):
	mask = np.array(mask).transpose()
	w, h = mask.shape
	img = img.convert('RGB')
	coord = np.where(mask==np.max(mask))
	draw = ImageDraw.Draw(img)
	draw.arc([coord[0][0]-5,coord[1][0]-5,coord[0][0]+5,coord[1][0]+5], 0, 360, 'red')
	draw.line([coord[0][0],0,coord[0][0],h], 'red')
	draw.line([0,coord[1][0],w,coord[1][0]], 'red')
	return img

def conv(vec1, vec2):
	return reduce(lambda x,y:x+y,[e[0]*e[1] for e in zip(vec1,vec2)]) 

def indicate_line(img, mask):
	mask = np.array(mask).transpose()
	h, w = mask.shape
	kernel_w = [255 for e in range(w)]
	kernel_h = [255 for e in range(h)]
	max_x, max_y = 0, 0
	max_conv = 0
	for i in range(80,h-80):
		cur_vec =[e for e in list(mask[i,:])]
		cur_cov = conv(cur_vec, kernel_h)
		if cur_cov > max_conv:
			max_conv = cur_cov
			max_x = i
	max_conv = 0
	for j in range(80,w-80):
		cur_vec = [e for e in list(mask[:,j])]
		cur_cov = conv(cur_vec, kernel_w)
		if cur_cov > max_conv:
			max_conv = cur_cov
			max_y = j
	coord = (max_x, max_y)
	# mask = Image.fromarray(mask.astype('uint8').transpose())
	img = img.convert('RGB')
	draw = ImageDraw.Draw(img)
	draw.arc([coord[0]-5,coord[1]-5,coord[0]+5,coord[1]+5], 0, 360, 'red')
	draw.line([coord[0],0,coord[0],w], 'red')
	draw.line([0,coord[1],h,coord[1]], 'red')
	return img


def conv_block(data, num_filter, kernel=(3,3), dilate=(1,1), pad=(2,2), stride=(1,1)):
	if dilate != (0,0):
		conv = mx.symbol.Convolution(data=data, num_filter=num_filter, kernel=kernel, dilate=dilate, pad=pad, stride=stride)
	else:
		conv = mx.symbol.Convolution(data=data, num_filter=num_filter, kernel=kernel, pad=pad, stride=stride)
	norm = mx.symbol.BatchNorm(data=conv)
	actv = mx.symbol.Activation(data=norm, act_type='relu')
	return actv

def pool_block(data):
	return mx.symbol.Pooling(data=data, kernel=(2,2), stride=(2,2), pool_type='max')

def model_000(train):
	data = mx.symbol.Variable('data')
	label = mx.symbol.Variable('softmax_label')
	c1 = conv_block(data, 32, (3,3), (0,0), (1,1), (1,1))
	c2 = conv_block(c1, 32, (3,3), (0,0), (1,1), (1,1))
	p2 = pool_block(c2)
	c3 = conv_block(p2, 16, (3,3), (0,0), (1,1), (1,1))
	c4 = conv_block(p2, 16, (3,3), (3,3), (3,3), (1,1))
	c4_c = mx.symbol.concat(c3,c4)
	p4 = pool_block(c4_c)
	c5_1 = conv_block(p4, 16, (3,3), (0,0), (1,1), (1,1))
	c5_2 = conv_block(p4, 16, (3,3), (8,8), (8,8), (1,1))
	c5_3 = conv_block(p4, 16, (3,3), (32,32), (32,32), (1,1))
	c5_c = mx.symbol.concat(c5_1,c5_2,c5_3)
	p5 = pool_block(c5_c)
	c6_0 = conv_block(p5, 16, (3,3), (0,0), (1,1), (1,1))
	c6_1 = conv_block(p5, 8, (3,3), (8,8), (8,8), (1,1))
	c6_2 = conv_block(p5, 8, (3,3), (16,16), (16,16), (1,1))
	c6_3 = conv_block(p5, 8, (3,3), (64,64), (64,64), (1,1))
	c6_c = mx.symbol.concat(c6_0,c6_1,c6_2,c6_3)
	# c7 = conv_block(c6_c, 64, (3,3), (0,0), (1,1), (1,1))
	# c8 = conv_block(c7, 64, (3,3), (4,4), (4,4), (1,1))
	co = conv_block(c6_c, 1, (1,1), (0,0), (0,0), (1,1))
	if not train:
		return mx.symbol.Group([co, c5_c])
	loss = mx.symbol.SoftmaxOutput(co, label)
	return loss

def model(train):
	data = mx.symbol.Variable('data')
	label = mx.symbol.Variable('softmax_label')
	c1 = conv_block(data, 32, (3,3), (0,0), (1,1), (1,1))
	p1 = pool_block(c1)
	c2 = conv_block(p1, 32, (3,3), (0,0), (1,1), (1,1))
	p2 = pool_block(c2)
	c3 = conv_block(p2, 128, (3,3), (12,12), (12,12), (1,1))
	p3 = pool_block(c3)
	c4 = conv_block(p3, 8, (3,3), (0,0), (1,1), (1,1))
	co = conv_block(c4, 1, (1,1), (0,0), (0,0), (1,1))
	if not train:
		return mx.symbol.Group([co, c4])
	loss = mx.symbol.SoftmaxOutput(co, label)
	return loss

def train():
	diter = init_data(True)
	symbol = model(True)
	mod = mx.mod.Module(symbol=symbol, context=ctx, data_names=('data',), label_names=('softmax_label',))
	mod.bind(data_shapes=diter.provide_data, label_shapes=diter.provide_label)
	mod.init_params(initializer=mx.init.Uniform(scale=.1))
	# _, arg_params, aux_params = mx.model.load_checkpoint(model_prefix, 320)
	# mod.set_params(arg_params, aux_params, allow_missing=True)
	mod.fit(
		diter,
		optimizer = 'adam',
		optimizer_params = {'learning_rate':0.005},
		eval_metric = 'rmse',
		batch_end_callback = mx.callback.Speedometer(batch_size, 1),
		epoch_end_callback = mx.callback.do_checkpoint(model_prefix, 10),
		num_epoch = 2500,
		)

def predict():
	ctx = mx.cpu(0)
	diter = init_data(False)
	symbol = model(False)
	mod = mx.mod.Module(symbol=symbol, context=ctx, data_names=('data',), label_names=('softmax_label',))
	mod.bind(for_training=False, data_shapes=diter.provide_data)
	_, arg_params, aux_params = mx.model.load_checkpoint(model_prefix, 1580)
	mod.set_params(arg_params, aux_params, allow_missing=True)
	folder = 'val/raw/'
	for _,_, fs in os.walk(folder):
		fs = fs[:20]
		for f in fs:
			img = Image.open(folder+f)
			img = img.rotate(random.randint(-45,45), resample=Image.BICUBIC)
			img = img.filter(ImageFilter.SMOOTH_MORE)
			img = img.filter(ImageFilter.DETAIL)
			img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
			img = img.filter(ImageFilter.SMOOTH_MORE)
			w,h = img.size
			array = mx.nd.zeros((1,1,w,h))
			npimg = np.array(img.convert('L'))
			npimg = (npimg-npimg.mean())/npimg.std()
			array[0,0,:] = mx.nd.array(npimg).transpose()
			mod.forward(Batch([array]))
			out = mod.get_outputs()[0][0][0].asnumpy().transpose()
			out = 255*(out-np.min(out))/(np.max(out)-np.min(out))
			mask = Image.fromarray(out.astype('uint8')).resize((w,h))
			mask.save('val/pred/'+f.split('.')[0]+'_mask.png')
			# res = indicate_line(img, mask)
			res = img
			res.save('val/pred/'+f.split('.')[0]+'_predict.png')
			print '%s predict finished'%f

if __name__ == '__main__':
	print 'using mxnet version %s'%mx.__version__
	predict()