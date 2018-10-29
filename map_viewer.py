# coding:utf-8
# @author: xiaoshanghua
# map viewer

# TODO 10-25
# 1.选中单张图像后添加边框  V
# 2.选择是否显示网格线      V
# 3.支持自定义网格线宽度    V
# 4.验证透明度对提高显示效果的可用性
# 5.添加修改/添加/删除单张图并回传数据库 V
# 6.添加修改历史/redo-undo 
# 7.改变坐标中心为中心的0,0 V
# 8.点击查看全地图示例图    V

import Tkinter as tk
import tkFileDialog
import tkMessageBox
import numpy as np
import random
import os
import sys
import sqlite3
import traceback
import datetime
import copy

from PIL import Image, ImageTk

class Imgobj:
    def __init__(self, idx, image, x, y, theta):
        self.idx = idx
        self.image = image
        self.x = x
        self.y = y
        self.ox = x
        self.oy = y
        self.theta = theta
        self.show = True
        self.image_back = None
    
    def enter_boundingbox(self, idx):
        # if self.image_back==None:
        #     self.image_back = self.image
        #     tmp = np.array(self.image.resize((320,320)).convert('RGB'))
        #     tmp[:320,0,0] = 255
        #     tmp[:320,319,0] = 255
        #     tmp[0,:320,0] = 255
        #     tmp[319,:320,0] = 255
        #     self.image = Image.fromarray(tmp.astype('uint8')).resize((320*scale, 320*scale))
        if self.image_back==None:
            self.image_back = self.image
            tmp = np.array(self.image.convert('RGB'))
            w, h = self.image.size
            tmp[:w,   0:2,   idx] = 255
            tmp[:w,   h-2:,  idx] = 255
            tmp[0:2,  :h,    idx] = 255
            tmp[w-2:, :h,    idx] = 255
            self.image = Image.fromarray(tmp.astype('uint8'))

    def leave_boundingbox(self):
        self.image = self.image_back
        self.image_back = None

class Lineobj:
    def __init__(self, direct, show):
        self.direct = direct
        self.show = show

    def show_flag(self):
        self.show = not self.show

class Mapviewer:
    def __init__(self):
        self.dragged_item = tk.ALL
        self.imgsize = 320
        self.mil2pix_ratio = 0.40625
        self.current_coords = 0, 0
        self.total_map_shift = (0, 0)
        self.width = 1280
        self.height = 960
        self.scale = 1.0
        self.img_dict = {}
        self.grid_horz = []
        self.grid_vert = []
        self.canvas = None
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
        # self.coord_central = 160*self.mil2pix_ratio, 160*self.mil2pix_ratio
        self.coord_central = 160*self.mil2pix_ratio, 160*self.mil2pix_ratio
        self.db_path = 'D:/Workspace/map/MapData/suzhou.db'
        # self.db_path = ''
        self.dragging_img_set = set()
        self.modify_img_dict = {}
        self.configfile = {}
        self.selected_node_id_int = None
        self.img_insert = None
        # preference
        self.grid_line_width = 1
        self.coord_line_width = 1

        try:
            with open('mapviewer.cfg', 'r') as f:
                for line in f.readlines():
                    k, w = line.replace(' ','').split('=')
                    self.configfile[k]=w
            # if self.configfile['DBPATH']:
            #     self.db_path = self.configfile['DBPATH']
        except:
            print 'no config file exist'

    def start_drag(self, event):
        # result = self.canvas.find_withtag('current')
        result = self.canvas.gettags('current')
        if len(result)>2:
            self.dragged_item = int(result[1])
        else:
            self.dragged_item = tk.ALL
        self.current_coords = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.drag_start = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

    def stop_drag(self, event):
        self.drag_end = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        try:
            if self.dragged_item==tk.ALL or self.edit_mod_flag==False:
                # self.window = [(self.total_map_shift[0]/self.scale, (self.total_map_shift[0]+1280)/self.scale), (self.total_map_shift[1]/self.scale, (self.total_map_shift[1]+960)/self.scale)]
                self.calc_visible(False)
        except Exception as e:
            print 'stop_drag err'
            print e
        self.dragged_item = tk.ALL

    def drag(self, event):
        try:
            xc, yc = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
            dx, dy = xc-self.current_coords[0], yc-self.current_coords[1]
            self.total_map_shift = self.total_map_shift[0]-dx/self.scale, self.total_map_shift[1]-dy/self.scale
            curr_img_id = self.canvas.find_withtag('current')
            self.current_coords = xc, yc
            self.last_canvx, self.last_canvy = xc, yc
            if self.dragged_item != tk.ALL and self.edit_mod_flag == True:
                # 拖拽编辑模式
                self.canvas.tag_raise('current')
                if self.dragged_item not in self.modify_img_dict.keys():
                    self.modify_img_dict[self.dragged_item] = (0,0)
                self.dragging_img_set.add(self.dragged_item)
                self.canvas.move(curr_img_id, dx, dy)
                self.img_dict[self.dragged_item].enter_boundingbox(0)
                self.img_dict[self.dragged_item].x += dx
                self.img_dict[self.dragged_item].y += dy
                self.modify_img_dict[self.dragged_item] = (self.modify_img_dict[self.dragged_item][0]+dx/self.scale, self.modify_img_dict[self.dragged_item][1]+dy/self.scale)
                # self.calc_visible(False)
            else:
                # self.canvas.delete('baseline')
                self.canvas.move(tk.ALL, dx, dy)
                # self.canvas.create_line(640,0,640,960, fill='blue', tags='baseline')
                # self.canvas.create_line(0,480,1280,480, fill='blue', tags='baseline')
                for k in self.img_dict.keys():
                    self.img_dict[k].x += dx
                    self.img_dict[k].y += dy
                for i in range(len(self.grid_vert)):
                    self.grid_vert[i] = (self.grid_vert[i][0], self.grid_vert[i][1]+dy, self.grid_vert[i][2], self.grid_vert[i][3]+dy)
                for j in range(len(self.grid_horz)):
                    self.grid_horz[j] = (self.grid_horz[j][0]+dx, self.grid_horz[j][1], self.grid_horz[j][2]+dx, self.grid_horz[j][3])
                self.coord_central = (self.coord_central[0]+dx, self.coord_central[1]+dy)
        except Exception as e:
            print 'drag err'
            print e

    def zoomer(self, event):
        if not self.mutex:
            self.mutex = True
            self.mouse_pos_variable.set('鼠标位置：%s, %s'%(round(self.total_map_shift[0]+self.canvas.canvasx(event.x)/self.scale, 2), round(self.total_map_shift[1]+self.canvas.canvasy(event.y)/self.scale, 2)))
            if event.delta > 0:
                if self.scale < 2**4:
                    self.scale *= self.factor
                    self.zoom_scale.set('缩放系数：%s'%round(self.scale, 5))
                    for k in self.img_dict.keys():
                        self.img_dict[k].x *= self.factor
                        self.img_dict[k].y *= self.factor
                    for i in range(len(self.grid_vert)):
                        self.grid_vert[i] = (self.grid_vert[i][0]*self.factor, self.grid_vert[i][1]*self.factor, self.grid_vert[i][2]*self.factor, self.grid_vert[i][3]*self.factor)
                    for j in range(len(self.grid_horz)):
                        self.grid_horz[j] = (self.grid_horz[j][0]*self.factor, self.grid_horz[j][1]*self.factor, self.grid_horz[j][2]*self.factor, self.grid_horz[j][3]*self.factor)
                    self.coord_central = (self.coord_central[0]*self.factor, self.coord_central[1]*self.factor)
                    # self.window = [((self.window[0][0])/self.factor, (self.window[0][1])/self.factor), ((self.window[1][0])/self.factor, (self.window[1][1])/self.factor)]
                    self.redraw()
                else:
                    print 'achieved top'
            elif event.delta <0:
                if self.scale > 0.5**4:
                    self.scale /= self.factor
                    self.zoom_scale.set('缩放系数：%s'%round(self.scale, 5))
                    for k in self.img_dict.keys():
                        self.img_dict[k].x /= self.factor
                        self.img_dict[k].y /= self.factor
                    for i in range(len(self.grid_vert)):
                        self.grid_vert[i] = (self.grid_vert[i][0]/self.factor, self.grid_vert[i][1]/self.factor, self.grid_vert[i][2]/self.factor, self.grid_vert[i][3]/self.factor)
                    for j in range(len(self.grid_horz)):
                        self.grid_horz[j] = (self.grid_horz[j][0]/self.factor, self.grid_horz[j][1]/self.factor, self.grid_horz[j][2]/self.factor, self.grid_horz[j][3]/self.factor)
                    self.coord_central = (self.coord_central[0]/self.factor, self.coord_central[1]/self.factor)
                    # self.window = [((self.window[0][0])*self.factor, (self.window[0][1])*self.factor), ((self.window[1][0])*self.factor, (self.window[1][1])*self.factor)]
                    self.redraw()
                else:
                    print 'achieved bottom'
            if self.scale <= 0.2:
                self.edit_delete_var.set('删除选中图像：暂无选中ID')
                self.edit_delete_flag = False
                self.edit_delete_btn.config(state=tk.DISABLED)
            self.mutex = False

    def redraw(self):
        # TODO: num_tks
        self.calc_visible(True)

    def single_click_callback(self, event):
        idx = self.edit_history_listbox.curselection()
        # if len(idx)>0:
        #     item = self.edit_history_listbox.get(idx[0])
        #     pid = int(item.split('  ')[0].split(':')[1])
        #     for e in self.edit_history_listbox.get(0, tk.END):
        #         print int(e.split('  ')[0].split(':')[1])
        #         self.img_dict[int(e.split('  ')[0].split(':')[1])].leave_boundingbox()
        #     print 'select: %s'%int(e.split('  ')[0].split(':')[1])
        #     self.img_dict[pid].enter_boundingbox(1)
        #     self.calc_visible(False)

    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ 回调函数 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def show_global_map_callback(self):
        # toplevel = tk.Toplevel()
        # global_canvas = tk.Canvas(toplevel, width=1280, height=960)
        width = 2048
        height = float(width)*(self.maxy/float(self.maxx))
        global_img = np.zeros((int(width*self.mil2pix_ratio),int(height*self.mil2pix_ratio)))
        scale = float(width)*self.mil2pix_ratio/(self.maxx+1000)
        err_cnt = 0
        for k in self.img_dict.keys():
            try:
                imgobj = self.img_dict[k]
                x, y = int(scale*imgobj.ox), int(scale*imgobj.oy)
                w, h = int(imgobj.image.size[0]*scale*self.mil2pix_ratio), int(imgobj.image.size[1]*scale*self.mil2pix_ratio)
                # imgarr = np.array(imgobj.image.resize((int(w), int(h))))
                imgarr = np.array(imgobj.image.resize((w, h)))
                global_img[x:x+w, y:y+h] = imgarr
            except:
                err_cnt += 1
        print 'total err when constructing global img: %s'%err_cnt
        global_arr = global_img.transpose().astype('uint8')
        # for i in range(int(global_arr.shape[0]//2)):
        #     swap = copy.deepcopy(global_arr[i,:])
        #     global_arr[i,:] = copy.deepcopy(global_arr[int(global_arr.shape[0]-i-1),:])
        #     global_arr[int(global_arr.shape[0]-i-1),:] = copy.deepcopy(swap)
        global_img = Image.fromarray(global_arr).resize((width, int(height)))
        global_img.save('map.bmp')
        global_img.show()
        # toplevel = tk.Toplevel(width=1024, height=int(height//2))
        # toplevel.title('全图预览')
        # map_canvas = tk.Canvas(toplevel, width=1024, height=int(height//2))
        # map_canvas.create_image(0, 0, image=ImageTk.PhotoImage(global_img.resize((1024,int(height//2)))))
        # map_canvas.pack()
        # global_canvas.create_image(1, 1 ,ImageTk.PhotoImage(global_img), anchor='nw')
        # global_canvas.pack()

    def mouse_pos_callback(self, event):
        self.mouse_pos_variable.set('鼠标位置：%s, %s'%(round(self.total_map_shift[0]+self.canvas.canvasx(event.x)/self.scale, 2), -1*round(self.total_map_shift[1]+self.canvas.canvasy(event.y)/self.scale, 2)))

    def mouse_db_click_callback(self, event):
        if self.scale<=0.2:
            tkMessageBox.showinfo('提示', '当前缩放尺度不支持双击选中')
            return
        result = self.canvas.gettags('current')
        try:
            if result:
                curr_img_id = int(result[1])
                self.selected_node_id_int = curr_img_id
                self.selected_node_id.set('选中节点ID：%s'%curr_img_id)
                self.selected_node_pos.set('选中节点位置：%s，%s'%(round(self.img_dict[curr_img_id].ox, 1), -1*round(self.img_dict[curr_img_id].oy, 1)))
                self.edit_delete_var.set('删除选中图像：%s'%curr_img_id)
                self.edit_delete_flag = True
                self.edit_delete_btn.config(state=tk.NORMAL)
            else:
                self.edit_delete_var.set('删除选中图像：暂无选中ID')
                self.edit_delete_flag = False
                self.edit_delete_btn.config(state=tk.DISABLED)
        except Exception as e:
            print e

    def mil2pix_btn_callback(self):
        self.mil2pix_ratio = self.mil2pix.get()
        self.reinit_everything()

    def center_btn_callback(self):
        # TODO: fix bug
        # bug - 当改变中心点坐标时，图像与网格基准坐标都发生了改变
        self.coord_central = ((self.left_top_x.get()-self.total_map_shift[0]+self.imgsize//2)*self.scale, -1*(self.left_top_y.get()+self.total_map_shift[1]-self.imgsize//2)*self.scale)
        # self.change_focus(self.coord_central[0], self.coord_central[1])
        self.calc_visible(False)

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
            tkMessageBox.showinfo('提示', '当前缩放尺度不支持拖拽编辑')
            return
        self.edit_mod_flag = not self.edit_mod_flag
        if self.edit_mod_flag:
            self.edit_mod_var.set('退出拖拽编辑模式')
        else:
            self.edit_mod_var.set('进入拖拽编辑模式')
            for item in self.dragging_img_set:
                self.img_dict[item].leave_boundingbox()
            self.edit_history_listbox.delete(0,tk.END)
            for k in self.modify_img_dict.keys():
                self.edit_history_listbox.insert(tk.END, 'id:%s  x:%s  y:%s'%(k, round(self.modify_img_dict[k][0],2), round(self.modify_img_dict[k][1],2)))
            self.dragging_img_set = set()
            self.calc_visible(False)
        # self.edit_mod_var.set('退出拖拽编辑模式') if self.edit_mod_flag else self.edit_mod_var.set('进入拖拽编辑模式')

    def edit_commit_callback(self):
        result = tkMessageBox.askquestion('提示', '确认提交修改？', icon='warning')
        if result == 'yes':
            if self.edit_mod_flag:
                tkMessageBox.showwarning('提示', '请先退出拖拽编辑模式')
                return
            if len(self.edit_history_listbox.get(0, tk.END))==0:
                tkMessageBox.showinfo('提示', '当前无修改历史')
                return
            try:
                conn = sqlite3.connect(self.db_path)
                curs = conn.cursor()
                # res = curs.execute('select id, x, y, heading, processed_image, raw_image from zhdl_map')
            except Exception as e:
                tkMessageBox.showinfo('提示', '请在选项中正确配置数据库文件地址')
            try:
                # for item in self.edit_history_listbox.get(0, tk.END):
                #     imgobj = self.img_dict[int(item.split('  ')[0].split(':')[1])]
                #     shiftx = float(item.split('  ')[1].split(':')[1])
                #     shifty = float(item.split('  ')[2].split(':')[1])
                #     curs.execute('update zhdl_map set x=%s, y=%s where id=%s'%(imgobj.ox+shiftx, imgobj.oy+shifty, imgobj.idx))
                #     conn.commit()
                for k in self.modify_img_dict:
                    curs.execute('update zhdl_map set x=%s, y=%s where id=%s'%(self.img_dict[k].ox+self.modify_img_dict[k][0], -1*(self.img_dict[k].oy+self.modify_img_dict[k][1]), k))
                    conn.commit()
                conn.close()
                tkMessageBox.showinfo('提示', '提交修改成功')
                self.edit_history_listbox.delete(0, tk.END)
                self.modify_img_dict = {}
            except:
                tkMessageBox.showerror('提示', '提交修改失败')
            else:
                pass

    def edit_abort_callback(self):
        if len(self.edit_history_listbox.get(0, tk.END))==0:
            tkMessageBox.showinfo('提示', '当前无修改历史')
            return
        self.edit_mod_flag = False
        # TODO:redo all the modification
        # for k in self.dragging_img_set:
        #     self.img_dict[k].x = (self.img_dict[k].ox+self.total_map_shift[0])/self.scale
        #     self.img_dict[k].y = (self.img_dict[k].oy+self.total_map_shift[1])/self.scale
        # self.calc_visible(False)
        self.reinit_everything()
        self.edit_history_listbox.delete(0,tk.END)

    def edit_delete_callback(self):
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
                print e
                tkMessageBox.showerror('错误', '删除失败')

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
                    curs.execute('insert into zhdl_map (id, x, y, heading, processed_image, raw_image) values (%s,%s,%s,%s,%s,%s)'%(
                        self.img_insert.idx, 
                        self.img_insert.x+self.total_map_shift[0], 
                        self.img_insert.y+self.total_map_shift[1], 
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
            self.reinit_everything()
            self.center_btn_callback()
            self.grid_gap_btn_callback()
            tkMessageBox.showinfo('提示', '地图导入完成')
            with open('mapviewer.cfg', 'w+') as f:
                for line in f.readlines():
                    k, w = line.replace(' ','').split('=')
                    self.configfile[k]=w
                self.configfile['DBPATH'] = self.db_path
                w = '\n'.join([k+'='+self.configfile[k] for k in self.configfile.keys()])
                f.write(w)

    def preference_callback(self):
        toplevel = tk.Toplevel()
        toplevel.title('参数设置')

        grid_width_frame = tk.Frame(toplevel)
        grid_width_frame.grid(pady=2)
        self.grid_width_val.set(self.grid_line_width)
        grid_width_lbl = tk.Button(grid_width_frame, text='网格线宽度')
        grid_width_ent = tk.Entry(grid_width_frame, textvariable=self.grid_width_val)
        grid_width_lbl.grid(row=0, column=0, pady=2, padx=2)
        grid_width_ent.grid(row=0, column=1, pady=2, padx=2)

        coord_width_frame = tk.Frame(toplevel)
        coord_width_frame.grid(pady=2)
        self.coord_width_val.set(self.coord_line_width)
        coord_width_lbl = tk.Button(coord_width_frame, text='坐标线宽度')
        coord_width_ent = tk.Entry(coord_width_frame, textvariable=self.coord_width_val)
        coord_width_lbl.grid(row=0, column=0, pady=2, padx=2)
        coord_width_ent.grid(row=0, column=1, pady=2, padx=2)

        donothing_4_1 = tk.Frame(toplevel, height=8, width=120)
        donothing_4_1.grid()
        donothing_4_2 = tk.Frame(toplevel, bg='#555', height=1, width=220)
        donothing_4_2.grid()
        donothing_4_3 = tk.Frame(toplevel, height=8, width=120)
        donothing_4_3.grid()

        preference_commit_btn = tk.Button(toplevel, text='提交参数修改', command=self.preference_commit_callback)
        preference_commit_btn.grid(pady=0)

    def preference_commit_callback(self):
        self.grid_line_width = self.grid_width_val.get()
        self.coord_line_width = self.coord_width_val.get()
        self.calc_visible(False)

    def export_to_sqlite_callback(self):
        self.tl_sql_export = tk.Toplevel()
        # self.img_path_val = tk.StringVar()
        # self.sql_path_val = tk.StringVar()
        # self.sql_table_val = tk.StringVar()
        # self.sample_equipnum_val = tk.StringVar()
        # self.sample_rate_val = tk.DoubleVar()

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
        export_commit_btn = tk.Button(tl_btn_frame, text='启动导入', command=self.export_commit_btn_callback)
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
            self.reinit_everything(load_source='folder')
            try:
                conn = sqlite3.connect(self.db_path)
                curs = conn.cursor()
                for k in self.img_dict.keys():
                    curs.execute('insert into zhdl_map (x, y, heading, raw_image) values (%s, %s, %s, "%s")'%(
                            self.img_dict[k].ox,
                            self.img_dict[k].oy,
                            self.img_dict[k].theta,
                            str(np.array(self.img_dict[k].image.resize((320,320))).reshape((320*320))),
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
             

    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ 功能函数 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def reinit_everything(self, load_source='db'):
        self.dragged_item = tk.ALL
        self.imgsize = 320
        self.current_coords = 0, 0
        self.total_map_shift = (0, 0)
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
        self.dragging_img_set = set()
        self.modify_img_dict = {}
        self.edit_history_listbox.delete(0, tk.END)

        self.imgsize = int(320*self.mil2pix_ratio)
        if load_source=='db':
            self.img_load_db()
        else:
            self.img_load_folder()
        self.init_binding()
        self.calc_visible(False)
        self.grid_load()

    def img_load_folder(self):
        self.img_dict = {}
        for _,_,fs in os.walk(self.img_path_val.get()):
            img_cnt = 0
            for c, f in enumerate(fs):
                img = Image.open(self.img_path_val.get()+'/'+f).resize((self.imgsize,self.imgsize))
                idx, curx, cury, theta = float(f.split('_')[0]), float(f.split('_')[1]), float(f.split('_')[2]), float(f.split('_')[3].split('.')[0])
                imgobj = Imgobj(idx=idx,
                                image=img,
                                x=curx,
                                y=-1*cury,
                                theta=theta)
                self.img_dict[idx] = imgobj
                self.maxx = max(self.maxx, curx)
                self.maxy = max(self.maxy, cury)
                img_cnt += 1
            print 'current map read finished with sample number %s.'%img_cnt

    def img_load_db(self):
        # conn = sqlite3.connect('D:/Workspace/map/MapData/suzhou.db')
        try:
            conn = sqlite3.connect(self.db_path)
            curs = conn.cursor()
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
                except Exception as e:
                    print 'current map load finished with sample number %s.'%img_cnt
                    break
        except Exception as e:
            tkMessageBox.showinfo('提示', '请在选项中正确配置数据库文件地址')
            res = iter([])
        finally:
            conn.close()

    def grid_load(self):
        self.grid_horz = []
        self.grid_vert = []
        cx, cy = self.coord_central
        print self.coord_central
        # for i in range(int(self.maxx//self.x_axis_gap_val)):
        #     # 横向分布的竖线
        #     self.grid_horz.append(((i*self.x_axis_gap_val+self.imgsize//2)*self.scale,
        #                         -1e7,
        #                         (i*self.x_axis_gap_val+self.imgsize//2)*self.scale,
        #                         (1e7)*self.scale))
        # for j in range(int(self.maxy//self.y_axis_gap_val)):
        #     # 纵向分布的横线
        #     self.grid_vert.append((-1e7,
        #                         -1*(j*self.y_axis_gap_val-self.imgsize//2)*self.scale,
        #                         (1e7)*self.scale,
        #                         -1*(j*self.y_axis_gap_val-self.imgsize//2)*self.scale))
        for i in range(int(self.maxx//(self.x_axis_gap_val))):
            self.grid_horz.append((cx+(i*self.x_axis_gap_val)*self.scale,
                                -1e7,
                                cx+(i*self.x_axis_gap_val)*self.scale,
                                (1e7)*self.scale))
        for j in range(int(self.maxy//(self.y_axis_gap_val))):
            self.grid_vert.append((-1e7,
                                cy-1*(j*self.y_axis_gap_val)*self.scale,
                                (1e7)*self.scale,
                                cy-1*(j*self.y_axis_gap_val)*self.scale))
        for i in range(int(self.maxx//(self.x_axis_gap_val))):
            self.grid_horz.append((cx-(i*self.x_axis_gap_val)*self.scale,
                                -1e7,
                                cx-(i*self.x_axis_gap_val)*self.scale,
                                (1e7)*self.scale))
        for j in range(int(self.maxy//(self.y_axis_gap_val))):
            self.grid_vert.append((-1e7,
                                cy+1*(j*self.y_axis_gap_val)*self.scale,
                                (1e7)*self.scale,
                                cy+1*(j*self.y_axis_gap_val)*self.scale))
    def img_edit_2_db(self):
        pass

    # def change_focus(self, x, y):
    #     dx = (x-self.total_map_shift[0])/self.scale
    #     dy = (y-self.total_map_shift[1])/self.scale
    #     for k in self.img_dict.keys():
    #         self.img_dict[k].x += dx
    #         self.img_dict[k].y += dy
    #     for i in range(len(self.grid_vert)):
    #         self.grid_vert[i] = (self.grid_vert[i][0], self.grid_vert[i][1]+dy, self.grid_vert[i][2], self.grid_vert[i][3]+dy)
    #     for j in range(len(self.grid_horz)):
    #         self.grid_horz[j] = (self.grid_horz[j][0]+dx, self.grid_horz[j][1], self.grid_horz[j][2]+dx, self.grid_horz[j][3])

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
        size = int(self.imgsize*self.scale)
        show_cnt = 0
        self.canvas.delete(tk.ALL)
        self.tk_dict = {}
        for k in sorted(self.img_dict.keys()):
            if self.img_dict[k].x+self.imgsize*self.scale>self.window[0][0] and self.img_dict[k].x<self.window[0][1] and self.img_dict[k].y+self.imgsize*self.scale>self.window[1][0] and self.img_dict[k].y<self.window[1][1]:
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
        for k in sorted(self.tk_dict.keys()):
                # if is_scale:
                #     self.canvas.create_image(self.img_dict[k].x*self.scale, self.img_dict[k].y*self.scale, image=self.tk_dict[k], anchor='nw', tags=('img', k))
                # else:
                self.canvas.create_image(self.img_dict[k].x, self.img_dict[k].y, image=self.tk_dict[k], anchor='nw', tags=('img', k))
        if self.show_grid_flag:
            for e in self.grid_vert:
                self.canvas.create_line(e[0], e[1], e[2], e[3], fill='purple', width=self.grid_line_width, tags='coordline')
            for e in self.grid_horz:
                self.canvas.create_line(e[0], e[1], e[2], e[3], fill='purple', width=self.grid_line_width, tags='coordline')
            self.canvas.tag_raise('coordline')
        self.canvas.create_line(self.coord_central[0],-1e7,self.coord_central[0],1e7, width=self.coord_line_width, fill='blue', tags='baseline')
        self.canvas.create_line(-1e7,self.coord_central[1],1e7,self.coord_central[1], width=self.coord_line_width, fill='blue', tags='baseline')
        self.canvas.tag_raise('baseline')
        print 'current showing %s tiles with size %s, scale %s'%(show_cnt, size, self.scale)

    def init_binding(self):
        self.canvas.bind('<ButtonPress-1>', self.start_drag)
        self.canvas.bind('<ButtonRelease-1>', self.stop_drag)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.canvas.bind_all('<MouseWheel>', self.zoomer)
        self.canvas.bind('<Motion>', self.mouse_pos_callback)
        self.canvas.bind('<Double-Button-1>', self.mouse_db_click_callback)
        self.edit_history_listbox.bind('<Button-1>', self.single_click_callback)

    def run(self):
        self.root = tk.Tk()
        self.root.iconbitmap(default='D:/Workspace/map/map_dragging_validate/py/tkinter/quick.ico')
        self.root.title('Quicktron Texture Location Map Dispalyer')
        self.root.geometry('{}x{}'.format(1400,960))

        # self.top_frame = tk.Frame(self.root, height=30)
        self.control_frame = tk.Frame(self.root, width=120, height=960)
        self.canvas_frame = tk.Frame(self.root, width=1280, height=960)
        # self.top_frame.grid(row=0, columnspan=2, sticky='w')
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
        self.dropmenu.add_command(label='从salite导入', command=self.import_from_sqlite_callback)
        self.dropmenu.add_command(label='往sqlite导出', command=self.export_to_sqlite_callback)
        self.menubar.add_cascade(label='选项', menu=self.dropmenu)
        # self.menubar.config(background='#f0f0f0')

        # ------------------------------------------ 控制侧栏 ------------------------------------------

        self.donothing_t_3 = tk.Frame(self.control_frame, height=8, width=120)
        self.donothing_t_3.grid()
        self.show_global_map_btn = tk.Button(self.control_frame, text='点击查看全局地图', command=self.show_global_map_callback)
        self.show_global_map_btn.grid(sticky='', pady=2)

        self.donothing_0_1 = tk.Frame(self.control_frame, height=8, width=120)
        self.donothing_0_1.grid()
        self.donothing_0_2 = tk.Frame(self.control_frame, bg='#555', height=1, width=220)
        self.donothing_0_2.grid()
        self.donothing_0_3 = tk.Frame(self.control_frame, height=8, width=120)
        self.donothing_0_3.grid()

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
        self.mil2pix.set(0.40625)
        self.mil2pix_lbl = tk.Label(self.control_frame, text='毫米/像素')
        self.mil2pix_ent = tk.Entry(self.control_frame, textvariable=self.mil2pix)
        self.mil2pix_btn = tk.Button(self.control_frame, text='设定新的毫米/像素', command=self.mil2pix_btn_callback)
        self.mil2pix_lbl.grid(sticky='', pady=2)
        self.mil2pix_ent.grid(sticky='', pady=2)
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
        self.x_axis_gap_lbl = tk.Label(self.control_frame, text='x轴网格间距(mm)')
        self.x_axis_gap_ent = tk.Entry(self.control_frame, textvariable=self.x_axis_gap)
        self.y_axis_gap_lbl = tk.Label(self.control_frame, text='y轴网格间距(mm)')
        self.y_axis_gap_ent = tk.Entry(self.control_frame, textvariable=self.y_axis_gap)
        self.grid_gap_btn = tk.Button(self.control_frame, text='设定新网格间距', command=self.grid_gap_btn_callback)
        self.grid_show_btn = tk.Button(self.control_frame, textvariable=self.show_grid_str, command=self.grid_show_btn_callback)
        self.x_axis_gap_lbl.grid(sticky='', pady=2)
        self.x_axis_gap_ent.grid(sticky='', pady=2)
        self.y_axis_gap_lbl.grid(sticky='', pady=2)
        self.y_axis_gap_ent.grid(sticky='', pady=2)
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
        self.edit_mod_var.set('进入拖拽编辑模式')
        self.edit_mod_btn = tk.Button(self.control_frame, textvariable=self.edit_mod_var, command=self.edit_mod_callback)
        self.edit_mod_btn.grid(pady=2)

        self.edit_frame = tk.Frame(self.control_frame)
        self.edit_frame.grid(pady=2)
        self.edit_commit_btn = tk.Button(self.edit_frame, text='提交修改', command=self.edit_commit_callback)
        self.edit_abort_btn = tk.Button(self.edit_frame, text='放弃修改', command=self.edit_abort_callback)
        self.edit_commit_btn.grid(row=0, column=0, pady=2, padx=2)
        self.edit_abort_btn.grid(row=0, column=1, pady=2, padx=2)

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

        self.grid_width_val = tk.DoubleVar()
        self.coord_width_val = tk.DoubleVar()

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

        # self.finetune_btn = tk.Button(self.control_frame, text='打开地图微调', command=self.fintune_callback)
        # self.finetune_btn.grid(pady=2)

        # # TODO:
        # # 加入选中tile之后输入坐标偏移进行微调
        # # 加入编辑历史：1.可导出编辑历史日志 2.可根据单条历史进行编辑撤销

        # self.open_history_btn = tk.Button(self.control_frame, text='打开编辑历史', command=self.open_history_callback)
        # self.open_history_btn.grid(pady=2)

        # self.history_export_btn = tk.Button(self.control_frame, text='导出地图编辑历史', command=self.history_export_callback)
        # self.history_export_btn.grid(pady=2)
       
        self.root.resizable(width=False, height=False)
        self.root.configure(menu=self.menubar)
        self.reinit_everything()
        self.root.mainloop()


if __name__ == '__main__':
    mv = Mapviewer()
    mv.run()
