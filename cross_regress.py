#coding:utf-8

from PIL import Image, ImageDraw
from collections import namedtuple

import mxnet as mx
import numpy as np
import os
import logging
import random

ctx = mx.gpu(0)
batch_size = 64
model_prefix = 'params/foo'
Batch = namedtuple('Batch', ['data'])
size_1 = 256
size_2 = 32

logging.getLogger().setLevel(logging.DEBUG)

def init_data(train):
	if train:
		data, label = mx.nd.zeros((300,1,size_1,size_1)), mx.nd.zeros((300,3))
		for _,_,fs in os.walk('train/data'):
			random.shuffle(fs)
			for i, f in enumerate(fs):
				img = Image.open('train/data/'+f)
				x, y = f.split('.')[0].split('_')[1:]
				x, y = int(x), int(y)
				if random.randint(0,10)>3:
					angle = random.randint(0,45)
					img = np.array(img.rotate(angle))
					img[img>210] = 210
					data[i] = img
					label[i] = np.array([x, y, angle])
					# label[i] = np.array(Image.open('train/label/'+f).resize((size_2,size_2), resample=Image.BICUBIC).rotate(angle))
				else:
					img = np.array(img)
					img[img>210] = 210
					data[i] = img
					label[i] = np.array([x, y, 0])
					# label[i] = np.array(Image.open('train/label/'+f).resize((size_2,size_2), resample=Image.BICUBIC))/255.
		return mx.io.NDArrayIter(data=data, label=label, batch_size=batch_size, shuffle=True)
	else:
		data, label = mx.nd.zeros((1,1,size_1,size_1)), mx.nd.zeros((1,3))
		return mx.io.NDArrayIter(data=data, label=label, batch_size=1, shuffle=True)

def indicate_point(img, coord):
	coord = [int(e) for e in coord]
	draw = ImageDraw.Draw(img)
	draw.arc([coord[0]-5,coord[1]-5,coord[0]+5,coord[1]+5], 0, 360, 'red')
	return img

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

def model(train):
	data = mx.symbol.Variable('data')
	label = mx.symbol.Variable('softmax_label')
	c1 = conv_block(data, 16, (3,3), (0,0), (1,1), (1,1))
	p1 = pool_block(c1)
	c2 = conv_block(p1, 16, (3,3), (0,0), (1,1), (1,1))
	p2 = pool_block(c2)
	c3 = conv_block(p2, 24, (3,3), (3,3), (3,3), (1,1))
	c4 = conv_block(c3, 24, (3,3), (3,3), (3,3), (1,1))
	p4 = pool_block(c4)
	c5_1 = conv_block(p4, 16, (3,3), (8,8), (8,8), (1,1))
	c5_2 = conv_block(p4, 16, (3,3), (16,16), (16,16), (1,1))
	c5_3 = conv_block(p4, 16, (3,3), (32,32), (32,32), (1,1))
	c5_c = mx.symbol.concat(c5_1,c5_2,c5_3)
	p4 = pool_block(c5_c)
	c6_1 = conv_block(p4, 16, (3,3), (8,8), (8,8), (1,1))
	c6_2 = conv_block(p4, 16, (3,3), (16,16), (16,16), (1,1))
	c6_3 = conv_block(p4, 16, (3,3), (64,64), (64,64), (1,1))
	c6_c = mx.symbol.concat(c6_1,c6_2,c6_3)
	p6 = pool_block(c6_c)
	c7 = conv_block(p6, 32, (3,3), (3,3), (3,3), (1,1))
	p7 = pool_block(c7)
	c8 = conv_block(p7, 64, (3,3), (0,0), (1,1), (1,1))
	p8 = pool_block(c8)
	c9 = conv_block(p8, 128, (3,3), (0,0), (1,1), (1,1))
	p9 = pool_block(c9)
	co = conv_block(p9, 3, (1,1), (0,0), (0,0), (1,1))
	if not train:
		return co
	loss = mx.symbol.LinearRegressionOutput(co, label)
	return loss

def train():
	diter = init_data(True)
	symbol = model(True)
	mod = mx.mod.Module(symbol=symbol, context=ctx, data_names=('data',), label_names=('softmax_label',))
	mod.bind(data_shapes=diter.provide_data, label_shapes=diter.provide_label)
	mod.init_params(initializer=mx.init.Uniform(scale=.1))
	mod.fit(
		diter,
		optimizer = 'adam',
		optimizer_params = {'learning_rate':0.025},
		eval_metric = 'rmse',
		batch_end_callback = mx.callback.Speedometer(batch_size, 1),
		epoch_end_callback = mx.callback.do_checkpoint(model_prefix, 10),
		num_epoch = 1000,
		)

def predict():
	ctx = mx.cpu(0)
	diter = init_data(False)
	symbol = model(False)
	mod = mx.mod.Module(symbol=symbol, context=ctx, data_names=('data',), label_names=('softmax_label',))
	mod.bind(for_training=False, data_shapes=diter.provide_data)
	_, arg_params, aux_params = mx.model.load_checkpoint(model_prefix, 200)
	mod.set_params(arg_params, aux_params, allow_missing=True)
	folder = 'val/raw/'
	for _,_, fs in os.walk(folder):
		for f in fs:
			img = Image.open(folder+f)
			img = img.rotate(random.randint(-45,45))
			w,h = img.size
			array = mx.nd.zeros((1,1,w,h))
			npimg = np.array(img.convert('L'))
			npimg[npimg>210] = 210
			array[0,0,:] = mx.nd.array(npimg).transpose()
			mod.forward(Batch([array]))

			out = mod.get_outputs()[0][0][0].asnumpy()
			res = indicate_point(img, out)
			res = img
			res.save('val/pred/'+f.split('.')[0]+'_predict.png')
			print '%s predict finished'%f

if __name__ == '__main__':
	print 'using mxnet version %s'%mx.__version__
	predict()