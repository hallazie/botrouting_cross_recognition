#coding:utf-8

import Tkinter as tk
import numpy as np
import random
import os
import sys

from PIL import Image, ImageTk

class mapviewer:

    def __init__(self):
        self.dragged_item = 'all'
        self.imgsize = 320
        self.current_coords = 0, 0
        self.width = 1280
        self.height = 960
        self.scale = 1.0
        self.num_img = 1024
        # self.num_img = 120*11
        self.img_list, self.tk_list, self.pos_list = [], [], []
        self.canvas = None
        self.last_canvx, self.last_canvy = 0, 0
        self.window = [(0-self.imgsize, self.width+self.imgsize), (0-self.imgsize, self.height+self.imgsize)]
        self.factor = 1.1
        self.maxx, self.maxy = 0, 0
        self.mutex = False

    def start_drag(self, event):
        # result = self.canvas.find_withtag('current')
        result = self.canvas.gettags('current')
        print result
        if result:
            self.dragged_item = int(result[1])
            self.current_coords = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        else:
            self.dragged_item = 'all'
            self.current_coords = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

    def stop_drag(self, event):
        self.calc_visible(False)
        self.dragged_item = 'all'

    def drag(self, event):
        xc, yc = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        dx, dy = xc - self.current_coords[0], yc - self.current_coords[1]
        curr_img_id = self.canvas.find_withtag('current')
        self.current_coords = xc, yc
        self.last_canvx, self.last_canvy = xc, yc
        if self.dragged_item == 'all':
            self.canvas.move(self.dragged_item, dx, dy)
            for i in range(len(self.pos_list)):
                self.pos_list[i] = (self.pos_list[i][0]+dx/self.scale, self.pos_list[i][1]+dy/self.scale)
        else:
            self.canvas.move(curr_img_id, dx, dy)
            self.pos_list[self.dragged_item] = (self.pos_list[self.dragged_item][0]+dx/self.scale, self.pos_list[self.dragged_item][1]+dy/self.scale)

    def zoomer(self, event):
        if not self.mutex:
            self.mutex = True
            if event.delta > 0:
                if self.scale < 2**3:
                    self.scale *= self.factor
                    self.window = [((self.window[0][0])/self.factor, (self.window[0][1])/self.factor), ((self.window[1][0])/self.factor, (self.window[1][1])/self.factor)]
                    self.redraw()
                else:
                    print 'achieved top'
            elif event.delta <0:
                if self.scale > 0.5**3:
                    self.scale /= self.factor
                    self.window = [((self.window[0][0])*self.factor, (self.window[0][1])*self.factor), ((self.window[1][0])*self.factor, (self.window[1][1])*self.factor)]
                    self.redraw()
                else:
                    print 'achieved bottom'
            self.mutex = False

    def redraw(self):
        # TODO: num_tks
        # self.base += self.num_img
        self.calc_visible(True)
        self.canvas.scale('all', self.width//2, self.height//2, self.scale, self.scale)

    # --------------------------------------------------------------------------------------------------

    def img_load(self):
        for _,_,fs in os.walk('../bj_img'):
            for c, f in enumerate(fs):
                if c == self.num_img:
                    break
                img = Image.open('../bj_img/%s'%(f)).resize((self.imgsize,self.imgsize))
                curx, cury = float(f.split('_')[1])-1000, float(f.split('_')[2])-1000
                self.maxx, self.maxy = max(curx, self.maxx), max(cury, self.maxy)
                self.img_list.append(img)
                self.pos_list.append((curx, cury))
        tmp_orgx, tmp_orgy = self.maxx//2, self.maxy//2
        for i in range(len(self.pos_list)):
            self.pos_list[i] = (self.pos_list[i][0]-tmp_orgx, self.pos_list[i][1]-tmp_orgx)

    def calc_visible(self, is_scale):
        size = int(self.imgsize*self.scale)
        show_cnt = 0
        self.tk_list = []
        self.canvas.delete('all')
        print 'window:%s, size:%s,%s'%(self.window, self.window[0][1]-self.window[0][0], self.window[1][1]-self.window[1][0])
        for i in range(len(self.pos_list)):
            if self.pos_list[i][0]>self.window[0][0] and self.pos_list[i][0]<self.window[0][1] and self.pos_list[i][1]>self.window[1][0] and self.pos_list[i][1]<self.window[1][1]:
                self.tk_list.append(ImageTk.PhotoImage(self.img_list[i].resize((size, size))))
                show_cnt += 1
            else:
                self.tk_list.append(0)
        print 'current showing %s tiles with size %s, scale %s'%(show_cnt, size, self.scale)
        for i in range(len(self.pos_list)):
            if self.tk_list[i] != 0:
                if not is_scale:
                    self.canvas.create_image(self.pos_list[i][0]*self.scale, self.pos_list[i][1]*self.scale, image=self.tk_list[i], anchor='nw', tags=('img',str(i)))
                else:
                    self.canvas.create_image(self.pos_list[i][0], self.pos_list[i][1], image=self.tk_list[i], anchor='nw', tags=('img',str(i)))

    def run(self):
        self.img_load()

        root = tk.Tk()

        self.canvas = tk.Canvas(width=self.width, height=self.height)
        self.canvas.pack()
        self.canvas.bind('<ButtonPress-1>', self.start_drag)
        self.canvas.bind('<ButtonRelease-1>', self.stop_drag)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.canvas.bind_all('<MouseWheel>', self.zoomer)

        self.calc_visible(False)

        root.mainloop()

if __name__ == '__main__':
    mv = mapviewer()
    mv.run()
