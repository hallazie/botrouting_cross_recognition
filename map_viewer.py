# coding:utf-8
# @author: xiaoshanghua
# map viewer

try:
    print 'using Tkinter'
    import Tkinter as tk
except:
    print 'using tkinter'
    import tkinter as tk

import tkFileDialog
import tkMessageBox
import ttk

import numpy as np
import math
import random
import os
import sys
import sqlite3
import traceback
import datetime
import copy
import socket as sk
import threading
import time

from PIL import Image, ImageTk

class Imgobj:
    '''
        Imgobj中始终存储原始图像（320*320）
        不同绘图模式中，使用绘图时变换或存储临时图像：
            旋转：临时绘制
            边框：以flag判断是否有边框，有则使用边框备份。
    '''
    def __init__(self, idx, image, x, y, theta):
        self.idx = idx
        self.image = image
        self.x = x
        self.y = y
        self.ox = x
        self.oy = y
        self.theta = theta
        self.rot = 0.
        self.image_boxed = None

        self.shown = True
        self.labeled = False
        self.fixed = False
        self.boxed = False
    
    def enter_boundingbox(self, idx):
        if self.image_boxed == None:
            self.boxed = True
            tmp = np.array(self.image.convert('RGB'))
            w, h = self.image.size
            for i in range(3):
                if i == idx:
                    tmp[:w,   0:5,   i] = 255
                    tmp[:w,   h-5:,  i] = 255
                    tmp[0:5,  :h,    i] = 255
                    tmp[w-5:, :h,    i] = 255
                else:
                    tmp[:w,   0:5,   i] = 0
                    tmp[:w,   h-5:,  i] = 0
                    tmp[0:5,  :h,    i] = 0
                    tmp[w-5:, :h,    i] = 0
            self.image_boxed = Image.fromarray(tmp.astype('uint8'))

    def leave_boundingbox(self):
        if self.image_boxed != None:
            self.image_boxed = None
            self.boxed = False

class Mapviewer:
    def __init__(self):
        # basick vars
        self.imgsize = 320
        self.mil2pix_ratio = 0.40625
        self.scale = 1.0
        self.width = 1280
        self.height = 960
        self.window = [(0, 1280), (0, 960)]
        self.factor = 1.1
        self.maxx, self.maxy = 0, 0
        self.db_path = ''
        self.configfile = {}
        self.using_db = True

        # tk vars
        self.canvas = None

        # canvas vars
        self.dragged_item = tk.ALL
        self.current_coords = 0, 0
        self.current_angle = 0.
        self.total_map_shift = (640, 480)           # 屏幕左上角所显示的位置，平移/缩放均会影响
        self.x_axis_gap_val = 1000
        self.y_axis_gap_val = 1000
        self.coord_central = 160*self.mil2pix_ratio, 160*self.mil2pix_ratio
        self.selected_node_id_int = None
        self.selected_node_canvas_id_int = None
        self.img_insert = None
        self.curr_img_rotate = 0.0

        # item vars
        self.img_dict = {}
        self.modify_img_dict = {}
        self.grid_horz = []
        self.grid_vert = []
        self.edit_history = []
        self.dragging_img_set = set()

        # util vars
        self.edit_mod_flag = False
        self.mutex = False
        self.mutex_unlock_count = 0
        self.show_grid_flag = True
        self.edit_delete_flag = False
        self.enter_label_mod = False
        self.progress_total = 0
        self.progress_current = 0

        # socket vars 
        self.sk_top_alive = False
        self.sk_control_focus = False
        self.sk_image = None
        self.sk_image_idx = 0
        self.sk_image_panel = None
        self.sock_open_flag = False

        # global view vars
        self.global_view_flag = False
        
        # preference vars
        self.grid_line_width = 1
        self.coord_line_width = 1
        self.sqlite_table_name = 'zhdl_map'
        self.sk_save_path = ''

        try:
            with open('mapviewer.cfg', 'r') as f:
                for line in f.readlines():
                    k, w = line.replace(' ','').split('=')
                    self.configfile[k]=w
            if self.configfile['DBPATH']:
                self.db_path = self.configfile['DBPATH']
        except:
            print 'no config file exist'

    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 画布鼠标方法 +++++++++++++++++++++++++++++++++++++++++++++++++++

    def start_drag_item(self, event):
        result = self.canvas.gettags('current')
        if len(result)>2:
            self.dragged_item = int(result[1])
        else:
            self.dragged_item = tk.ALL
        self.current_coords = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

    def stop_drag_item(self, event):
        pass

    def drag_item(self, event):
        try:
            xc, yc = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
            dx, dy = xc-self.current_coords[0], yc-self.current_coords[1]
            self.total_map_shift = self.total_map_shift[0]-dx/self.scale, self.total_map_shift[1]-dy/self.scale
            curr_img_id = self.canvas.find_withtag('current')
            self.current_coords = xc, yc
            if self.dragged_item != tk.ALL and self.edit_mod_flag==True and self.img_dict[self.dragged_item].fixed==False:
                # 拖拽编辑模式
                self.canvas.tag_raise('current')
                self.canvas.tag_raise('coordline')
                self.canvas.tag_raise('baseline')
                if self.dragged_item not in self.modify_img_dict.keys():
                    self.modify_img_dict[self.dragged_item] = (0,0)
                self.dragging_img_set.add(self.dragged_item)
                self.canvas.move(curr_img_id, dx, dy)
                self.img_dict[self.dragged_item].enter_boundingbox(0)
                self.img_dict[self.dragged_item].x += dx
                self.img_dict[self.dragged_item].y += dy
                self.modify_img_dict[self.dragged_item] = (self.modify_img_dict[self.dragged_item][0]+dx/self.scale, self.modify_img_dict[self.dragged_item][1]+dy/self.scale)
            # else:
            #     self.canvas.delete('baseline')
            #     self.canvas.move(tk.ALL, dx, dy)
            #     self.canvas.create_line(640,0,640,960, fill='blue', tags='baseline')
            #     self.canvas.create_line(0,480,1280,480, fill='blue', tags='baseline')
            #     for k in self.img_dict.keys():
            #         self.img_dict[k].x += dx
            #         self.img_dict[k].y += dy
            #     for i in range(len(self.grid_vert)):
            #         self.grid_vert[i] = (self.grid_vert[i][0], self.grid_vert[i][1]+dy, self.grid_vert[i][2], self.grid_vert[i][3]+dy)
            #     for j in range(len(self.grid_horz)):
            #         self.grid_horz[j] = (self.grid_horz[j][0]+dx, self.grid_horz[j][1], self.grid_horz[j][2]+dx, self.grid_horz[j][3])
            #     self.coord_central = (self.coord_central[0]+dx, self.coord_central[1]+dy)
        except Exception as e:
            print 'drag '+str(e)

    def start_drag_canvas(self, event):
        self.root.config(cursor='fleur')
        self.dragged_item = tk.ALL
        self.current_coords = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

    def stop_drag_canvas(self, event):
        self.root.config(cursor='arrow')
        self.calc_visible(False)

    def drag_canvas(self, event):
        try:
            xc, yc = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
            dx, dy = xc-self.current_coords[0], yc-self.current_coords[1]
            self.total_map_shift = self.total_map_shift[0]-dx/self.scale, self.total_map_shift[1]-dy/self.scale
            curr_img_id = self.canvas.find_withtag('current')
            self.current_coords = xc, yc
            # if self.dragged_item != tk.ALL and self.edit_mod_flag==True and self.img_dict[self.dragged_item].fixed==False:
            #     # 拖拽编辑模式
            #     self.canvas.tag_raise('current')
            #     self.canvas.tag_raise('coordline')
            #     self.canvas.tag_raise('baseline')
            #     if self.dragged_item not in self.modify_img_dict.keys():
            #         self.modify_img_dict[self.dragged_item] = (0,0)
            #     self.dragging_img_set.add(self.dragged_item)
            #     self.canvas.move(curr_img_id, dx, dy)
            #     self.img_dict[self.dragged_item].enter_boundingbox(0)
            #     self.img_dict[self.dragged_item].x += dx
            #     self.img_dict[self.dragged_item].y += dy
            #     self.modify_img_dict[self.dragged_item] = (self.modify_img_dict[self.dragged_item][0]+dx/self.scale, self.modify_img_dict[self.dragged_item][1]+dy/self.scale)
            # else:
            self.canvas.delete('baseline')
            self.canvas.move(tk.ALL, dx, dy)
            self.canvas.create_line(640,0,640,960, fill='blue', tags='baseline')
            self.canvas.create_line(0,480,1280,480, fill='blue', tags='baseline')
            for k in self.img_dict.keys():
                self.img_dict[k].x += dx
                self.img_dict[k].y += dy
            for i in range(len(self.grid_vert)):
                self.grid_vert[i] = (self.grid_vert[i][0], self.grid_vert[i][1]+dy, self.grid_vert[i][2], self.grid_vert[i][3]+dy)
            for j in range(len(self.grid_horz)):
                self.grid_horz[j] = (self.grid_horz[j][0]+dx, self.grid_horz[j][1], self.grid_horz[j][2]+dx, self.grid_horz[j][3])
            self.coord_central = (self.coord_central[0]+dx, self.coord_central[1]+dy)
        except Exception as e:
            print 'drag '+str(e)


    def start_rotate(self, event):
        if self.edit_mod_flag:
            self.current_angle = self.canvas.canvasy(event.x)
        self.calc_visible(False)

    def stop_rotate(self, event):
        if self.edit_mod_flag:
            try:
                self.img_dict[self.selected_node_id_int].rot += self.current_rotate*0.1
                self.calc_visible(False)
                self.current_rotate = 0.
                if self.selected_node_id_int not in self.modify_img_dict.keys():
                    self.modify_img_dict[self.selected_node_id_int] = (0,0)
            except Exception as e:
                print 'stop_rotate '+str(e)

    def rotate(self, event):
        if self.edit_mod_flag:
            ca = self.canvas.canvasx(event.x)
            self.current_rotate = ca - self.current_angle
            try:
                if self.selected_node_id_int != None:
                    print 'rotating image %s with angle %s'%(self.selected_node_id_int, self.current_rotate)
                    self.canvas.delete('selected')
                    self.rotate_img = self.img_dict[self.selected_node_id_int].image.convert('RGBA')
                    self.rotate_arr = np.array(self.rotate_img)
                    self.rotate_arr[:,:,3] = (self.rotate_arr[:,:,0]+self.rotate_arr[:,:,1]+self.rotate_arr[:,:,2]!=0)*self.rotate_arr[:,:,3]
                    self.rotate_img = Image.fromarray(self.rotate_arr.astype('uint8')).resize((int(self.imgsize*self.scale), int(self.imgsize*self.scale))).rotate(self.img_dict[self.selected_node_id_int].theta+self.current_rotate*0.1+self.img_dict[self.selected_node_id_int].rot, expand=True)
                    self.rotaet_tkimg = ImageTk.PhotoImage(self.rotate_img)
                    print self.rotate_img.size[0]
                    print self.imgsize*self.scale
                    shift = (self.rotate_img.size[0])/2.
                    self.canvas.create_image((self.img_dict[self.selected_node_id_int].x-shift, self.img_dict[self.selected_node_id_int].y-shift), image=self.rotaet_tkimg, anchor='nw', tags=('img', self.selected_node_id_int, 'selected'))
                    self.edit_rotate_val.set('图像：%s，旋转角度：%s°'%(self.selected_node_id_int, round(self.img_dict[self.selected_node_id_int].rot+self.current_rotate*0.1, 2)))
            except Exception as e:
                traceback.print_exc()
                print self.canvas.gettags('current')

    def zoomer(self, event):
        if not self.mutex:
            self.mutex = True
            if event.delta > 0:
                if self.scale < 2**3:
                    self.scale *= self.factor
                    self.zoom_scale.set('缩放系数：%s'%round(self.scale, 5))
                    for k in self.img_dict.keys():
                        self.img_dict[k].x = (self.img_dict[k].x - 640) * self.factor + 640
                        self.img_dict[k].y = (self.img_dict[k].y - 480) * self.factor + 480
                    for i in range(len(self.grid_vert)):
                        self.grid_vert[i] = (
                            (self.grid_vert[i][0] - 640) * self.factor + 640,
                            (self.grid_vert[i][1] - 480) * self.factor + 480,
                            (self.grid_vert[i][2] - 640) * self.factor + 640,
                            (self.grid_vert[i][3] - 480) * self.factor + 480)
                    for j in range(len(self.grid_horz)):
                        self.grid_horz[j] = (
                            (self.grid_horz[j][0] - 640) * self.factor + 640,
                            (self.grid_horz[j][1] - 480) * self.factor + 480,
                            (self.grid_horz[j][2] - 640) * self.factor + 640,
                            (self.grid_horz[j][3] - 480) * self.factor + 480)
                    self.calc_visible(True)
                else:
                    print 'achieved top'
            elif event.delta <0:
                if self.scale > 0.5**4:
                    if self.edit_mod_flag and self.scale/self.factor<=0.2:
                        tkMessageBox.showwarning('提示', '请先退出编辑模式')
                        self.mutex = False
                        return
                    self.scale /= self.factor
                    self.zoom_scale.set('缩放系数：%s'%round(self.scale, 5))
                    for k in self.img_dict.keys():
                        self.img_dict[k].x = (self.img_dict[k].x - 640) / self.factor + 640
                        self.img_dict[k].y = (self.img_dict[k].y - 480) / self.factor + 480
                    for i in range(len(self.grid_vert)):
                        self.grid_vert[i] = (
                            (self.grid_vert[i][0] - 640) / self.factor + 640,
                            (self.grid_vert[i][1] - 480) / self.factor + 480,
                            (self.grid_vert[i][2] - 640) / self.factor + 640,
                            (self.grid_vert[i][3] - 480) / self.factor + 480)
                    for j in range(len(self.grid_horz)):
                        self.grid_horz[j] = (
                            (self.grid_horz[j][0] - 640) / self.factor + 640,
                            (self.grid_horz[j][1] - 480) / self.factor + 480,
                            (self.grid_horz[j][2] - 640) / self.factor + 640,
                            (self.grid_horz[j][3] - 480) / self.factor + 480)
                    self.calc_visible(True)
                else:
                    print 'achieved bottom'
            # 因为zoomer bind的是all，所以event.x与y需要减去相应的左和上的距离。
            shift_x, shift_y = ((event.x - 220) - 640) / self.scale, ((event.y - 2) - 480) / self.scale
            self.mouse_pos_variable.set('鼠标位置：%s, %s'%(round(self.total_map_shift[0]+shift_x, 2), -1*round(self.total_map_shift[1]+shift_y, 2)))
            if self.scale <= 0.2:
                self.edit_delete_var.set('删除选中图像：暂无选中ID')
                self.edit_delete_flag = False
                self.edit_delete_btn.config(state=tk.DISABLED)
            self.mutex = False

    def zoomer_up(self, event):
        if not self.mutex:
            self.mutex = True
            self.mouse_pos_variable.set('鼠标位置：%s, %s'%(round(self.total_map_shift[0]+self.canvas.canvasx(event.x)/self.scale, 2), -1*round(self.total_map_shift[1]+self.canvas.canvasy(event.y)/self.scale, 2)))
            if self.scale < 2**4:
                self.scale *= self.factor
                self.zoom_scale.set('缩放系数：%s'%round(self.scale, 5))
                for k in self.img_dict.keys():
                    self.img_dict[k].x = (self.img_dict[k].x - 640) * self.factor + 640
                    self.img_dict[k].y = (self.img_dict[k].y - 480) * self.factor + 480
                for i in range(len(self.grid_vert)):
                    self.grid_vert[i] = (
                        (self.grid_vert[i][0] - 640) * self.factor + 640,
                        (self.grid_vert[i][1] - 480) * self.factor + 480,
                        (self.grid_vert[i][2] - 640) * self.factor + 640,
                        (self.grid_vert[i][3] - 480) * self.factor + 480)
                for j in range(len(self.grid_horz)):
                    self.grid_horz[j] = (
                        (self.grid_horz[j][0] - 640) * self.factor + 640,
                        (self.grid_horz[j][1] - 480) * self.factor + 480,
                        (self.grid_horz[j][2] - 640) * self.factor + 640,
                        (self.grid_horz[j][3] - 480) * self.factor + 480)
                self.calc_visible(True)
            else:
                print 'achieved top'

            if self.scale <= 0.2:
                self.edit_delete_var.set('删除选中图像：暂无选中ID')
                self.edit_delete_flag = False
                self.edit_delete_btn.config(state=tk.DISABLED)
            self.mutex = False

    def zoomer_dw(self, event):
        if not self.mutex:
            self.mutex = True
            self.mouse_pos_variable.set('鼠标位置：%s, %s'%(round(self.total_map_shift[0]+self.canvas.canvasx(event.x)/self.scale, 2), -1*round(self.total_map_shift[1]+self.canvas.canvasy(event.y)/self.scale, 2)))

            if self.scale > 0.5**4:
                if self.edit_mod_flag and self.scale/self.factor<=0.2:
                    tkMessageBox.showwarning('提示', '请先退出编辑模式')
                    self.mutex = False
                    return
                self.scale /= self.factor
                self.zoom_scale.set('缩放系数：%s'%round(self.scale, 5))
                for k in self.img_dict.keys():
                    self.img_dict[k].x = (self.img_dict[k].x - 640) / self.factor + 640
                    self.img_dict[k].y = (self.img_dict[k].y - 480) / self.factor + 480
                for i in range(len(self.grid_vert)):
                    self.grid_vert[i] = (
                        (self.grid_vert[i][0] - 640) / self.factor + 640,
                        (self.grid_vert[i][1] - 480) / self.factor + 480,
                        (self.grid_vert[i][2] - 640) / self.factor + 640,
                        (self.grid_vert[i][3] - 480) / self.factor + 480)
                for j in range(len(self.grid_horz)):
                    self.grid_horz[j] = (
                        (self.grid_horz[j][0] - 640) / self.factor + 640,
                        (self.grid_horz[j][1] - 480) / self.factor + 480,
                        (self.grid_horz[j][2] - 640) / self.factor + 640,
                        (self.grid_horz[j][3] - 480) / self.factor + 480)
                self.calc_visible(True)
            else:
                print 'achieved bottom'
            if self.scale <= 0.2:
                self.edit_delete_var.set('删除选中图像：暂无选中ID')
                self.edit_delete_flag = False
                self.edit_delete_btn.config(state=tk.DISABLED)
            self.mutex = False

    def edit_single_click_callback(self, event):
        idx = self.edit_history_listbox.curselection()
        if len(idx)>0:
            item = self.edit_history_listbox.get(idx[0])
            pid = int(item.split('  ')[0].split(':')[1])
            for e in self.edit_history_listbox.get(0, tk.END):
                self.img_dict[int(e.split('  ')[0].split(':')[1])].leave_boundingbox()
            self.img_dict[pid].enter_boundingbox(1)
            self.calc_visible(False)

    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 界面回调方法 ++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def mouse_pos_callback(self, event):
        try:
            self.mouse_pos_variable.set('鼠标位置：%s, %s'%(round(self.total_map_shift[0]+(self.canvas.canvasx(event.x)-640)/self.scale, 2), -1*round(self.total_map_shift[1]+(self.canvas.canvasy(event.y)-480)/self.scale, 2)))
        except Exception as e:
            print 'mouse_pos_callback '+str(e)

    def mouse_db_click_callback(self, event):
        if self.scale<=0.2:
            tkMessageBox.showinfo('提示', '当前缩放尺度不支持双击选中')
            return
        result = self.canvas.gettags('current')
        try:
            if result:
                curr_img_id = int(result[1])
                self.selected_node_id_int = curr_img_id
                self.selected_node_canvas_id_int = self.canvas.find_withtag('current')[0]
                self.selected_node_id.set('选中节点ID：%s'%curr_img_id)
                self.selected_node_pos.set('选中节点位置：%s，%s'%(round(self.img_dict[curr_img_id].ox, 1), -1*round(self.img_dict[curr_img_id].oy, 1)))
                self.edit_delete_var.set('删除选中图像：%s'%curr_img_id)
                self.edit_delete_flag = True
                self.edit_delete_btn.config(state=tk.NORMAL)
                for k in self.img_dict.keys():
                    self.img_dict[k].leave_boundingbox()
                self.img_dict[curr_img_id].enter_boundingbox(1)
                self.calc_visible(False)
                self.canvas.tag_raise('current')
                self.canvas.tag_raise('coordline')
                self.canvas.tag_raise('baseline')
            else:
                for k in self.img_dict.keys():
                    self.img_dict[k].leave_boundingbox()                
                self.selected_node_id_int = None
                self.selected_node_canvas_id_int = None
                self.selected_node_id.set('选中节点ID：-')
                self.selected_node_pos.set('选中节点位置：-')
                self.edit_delete_var.set('删除选中图像：暂无选中ID')
                self.edit_rotate_val.set('当前无旋转图像')
                self.edit_delete_flag = False
                self.edit_delete_btn.config(state=tk.DISABLED)
        except Exception as e:
            print 'mouse_db_click_callback '+str(e)

    def mil2pix_btn_callback(self):
        self.mil2pix_ratio = self.mil2pix.get()
        self.reinitialize()
        self.center_btn_callback()
        self.grid_gap_btn_callback()

    def center_btn_callback(self):
        # TODO: fix bug
        # # bug - 当改变中心点坐标时，图像与网格基准坐标都发生了改变
        # self.coord_central = ((self.left_top_x.get()-self.total_map_shift[0]+self.imgsize//2)*self.scale, -1*(self.left_top_y.get()+self.total_map_shift[1]-self.imgsize//2)*self.scale)
        # # self.change_focus(self.coord_central[0], self.coord_central[1])
        # self.calc_visible(False)
        self.change_focus(self.left_top_x.get(), self.left_top_y.get())

    def grid_gap_btn_callback(self):
        self.x_axis_gap_val = self.x_axis_gap.get()
        self.y_axis_gap_val = self.y_axis_gap.get()
        self.grid_load()
        self.calc_visible(False)

    def grid_show_btn_callback(self):
        self.show_grid_flag = not self.show_grid_flag
        if self.show_grid_flag:
            self.show_grid_str.set('已打开网格显示')
        else:
            self.show_grid_str.set('已关闭网格显示')
        self.calc_visible(False)

    def edit_mod_callback(self):
        if self.edit_mod_flag==False and self.scale<0.2:
            tkMessageBox.showinfo('提示', '当前缩放尺度不支持编辑')
            return
        self.edit_mod_flag = not self.edit_mod_flag
        if self.edit_mod_flag:
            self.edit_mod_var.set('退出编辑模式')
            for item in self.dragging_img_set:
                self.img_dict[item].leave_boundingbox()
                self.img_dict[item].enter_boundingbox(0)
            self.calc_visible(False)
        else:
            self.edit_mod_var.set('进入编辑模式')
            for item in self.dragging_img_set:
                self.img_dict[item].leave_boundingbox()
            self.edit_history_listbox.delete(0,tk.END)
            for k in self.modify_img_dict.keys():
                self.edit_history_listbox.insert(tk.END, 'id:%s  x:%s  y:%s  θ:%s'%(k, round(self.modify_img_dict[k][0],1), -1*round(self.modify_img_dict[k][1],1), self.img_dict[k].rot))
            self.dragging_img_set = set()
            self.calc_visible(False)
        # self.edit_mod_var.set('退出拖拽编辑模式') if self.edit_mod_flag else self.edit_mod_var.set('进入编辑模式')

    def edit_commit_callback(self):
        if self.using_db:
            result = tkMessageBox.askquestion('提示', '确认提交修改？', icon='warning')
            if result == 'yes':
                # if self.global_view_flag:
                #     self.global_image_gen()
                if self.edit_mod_flag:
                    tkMessageBox.showwarning('提示', '请先退出编辑模式')
                    return
                if len(self.edit_history_listbox.get(0, tk.END))==0:
                    tkMessageBox.showinfo('提示', '当前无修改历史')
                    return
                try:
                    conn = sqlite3.connect(self.db_path)
                    curs = conn.cursor()
                except Exception as e:
                    tkMessageBox.showinfo('提示', '请在选项中正确配置数据库文件地址')
                try:
                    for k in self.modify_img_dict:
                        # rot = abs(self.img_dict[k].rot)%90
                        # if rot < 45:
                        #     rat = 1/math.sin(((90-rot)/180.)*math.pi)
                        # else:
                        #     rat = 1/math.sin(((rot)/180.)*math.pi)
                        # rot_shift = -1*self.mil2pix_ratio*(320*(rat-1)/2)
                        self.img_dict[k].ox += self.modify_img_dict[k][0]
                        self.img_dict[k].oy += self.modify_img_dict[k][1]
                        self.img_dict[k].theta += self.img_dict[k].rot
                        curs.execute('update zhdl_map set x=%s, y=%s, heading=%s where id=%s'%(self.img_dict[k].ox, -1*(self.img_dict[k].oy), self.img_dict[k].theta, k))
                        conn.commit()
                    conn.close()
                    tkMessageBox.showinfo('提示', '提交修改成功')
                    self.edit_history_listbox.delete(0, tk.END)
                    self.modify_img_dict = {}
                except Exception as e:
                    tkMessageBox.showerror('提示', '提交修改失败\n%s'%str(e))
                else:
                    pass
        else:
            tkMessageBox.showinfo('提示', '当前使用文件源，暂未实现回传功能')

    def edit_abort_callback(self):
        if len(self.edit_history_listbox.get(0, tk.END))==0:
            tkMessageBox.showinfo('提示', '当前无修改历史')
            return
        self.edit_mod_flag = False
        # TODO:redo all the modification
        for item in self.edit_history_listbox.get(0, tk.END):
            idx, dx, dy, dtheta = [e.split(':')[1] for e in item.split('  ')]
            idx, dx, dy, dtheta = int(idx), float(dx), -1*float(dy), float(dtheta)
            self.img_dict[idx].x -= dx*self.scale
            self.img_dict[idx].y -= dy*self.scale
            self.img_dict[idx].rot -= dtheta
        self.calc_visible(False)
        self.edit_history_listbox.delete(0,tk.END)
        self.dragging_img_set = set()
        self.modify_img_dict = {}

    def edit_delete_callback(self):
        if self.using_db:
            result = tkMessageBox.askquestion('警告', '确认删除选中图像：%s？'%self.selected_node_id_int, icon='warning')
            if result == 'yes':
                try:
                    conn = sqlite3.connect(self.db_path)
                    curs = conn.cursor()
                    curs.execute('delete from zhdl_map where id=%s'%self.selected_node_id_int)
                    conn.commit()
                    conn.close()
                    tkMessageBox.showinfo('提示', '删除成功')
                except Exception as e:
                    print 'edit_delete_callback '+str(e)
                    tkMessageBox.showerror('错误', '删除失败')
        else:
            tkMessageBox.showinfo('提示', '当前使用文件源，暂未实现回传功能')

    def open_history_callback(self):
        pass

    def history_export_callback(self):
        if len(self.edit_history) == 0:
            tkMessageBox.showinfo('提示', '当前无修改历史')
        else:
            self.export_edit_history()

    def fintune_callback(self):
        pass

    def import_single_img_callback(self):
        image_path = tkFileDialog.askopenfilename(**dict(defaultextension='.bmp', filetypes=[('图片文件','*.bmp')]))
        if image_path:
            img_id = sorted(self.img_dict.keys())[-1]+1
            img = Image.open(image_path).convert('L').resize((320,320))
            imgobj = Imgobj(idx=img_id,
                            image=img,
                            x=0,
                            y=0,
                            theta=0)
            self.img_dict[img_id] = imgobj
            self.img_insert = imgobj
            # self.canvas.create_image(self.total_map_shift[0], self.total_map_shift[1], image=ImageTk.PhotoImage(img), anchor='nw', tags=('img', img_id))
            self.calc_visible(False)

    def import_single_img_commit_callback(self):
        #TODO: BUGFIX
        if self.img_insert != None:
            result = tkMessageBox.askquestion('提示', '确认插入新图像到数据库')
            if result == 'yes':
                try:
                    conn = sqlite3.connect(self.db_path)
                    curs = conn.cursor()
                    curs.execute('insert into zhdl_map values (?,?,?,?,?,?)',(
                        self.img_insert.idx, 
                        self.img_insert.x+self.total_map_shift[0], 
                        -1*(self.img_insert.y+self.total_map_shift[1]), 
                        self.img_insert.theta,
                        None, 
                        np.array(self.img_insert.image).reshape((320*320))
                    ))
                    conn.commit()
                    conn.close()
                    self.img_insert = None
                    tkMessageBox.showinfo('提示', '插入新图像到数据库成功')
                except:
                    tkMessageBox.showerror('错误', '插入新图像到数据库失败')
        else:
            tkMessageBox.showerror('错误', '暂无新的插入图像')

    def import_from_sqlite_callback(self):
        tmp = tkFileDialog.askopenfilename(**dict(defaultextension='.bin', filetypes=[('db数据库文件','*.db')]))
        if tmp!='':
            self.db_path = tmp
            self.reinitialize()
            self.center_btn_callback()
            # self.grid_show_btn_callback()
            tkMessageBox.showinfo('提示', '地图导入完成')
            with open('mapviewer.cfg', 'w+') as f:
                for line in f.readlines():
                    k, w = line.replace(' ','').split('=')
                    self.configfile[k]=w
                self.configfile['DBPATH'] = self.db_path
                w = '\n'.join([k+'='+self.configfile[k] for k in self.configfile.keys()])
                f.write(w)

    def preference_callback(self):
        self.pref_toplevel = tk.Toplevel()
        self.pref_toplevel.title('参数设置')

        grid_width_frame = tk.Frame(self.pref_toplevel)
        grid_width_frame.grid(pady=2)
        self.grid_width_val.set(self.grid_line_width)
        grid_width_lbl = tk.Button(grid_width_frame, text='网格线宽度')
        grid_width_ent = tk.Entry(grid_width_frame, textvariable=self.grid_width_val)
        grid_width_lbl.grid(row=0, column=0, pady=2, padx=2)
        grid_width_ent.grid(row=0, column=1, pady=2, padx=2)

        coord_width_frame = tk.Frame(self.pref_toplevel)
        coord_width_frame.grid(pady=2)
        self.coord_width_val.set(self.coord_line_width)
        coord_width_lbl = tk.Button(coord_width_frame, text='坐标线宽度')
        coord_width_ent = tk.Entry(coord_width_frame, textvariable=self.coord_width_val)
        coord_width_lbl.grid(row=0, column=0, pady=2, padx=2)
        coord_width_ent.grid(row=0, column=1, pady=2, padx=2)

        self.sk_path_val.set('D:/')
        sk_path_btn = tk.Button(self.pref_toplevel, text='图像采集存储目录', command=self.sk_path_callback)
        sk_path_lbl = tk.Label(self.pref_toplevel, textvariable=self.sk_path_val)
        sk_path_btn.grid(pady=2)
        sk_path_lbl.grid(pady=2)

        donothing_4_1 = tk.Frame(self.pref_toplevel, height=8, width=120)
        donothing_4_1.grid()
        donothing_4_2 = tk.Frame(self.pref_toplevel, bg='#555', height=1, width=220)
        donothing_4_2.grid()
        donothing_4_3 = tk.Frame(self.pref_toplevel, height=8, width=120)
        donothing_4_3.grid()

        preference_commit_btn = tk.Button(self.pref_toplevel, text='提交参数修改', command=self.preference_commit_callback)
        preference_commit_btn.grid(pady=5)

    def sk_path_callback(self):
        img_path = tkFileDialog.askdirectory()
        self.sk_path_val.set(img_path)

    def preference_commit_callback(self):
        self.grid_line_width = self.grid_width_val.get()
        self.coord_line_width = self.coord_width_val.get()
        self.calc_visible(False)
        self.pref_toplevel.destroy()

    def export_to_sqlite_callback(self):
        self.ex_sql_export = tk.Toplevel()

        sql_path_lbl_frame = tk.Frame(self.ex_sql_export)
        sql_path_lbl_frame.grid(pady=2)
        sql_path_lb0 = tk.Label(sql_path_lbl_frame, text='Sqlite.db文件路径：')
        sql_path_lbl = tk.Label(sql_path_lbl_frame, textvariable=self.sql_path_val)
        sql_path_lb0.grid(row=0, column=0, pady=2)
        sql_path_lbl.grid(row=0, column=1, pady=2)

        donothing_1_1 = tk.Frame(self.ex_sql_export, height=8, width=640)
        donothing_1_1.grid()
        donothing_1_2 = tk.Frame(self.ex_sql_export, bg='#555', height=1, width=640)
        donothing_1_2.grid()
        donothing_1_3 = tk.Frame(self.ex_sql_export, height=8, width=640)
        donothing_1_3.grid()

        sql_table_frame = tk.Frame(self.ex_sql_export)
        sql_table_frame.grid(pady=2)
        sql_table_lbl = tk.Label(sql_table_frame, text='Sqlite表名')
        sql_table_ent = tk.Entry(sql_table_frame, textvariable=self.sql_table_val)
        sql_table_lbl.grid(row=0, column=0, padx=2)
        sql_table_ent.grid(row=0, column=1, padx=2)

        sample_equipnum_frame = tk.Frame(self.ex_sql_export)
        sample_equipnum_frame.grid(pady=2)
        sample_equipnum_lbl = tk.Label(sample_equipnum_frame, text='采集设备号')
        sample_equipnum_ent = tk.Entry(sample_equipnum_frame, textvariable=self.sample_equipnum_val)
        sample_equipnum_lbl.grid(row=0, column=0, pady=2)
        sample_equipnum_ent.grid(row=0, column=1, pady=2)

        sample_rate_frame = tk.Frame(self.ex_sql_export)
        sample_rate_frame.grid(pady=2)
        sample_rate_lbl = tk.Label(sample_rate_frame, text='采集速度')
        sample_rate_ent = tk.Entry(sample_rate_frame, textvariable=self.sample_rate_val)
        sample_rate_lbl.grid(row=0, column=0, pady=2)
        sample_rate_ent.grid(row=0, column=1, pady=2)

        donothing_2_1 = tk.Frame(self.ex_sql_export, height=8, width=640)
        donothing_2_1.grid()
        donothing_2_2 = tk.Frame(self.ex_sql_export, bg='#555', height=1, width=640)
        donothing_2_2.grid()
        donothing_2_3 = tk.Frame(self.ex_sql_export, height=8, width=640)
        donothing_2_3.grid()

        ex_btn_frame = tk.Frame(self.ex_sql_export)
        ex_btn_frame.grid(pady=2)
        sql_path_btn = tk.Button(ex_btn_frame, text='选择Sqlite', command=self.sql_path_btn_callback)
        sql_path_btn.grid(row=0, column=1, padx=2, pady=2)
        export_commit_btn = tk.Button(ex_btn_frame, text='启动导入', command=self.export_commit_btn_callback)
        export_commit_btn.grid(row=0, column=2, padx=2, pady=2)

        donothing_3_3 = tk.Frame(self.ex_sql_export, height=8, width=480)
        donothing_3_3.grid()

    def folder_to_sqlite_callback(self):
        self.tl_sql_export = tk.Toplevel()

        img_path_lbl_frame = tk.Frame(self.tl_sql_export)
        img_path_lbl_frame.grid(pady=2)
        img_path_lb0 = tk.Label(img_path_lbl_frame, text='图像文件夹路径：')
        img_path_lbl = tk.Label(img_path_lbl_frame, textvariable=self.img_path_val)
        img_path_lb0.grid(row=0, column=0, padx=2)
        img_path_lbl.grid(row=0, column=1, padx=2)
        sql_path_lbl_frame = tk.Frame(self.tl_sql_export)
        sql_path_lbl_frame.grid(pady=2)
        sql_path_lb0 = tk.Label(sql_path_lbl_frame, text='Sqlite文件夹路径：')
        sql_path_lbl = tk.Label(sql_path_lbl_frame, textvariable=self.sql_path_val)
        sql_path_lb0.grid(row=0, column=0, pady=2)
        sql_path_lbl.grid(row=0, column=1, pady=2)

        donothing_1_1 = tk.Frame(self.tl_sql_export, height=8, width=640)
        donothing_1_1.grid()
        donothing_1_2 = tk.Frame(self.tl_sql_export, bg='#555', height=1, width=640)
        donothing_1_2.grid()
        donothing_1_3 = tk.Frame(self.tl_sql_export, height=8, width=640)
        donothing_1_3.grid()

        sql_table_frame = tk.Frame(self.tl_sql_export)
        sql_table_frame.grid(pady=2)
        sql_table_lbl = tk.Label(sql_table_frame, text='Sqlite表名')
        sql_table_ent = tk.Entry(sql_table_frame, textvariable=self.sql_table_val)
        sql_table_lbl.grid(row=0, column=0, padx=2)
        sql_table_ent.grid(row=0, column=1, padx=2)

        sample_equipnum_frame = tk.Frame(self.tl_sql_export)
        sample_equipnum_frame.grid(pady=2)
        sample_equipnum_lbl = tk.Label(sample_equipnum_frame, text='采集设备号')
        sample_equipnum_ent = tk.Entry(sample_equipnum_frame, textvariable=self.sample_equipnum_val)
        sample_equipnum_lbl.grid(row=0, column=0, pady=2)
        sample_equipnum_ent.grid(row=0, column=1, pady=2)

        sample_rate_frame = tk.Frame(self.tl_sql_export)
        sample_rate_frame.grid(pady=2)
        sample_rate_lbl = tk.Label(sample_rate_frame, text='采集速度')
        sample_rate_ent = tk.Entry(sample_rate_frame, textvariable=self.sample_rate_val)
        sample_rate_lbl.grid(row=0, column=0, pady=2)
        sample_rate_ent.grid(row=0, column=1, pady=2)

        donothing_2_1 = tk.Frame(self.tl_sql_export, height=8, width=640)
        donothing_2_1.grid()
        donothing_2_2 = tk.Frame(self.tl_sql_export, bg='#555', height=1, width=640)
        donothing_2_2.grid()
        donothing_2_3 = tk.Frame(self.tl_sql_export, height=8, width=640)
        donothing_2_3.grid()

        tl_btn_frame = tk.Frame(self.tl_sql_export)
        tl_btn_frame.grid(pady=2)
        img_path_btn = tk.Button(tl_btn_frame, text='选择文件夹', command=self.img_path_btn_callback)
        img_path_btn.grid(row=0, column=0, padx=2, pady=2)
        sql_path_btn = tk.Button(tl_btn_frame, text='选择Sqlite', command=self.sql_path_btn_callback)
        sql_path_btn.grid(row=0, column=1, padx=2, pady=2)
        export_commit_btn = tk.Button(tl_btn_frame, text='启动导入', command=self.folder_to_sqlite_commit_btn_callback)
        export_commit_btn.grid(row=0, column=2, padx=2, pady=2)

        donothing_3_3 = tk.Frame(self.tl_sql_export, height=8, width=480)
        donothing_3_3.grid()

    def img_path_btn_callback(self):
        img_path = tkFileDialog.askdirectory()
        self.img_path_val.set(img_path)

    def sql_path_btn_callback(self):
        sql_path = tkFileDialog.askopenfilename(defaultextension='.db', filetypes=[('Sqlite数据库文件','*.db')])
        self.sql_path_val.set(sql_path)

    def export_commit_btn_callback(self):
        if self.sql_table_val.get()!='zhdl_map':
            tkMessageBox.showerror('错误', '目前只支持数据表名：zhdl_map')
            return
        if self.sample_equipnum_val=='':
            tkMessageBox.showerror('错误', '请输入有效设备名')
            return
        if self.sample_rate_val>0. and self.sample_rate_val<5.:
            tkMessageBox.showerror('错误', '采集速度必须处于有效范围内 ( 0~5m/s ) ')
            return
        try:
            conn = sqlite3.connect(self.sql_path_val.get())
            curs = conn.cursor()
            cnt = 0
            for k in self.img_dict.keys():
                try:
                    img = self.img_dict[k].image
                    print np.array(img).shape
                    curs.execute('insert into zhdl_map values (?,?,?,?,?,?)',(
                        k,
                        self.img_dict[k].ox,
                        -1*self.img_dict[k].oy,
                        self.img_dict[k].theta,
                        None,
                        buffer(img.tobytes()),
                        ))
                    cnt += 1
                except Exception as e:
                    pass
            conn.commit()
            conn.close()
            tkMessageBox.showinfo('提示', '导入数据库成功，共导入 %s 张图像'%cnt)
        except Exception as e:
            traceback.print_exc()
            tkMessageBox.showerror('错误', '导入数据库失败\n%s'%str(e))
            return            

    def folder_to_sqlite_commit_btn_callback(self):
        valid_flag = True
        if self.sql_table_val.get()!='zhdl_map':
            tkMessageBox.showerror('错误', '目前只支持数据表名：zhdl_map')
            return
        if self.sample_equipnum_val=='':
            tkMessageBox.showerror('错误', '请输入有效设备名')
            return
        if self.sample_rate_val>0. and self.sample_rate_val<5.:
            tkMessageBox.showerror('错误', '采集速度必须处于有效范围内 ( 0~5m/s ) ')
            return
        try:
            self.reinitialize(load_source='folder')
            try:
                conn = sqlite3.connect(self.sql_path_val.get())
                curs = conn.cursor()
                for k in self.img_dict.keys():
                    img = self.img_dict[k].image
                    curs.execute('insert into zhdl_map values (?,?,?,?,?,?)',(
                        k,
                        self.img_dict[k].ox,
                        -1*self.img_dict[k].oy,
                        self.img_dict[k].theta,
                        None,
                        buffer(img.resize((320,320)).tobytes()),
                    ))
                conn.commit()
                conn.close()
                tkMessageBox.showinfo('提示', '导入数据库成功')
            except Exception as e:
                traceback.print_exc()
                tkMessageBox.showerror('错误', '导入数据库失败\n%s'%str(e))
                return   
        except Exception as e:
            traceback.print_exc()
            tkMessageBox.showerror('错误', '图片读取失败\n%s'%str(e))
            return

    def import_labeled_set_callback(self):
        self.using_db = False
        self.loading_disable()
        if not self.enter_label_mod:
            self.reinitialize_params()
            self.enter_label_mod = True
        img_path = tkFileDialog.askdirectory()
        fs = []
        # TODO：添加根据固定文件名格式判断图像是否为有效地图文件
        for _,_,tfs in os.walk(img_path):
            for f in tfs:
                if f.lower().endswith('.bmp'):
                    fs.append(f)
        cnt = 0
        self.progress['maximum'] = len(fs)
        self.progress['value'] = 0
        self.progress_msg.set('  正在载入')
        try:
            for f in fs:
                try:
                    img = Image.open(img_path+'/'+f).resize((320,320))
                    idx, curx, cury, theta = int(f.split('_')[0]), float(f.split('_')[1]), float(f.split('_')[2]), float(f.split('_')[3].split('.')[0])
                    if idx in self.img_dict.keys():
                        continue
                    imgobj = Imgobj(idx=idx,
                                    image=img,
                                    x=curx,
                                    y=-1*cury,
                                    theta=theta)
                    imgobj.labeled = True
                    imgobj.x = (imgobj.x - self.total_map_shift[0]) * self.scale + 640
                    imgobj.y = (imgobj.y - self.total_map_shift[1]) * self.scale + 480
                    self.img_dict[idx] = imgobj
                    self.maxx = max(self.maxx, curx)
                    self.maxy = max(self.maxy, cury)
                    cnt += 1
                    self.progress['value'] = cnt
                    self.progress.update()
                except:
                    pass
            if cnt == 0:
                tkMessageBox.showinfo('提示', '当前文件夹无有效地图数据文件')
                return
            self.progress.stop()
            self.progress_msg.set('  载入完成')
            tkMessageBox.showinfo('提示', '标注集读取成功，新增 %s 张样本'%cnt)
            self.grid_load()
            self.calc_visible(False)
        except Exception as e:
            pass
        finally:
            self.loading_enable()

    def import_raw_set_callback(self):
        self.using_db = False
        self.loading_disable()
        if not self.enter_label_mod:
            self.reinitialize_params()
            self.enter_label_mod = True
        img_path = tkFileDialog.askdirectory()
        fs = []
        # TODO：添加根据固定文件名格式判断图像是否为有效地图文件
        for _,_,tfs in os.walk(img_path):
            for f in tfs:
                if f.lower().endswith('.bmp'):
                    fs.append(f)
        cnt = 0
        self.progress['maximum'] = len(fs)
        self.progress['value'] = 0
        self.progress_msg.set('  正在载入')
        try:
            for f in fs:
                try:
                    # img = Image.open(img_path+'/'+f).resize((self.imgsize,self.imgsize))
                    img = Image.open(img_path+'/'+f).resize((320,320))
                    idx, curx, cury, theta = int(f.split('_')[0]), float(f.split('_')[1]), float(f.split('_')[2]), float(f.split('_')[3].split('.')[0])
                    if idx in self.img_dict.keys():
                        continue
                    imgobj = Imgobj(idx=idx,
                                    image=img,
                                    x=curx,
                                    y=-1*cury,
                                    theta=theta)
                    imgobj.labeled = False
                    imgobj.x = (imgobj.x - self.total_map_shift[0]) * self.scale + 640
                    imgobj.y = (imgobj.y - self.total_map_shift[1]) * self.scale + 480
                    self.img_dict[idx] = imgobj
                    self.maxx = max(self.maxx, curx)
                    self.maxy = max(self.maxy, cury)
                    cnt += 1
                    self.progress['value'] = cnt
                    self.progress.update()
                except:
                    pass
            if cnt == 0:
                tkMessageBox.showinfo('提示', '当前文件夹无有效地图数据文件')
                return
            self.progress.stop()
            self.progress_msg.set('  载入完成')         
            tkMessageBox.showinfo('提示', '未标注集读取成功，新增 %s 张样本'%cnt)
            self.grid_load()
            self.calc_visible(False)
        except Exception as e:
            pass
        finally:
            self.loading_enable()

    def fix_labeled_set_callback(self):
        # self.enter_label_mod_lock = not self.enter_label_mod_lock
        for k in self.img_dict.keys():
            if self.img_dict[k].labeled:
                self.img_dict[k].fixed = True
                self.img_dict[k].enter_boundingbox(2)

    def labeled_irredundancy_callback(self):
        tkMessageBox.showinfo('提示', 'function not applied yet')

    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 图像采集界面 ++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def open_socket_callback(self):
        if self.sk_top_alive == True:
            tkMessageBox.showwarning('错误', '已有打开的采集窗口')
            return
        if not self.sock_open_flag:
            tkMessageBox.showwarning('错误', '未检测到摄像头连接')
            return

        self.sk_top = tk.Toplevel()
        self.sk_left = tk.Frame(self.sk_top)
        self.sk_right = tk.Frame(self.sk_top)
        self.sk_left.grid(row=0, column=0, padx=2, pady=2)
        self.sk_right.grid(row=0, column=1, padx=2, pady=2)
        self.sk_top.resizable(width=False, height=False)

        # TODO: 添加双击listbox中item，显示对应的图像
        self.sk_listbox_val = tk.StringVar()
        self.sk_listbox_val.set('')
        self.sk_listbox_lbl = tk.Label(self.sk_left, textvariable=self.sk_listbox_val)
        self.sk_listbox_lbl.grid(pady=2)

        self.sk_listbox_frame = tk.Frame(self.sk_left, height=480)
        self.sk_listbox_frame.grid(pady=2)
        self.sk_listbox = tk.Listbox(self.sk_listbox_frame, height=28)
        self.sk_listbox.pack(side='left', fill='y')
        self.sk_left_scrollbar = tk.Scrollbar(self.sk_listbox_frame, orient=tk.VERTICAL)
        self.sk_left_scrollbar.config(command=self.sk_listbox.yview)
        self.sk_left_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.sk_listbox.config(yscrollcommand=self.sk_left_scrollbar.set)

        self.sk_canvas = tk.Canvas(self.sk_right, width=640, height=480)
        self.sk_canvas.sk_canvas_image = ImageTk.PhotoImage(Image.fromarray(np.zeros((480, 640), dtype='uint8')).resize((640, 480)))
        self.sk_canvas_panel = self.sk_canvas.create_image(0, 0, image=self.sk_canvas.sk_canvas_image, anchor='nw', tags=('sk_img'))
        self.sk_canvas.grid(pady=2)
        self.sk_frame = tk.Frame(self.sk_right)
        self.sk_frame.grid(pady=2)

        self.sk_canvas.create_line(0, 240, 640, 240, fill='#9a9a66', width=1, dash=(5,5), tags='groundtruth')
        self.sk_canvas.create_line(320, 0, 320, 480, fill='#9a9a66', width=1, dash=(5,5), tags='groundtruth')
        self.sk_canvas.tag_raise('groundtruth')

        self.sk_x_lbl = tk.Label(self.sk_frame, text='x: ')
        self.sk_x_lbl.grid(row=0, column=0, padx=2)
        self.sk_x_val = tk.DoubleVar()
        self.sk_x_val.set(0.)
        self.sk_x_ent = tk.Entry(self.sk_frame, textvariable=self.sk_x_val)
        self.sk_x_ent.grid(row=0, column=1, padx=2)

        self.sk_y_lbl = tk.Label(self.sk_frame, text='y: ')
        self.sk_y_lbl.grid(row=0, column=2, padx=2)
        self.sk_y_val = tk.DoubleVar()
        self.sk_y_val.set(0.)
        self.sk_y_ent = tk.Entry(self.sk_frame, textvariable=self.sk_y_val)
        self.sk_y_ent.grid(row=0, column=3, padx=2)

        self.sk_t_lbl = tk.Label(self.sk_frame, text='θ: ')
        self.sk_t_lbl.grid(row=0, column=4, padx=2)
        self.sk_t_val = tk.DoubleVar()
        self.sk_t_val.set(0.)
        self.sk_t_ent = tk.Entry(self.sk_frame, textvariable=self.sk_t_val)
        self.sk_t_ent.grid(row=0, column=5, padx=2)

        self.sk_commit_btn = tk.Button(self.sk_frame, text='导入图像', command=self.sk_commit_btn_callback)
        self.sk_commit_btn.grid(row=0, column=6, padx=2)

        for _,_,fs in os.walk(self.sk_path_val.get()):
            sk_max_id = 0
            for f in fs:
                tid, tx, ty, tt = f[:-4].split('_')
                self.sk_listbox.insert(tk.END, 'id:%s  x:%s  y:%s  theta:%s'%(tid, tx, ty, tt))
                sk_max_id = max(int(tid), sk_max_id)
            self.sk_listbox_val.set('当前已采集 %s 张图像'%len(fs))
            self.sk_image_idx = sk_max_id + 1
            break

        self.sk_top_alive = True
        self.sk_top.protocol('WM_DELETE_WINDOW', self.on_sk_closing)
        self.sk_canvas_refresh()

    def on_sk_closing(self):
        self.sk_top_alive = False
        self.sk_top.destroy()

    def sk_focus_validate(self):
        self.sk_control_focus = not self.sk_control_focus

    def sk_canvas_refresh(self):
        try:
            self.sk_canvas.sk_canvas_image = ImageTk.PhotoImage(self.sk_image)
            self.sk_canvas.itemconfig(self.sk_canvas_panel, image=self.sk_canvas.sk_canvas_image)
            self.sk_top.after(50, self.sk_canvas_refresh)
        except Exception as e:
            print 'sk_canvas_refresh | '+str(e)

    def socket_loop(self):
        self.sock = sk.socket(sk.AF_INET, sk.SOCK_DGRAM)
        self.sock.bind(('192.168.1.11', 20014))
        self.sock_open_flag = True

        self.sk_frame_id = 0
        self.sk_frame_id_curr = 0
        self.sk_line_idx = 0
        self.sk_line_idx_prev = 0
        self.n_add = 0

        self.bmp = ''
        cnt = 0
        while True:
            # if not self.sk_top_alive:
            #     continue
            # if not self.sk_control_focus:
            #     continue
            try:
                data, _ = self.sock.recvfrom(672)
                if len(data) != 672:
                    continue
                self.sk_frame_id = ord(data[6]) * 256 + ord(data[7])
                self.sk_line_idx = ord(data[8]) * 256 + ord(data[9])
                if self.sk_line_idx == 0:
                    self.bmp = ''
                self.bmp += data[32:]
                if self.sk_line_idx==479 and len(self.bmp)==480*640:
                    self.sk_frame_id_curr = self.sk_frame_id
                    arr = np.fromstring(self.bmp, dtype='uint8').reshape((480,640))
                    self.sk_image = Image.fromarray(arr)

                    # try:
                    #     self.sk_canvas.sk_canvas_image = ImageTk.PhotoImage(self.sk_image)
                    #     self.sk_canvas.itemconfig(self.sk_canvas_panel, image=self.sk_canvas.sk_canvas_image)
                    # except Exception as e:
                    #     print 'sk_canvas '+str(e)

                    self.bmp = ''
            except Exception as e:
                self.bmp = ''
                print 'sock_loop inner '+str(e)
                # traceback.print_exc()

    def sk_commit_btn_callback(self):
        if self.sk_image == None:
            tkMessageBox.showwarning('错误', '暂无图像')
            return
        if self.sk_path_val.get()=='' or not os.path.exists(self.sk_path_val.get()):
            tkMessageBox.showerror('错误', '请在参数设置中正确设置采样保存路径')
            return
        try:
            curx = float(self.sk_x_val.get())
            cury = float(self.sk_y_val.get())
            curt = float(self.sk_t_val.get())
            filename = '%s_%s_%s_%s.bmp'%(self.sk_image_idx, curx, cury, curt)
            self.sk_image.save(os.path.join(self.sk_path_val.get(), filename))
            self.sk_image_idx += 1
            for _,_, fs in os.walk(self.sk_path_val.get()):
                self.sk_image_idx = len(fs)
                self.sk_listbox_val.set('当前已采集 %s 张图像'%len(fs))
                self.sk_listbox.delete(0,tk.END)
                for f in fs:
                    tid, tx, ty, tt = f[:-4].split('_')
                    self.sk_listbox.insert(tk.END, 'id:%s  x:%s  y:%s  theta:%s'%(tid, tx, ty, tt))
        except Exception as e:
            print 'sk_commit_btn_callback '+str(e)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 全局图像界面 ++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def show_global_map_callback(self):
        self.global_view_flag = True
        self.global_canvas_width = 2048
        self.global_canvas_height = float(self.global_canvas_width)*(self.maxy/float(self.maxx))
        global_img = np.zeros((int(self.global_canvas_width*self.mil2pix_ratio),int(self.global_canvas_height*self.mil2pix_ratio)))
        self.global_canvas_scale = float(self.global_canvas_width)*self.mil2pix_ratio/(self.maxx+1000)
        err_cnt = 0
        for k in self.img_dict.keys():
            try:
                imgobj = self.img_dict[k]
                x, y = int(self.global_canvas_scale*imgobj.ox), int(self.global_canvas_scale*imgobj.oy)
                w, h = int(imgobj.image.size[0]*self.global_canvas_scale*self.mil2pix_ratio), int(imgobj.image.size[1]*self.global_canvas_scale*self.mil2pix_ratio)
                imgarr = np.array(imgobj.image.resize((w, h)))
                global_img[x:x+w, y:y+h] = imgarr
            except:
                err_cnt += 1
        print 'total err when constructing global img: %s'%err_cnt
        global_arr = global_img.transpose().astype('uint8')

        global_img = Image.fromarray(global_arr).resize((self.global_canvas_width, int(self.global_canvas_height)))
        global_img.save('map.bmp')

        self.global_view_toplevel = tk.Toplevel(width=1024, height=int(self.global_canvas_height//2))
        self.global_view_toplevel.bind('<Button-1>', self.global_view_change_focus)
        self.global_view_toplevel.title('全图预览')
        self.global_view_toplevel.resizable(width=False, height=False)
        self.global_view_topframe = tk.Frame(self.global_view_toplevel)
        self.global_view_topframe.grid()
        self.global_viewmap_canvas = tk.Canvas(self.global_view_topframe, width=1024, height=int(self.global_canvas_height//2))
        self.global_viewmap_canvas.img = ImageTk.PhotoImage(global_img.resize((1024,int(self.global_canvas_height//2))))
        self.global_viewmap_canvas.create_image(1024//2, int(self.global_canvas_height//4), image=self.global_viewmap_canvas.img)
        self.global_viewmap_canvas.grid()
        self.global_viewmap_canvas.bind('<Button-1>', self.global_view_change_focus)
        self.global_view_toplevel.protocol('WM_DELETE_WINDOW', self.on_global_closing)

    def global_image_gen(self):
        self.global_canvas_width = 2048
        self.global_canvas_height = float(self.global_canvas_width)*(self.maxy/float(self.maxx))
        global_img = np.zeros((int(self.global_canvas_width*self.mil2pix_ratio),int(self.global_canvas_height*self.mil2pix_ratio)))
        self.global_canvas_scale = float(self.global_canvas_width)*self.mil2pix_ratio/(self.maxx+1000)
        err_cnt = 0
        for k in self.img_dict.keys():
            try:
                imgobj = self.img_dict[k]
                x, y = int(self.global_canvas_scale*imgobj.ox), int(self.global_canvas_scale*imgobj.oy)
                w, h = int(imgobj.image.size[0]*self.global_canvas_scale*self.mil2pix_ratio), int(imgobj.image.size[1]*self.global_canvas_scale*self.mil2pix_ratio)
                imgarr = np.array(imgobj.image.resize((w, h)))
                global_img[x:x+w, y:y+h] = imgarr
            except:
                err_cnt += 1
        print 'total err when constructing global img: %s'%err_cnt
        global_arr = global_img.transpose().astype('uint8')
        global_img = Image.fromarray(global_arr).resize((self.global_canvas_width, int(self.global_canvas_height)))
        self.global_viewmap_canvas.img = ImageTk.PhotoImage(global_img.resize((1024,int(self.global_canvas_height//2))))
        self.global_viewmap_canvas.itemconfig(self.global_view_topframe, image=self.global_viewmap_canvas.img)

    def on_global_closing(self):
        self.global_view_flag = False
        self.global_view_toplevel.destroy()

    def global_view_change_focus(self, event):
        x, y = self.global_viewmap_canvas.canvasx(event.x)/float(self.global_canvas_width//2)*(self.maxx+1000)-self.scale*self.imgsize, (1.-self.global_viewmap_canvas.canvasy(event.y)/float(self.global_canvas_height//2))*(self.maxy+1000)+self.scale*self.imgsize
        print 'total view focus: %s | %s, %s |%s'%(x, self.maxx, y, self.maxy)
        print self.imgsize
        self.change_focus(x, y)

    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 后台工具方法 ++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def do_nothing(self, event):
        pass

    def loading_disable(self):
        self.root.config(cursor='wait')
        self.canvas.config(state=tk.DISABLED)
        self.canvas.bind('<ButtonPress-1>', self.do_nothing)
        self.canvas.bind('<ButtonRelease-1>', self.do_nothing)
        self.canvas.bind('<B1-Motion>', self.do_nothing)
        self.canvas.bind('<ButtonPress-2>', self.do_nothing)
        self.canvas.bind('<ButtonRelease-2>', self.do_nothing)
        self.canvas.bind('<B2-Motion>', self.do_nothing)
        self.canvas.bind('<ButtonPress-3>', self.do_nothing)
        self.canvas.bind('<ButtonRelease-3>', self.do_nothing)
        self.canvas.bind('<B3-Motion>', self.do_nothing)
        self.canvas.bind_all('<MouseWheel>', self.do_nothing)
        self.canvas.bind('<Button-4>', self.do_nothing)
        self.canvas.bind('<Button-5>', self.do_nothing)
        self.canvas.bind('<Motion>', self.do_nothing)
        self.canvas.bind('<Double-Button-1>', self.do_nothing)
        self.edit_mod_btn.config(state=tk.DISABLED)

    def loading_enable(self):
        self.root.config(cursor='')
        self.canvas.config(state=tk.NORMAL)
        self.canvas.bind('<ButtonPress-1>', self.start_drag_item)
        self.canvas.bind('<ButtonRelease-1>', self.stop_drag_item)
        self.canvas.bind('<B1-Motion>', self.drag_item)
        self.canvas.bind('<ButtonPress-2>', self.start_drag_canvas)
        self.canvas.bind('<ButtonRelease-2>', self.stop_drag_canvas)
        self.canvas.bind('<B2-Motion>', self.drag_canvas)
        self.canvas.bind('<ButtonPress-3>', self.start_rotate)
        self.canvas.bind('<ButtonRelease-3>', self.stop_rotate)
        self.canvas.bind('<B3-Motion>', self.rotate)
        self.canvas.bind_all('<MouseWheel>', self.zoomer)
        self.canvas.bind('<Button-4>', self.zoomer_up)
        self.canvas.bind('<Button-5>', self.zoomer_dw)
        self.canvas.bind('<Motion>', self.mouse_pos_callback)
        self.canvas.bind('<Double-Button-1>', self.mouse_db_click_callback)
        self.edit_mod_btn.config(state=tk.NORMAL)

    def reinitialize_params(self):
        self.dragged_item = tk.ALL
        self.current_coords = 0, 0
        self.current_angle = 0.
        self.total_map_shift = (640, 480)
        self.width = 1280
        self.height = 960
        self.scale = 1.0
        self.img_dict = {}
        self.grid_horz = []
        self.grid_vert = []
        self.last_canvx, self.last_canvy = 0, 0
        self.window = [(0, 1280), (0, 960)]
        self.factor = 1.1
        self.maxx, self.maxy = 0, 0
        self.mutex = False
        self.mutex_unlock_count = 0
        self.edit_mod_flag = False
        self.edit_history = []
        self.x_axis_gap_val = 1000
        self.y_axis_gap_val = 1000
        self.show_grid_flag = True
        self.edit_delete_flag = False
        self.dragging_img_set = set()
        self.modify_img_dict = {}
        self.edit_history_listbox.delete(0, tk.END)
        self.zoom_scale.set('缩放系数：1.0')
        self.imgsize = int(320*self.mil2pix_ratio)
        self.coord_central = 160*self.mil2pix_ratio, 160*self.mil2pix_ratio

        # new add
        self.selected_node_id_int = None
        self.selected_node_canvas_id_int = None
        self.img_insert = None
        self.enter_label_mod = False
        self.using_db = True
        self.curr_img_rotate = 0.0
        
        self.sk_top_alive = False
        self.sk_control_focus = False
        self.sk_image = None
        self.sk_image_idx = 0
        self.sk_image_panel = None

    def reinitialize(self, load_source='db'):
        self.reinitialize_params()

        if load_source=='db':
            self.img_load_db()
        else:
            self.img_load_folder()
        self.init_binding()
        self.grid_load()
        self.calc_visible(False)
        
    def img_load_folder(self):
        self.using_db = False
        self.enter_label_mod = False
        self.img_dict = {}
        for _,_,fs in os.walk(self.img_path_val.get()):
            img_cnt = 0
            self.progress['value'] = 0
            self.progress['maximum'] = len(fs)
            self.progress_msg.set('  正在载入')
            for c, f in enumerate(fs):
                # img = Image.open(self.img_path_val.get()+'/'+f).resize((self.imgsize,self.imgsize))
                img = Image.open(self.img_path_val.get()+'/'+f).resize((320,320))
                idx, curx, cury, theta = int(f.split('_')[0]), float(f.split('_')[1]), float(f.split('_')[2]), float(f.split('_')[3].split('.')[0])
                imgobj = Imgobj(idx=idx,
                                image=img,
                                x=curx,
                                y=-1*cury,
                                theta=theta)
                self.img_dict[idx] = imgobj
                self.maxx = max(self.maxx, curx)
                self.maxy = max(self.maxy, cury)
                img_cnt += 1
                print img_cnt
                self.progress['value'] = img_cnt
                self.progress.update()
            print 'current map read finished with sample number %s.'%img_cnt
            self.progress_msg.set('  载入完成')
            self.progress.stop()
            break

    def img_load_db(self):
        self.using_db = True
        self.enter_label_mod = False
        self.loading_disable()
        try:
            conn = sqlite3.connect(self.db_path)
            curs = conn.cursor()
            cnt = curs.execute('select count(id) from zhdl_map').next()[0]
            self.progress['value'] = 0
            self.progress['maximum'] = cnt
            self.progress_msg.set('  正在载入')
            res = curs.execute('select id, x, y, heading, processed_image, raw_image from zhdl_map')
            img_cnt = 0
            while True:
                try:
                    data = res.next()
                    # TODO: 添加选择分支
                    # 当data[5]的格式为lz4时使用解码器解码
                    curr_img = Image.fromarray(np.array(data[5]).reshape((320, 320)).astype('uint8'))
                    imgobj = Imgobj(idx=data[0],
                                    image=curr_img,
                                    x=data[1],
                                    y=-1*data[2],
                                    theta=data[3])
                    self.img_dict[data[0]] = imgobj
                    self.maxx = max(self.maxx, data[1])
                    self.maxy = max(self.maxy, data[2])
                    img_cnt += 1
                    self.progress['value'] = img_cnt
                    self.progress.update()
                except Exception as e:
                    print 'current map load finished with sample number %s.'%img_cnt
                    break
            self.progress_msg.set('  载入完成')
            self.progress.stop()
            conn.close()
        except Exception as e:
            print e
            tkMessageBox.showinfo('提示', '请在选项中正确配置数据库文件地址')
            res = iter([])
        finally:
            self.loading_enable()

    def grid_load(self):
        self.grid_horz = []
        self.grid_vert = []
        cx, cy = self.coord_central
        for i in range(2*int(self.maxx//(self.x_axis_gap_val))):
            self.grid_horz.append((cx+(i*self.x_axis_gap_val)*self.scale,
                                -1e7,
                                cx+(i*self.x_axis_gap_val)*self.scale,
                                (1e7)*self.scale))
        for j in range(2*int(self.maxy//(self.y_axis_gap_val))):
            self.grid_vert.append((-1e7,
                                cy-1*(j*self.y_axis_gap_val)*self.scale,
                                (1e7)*self.scale,
                                cy-1*(j*self.y_axis_gap_val)*self.scale))
        for i in range(2*int(self.maxx//(self.x_axis_gap_val))):
            self.grid_horz.append((cx-(i*self.x_axis_gap_val)*self.scale,
                                -1e7,
                                cx-(i*self.x_axis_gap_val)*self.scale,
                                (1e7)*self.scale))
        for j in range(2*int(self.maxy//(self.y_axis_gap_val))):
            self.grid_vert.append((-1e7,
                                cy+1*(j*self.y_axis_gap_val)*self.scale,
                                (1e7)*self.scale,
                                cy+1*(j*self.y_axis_gap_val)*self.scale))
    def img_edit_2_db(self):
        pass

    def change_focus(self, x, y):
        dx = -1*(x-self.total_map_shift[0])*self.scale
        dy = (y+self.total_map_shift[1])*self.scale
        print str((dx, dy))
        self.total_map_shift = (x, -1*y)
        for k in self.img_dict.keys():
            self.img_dict[k].x += dx
            self.img_dict[k].y += dy
        for i in range(len(self.grid_vert)):
            self.grid_vert[i] = (self.grid_vert[i][0], self.grid_vert[i][1]+dy, self.grid_vert[i][2], self.grid_vert[i][3]+dy)
        for j in range(len(self.grid_horz)):
            self.grid_horz[j] = (self.grid_horz[j][0]+dx, self.grid_horz[j][1], self.grid_horz[j][2]+dx, self.grid_horz[j][3])
        self.calc_visible(False)

    def export_edit_history(self):
        export_file_name = '-'.join(str(datetime.datetime.now()).split(' ')).replace(':', '-')+'.txt'
        if not os.path.exists('log'):
            os.mkdir('log')
        file_open_mod = 'w'
        if os.path.exists('log/'+export_file_name):
            file_open_mod = 'a'
        else:
            file_open_mod = 'w'
        with open('log/'+export_file_name, file_open_mod) as logfile:
            for line in self.edit_history:
                logfile.write(line)

    def calc_visible(self, is_scale):
        print 'total shift: %s,%s'%(self.total_map_shift)
        show_cnt = 0
        self.canvas.delete(tk.ALL)
        self.tk_dict = {}
        # ----------------------------------------过滤----------------------------------------
        for k in sorted(self.img_dict.keys()):
            if self.img_dict[k].x+self.imgsize*self.scale>self.window[0][0] and self.img_dict[k].x<self.window[0][1] and self.img_dict[k].y+self.imgsize*self.scale>self.window[1][0] and self.img_dict[k].y<self.window[1][1]:
                show_cnt += 1
                # 采样
                if self.scale<0.2 and self.scale>0.1 and show_cnt%2==0:
                    continue
                if self.scale<0.1 and show_cnt%3!=0:
                    continue
                size = int(self.img_dict[k].image.size[0]*self.scale*self.mil2pix_ratio)
                # 判断是否有box
                if self.img_dict[k].boxed:
                    curr_img = self.img_dict[k].image_boxed
                else:
                    curr_img = self.img_dict[k].image
                if self.scale>=0.75:
                    swap_arr = np.array(curr_img.convert('RGBA'))
                    swap_arr[:,:,3] = (swap_arr[:,:,0]+swap_arr[:,:,1]+swap_arr[:,:,2]!=0)*swap_arr[:,:,3]
                    swap_img = Image.fromarray(swap_arr.astype('uint8')).rotate(self.img_dict[k].rot+self.img_dict[k].theta, expand=True)
                    swap_siz = int(swap_img.size[0]*self.scale*self.mil2pix_ratio)
                    self.tk_dict[k] = ImageTk.PhotoImage(swap_img.resize((swap_siz, swap_siz), resample=Image.LANCZOS))
                else:
                    if self.img_dict[k].boxed:
                        self.tk_dict[k] = ImageTk.PhotoImage(curr_img.resize((size, size), resample=Image.LANCZOS))
                    else:
                        self.tk_dict[k] = ImageTk.PhotoImage(curr_img.resize((size, size)))
            else:
                pass
        # ----------------------------------------绘制----------------------------------------
        
        for k in sorted(self.tk_dict.keys()):
            if self.scale>=0.75:
                shift = self.tk_dict[k].width()//2
            else:
                shift = self.imgsize*self.scale//2
            if k == self.selected_node_id_int:
                self.canvas.create_image(self.img_dict[k].x-shift, self.img_dict[k].y-shift, image=self.tk_dict[k], anchor='nw', tags=('img', k, 'selected'))
            else:
                self.canvas.create_image(self.img_dict[k].x-shift, self.img_dict[k].y-shift, image=self.tk_dict[k], anchor='nw', tags=('img', k))
        shift = self.imgsize*self.scale//2
        if self.show_grid_flag:
            for e in self.grid_vert: 
                self.canvas.create_line(e[0]-shift, e[1]-shift, e[2]-shift, e[3]-shift, fill='purple', width=self.grid_line_width, tags='coordline')
            for e in self.grid_horz:
                self.canvas.create_line(e[0]-shift, e[1]-shift, e[2]-shift, e[3]-shift, fill='purple', width=self.grid_line_width, tags='coordline')
            self.canvas.tag_raise('coordline')
        self.canvas.create_line(0, 480, 1280, 480, fill='blue', tags='baseline')
        self.canvas.create_line(640, 0, 640, 960, fill='blue', tags='baseline')
        self.canvas.tag_raise('baseline')

    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 初始化方法 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def init_binding(self):
        self.canvas.bind('<ButtonPress-1>', self.start_drag_item)
        self.canvas.bind('<ButtonRelease-1>', self.stop_drag_item)
        self.canvas.bind('<B1-Motion>', self.drag_item)
        self.canvas.bind('<ButtonPress-2>', self.start_drag_canvas)
        self.canvas.bind('<ButtonRelease-2>', self.stop_drag_canvas)
        self.canvas.bind('<B2-Motion>', self.drag_canvas)
        self.canvas.bind('<ButtonPress-3>', self.start_rotate)
        self.canvas.bind('<ButtonRelease-3>', self.stop_rotate)
        self.canvas.bind('<B3-Motion>', self.rotate)
        self.canvas.bind_all('<MouseWheel>', self.zoomer)
        self.canvas.bind('<Button-4>', self.zoomer_up)
        self.canvas.bind('<Button-5>', self.zoomer_dw)
        self.canvas.bind('<Motion>', self.mouse_pos_callback)
        self.canvas.bind('<Double-Button-1>', self.mouse_db_click_callback)
        self.edit_history_listbox.bind('<Button-1>', self.edit_single_click_callback)

    def init_mainpage(self):
        self.root = tk.Tk()
        self.root.iconbitmap(default= os.path.join(os.getcwd(), 'quick.ico'))
        # self.imgicon = ImageTk.PhotoImage(file=os.path.join(os.getcwd(),'quick.ico'))
        # self.root.tk.call('wm', 'iconphoto', self.root._w, self.imgicon)
        self.root.title('Quicktron Texture Location Map Dispalyer')
        self.root.geometry('{}x{}'.format(1400,960))

        self.control_frame = tk.Frame(self.root, width=120, height=960)
        self.canvas_frame = tk.Frame(self.root, width=1280, height=960)
        self.control_frame.grid(row=0, column=0, sticky='n')
        self.canvas_frame.grid(row=0, column=1, sticky='e')

        # ------------------------------------------ 地图绘板 ------------------------------------------

        self.canvas = tk.Canvas(self.canvas_frame, width=self.width, height=self.height, bg='#151515')
        self.canvas.grid(pady=2)

        # ------------------------------------------ 下拉菜单 ------------------------------------------

        self.menubar = tk.Menu(self.root)
        self.dropmenu = tk.Menu(self.menubar, tearoff=0)
        self.dropmenu.add_command(label='参数设置', command=self.preference_callback)
        self.dropmenu.add_separator()
        self.dropmenu.add_command(label='导入一张图像', command=self.import_single_img_callback)
        self.dropmenu.add_command(label='提交导入图像', command=self.import_single_img_commit_callback)
        self.dropmenu.add_separator()
        self.dropmenu.add_command(label='导入标注集合', command=self.import_labeled_set_callback)
        self.dropmenu.add_command(label='导入未标注集合', command=self.import_raw_set_callback)
        self.dropmenu.add_command(label='固定标注集合', command=self.fix_labeled_set_callback)
        self.dropmenu.add_command(label='标注去重', command=self.labeled_irredundancy_callback)
        self.dropmenu.add_separator()
        self.dropmenu.add_command(label='从Sqlite导入', command=self.import_from_sqlite_callback)
        self.dropmenu.add_command(label='往Sqlite导出', command=self.export_to_sqlite_callback)
        self.dropmenu.add_separator()
        self.dropmenu.add_command(label='打开图像采集Socket', command=self.open_socket_callback)
        self.dropmenu.add_command(label='文件夹到出为Sqlite', command=self.folder_to_sqlite_callback)
        self.menubar.add_cascade(label='选项', menu=self.dropmenu)
        # self.menubar.config(background='#f0f0f0')

        # ------------------------------------------ 控制侧栏 ------------------------------------------

        self.donothing_t_3 = tk.Frame(self.control_frame, height=8, width=120)
        self.donothing_t_3.grid()
        self.show_global_map_btn = tk.Button(self.control_frame, text='全局地图', command=self.show_global_map_callback)
        self.show_global_map_btn.grid(sticky='', pady=2)

        self.donothing_0_1 = tk.Frame(self.control_frame, height=8, width=120)
        self.donothing_0_1.grid()
        self.donothing_0_2 = tk.Frame(self.control_frame, bg='#555', height=1, width=220)
        self.donothing_0_2.grid()
        self.donothing_0_3 = tk.Frame(self.control_frame, height=8, width=120)
        self.donothing_0_3.grid()

        self.mouse_pos_variable = tk.StringVar()
        self.mouse_pos_variable.set('鼠标位置：-')
        self.mouse_pos_lbl = tk.Label(self.control_frame, textvariable=self.mouse_pos_variable)
        self.mouse_pos_lbl.grid(sticky='', pady=2)
        self.selected_node_id = tk.StringVar()
        self.selected_node_id.set('选中节点ID：-')
        self.selected_node_pos = tk.StringVar()
        self.selected_node_pos.set('选中节点位置：-')
        self.selected_node_id_lbl = tk.Label(self.control_frame, textvariable=self.selected_node_id)
        self.selected_node_pos_lbl = tk.Label(self.control_frame, textvariable=self.selected_node_pos)
        self.selected_node_id_lbl.grid(sticky='', pady=2)
        self.selected_node_pos_lbl.grid(sticky='', pady=2)

        self.mil2pix_frame = tk.Frame(self.control_frame)
        self.mil2pix_frame.grid(pady=2)
        self.mil2pix = tk.DoubleVar()
        self.mil2pix.set(0.40625)
        self.mil2pix_lbl = tk.Label(self.mil2pix_frame, text='毫米/像素  ')
        self.mil2pix_ent = tk.Entry(self.mil2pix_frame, textvariable=self.mil2pix, width=12)
        self.mil2pix_btn = tk.Button(self.control_frame, text='设定新的毫米/像素', command=self.mil2pix_btn_callback)
        self.mil2pix_lbl.grid(row=0, column=0, sticky='', pady=2)
        self.mil2pix_ent.grid(row=0, column=1, sticky='', pady=2)
        self.mil2pix_btn.grid(sticky='', pady=2)

        self.zoom_scale = tk.StringVar()
        self.zoom_scale.set('缩放系数：1.0')
        self.zoom_scale_lbl = tk.Label(self.control_frame, textvariable=self.zoom_scale)
        self.zoom_scale_lbl.grid(sticky='', pady=2)

        self.donothing_1_1 = tk.Frame(self.control_frame, height=8, width=120)
        self.donothing_1_1.grid()
        self.donothing_1_2 = tk.Frame(self.control_frame, bg='#555', height=1, width=220)
        self.donothing_1_2.grid()
        self.donothing_1_3 = tk.Frame(self.control_frame, height=8, width=120)
        self.donothing_1_3.grid()

        self.x_axis_gap = tk.IntVar()
        self.y_axis_gap = tk.IntVar()
        self.show_grid_str = tk.StringVar()
        self.x_axis_gap.set(1000)
        self.y_axis_gap.set(1000)
        self.show_grid_str.set('已打开网格显示')
        self.x_axis_gap_frm = tk.Frame(self.control_frame)
        self.x_axis_gap_frm.grid()
        self.y_axis_gap_frm = tk.Frame(self.control_frame)
        self.y_axis_gap_frm.grid()
        self.x_axis_gap_lbl = tk.Label(self.x_axis_gap_frm, text='x轴网格间距(mm)  ')
        self.x_axis_gap_ent = tk.Entry(self.x_axis_gap_frm, textvariable=self.x_axis_gap, width=8)
        self.y_axis_gap_lbl = tk.Label(self.y_axis_gap_frm, text='y轴网格间距(mm)  ')
        self.y_axis_gap_ent = tk.Entry(self.y_axis_gap_frm, textvariable=self.y_axis_gap, width=8)
        self.grid_gap_btn = tk.Button(self.control_frame, text='设定新网格间距', command=self.grid_gap_btn_callback)
        self.grid_show_btn = tk.Button(self.control_frame, textvariable=self.show_grid_str, command=self.grid_show_btn_callback)
        self.x_axis_gap_lbl.grid(row=0, column=0, sticky='', pady=2)
        self.x_axis_gap_ent.grid(row=0, column=1, sticky='', pady=2)
        self.y_axis_gap_lbl.grid(row=0, column=0, sticky='', pady=2)
        self.y_axis_gap_ent.grid(row=0, column=1, sticky='', pady=2)
        self.grid_gap_btn.grid(sticky='', pady=2)
        self.grid_show_btn.grid(sticky='', pady=2)

        self.donothing_2_1 = tk.Frame(self.control_frame, height=8, width=120)
        self.donothing_2_1.grid()
        self.donothing_2_2 = tk.Frame(self.control_frame, bg='#555', height=1, width=220)
        self.donothing_2_2.grid()
        self.donothing_2_3 = tk.Frame(self.control_frame, height=8, width=120)
        self.donothing_2_3.grid()

        self.left_top_x = tk.IntVar()
        self.left_top_y = tk.IntVar()
        self.left_top_x_lbl = tk.Label(self.control_frame, text='视野中心x坐标(mm)')
        self.left_top_x_ent = tk.Entry(self.control_frame, textvariable=self.left_top_x)
        self.left_top_y_lbl = tk.Label(self.control_frame, text='视野中心y坐标(mm)')
        self.left_top_y_ent = tk.Entry(self.control_frame, textvariable=self.left_top_y)
        self.left_top_btn = tk.Button(self.control_frame, text='设定新中心点', command=self.center_btn_callback)
        self.left_top_x_lbl.grid(pady=2)
        self.left_top_x_ent.grid(pady=2)
        self.left_top_y_lbl.grid(pady=2)
        self.left_top_y_ent.grid(pady=2)
        self.left_top_btn.grid(pady=2)

        self.donothing_3_1 = tk.Frame(self.control_frame, height=8, width=120)
        self.donothing_3_1.grid()
        self.donothing_3_2 = tk.Frame(self.control_frame, bg='#555', height=1, width=220)
        self.donothing_3_2.grid()
        self.donothing_3_3 = tk.Frame(self.control_frame, height=8, width=120)
        self.donothing_3_3.grid()

        # 保持stat flag
        self.edit_mod_var = tk.StringVar()
        self.edit_mod_var.set('进入编辑模式')
        self.edit_mod_btn = tk.Button(self.control_frame, textvariable=self.edit_mod_var, command=self.edit_mod_callback)
        self.edit_mod_btn.grid(pady=2)

        self.edit_rotate_val = tk.StringVar()
        self.edit_rotate_val.set('当前无旋转图像')
        self.edit_rotate_lal = tk.Label(self.control_frame, textvariable=self.edit_rotate_val)
        self.edit_rotate_lal.grid(pady=2)

        self.edit_history_father = tk.Frame(self.control_frame)
        self.edit_history_father.grid(pady=2)
        self.edit_history_frame = tk.Frame(self.edit_history_father)
        self.edit_history_frame.pack()
        self.edit_history_listbox = tk.Listbox(self.edit_history_frame)
        self.edit_history_listbox.pack(side='left', fill='y')
        self.edit_history_scrollbar = tk.Scrollbar(self.edit_history_frame, orient=tk.VERTICAL)
        self.edit_history_scrollbar.config(command=self.edit_history_listbox.yview)
        self.edit_history_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.edit_history_listbox.config(yscrollcommand=self.edit_history_scrollbar.set)

        self.edit_frame = tk.Frame(self.control_frame)
        self.edit_frame.grid(pady=2)
        self.edit_commit_btn = tk.Button(self.edit_frame, text='提交修改', command=self.edit_commit_callback)
        self.edit_abort_btn = tk.Button(self.edit_frame, text='放弃修改', command=self.edit_abort_callback)
        self.edit_commit_btn.grid(row=0, column=0, pady=2, padx=2)
        self.edit_abort_btn.grid(row=0, column=1, pady=2, padx=2)

        self.donothing_4_1 = tk.Frame(self.control_frame, height=8, width=120)
        self.donothing_4_1.grid()
        self.donothing_4_2 = tk.Frame(self.control_frame, bg='#555', height=1, width=220)
        self.donothing_4_2.grid()
        self.donothing_4_3 = tk.Frame(self.control_frame, height=8, width=120)
        self.donothing_4_3.grid()

        self.edit_delete_var = tk.StringVar()
        self.edit_delete_var.set('删除选中图像：暂无选中ID')
        self.edit_delete_btn = tk.Button(self.control_frame, textvariable=self.edit_delete_var, command=self.edit_delete_callback, state=tk.DISABLED)
        self.edit_delete_btn.grid(pady=2)

        self.donothing_5_1 = tk.Frame(self.control_frame, height=16, width=120)
        self.donothing_5_1.grid()
        self.donothing_5_2 = tk.Frame(self.control_frame, bg='#555', height=1, width=220)
        self.donothing_5_2.grid()
        self.donothing_5_3 = tk.Frame(self.control_frame, height=16, width=120)
        self.donothing_5_3.grid()

        self.progress_frm = tk.Frame(self.control_frame)
        self.progress_frm.grid(pady=2)
        self.progress = ttk.Progressbar(self.progress_frm, orient='horizontal', length=120, mode='determinate')
        self.progress_msg = tk.StringVar()
        self.progress_msg.set('  载入完成')
        self.progress_lbl = tk.Label(self.progress_frm, textvariable=self.progress_msg)
        self.progress_lbl.grid(row=0, column=1, pady=2)
        self.progress.grid(row=0, column=0, pady=2)

        self.grid_width_val = tk.DoubleVar()
        self.coord_width_val = tk.DoubleVar()
        self.sk_path_val = tk.StringVar()
        self.sk_path_val.set('')

        self.img_path_val = tk.StringVar()
        self.img_path_val.set('D:/')
        self.sql_path_val = tk.StringVar()
        self.sql_path_val.set('D:/')
        self.sql_table_val = tk.StringVar()
        self.sql_table_val.set('zhdl_map')
        self.sample_equipnum_val = tk.StringVar()
        self.sample_equipnum_val.set('1')
        self.sample_rate_val = tk.DoubleVar()
        self.sample_rate_val.set(1.0)
       
        self.global_view_toplevel = None

        self.root.resizable(width=False, height=False)
        self.root.configure(menu=self.menubar)
        self.reinitialize()

    def run(self):
        self.init_mainpage()

        # self.socket_loop_thread = threading.Thread(target=self.socket_loop)
        # self.socket_loop_thread.daemon = True
        # self.socket_loop_thread.start()

        self.main_loop_thread = threading.Thread(target=self.root.mainloop)
        self.main_loop_thread.run()

if __name__ == '__main__':
    mv = Mapviewer()
    mv.run()
