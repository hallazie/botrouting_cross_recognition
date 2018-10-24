# coding:utf-8
# @author: xiaoshanghua
# map viewer

import Tkinter as tk
import tkMessageBox
import numpy as np
import random
import os
import sys
import sqlite3
import traceback
import datetime

from PIL import Image, ImageTk

class Imgobj:
    def __init__(self, idx, image, x, y, theta):
        self.idx = idx
        self.image = image
        self.x = x
        self.y = y
        self.theta = theta
        self.show = True

class Mapviewer:
    def __init__(self):
        self.dragged_item = tk.ALL
        self.imgsize = 320
        self.current_coords = 0, 0
        self.total_map_shift = (0, 0)
        self.width = 1280
        self.height = 960
        self.scale = 1.0
        self.num_img = 1024
        self.img_dict = {}
        self.canvas = None
        self.last_canvx, self.last_canvy = 0, 0
        self.window = [(0, 1280), (0, 960)]
        self.factor = 1.1
        self.maxx, self.maxy = 0, 0
        self.mutex = False
        self.mutex_unlock_count = 0
        self.mil2pix_ratio = 0.68181818
        self.edit_mod_flag = False
        self.edit_history = []

    def start_drag(self, event):
        # result = self.canvas.find_withtag('current')
        result = self.canvas.gettags('current')
        if result:
            self.dragged_item = int(result[1])
            self.current_coords = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        else:
            self.dragged_item = tk.ALL
            self.current_coords = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

    def stop_drag(self, event):
        try:
            if self.dragged_item==tk.ALL or self.edit_mod_flag==False:
                # self.window = [(self.total_map_shift[0]/self.scale, (self.total_map_shift[0]+1280)/self.scale), (self.total_map_shift[1]/self.scale, (self.total_map_shift[1]+960)/self.scale)]
                self.calc_visible(False)
        except Exception as e:
            print e
        self.dragged_item = tk.ALL

    def drag(self, event):
        try:
            xc, yc = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
            dx, dy = xc-self.current_coords[0], yc-self.current_coords[1]
            self.total_map_shift = self.total_map_shift[0]-dx, self.total_map_shift[1]-dy
            curr_img_id = self.canvas.find_withtag('current')
            self.current_coords = xc, yc
            self.last_canvx, self.last_canvy = xc, yc
            if self.dragged_item != tk.ALL and self.edit_mod_flag == True:
                self.canvas.move(curr_img_id, dx, dy)
                self.img_dict[self.dragged_item].x += dx
                self.img_dict[self.dragged_item].y += dy
            else:
                self.canvas.move(tk.ALL, dx, dy)
                for k in self.img_dict.keys():
                    self.img_dict[k].x += dx
                    self.img_dict[k].y += dy
        except Exception as e:
            print e

    def zoomer(self, event):
        if not self.mutex:
            self.mutex = True
            if event.delta > 0:
                if self.scale < 2**4:
                    self.scale *= self.factor
                    self.zoom_scale.set('缩放系数：%s'%round(self.scale, 5))
                    for k in self.img_dict.keys():
                        self.img_dict[k].x *= self.factor
                        self.img_dict[k].y *= self.factor
                    # self.window = [((self.window[0][0])/self.factor, (self.window[0][1])/self.factor), ((self.window[1][0])/self.factor, (self.window[1][1])/self.factor)]
                    self.redraw()
                else:
                    print 'achieved top'
            elif event.delta <0:
                if self.scale > 0.5**4:
                    self.scale /= self.factor
                    for k in self.img_dict.keys():
                        self.img_dict[k].x /= self.factor
                        self.img_dict[k].y /= self.factor
                    self.zoom_scale.set('缩放系数：%s'%round(self.scale, 5))
                    # self.window = [((self.window[0][0])*self.factor, (self.window[0][1])*self.factor), ((self.window[1][0])*self.factor, (self.window[1][1])*self.factor)]
                    self.redraw()
                else:
                    print 'achieved bottom'
            self.mutex = False

    def redraw(self):
        # TODO: num_tks
        self.calc_visible(True)

    def mouse_pos_callback(self, event):
        self.mouse_pos_variable.set('鼠标位置：%s, %s'%(self.total_map_shift[0]+self.canvas.canvasx(event.x), self.total_map_shift[1]+self.canvas.canvasy(event.y)))

    def mouse_click_callback(self, event):
        result = self.canvas.gettags('current')
        if result:
            curr_img_id = int(result[1])
            self.selected_node_id.set('选中节点ID：%s'%curr_img_id)
            self.selected_node_pos.set('选中节点位置：%s，%s'%(round(self.img_dict[curr_img_id].x, 4), round(self.img_dict[curr_img_id].y, 4)))

    def mil2pix_btn_callback(self):
        # self.mil2pix_ratio = self.mil2pix.get()
        pass

    def left_top_btn_callback(self):
        pass

    def edit_mod_callback(self):
        if self.edit_mod_flag==False and self.scale<0.2:
            tkMessageBox.showinfo('提示', '当前缩放尺度不支持拖拽编辑')
            return 
        self.edit_mod_flag = not self.edit_mod_flag
        self.edit_mod_var.set('退出拖拽编辑模式') if self.edit_mod_flag else self.edit_mod_var.set('进入拖拽编辑模式')

    def open_history_callback(self):
        pass

    def history_export_callback(self):
        if len(self.edit_history) == 0:
            tkMessageBox.showinfo('提示', '当前无修改历史')
        else:
            self.export_edit_history()

    def fintune_callback(self):
        pass


    # --------------------------------------------------------------------------------------------------

    # def img_load(self):
    #     for _,_,fs in os.walk('../bj_img'):
    #         for c, f in enumerate(fs):
    #             if c == self.num_img:
    #                 break
    #             img = Image.open('../bj_img/%s'%(f)).resize((self.imgsize,self.imgsize))
    #             curx, cury = float(f.split('_')[1])-1000, float(f.split('_')[2])-1000
    #             self.maxx, self.maxy = max(curx, self.maxx), max(cury, self.maxy)
    #             self.img_list.append(img)
    #             self.pos_list.append((curx, cury))
    #     tmp_orgx, tmp_orgy = self.maxx//2, self.maxy//2
    #     for i in range(len(self.pos_list)):
    #         self.pos_list[i] = (self.pos_list[i][0]-tmp_orgx, self.pos_list[i][1]-tmp_orgx)

    def img_load_db(self):
        conn = sqlite3.connect('D:/Workspace/map/MapData/bjyz_remote_control.db')
        # conn = sqlite3.connect('D:/Workspace/map/MapData/suzhou.db')
        curs = conn.cursor()
        res = curs.execute('select id, x, y, heading, processed_image, raw_image from zhdl_map')
        img_cnt = 0
        while True:
            try:
                data = res.next()
                curr_img = Image.fromarray(np.array(data[5]).reshape((self.imgsize, self.imgsize)).astype('uint8'))
                imgobj = Imgobj(idx=data[0],
                                image=curr_img,
                                x=data[1],
                                y=data[2],
                                theta=data[3])
                self.img_dict[data[0]] = imgobj
                img_cnt += 1
            except Exception as e:
                print 'current map load finished with sample number %s.'%img_cnt
                break

    def img_edit_2_db(self):
        pass

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
        size = int(self.imgsize*self.scale)
        show_cnt = 0
        self.canvas.delete(tk.ALL)
        self.tk_dict = {}

        for k in self.img_dict.keys():
            if self.img_dict[k].x+320*self.scale>self.window[0][0] and self.img_dict[k].x<self.window[0][1] and self.img_dict[k].y+320*self.scale>self.window[1][0] and self.img_dict[k].y<self.window[1][1]:
                show_cnt += 1
                # print 'show!\twindow:%s, coord:%s'%(str(self.window), str((self.img_dict[k].x, self.img_dict[k].y)))
                if self.scale<0.2 and self.scale>0.1 and show_cnt%2==0:
                    continue
                    # pass 
                if self.scale<0.1 and show_cnt%3!=0:
                    continue
                if is_scale:
                    self.tk_dict[k] = ImageTk.PhotoImage(self.img_dict[k].image.resize((size, size)))
                else:
                    self.tk_dict[k] = ImageTk.PhotoImage(self.img_dict[k].image.resize((size, size)))
            else:
                pass

        for k in self.tk_dict.keys():
                # if is_scale:
                #     self.canvas.create_image(self.img_dict[k].x*self.scale, self.img_dict[k].y*self.scale, image=self.tk_dict[k], anchor='nw', tags=('img', k))
                # else:
                self.canvas.create_image(self.img_dict[k].x, self.img_dict[k].y, image=self.tk_dict[k], anchor='nw', tags=('img', k))
        print 'current showing %s tiles with size %s, scale %s'%(show_cnt, size, self.scale)

    def init_binding(self):
        self.canvas.bind('<ButtonPress-1>', self.start_drag)
        self.canvas.bind('<ButtonRelease-1>', self.stop_drag)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.canvas.bind_all('<MouseWheel>', self.zoomer)
        self.canvas.bind('<Motion>', self.mouse_pos_callback)
        self.canvas.bind('<Double-Button-1>', self.mouse_click_callback)

    def run(self):
        self.root = tk.Tk()
        self.root.iconbitmap(default='quick.ico')
        self.root.title('Quicktron Map Dispalyer')
        self.root.geometry('{}x{}'.format(1400,1000))

        self.top_frame = tk.Frame(self.root, height=40)
        self.control_frame = tk.Frame(self.root, width=120, height=960)
        self.canvas_frame = tk.Frame(self.root, width=1280, height=960)
        self.top_frame.grid(row=0, columnspan=2, sticky='w')
        self.control_frame.grid(row=1, column=0, sticky='n')
        self.canvas_frame.grid(row=1, column=1, sticky='e')

        # ------------------------------------------ 地图绘板 ------------------------------------------

        self.canvas = tk.Canvas(self.canvas_frame, width=self.width, height=self.height, bg='#111')
        self.canvas.grid(pady=2)

        # ------------------------------------------ 下拉菜单 ------------------------------------------

        self.dropmenu = tk.OptionMenu(self.top_frame, '测试1', *['测试1', '参数对话框', '导入一张', '倒入标注集合'])
        self.dropmenu.grid(pady=2)

        # ------------------------------------------ 控制侧栏 ------------------------------------------

        self.mouse_pos_variable = tk.StringVar()
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

        self.mil2pix = tk.DoubleVar()
        self.mil2pix.set(0.6818181818)
        self.mil2pix_frame = tk.Frame(self.control_frame)
        self.mil2pix_frame.grid(pady=2)
        self.mil2pix_lbl = tk.Label(self.mil2pix_frame, text='毫米/像素')
        self.mil2pix_ent = tk.Entry(self.mil2pix_frame, textvariable=self.mil2pix)
        self.mil2pix_lbl.grid(row=0, column=0, sticky='', pady=2)
        self.mil2pix_ent.grid(row=0, column=1, sticky='', pady=2)
        self.mil2pix_btn = tk.Button(self.control_frame, text="设定新的毫米/像素", command=self.mil2pix_btn_callback)
        self.mil2pix_btn.grid(sticky='', pady=2)

        self.zoom_scale = tk.StringVar()
        self.zoom_scale.set('缩放系数：1.0')
        self.zoom_scale_lbl = tk.Label(self.control_frame, textvariable=self.zoom_scale)
        self.zoom_scale_lbl.grid(sticky='', pady=2)

        self.x_axis_gap = tk.IntVar()
        self.y_axis_gap = tk.IntVar()
        self.x_axis_gap_frame = tk.Frame(self.control_frame)
        self.y_axis_gap_frame = tk.Frame(self.control_frame)
        self.x_axis_gap_frame.grid(pady=2)
        self.y_axis_gap_frame.grid(pady=2)
        self.x_axis_gap_lbl = tk.Label(self.x_axis_gap_frame, text='x轴网格间距(mm)')
        self.x_axis_gap_ent = tk.Entry(self.x_axis_gap_frame, textvariable=self.x_axis_gap)
        self.x_axis_gap_lbl.grid(row=0, column=0, sticky='', pady=2)
        self.x_axis_gap_ent.grid(row=0, column=1, sticky='', pady=2)
        self.y_axis_gap_lbl = tk.Label(self.y_axis_gap_frame, text='y轴网格间距(mm)')
        self.y_axis_gap_ent = tk.Entry(self.y_axis_gap_frame, textvariable=self.y_axis_gap)
        self.y_axis_gap_lbl.grid(row=0, column=0, sticky='', pady=2)
        self.y_axis_gap_ent.grid(row=0, column=1, sticky='', pady=2)
        self.grid_gap_btn = tk.Button(self.control_frame, text='设定新网格间距', command=self.mil2pix_btn_callback)
        self.grid_gap_btn.grid(sticky='', pady=2)

        self.left_top_x = tk.IntVar()
        self.left_top_y = tk.IntVar()
        self.left_top_x_lbl = tk.Label(self.control_frame, text='视野左上角x坐标(mm)')
        self.left_top_x_ent = tk.Entry(self.control_frame, textvariable=self.left_top_x)
        self.left_top_y_lbl = tk.Label(self.control_frame, text='视野左上角y坐标(mm)')
        self.left_top_y_ent = tk.Entry(self.control_frame, textvariable=self.left_top_y)
        self.left_top_btn = tk.Button(self.control_frame, text='设定新中心点', command=self.left_top_btn_callback)
        self.left_top_x_lbl.grid(pady=2)
        self.left_top_x_ent.grid(pady=2)
        self.left_top_y_lbl.grid(pady=2)
        self.left_top_y_ent.grid(pady=2)
        self.left_top_btn.grid(pady=2)

        self.donothing_1 = tk.Frame(self.control_frame, height=15, width=120)
        self.donothing_1.grid()
        self.donothing_2 = tk.Frame(self.control_frame, bg='#555', height=1, width=220)
        self.donothing_2.grid()
        self.donothing_3 = tk.Frame(self.control_frame, height=15, width=120)
        self.donothing_3.grid()

        # 保持stat flag
        self.edit_mod_var = tk.StringVar()
        self.edit_mod_var.set('进入拖拽编辑模式')
        self.edit_mod_btn = tk.Button(self.control_frame, textvariable=self.edit_mod_var, command=self.edit_mod_callback)
        self.edit_mod_btn.grid(pady=2)

        self.finetune_btn = tk.Button(self.control_frame, text='打开地图微调', command=self.fintune_callback)
        self.finetune_btn.grid(pady=2)

        # TODO:
        # 加入选中tile之后输入坐标偏移进行微调
        # 加入编辑历史：1.可导出编辑历史日志 2.可根据单条历史进行编辑撤销

        self.open_history_btn = tk.Button(self.control_frame, text='打开编辑历史', command=self.open_history_callback)
        self.open_history_btn.grid(pady=2)

        self.history_export_btn = tk.Button(self.control_frame, text='导出地图编辑历史', command=self.history_export_callback)
        self.history_export_btn.grid(pady=2)

        self.img_load_db()
        self.init_binding()
        self.calc_visible(False)

        self.root.mainloop()

if __name__ == '__main__':
    mv = Mapviewer()
    mv.run()
