# coding:utf-8

'''
    Quicktron texture localization - ground texture map client
    powered by PyQt5
    support:
        * map viewing
        * HD map generation
        * map tile modification (manually shifting and rotation)
        * map data modification (sqlite DB and file, inserting, deleting)
        * map data transferring (DB to file / file to DB)
        * map data optimization (gradient updating)
        * etc.
    @author : xiao shanghua
    @mail   : xiaoshanghua@quicktron.com / hallazie@outlook.com
'''


import os
import sys
import logging
import traceback
import sqlite3
import numpy as np
import socket as sk
import reg_core
from PIL import Image as im
from PIL import  ImageQt as imq
from PyQt5.QtCore import Qt, QThread, QPointF, QPoint, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage, QTransform, QBrush, QPen, QColor, QDoubleValidator, QIcon
from PyQt5.QtWidgets import QWidget, QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsItem,  QHBoxLayout, QVBoxLayout, \
    QGraphicsPixmapItem, QPushButton, QLabel, QLineEdit, QFrame, QStatusBar, QAction, QListWidget, QListWidgetItem, QGraphicsLineItem, QErrorMessage, \
    QProgressBar, QFileDialog, QDialog, QMessageBox, QTableWidget, QTableWidgetItem
from PyQt5.QtOpenGL import QGLWidget

logging.basicConfig(level=logging.DEBUG)

M2PRATIO = 0.40625

class Image(QGraphicsItem):
    def __init__(self, idx, x, y, t):
        QGraphicsItem.__init__(self)
        self.idx = idx
        self.cx = x
        self.cy = y
        self.ct = t

class ImgInfObj:
    def __init__(self, idx, x, y, theta):
        self.idx = idx
        self.x = x
        self.y = y
        self.theta = theta

class LineSeparator(QFrame):
    def __init__(self):
        QFrame.__init__(self)
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)


class ThreadLoadPixPath(QThread):
    signal = pyqtSignal('PyQt_PyObject')
    def __init__(self, main_widget, path, kp_flag):
        QThread.__init__(self, main_widget)
        self.main_widget = main_widget
        self.isrunning = True
        self.path = path
        self.kp_flag = kp_flag

    def run(self):
        try:
            self.main_widget.canvas_view.setInteractive(False)
            self.main_widget.canvas_view.lock_zooming = True
            self.signal.emit('start:0')
            print('disabling canvas view interaction due to data loading...')
            self.main_widget.canvas_scene.clear_canvas()
            while self.isrunning:
                try:
                    for _, _, fs in os.walk(self.path):
                        total = len(fs)
                        self.signal.emit('min:%s' % 0)
                        self.signal.emit('max:%s' % len(fs))
                        current = 0
                        for f in fs:
                            file = self.path + '/' + f
                            idx = int(f[:-4].split('_')[0])
                            x = float(f[:-4].split('_')[1])
                            y = -1 * float(f[:-4].split('_')[2])
                            t = float(f[:-4].split('_')[3])
                            if idx not in self.main_widget.canvas_scene.pix_dict.keys():
                                pix = QPixmap(file)#.scaled(130, 130, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                                img = QGraphicsPixmapItem(pix)
                                img.setTransformOriginPoint(pix.width() // 2, pix.height() // 2)
                                img.setRotation(t + self.main_widget.canvas_scene.pix_rotate)
                                img.setPos(x / M2PRATIO - pix.width() // 2, y / M2PRATIO - pix.height() // 2)
                                img.setFlag(QGraphicsItem.ItemIsMovable)
                                img.cx = x
                                img.cy = y
                                img.ct = t
                                img.ox = x
                                img.oy = y
                                img.ot = t
                                img.idx = idx
                                img.kp_flag = self.kp_flag
                                self.main_widget.canvas_scene.pix_dict[idx] = img
                                self.main_widget.canvas_scene.maxx = max(x, self.main_widget.canvas_scene.maxx)
                                self.main_widget.canvas_scene.maxy = max(abs(y), self.main_widget.canvas_scene.maxy)
                                self.main_widget.canvas_scene.minx = min(x, self.main_widget.canvas_scene.minx)
                                self.main_widget.canvas_scene.miny = min(abs(y), self.main_widget.canvas_scene.miny)
                            current += 1
                            self.signal.emit('current:%s' % current)
                        break
                except Exception as e:
                    traceback.print_exc()
                self.isrunning = False
            self.main_widget.canvas_view.setInteractive(True)
            self.main_widget.canvas_view.lock_zooming = False
            # QApplication.restoreOverrideCursor()
            self.using_db = False
            print('enabling canvas view interaction...')
            self.signal.emit('stop:0')
        except Exception as e:
            traceback.print_exc()


class ThreadLoadPixDB(QThread):
    signal = pyqtSignal('PyQt_PyObject')
    def __init__(self, main_widget, path):
        QThread.__init__(self, main_widget)
        self.main_widget = main_widget
        self.isrunning = True
        self.path = path

    def run(self):
        try:
            self.main_widget.canvas_view.setInteractive(False)
            self.main_widget.canvas_view.lock_zooming = True
            # QApplication.setOverrideCursor(Qt.WaitCursor)
            self.signal.emit('start:0')
            print('disabling canvas view interaction due to data loading...')
            if not os.path.exists(self.path):
                self.signal.emit('error:数据库文件"%s"不存在'% self.path)
                # QMessageBox.critical(self.main_widget, '错误', '数据库文件"%s"不存在' % self.path)
                print('db not exist')
                return
            while self.isrunning:
                try:
                    conn = sqlite3.connect(self.path)
                    curs = conn.cursor()
                    cnt = curs.execute('select count(id) from zhdl_map').__next__()[0]
                    if cnt == 0:
                        # QMessageBox.critical(self.main_widget, '错误', '当前数据库中无有效地图文件')
                        self.signal.emit('error:当前数据库中无有效地图文件')
                        print('no valid images')
                        return
                except Exception as e:
                    traceback.print_exc()
                    # QMessageBox.critical(self.main_widget, '错误', '读取数据库出错，请正确配置数据库文件\n错误信息：%s' % e)
                    self.signal.emit('error:读取数据库出错，请正确配置数据库文件')
                    return
                res = curs.execute('select id, x, y, heading, raw_image from zhdl_map')
                # self.main_widget.canvas_scene.clear()
                self.main_widget.canvas_scene.clear_canvas()
                self.signal.emit('min:%s' % 0)
                self.signal.emit('max:%s' % cnt)
                current = 0
                while True:
                    try:
                        data = res.__next__()
                        idx = data[0]
                        x = data[1]
                        y = -1 * data[2]
                        t = data[3]
                        ttt = QImage(data[4], 320, 320, QImage.Format_Grayscale8)
                        pix = QPixmap.fromImage(ttt)#.scaled(130, 130, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        img = QGraphicsPixmapItem(pix)
                        img.setTransformOriginPoint(pix.width() // 2, pix.height() // 2)
                        img.setRotation(t + self.main_widget.canvas_scene.pix_rotate)
                        img.setPos(x / M2PRATIO - pix.width() // 2, y / M2PRATIO - pix.height() // 2)
                        img.setFlag(QGraphicsItem.ItemIsMovable)
                        img.cx = x
                        img.cy = y
                        img.ct = t
                        img.ox = x
                        img.oy = y
                        img.ot = t
                        img.idx = idx
                        img.kp_flag = False
                        self.main_widget.canvas_scene.pix_dict[idx] = img
                        self.main_widget.canvas_scene.maxx = max(x, self.main_widget.canvas_scene.maxx)
                        self.main_widget.canvas_scene.maxy = max(abs(y), self.main_widget.canvas_scene.maxy)
                        self.main_widget.canvas_scene.minx = min(x, self.main_widget.canvas_scene.minx)
                        self.main_widget.canvas_scene.miny = min(abs(y), self.main_widget.canvas_scene.miny)
                        current += 1
                        self.signal.emit('current:%s' % current)
                    except Exception as e:
                        traceback.print_exc()
                        break
                self.isrunning = False
            self.main_widget.canvas_view.setInteractive(True)
            self.main_widget.canvas_view.lock_zooming = False
            # QApplication.restoreOverrideCursor()
            self.using_db = True
            print('enabling canvas view interaction...')
            self.signal.emit('stop:0')

            with open(os.path.dirname(os.path.realpath(__file__))+os.path.sep+'mapviewer.cfg', 'w+') as f:
                for line in f.readlines():
                    k, w = line.replace(' ', '').split('=')
                    self.main_widget.configfile[k] = w
                self.main_widget.configfile['DBPATH'] = self.path
                w = '\n'.join([k + '=' + self.main_widget.configfile[k] for k in self.main_widget.configfile.keys()])
                f.write(w)
        except Exception as e:
            traceback.print_exc()


class ThreadExportPixDB(QThread):
    signal = pyqtSignal('PyQt_PyObject')
    def __init__(self, main_widget, export_db_path):
        QThread.__init__(self, main_widget)
        self.main_widget = main_widget
        self.export_db_path = export_db_path

    def run(self):
        try:
            self.signal.emit('start:0')
            self.signal.emit('min:%s' % 0)
            self.signal.emit('max:%s' % len(self.main_widget.canvas_scene.pix_dict))
            current = 0
            conn = sqlite3.connect(self.export_db_path)
            curs = conn.cursor()
            for k in self.main_widget.canvas_scene.pix_dict:
                itm = self.main_widget.canvas_scene.pix_dict[k]
                curs.execute('insert into zhdl_map values (?,?,?,?,?,?)', (
                    k,
                    itm.ox,
                    itm.oy,
                    itm.ot,
                    None,
                    # imq.fromqpixmap(itm.pixmap()).tobytes(),
                    np.array(imq.fromqpixmap(itm.pixmap()).convert('L')).astype('uint8').flatten().tobytes()
                ))
                current += 1
                self.signal.emit('current:%s' % current)
            conn.commit()
            conn.close()
            self.signal.emit('stop:0')
        except Exception as e:
            traceback.print_exc()


class ThreadHDGlobalMap(QThread):
    signal = pyqtSignal('PyQt_PyObject')
    def __init__(self, main_widget):
        QThread.__init__(self, main_widget)
        self.main_widget = main_widget
        self.isrunning = True

    def run(self):
        try:
            self.signal.emit('start:0')
            self.signal.emit('min:%s' % 0)
            self.signal.emit('max:%s' % len(self.main_widget.canvas_scene.pix_dict))
            current = 0
            width_max = 10240
            height_max = 10240
            canvas_width_param = self.main_widget.canvas_scene.maxx - self.main_widget.canvas_scene.minx + 2000
            canvas_height_param = self.main_widget.canvas_scene.maxy - self.main_widget.canvas_scene.miny + 2000
            if canvas_width_param > canvas_height_param:
                gv_width = width_max
                zoom_scale = float(width_max) / canvas_width_param
                gv_height = int(width_max * canvas_height_param / canvas_width_param)
            else:
                gv_height = height_max
                zoom_scale = float(height_max) / canvas_height_param
                gv_width = int(height_max * canvas_width_param / canvas_height_param)
            img_scale = max(int(320 * zoom_scale * M2PRATIO), 1)
            # gv_canvas = np.zeros((gv_width, gv_height))
            gv_canvas = im.new('L', (gv_width, gv_height))
            for k in self.main_widget.canvas_scene.pix_dict:
                itm = self.main_widget.canvas_scene.pix_dict[k]
                img = imq.fromqpixmap(itm.pixmap()).convert('L').resize((img_scale, img_scale))
                rot = self.main_widget.canvas_scene.pix_dict[k].ot - self.main_widget.canvas_scene.pix_rotate
                arr = np.array(img.convert('RGBA'))
                arr[:, :, 3] = (arr[:, :, 0] + arr[:, :, 1] + arr[:, :, 2] != 0) * arr[:, :, 3]
                gmi = im.fromarray(arr.astype('uint8')).rotate(rot, expand=True)
                shift = (gmi.size[0] - img_scale) // 2
                pos_x = int(gv_width * ((itm.ox - shift) - self.main_widget.canvas_scene.minx + 1000) / canvas_width_param)
                pos_y = int(gv_height * ((-1 * itm.oy + shift) - self.main_widget.canvas_scene.miny + 1000) / canvas_height_param)
                gv_canvas.paste(gmi, (pos_x-img_scale//2, gv_height - (pos_y - img_scale//2)), gmi)
                print('x:%s|%s\ty:%s|%s' % (pos_x, itm.ox, pos_y, itm.oy))
                print('x:%s\ty:%s\tt:%s' % (pos_x, pos_y, rot))
                current += 1
                self.signal.emit('current:%s' % current)

            # gv_image = im.fromarray(gv_canvas.transpose().astype('uint8'))
            gv_canvas.save(os.path.dirname(os.path.realpath(__file__))+os.path.sep + '/'+'hd_global_viewmap.png')
            gv_canvas.show()
            self.signal.emit('stop:0')
        except Exception as e:
            traceback.print_exc()


class ThreadGlobalMap(QThread):
    signal = pyqtSignal('PyQt_PyObject')
    def __init__(self, gv_dialog, main_widget):
        QThread.__init__(self, gv_dialog)
        self.gv_dialog = gv_dialog
        self.main_widget = main_widget
        self.isrunning = True

    def run(self):
        try:
            self.signal.emit('start:0')
            self.signal.emit('min:%s' % 0)
            self.signal.emit('max:%s' % len(self.main_widget.canvas_scene.pix_dict))
            width_max = 960
            height_max = 640
            canvas_width_param = self.main_widget.canvas_scene.maxx - self.main_widget.canvas_scene.minx + 2000
            canvas_height_param = self.main_widget.canvas_scene.maxy - self.main_widget.canvas_scene.miny + 2000
            if canvas_width_param > canvas_height_param:
                self.gv_dialog.gv_width = width_max
                self.gv_dialog.zoom_scale = float(width_max) / canvas_width_param
                self.gv_dialog.gv_height = int(width_max * canvas_height_param / canvas_width_param)
            else:
                self.gv_dialog.gv_height = height_max
                self.gv_dialog.zoom_scale = float(height_max) / canvas_height_param
                self.gv_dialog.gv_width = int(height_max * canvas_width_param / canvas_height_param)
            img_scale = max(int(320 * self.gv_dialog.zoom_scale * M2PRATIO), 1)
            self.gv_dialog.gv_canvas = np.zeros((self.gv_dialog.gv_width, self.gv_dialog.gv_height))
            current = 0
            for k in self.main_widget.canvas_scene.pix_dict:
                try:
                    itm = self.main_widget.canvas_scene.pix_dict[k]
                    arr = np.array(imq.fromqpixmap(itm.pixmap()).convert('L').resize((img_scale, img_scale)))
                    pos_x = int(self.gv_dialog.gv_width * (itm.ox - self.main_widget.canvas_scene.minx + 1000) / canvas_width_param)
                    pos_y = int(self.gv_dialog.gv_height * (-1 * itm.oy - self.main_widget.canvas_scene.miny + 1000) / canvas_height_param)
                    self.gv_dialog.gv_canvas[pos_x-img_scale//2:pos_x-img_scale//2+img_scale, pos_y-img_scale//2:pos_y-img_scale//2+img_scale] = arr
                except Exception as e:
                    traceback.print_exc()
                finally:
                    current += 1
                    self.signal.emit('current:%s' % current)
            self.gv_dialog.gv_image = im.fromarray(np.flip(self.gv_dialog.gv_canvas.transpose().astype('uint8'), 0))
            self.gv_dialog.gv_pixmap = imq.toqpixmap(self.gv_dialog.gv_image)
            self.signal.emit('stop:0')
        except Exception as e:
            traceback.print_exc()


class ThreadSocket(QThread):
    signal = pyqtSignal('PyQt_PyObject')
    def __init__(self, main_widget):
        QThread.__init__(self, main_widget)
        self.main_widget = main_widget
        self.isrunning = True

    def run(self):
        try:
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
                try:
                    data, _ = self.sock.recvfrom(672)
                    if len(data) != 672:
                        continue
                    self.sk_frame_id = ord(data[6]) * 256 + ord(data[7])
                    self.sk_line_idx = ord(data[8]) * 256 + ord(data[9])
                    if self.sk_line_idx == 0:
                        self.bmp = ''
                    self.bmp += data[32:]
                    if self.sk_line_idx == 479 and len(self.bmp) == 480 * 640:
                        self.sk_frame_id_curr = self.sk_frame_id
                        arr = np.fromstring(self.bmp, dtype='uint8').reshape((480, 640))
                        self.sk_image = im.fromarray(arr)

                        self.bmp = ''
                except Exception as e:
                    self.bmp = ''
                    print('sock_loop inner ' + str(e))
        except Exception as e:
            traceback.print_exc()


class ThreadGenBaseData(QThread):
    signal = pyqtSignal('PyQt_PyObject')
    def __init__(self, main_widget):
        QThread.__init__(self, main_widget)
        self.main_widget = main_widget
        self.isrunning = True
        self.reg = reg_core.reg_core()
        self.reg.initialize(640, 480, 8, os.path.dirname(os.path.realpath(__file__)) + os.path.sep + 'caliberation.values', 0)

    def run(self):
        try:
            self.signal.emit('start:0')
            self.signal.emit('min:0')
            self.signal.emit('max:1')
            gen_raw_path = self.main_widget.gen_raw_path.replace('/', '\\\\')
            gen_key_path = self.main_widget.gen_key_path.replace('/', '\\\\')
            gen_nod_path = self.main_widget.gen_nod_path.replace('/', '\\\\')
            if not os.path.exists(gen_raw_path):
                os.mkdir(gen_raw_path)
            if not os.path.exists(gen_key_path):
                os.mkdir(gen_key_path)
            if not os.path.exists(gen_nod_path):
                os.mkdir(gen_nod_path)
            self.reg.find_and_save_key(gen_raw_path, gen_key_path, gen_nod_path)
            self.signal.emit('current:1')
            QMessageBox.information(self, '提示', '基础数据已生成完成，请对标注点进行修正')
            self.main_widget.main_window.raw_path = gen_key_path
            self.signal.emit('stop:0')
        except Exception as e:
            traceback.print_exc()


class ThreadGenDB(QThread):
    signal = pyqtSignal('PyQt_PyObject')
    def __init__(self, main_widget):
        QThread.__init__(self, main_widget)
        self.main_widget = main_widget
        self.isrunning = True
        self.reg = reg_core.reg_core()
        self.reg.initialize(640, 480, 8, os.path.dirname(os.path.realpath(__file__)) + os.path.sep + 'caliberation.values', 0)

    def run(self):
        self.signal.emit('start:0')
        db_path = self.main_widget.gen_db_path
        db_name = self.main_widget.gen_db_name
        if not db_name.lower().endswith('.db'):
            db_name += '.db'
        db_full = db_path + '/' + db_name
        if os.path.exists(db_full):
            QMessageBox.warning(self, '错误', '数据库文件 "%s" 已存在'%db_full)
            return
        if not os.path.exists(self.main_widget.gen_key_path) or not os.path.exists(self.main_widget.gen_nod_path):
            QMessageBox.warning(self, '错误', '基础数据集路径配置错误')
            return
        try:
            self.signal.emit('start:1')
            conn = sqlite3.connect(db_full)
            create_raw_str = '''
                create table if not exists zhdl_raw (
                    id integer primary key,
                    timestamp integer,
                    device_num integer,
                    speed real,
                    x real not null,
                    y real not null,
                    theta real not null,
                    image blob not null,
                    is_keypoint integer not null,
                    pairid integer
                );
            '''
            create_map_str = '''
                create table if not exists zhdl_map (
                    id integer primary key,
                    x real not null,
                    y real not null,
                    heading real not null,
                    processed_image blob,
                    raw_image blob
                );
            '''
            create_link_str = '''
                create table if not exists zhdl_link (
                    id integer primary key,
                    raw_id integer not null,
                    link_id integer not null,
                    x real not null,
                    y real not null,
                    theta real not null,
                    is_keypoint integer not null
                );
            '''
            curs = conn.cursor()
            curs.execute(create_raw_str)
            curs.execute(create_map_str)
            curs.execute(create_link_str)
            conn.commit()
            self.signal.emit('start:2')
            gen_key_list = []
            gen_node_list = []
            for _,_,fs in os.walk(self.main_widget.gen_key_path):
                if len(fs) == 0:
                    QMessageBox.warning(self, '错误', '关键节点数据路径中无有效数据')
                    os.remove(db_full)
                    return
                self.signal.emit('min:0')
                self.signal.emit('max:%s'%len(fs))
                current = 0
                for f in fs:
                    idx, x, y, theta = f[:-4].split('_')
                    curs.execute('insert into zhdl_raw values (?,?,?,?,?,?,?,?,?,?)',(
                        int(idx),
                        0,
                        0,
                        0.3,
                        float(x),
                        float(y),
                        float(theta),
                        np.array(im.open(self.main_widget.gen_key_path+'/'+f)).astype('uint8').flatten().tobytes(),
                        1,
                        0,
                    ))
                    current += 1
                    self.signal.emit('current:%s'%current)
                    gen_key_list.append(ImgInfObj(int(idx), float(x), float(y), float(theta)))
            for _,_,fs in os.walk(self.main_widget.gen_nod_path):
                if len(fs) == 0:
                    QMessageBox.warning(self, '错误', '普通键节点数据路径中无有效数据')
                    os.remove(db_full)
                    return
                self.signal.emit('min:0')
                self.signal.emit('max:%s'%len(fs))
                current = 0
                for f in fs:
                    idx, x, y, theta = f[:-4].split('_')
                    curs.execute('insert into zhdl_raw values (?,?,?,?,?,?,?,?,?,?)',(
                        int(idx),
                        0,
                        0,
                        0.3,
                        float(x),
                        float(y),
                        float(theta),
                        np.array(im.open(self.nodeset_path_val.get()+'/'+f)).astype('uint8').flatten().tobytes(),
                        0,
                        0,
                    ))
                    current += 1
                    self.signal.emit('current:%s'%current)
                    gen_node_list.append(ImgInfObj(int(idx), float(x), float(y), float(theta)))
            conn.commit()

            # --------- 生成keypair ---------
            gen_pair_list = self.gen_find_all_key_pairs(gen_key_list)
            gen_link_list = []
            for e in gen_pair_list:
                gen_link_list.append([e[0]])
            for i in range(len(gen_node_list)):
                for k in range(len(gen_pair_list)):
                    if self.gen_find_node_inside_key_pair(gen_pair_list[k], gen_node_list[i]):
                        gen_link_list[k].append(gen_node_list[i])
            for k in range(len(gen_pair_list)):
                gen_link_list[k].append(gen_pair_list[k][1])

            # --------- 存入keypair ---------
            gen_link_idx = 1
            self.signal.emit('min:0')
            self.signal.emit('max:%s' % len(gen_link_list))
            current = 0
            for k in range(len(gen_link_list)):
                for i in range(len(gen_link_list[k])):
                    is_keypoint = 1 if i==0 or i==len(gen_link_list[k])-1 else 0
                    curs.execute('insert into zhdl_link values (?,?,?,?,?,?,?)', (
                        gen_link_idx,
                        gen_link_list[k][i].idx,
                        k,
                        gen_link_list[k][i].x,
                        gen_link_list[k][i].y,
                        gen_link_list[k][i].theta,
                        is_keypoint,
                        ))
                    gen_link_idx += 1
                current += 1
                self.signal.emit('current:%s' % current)
            conn.commit()

            # --------- 读入新数据并保存preprocessed ---------
            self.signal.emit('msg:正在生成 zhdl_map 数据表...')
            self.reg.gen_map_db(db_full.replace('/', '\\'))
            self.main_widget.main_window.db_path = db_full
            QMessageBox.information(self, '提示', '数据库创建成功')
            self.signal.emit('stop:0')
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, '错误', '数据库创建失败，错误信息：\n%s'%e)
            if os.path.exists(db_full):
                os.remove(db_full)
        finally:
            conn.close()

    def gen_find_all_key_pairs(self, key_list):
        pair_list = []
        for i in range(len(key_list)):
            for j in range(len(key_list)):
                if i != j:
                    inf1 = key_list[i]
                    inf2 = key_list[j]
                    if(tuple((inf1, inf2)) not in pair_list and tuple((inf2, inf1)) not in pair_list and abs(inf1.x-inf2.x)<1100 and abs(inf1.y-inf2.y)<1100 and self.euc_dis(inf1.x, inf1.y, inf2.x, inf2.y)<1100):
                        pair_list.append(tuple((inf1, inf2)))
        return pair_list

    def gen_find_node_inside_key_pair(self, kp, node):
        mid_x = (kp[0].x + kp[1].x) / 2.
        mid_y = (kp[0].y + kp[1].y) / 2.
        if abs(kp[0].x-kp[1].x) > abs(kp[0].y-kp[1].y):
            # 水平的link
            if abs(mid_x - node.x) < 500 and abs(mid_y - node.y) < 25:
                return True
            else:
                return False
        else:
            if abs(mid_y - node.y) < 500 and abs(mid_x - node.x) < 25:
                return True
            else:
                return False

# ------------------------------------------------- dialogs ------------------------------------------------------------


class MvAbout(QDialog):
    def __init__(self):
        QDialog.__init__(self)
        self.setGeometry(320, 120, 480, 480)
        self.box = QVBoxLayout()
        self.lbl001 = QLabel('Quicktron')
        self.lbl002 = QLabel('Texture Localization')
        self.lbl003 = QLabel('the about information will be listed here, currently have none.')
        self.box.addWidget(self.lbl001)
        self.box.addWidget(self.lbl002)
        self.box.addWidget(LineSeparator())
        self.box.addWidget(self.lbl003)
        self.box.addStretch(1)
        self.setLayout(self.box)
        self.setWindowTitle('快仓纹理定位地图管理器')
        self.setWindowIcon(QIcon(os.path.dirname(os.path.realpath(__file__)) + os.path.sep + 'ico.ico'))


class MvGlobalView(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        try:
            self.main_widget = parent
            self.gv_width = 100
            self.gv_height = 100
            self.zoom_scale = 0
            self.gv_canvas = None
            self.gv_image = None
            self.gv_pixmap = None
            self.vbox = QVBoxLayout()
            self.gv_lbl_image = QLabel()
            if self.main_widget.canvas_view.scene.gv_image == None:
                self.gen_global_view()
            else:
                self.gv_image = self.main_widget.canvas_view.scene.gv_image
                self.gv_pixmap = imq.toqpixmap(self.gv_image)
                self.gv_lbl_image.setPixmap(self.gv_pixmap)
                self.vbox.addWidget(self.gv_lbl_image)
                self.setWindowTitle('global view')
                self.setGeometry(320, 120, self.gv_pixmap.width(), self.gv_pixmap.height())
                self.setLayout(self.vbox)
                self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowSystemMenuHint)
                self.setFixedSize(self.gv_pixmap.width(), self.gv_pixmap.height())
                self.show()

        except Exception as e:
            traceback.print_exc()

    def gen_global_view(self):
        try:
            # width_max = 960
            # height_max = 640
            # canvas_width_param = self.main_widget.canvas_scene.maxx - self.main_widget.canvas_scene.minx + 2000
            # canvas_height_param = self.main_widget.canvas_scene.maxy - self.main_widget.canvas_scene.miny + 2000
            # if canvas_width_param > canvas_height_param:
            #     self.gv_width = width_max
            #     self.zoom_scale = float(width_max) / canvas_width_param
            #     self.gv_height = int(width_max * canvas_height_param / canvas_width_param)
            # else:
            #     self.gv_height = height_max
            #     self.zoom_scale = float(height_max) / canvas_height_param
            #     self.gv_width = int(height_max * canvas_width_param / canvas_height_param)
            # img_scale = max(int(320 * self.zoom_scale * M2PRATIO), 1)
            # self.gv_canvas = np.zeros((self.gv_width, self.gv_height))
            # for k in self.main_widget.canvas_scene.pix_dict:
            #     try:
            #         itm = self.main_widget.canvas_scene.pix_dict[k]
            #         arr = np.array(imq.fromqpixmap(itm.pixmap()).convert('L').resize((img_scale, img_scale)))
            #         pos_x = int(self.gv_width * (itm.ox - self.main_widget.canvas_scene.minx + 1000) / canvas_width_param)
            #         pos_y = int(self.gv_height * (-1 * itm.oy - self.main_widget.canvas_scene.miny + 1000) / canvas_height_param)
            #         self.gv_canvas[pos_x-img_scale//2:pos_x-img_scale//2+img_scale, pos_y-img_scale//2:pos_y-img_scale//2+img_scale] = arr
            #     except Exception as e:
            #         traceback.print_exc()
            # self.gv_image = im.fromarray(np.flip(self.gv_canvas.transpose().astype('uint8'), 0))
            # self.gv_pixmap = imq.toqpixmap(self.gv_image)
            # self.main_widget.canvas_view.scene.gv_image = self.gv_image
            # self.gv_image.save(os.path.dirname(os.path.realpath(__file__))+os.path.sep + '/'+'global_view.png')

            self.gv_thread = ThreadGlobalMap(self, self.main_widget)
            self.gv_thread.start()
            self.gv_thread.signal.connect(self.main_widget.main_window.handle_progress_bar)
            self.gv_thread.finished.connect(self.gv_thread_finished_handler)
            # self.gv_thread.finished.connect()

        except Exception as e:
            traceback.print_exc()

    def gv_thread_finished_handler(self):
        self.main_widget.canvas_view.scene.gv_image = self.gv_image
        self.gv_image.save(os.path.dirname(os.path.realpath(__file__)) + os.path.sep + '/' + 'global_view.png')
        self.gv_lbl_image.setPixmap(self.gv_pixmap)
        self.vbox.addWidget(self.gv_lbl_image)
        self.setWindowTitle('global view')
        self.setGeometry(320, 120, self.gv_pixmap.width(), self.gv_pixmap.height())
        self.setLayout(self.vbox)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowSystemMenuHint)
        self.setFixedSize(self.gv_pixmap.width(), self.gv_pixmap.height())
        self.show()

    def mousePressEvent(self, event):
        c_x = event.x()
        c_y = event.y()
        c_w = self.gv_pixmap.width()
        c_h = self.gv_pixmap.height()
        s_x = (float(c_x) / c_w) * abs(self.main_widget.canvas_view.scene.maxx - self.main_widget.canvas_view.scene.minx + 2000) + self.main_widget.canvas_view.scene.minx - 1000
        s_y = (1- float(c_y) / c_h) * abs(self.main_widget.canvas_view.scene.maxy - self.main_widget.canvas_view.scene.miny + 2000) + self.main_widget.canvas_view.scene.miny - 1000
        self.main_widget.canvas_view.centerOn(s_x / M2PRATIO, -1 * s_y / M2PRATIO)

class MvSocket(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.main_widget = parent
        self.setGeometry(320, 120, 860, 520)
        self.setFixedSize(860, 520)
        self.setWindowTitle('图像采集接口')
        self.box_root = QHBoxLayout()

        self.box_sk_record = QVBoxLayout()
        self.lst_sk_record = QListWidget()
        self.btn_sk_remove = QPushButton('删除当前图像')
        self.btn_sk_remove.setDisabled(True)
        self.btn_sk_remove.clicked.connect(self.handle_remove_photo)

        self.box_sk_canvas = QVBoxLayout()
        self.lbl_sk_canvas = QLabel()
        self.lbl_sk_canvas.setPixmap(imq.toqpixmap(im.new('L', (640, 480))))
        self.box_sk_param = QHBoxLayout()
        self.lbl_param_x = QLabel('x值：')
        self.ent_param_x = QLineEdit()
        self.ent_param_x.setValidator(QDoubleValidator())
        self.lbl_param_y = QLabel('y值：')
        self.ent_param_y = QLineEdit()
        self.ent_param_y.setValidator(QDoubleValidator())
        self.lbl_param_t = QLabel('θ值：')
        self.ent_param_t = QLineEdit()
        self.ent_param_t.setValidator(QDoubleValidator())
        self.btn_commit = QPushButton('采集当前图像')
        self.btn_commit.setFixedWidth(120)
        self.btn_commit.clicked.connect(self.handle_commit_photo)

        self.box_sk_record.addWidget(self.lst_sk_record)
        self.box_sk_record.addWidget(self.btn_sk_remove)
        self.box_sk_canvas.addWidget(self.lbl_sk_canvas)
        self.box_sk_param.addWidget(self.lbl_param_x)
        self.box_sk_param.addWidget(self.ent_param_x)
        self.box_sk_param.addWidget(self.lbl_param_y)
        self.box_sk_param.addWidget(self.ent_param_y)
        self.box_sk_param.addWidget(self.lbl_param_t)
        self.box_sk_param.addWidget(self.ent_param_t)
        self.box_sk_param.addWidget(self.btn_commit)
        self.box_sk_canvas.addLayout(self.box_sk_param)
        self.box_root.addLayout(self.box_sk_record)
        self.box_root.addLayout(self.box_sk_canvas)
        self.setLayout(self.box_root)

    def handle_commit_photo(self):
        pass

    def handle_remove_photo(self):
        pass

class MvPreference(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.main_widget = parent
        self.socket_path = ''

        self.setGeometry(320, 120, 480, 480)
        self.setWindowTitle('Preference')
        self.box_root = QVBoxLayout()

        self.box_dis_ttl = QHBoxLayout()
        self.lin_dis_ttl = LineSeparator()
        self.lbl_dis_ttl = QLabel('显示')
        self.box_dis_grid_width = QHBoxLayout()
        self.lbl_dis_grid_width = QLabel('网格线宽度')
        self.ent_dis_grid_width = QLineEdit(str(self.main_widget.canvas_scene.grid_width))
        self.ent_dis_grid_width.setValidator(QDoubleValidator())
        self.ent_dis_grid_width.setFixedWidth(120)
        self.box_dis_coord_width = QHBoxLayout()
        self.lbl_dis_coord_width = QLabel('坐标线宽度')
        self.ent_dis_coord_width = QLineEdit('1.')
        self.ent_dis_coord_width.setValidator(QDoubleValidator())
        self.ent_dis_coord_width.setFixedWidth(120)
        self.box_dis_rotate = QHBoxLayout()
        self.lbl_dis_rotate = QLabel('旋转角度  ')
        self.ent_dis_rotate = QLineEdit(str(self.main_widget.canvas_scene.pix_rotate))
        self.ent_dis_rotate.setValidator(QDoubleValidator())
        self.ent_dis_rotate.setFixedWidth(120)

        self.box_sok_ttl = QHBoxLayout()
        self.lin_sok_ttl = LineSeparator()
        self.lbl_sok_ttl = QLabel('图像采集')
        self.box_sok_path = QHBoxLayout()
        self.btn_sok_path = QPushButton('图像采集保存路径')
        self.btn_sok_path.clicked.connect(self.handle_socket_path)
        self.btn_sok_path.setFixedWidth(120)
        self.lbl_sok_path = QLabel(self.main_widget.socket_save_path)

        self.box_commit = QHBoxLayout()
        self.btn_commit = QPushButton('确认')
        self.btn_commit.clicked.connect(self.handle_pref_commit)
        self.btn_abort = QPushButton('放弃')
        self.btn_abort.clicked.connect(self.handle_pref_abort)
        self.btn_commit.setFixedWidth(80)
        self.btn_abort.setFixedWidth(80)

        self.lbl_dis_ttl.setFixedWidth(26)
        self.box_dis_ttl.addWidget(self.lbl_dis_ttl)
        self.box_dis_ttl.addWidget(self.lin_dis_ttl)
        self.box_root.addLayout(self.box_dis_ttl)
        self.box_dis_grid_width.addWidget(self.lbl_dis_grid_width)
        self.box_dis_grid_width.addWidget(self.ent_dis_grid_width)
        self.box_dis_grid_width.addStretch(1)
        self.box_root.addLayout(self.box_dis_grid_width)
        self.box_dis_coord_width.addWidget(self.lbl_dis_coord_width)
        self.box_dis_coord_width.addWidget(self.ent_dis_coord_width)
        self.box_dis_coord_width.addStretch(1)
        self.box_root.addLayout(self.box_dis_coord_width)
        self.box_dis_rotate.addWidget(self.lbl_dis_rotate)
        self.box_dis_rotate.addWidget(self.ent_dis_rotate)
        self.box_dis_rotate.addStretch(1)
        self.box_root.addLayout(self.box_dis_rotate)
        self.box_root.addSpacing(10)
        self.lbl_sok_ttl.setFixedWidth(48)
        self.box_sok_ttl.addWidget(self.lbl_sok_ttl)
        self.box_sok_ttl.addWidget(self.lin_sok_ttl)
        self.box_root.addLayout(self.box_sok_ttl)
        self.box_sok_path.addWidget(self.btn_sok_path)
        self.box_sok_path.addWidget(self.lbl_sok_path)
        self.box_root.addLayout(self.box_sok_path)
        self.box_root.addSpacing(10)
        self.box_root.addStretch(1)
        self.box_commit.addStretch(1)
        self.box_commit.addWidget(self.btn_commit)
        self.box_commit.addWidget(self.btn_abort)
        self.box_root.addLayout(self.box_commit)
        self.setLayout(self.box_root)

    def handle_socket_path(self):
        self.socket_path = os.path.normpath(QFileDialog.getExistingDirectory(self)).replace('\\', '/')
        self.lbl_sok_path.setText(self.socket_path)

    def handle_pref_commit(self):
        try:
            self.main_widget.canvas_scene.pix_rotate = float(self.ent_dis_rotate.text())
            self.main_widget.canvas_scene.grid_width = float(self.ent_dis_grid_width.text())
            self.main_widget.socket_save_path = self.socket_path
            self.main_widget.canvas_scene.reload_pixmaps()
            self.close()
        except Exception as e:
            traceback.print_exc()

    def handle_pref_abort(self):
        try:
            reply = QMessageBox.question(self, '提示', '确认退出？参数将不被修改', QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.close()
            else:
                pass
        except Exception as e:
            traceback.print_exc()


class MvGenConfig(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.main_widget = parent

        self.setGeometry(320, 120, 480, 480)
        self.setFixedSize(480, 480)
        self.setWindowTitle('梯度下降参数设置')
        self.box_root = QVBoxLayout()

        self.box_raw_data = QHBoxLayout()
        self.btn_raw_data = QPushButton('行车采集数据路径')
        self.btn_raw_data.clicked.connect(self.handle_ask_raw_data_path)
        self.val_raw_data = self.main_widget.gen_raw_path
        self.lbl_raw_data = QLabel()
        self.lbl_raw_data.setText(self.val_raw_data)
        self.box_key_data = QHBoxLayout()
        self.btn_key_data = QPushButton('关键节点保存路径')
        self.btn_key_data.clicked.connect(self.handle_ask_key_data_path)
        self.val_key_data = self.main_widget.gen_key_path
        self.lbl_key_data = QLabel()
        self.lbl_key_data.setText(self.val_key_data)
        self.box_nod_data = QHBoxLayout()
        self.btn_nod_data = QPushButton('中间节点保存路径')
        self.btn_nod_data.clicked.connect(self.handle_ask_nod_data_path)
        self.val_nod_data = self.main_widget.gen_nod_path
        self.lbl_nod_data = QLabel()
        self.lbl_nod_data.setText(self.val_nod_data)

        self.box_db_path = QHBoxLayout()
        self.btn_db_path = QPushButton('数据库保存路径')
        self.btn_db_path.clicked.connect(self.handle_ask_db_path)
        self.val_db_path = self.main_widget.gen_db_path
        self.lbl_db_path = QLabel()
        self.lbl_db_path.setText(self.val_db_path)
        self.box_db_name = QHBoxLayout()
        self.lbl_db_name = QLabel('数据库名')
        self.ent_db_name = QLineEdit()
        self.ent_db_name.setText(self.main_widget.gen_db_name)

        self.box_param = QHBoxLayout()
        self.lbl_x_rate = QLabel('x-学习率：')
        self.ent_x_rate = QLineEdit()
        self.ent_x_rate.setValidator(QDoubleValidator())
        self.ent_x_rate.setText(str(self.main_widget.gen_x_rate))
        self.lbl_y_rate = QLabel('y-学习率：')
        self.ent_y_rate = QLineEdit()
        self.ent_y_rate.setValidator(QDoubleValidator())
        self.ent_y_rate.setText(str(self.main_widget.gen_y_rate))
        self.lbl_t_rate = QLabel('θ-学习率：')
        self.ent_t_rate = QLineEdit()
        self.ent_t_rate.setValidator(QDoubleValidator())
        self.ent_t_rate.setText(str(self.main_widget.gen_t_rate))
        self.lbl_epochs = QLabel('迭代次数：')
        self.ent_epochs = QLineEdit()
        self.ent_epochs.setValidator(QDoubleValidator())
        self.ent_epochs.setText(str(self.main_widget.gen_epochs))

        self.box_commit = QHBoxLayout()
        self.btn_commit = QPushButton('提交参数')
        self.btn_commit.clicked.connect(self.handle_gen_commit_param)
        self.btn_abort = QPushButton('放弃参数')
        self.btn_abort.clicked.connect(self.handle_gen_abort_param)

        self.init_dialog()

    def init_dialog(self):
        self.btn_raw_data.setFixedWidth(120)
        self.btn_key_data.setFixedWidth(120)
        self.btn_nod_data.setFixedWidth(120)
        self.btn_db_path.setFixedWidth(120)
        self.ent_db_name.setFixedWidth(120)
        self.box_raw_data.addWidget(self.btn_raw_data)
        self.box_raw_data.addWidget(self.lbl_raw_data)
        self.box_key_data.addWidget(self.btn_key_data)
        self.box_key_data.addWidget(self.lbl_key_data)
        self.box_nod_data.addWidget(self.btn_nod_data)
        self.box_nod_data.addWidget(self.lbl_nod_data)
        self.box_root.addLayout(self.box_raw_data)
        self.box_root.addLayout(self.box_key_data)
        self.box_root.addLayout(self.box_nod_data)
        self.box_root.addWidget(LineSeparator())
        self.box_db_path.addWidget(self.btn_db_path)
        self.box_db_path.addWidget(self.lbl_db_path)
        self.box_db_name.addWidget(self.lbl_db_name)
        self.box_db_name.addWidget(self.ent_db_name)
        self.box_db_name.addStretch(1)
        self.box_root.addLayout(self.box_db_path)
        self.box_root.addLayout(self.box_db_name)
        self.box_root.addWidget(LineSeparator())
        self.box_param.addWidget(self.lbl_x_rate)
        self.box_param.addWidget(self.ent_x_rate)
        self.box_param.addWidget(self.lbl_y_rate)
        self.box_param.addWidget(self.ent_y_rate)
        self.box_param.addWidget(self.lbl_t_rate)
        self.box_param.addWidget(self.ent_t_rate)
        self.box_param.addWidget(self.lbl_epochs)
        self.box_param.addWidget(self.ent_epochs)
        self.box_root.addLayout(self.box_param)
        self.box_root.addWidget(LineSeparator())
        self.box_root.addStretch(1)
        self.box_commit.addStretch(1)
        self.box_commit.addWidget(self.btn_commit)
        self.box_commit.addWidget(self.btn_abort)
        self.box_root.addLayout(self.box_commit)
        self.setLayout(self.box_root)

    def handle_ask_raw_data_path(self):
        self.val_raw_data = os.path.normpath(QFileDialog.getExistingDirectory(self)).replace('\\', '/')
        self.lbl_raw_data.setText(self.val_raw_data)

    def handle_ask_key_data_path(self):
        self.val_key_data = os.path.normpath(QFileDialog.getExistingDirectory(self)).replace('\\', '/')
        self.lbl_key_data.setText(self.val_key_data)

    def handle_ask_nod_data_path(self):
        self.val_nod_data = os.path.normpath(QFileDialog.getExistingDirectory(self)).replace('\\', '/')
        self.lbl_nod_data.setText(self.val_nod_data)

    def handle_ask_db_path(self):
        self.val_db_path = os.path.normpath(QFileDialog.getExistingDirectory(self)).replace('\\', '/')
        self.lbl_db_path.setText(self.val_db_path)

    def handle_gen_commit_param(self):
        try:
            self.main_widget.gen_raw_path = self.val_raw_data
            self.main_widget.gen_key_path = self.val_key_data
            self.main_widget.gen_nod_path = self.val_nod_data
            self.main_widget.gen_db_path = self.val_db_path
            self.main_widget.gen_db_name = self.ent_db_name.text()
            self.main_widget.gen_x_rate = float(self.ent_x_rate.text())
            self.main_widget.gen_y_rate = float(self.ent_y_rate.text())
            self.main_widget.gen_t_rate = float(self.ent_t_rate.text())
            self.main_widget.gen_epochs = int(self.ent_epochs.text())
            self.close()
        except Exception as e:
            traceback.print_exc()

    def handle_gen_abort_param(self):
        try:
            reply = QMessageBox.question(self, '提示', '确认放弃修改？参数将不被保存', QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.close()
        except Exception as e:
            traceback.print_exc()





# ------------------------------------------------- graphics part ------------------------------------------------------

class MvView(QGraphicsView):
    def __init__(self, scene, parent):
        QGraphicsView.__init__(self, scene, parent)
        # self.setViewport(QGLWidget())
        self.main_widget = parent
        self.scene = scene
        self.drag_canvas_flag = False
        self.prev_x, self.prev_y = 0, 0
        self.lock_zooming = False

    def wheelEvent(self, QWheelEvent):
        try:
            if not self.lock_zooming:
                if QWheelEvent.angleDelta().y() > 0:
                    if self.scene.scale < 16:
                        self.scene.scale *= self.scene.scale_factor
                        print('zoom bigger: %f' % self.scene.scale)
                else:
                    if self.scene.scale > 0.0625:
                        self.scene.scale /= self.scene.scale_factor
                        print('zoom small: %f' % self.scene.scale)
                self.setTransform(QTransform.fromScale(self.scene.scale, self.scene.scale), False)
        except Exception as e:
            traceback.print_exc()

    def mousePressEvent(self, QMouseEvent):
        try:
            view_pos = QMouseEvent.pos()
            scen_pos = self.mapToScene(view_pos)
            modifier = QApplication.keyboardModifiers()
            if QMouseEvent.button() == 4:
                self.drag_canvas_flag = True
                self.prev_x = view_pos.x()
                self.prev_y = view_pos.y()
            elif QMouseEvent.button() == 1:
                if modifier == Qt.ControlModifier:
                    if self.scene.itemAt(scen_pos, QTransform()) != None:
                        self.scene.ctrl_selected_itm = self.scene.itemAt(scen_pos, QTransform())
                        self.main_widget.update_selected_info(self.scene.ctrl_selected_itm.idx, self.scene.ctrl_selected_itm.cx,
                                                              self.scene.ctrl_selected_itm.cy, self.scene.ctrl_selected_itm.ct)
                        self.scene.drag_item_flag = True
                        if self.scene.ctrl_selected_itm.idx not in self.main_widget.edit_data_dict.keys():
                            self.main_widget.edit_data_dict[self.scene.ctrl_selected_itm.idx] = [0, 0, 0]
            elif QMouseEvent.button() == 2:
                if modifier == Qt.ControlModifier:
                    if self.scene.itemAt(scen_pos, QTransform()) != None:
                        self.scene.ctrl_selected_itm = self.scene.itemAt(scen_pos, QTransform())
                        self.main_widget.update_selected_info(self.scene.ctrl_selected_itm.idx, self.scene.ctrl_selected_itm.cx,
                                                              self.scene.ctrl_selected_itm.cy, self.scene.ctrl_selected_itm.ct)
                        self.scene.rotate_item_flag = True
                        if self.scene.ctrl_selected_itm.idx not in self.main_widget.edit_data_dict.keys():
                            self.main_widget.edit_data_dict[self.scene.ctrl_selected_itm.idx] = [0, 0, 0]
        except Exception as e:
            traceback.print_exc()

    def mouseMoveEvent(self, QMouseEvent):
        try:
            view_pos = QMouseEvent.pos()
            scen_pos = self.mapToScene(view_pos)
            curr_x = view_pos.x()
            curr_y = view_pos.y()
            delta_x = self.prev_x - curr_x
            delta_y = self.prev_y - curr_y
            self.lock_zooming = True
            self.main_widget.val_mouse_pos = '鼠标位置：%s, %s' % (
            round((scen_pos.x()) * M2PRATIO, 2), -1 * round((scen_pos.y()) * M2PRATIO, 2))
            self.main_widget.lbl_mouse_pos.setText(self.main_widget.val_mouse_pos)

            if self.drag_canvas_flag:
                self.translate(delta_x, delta_y)
                self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + delta_x)
                self.verticalScrollBar().setValue(self.verticalScrollBar().value() + delta_y)

            elif self.scene.drag_item_flag == True and self.scene.ctrl_selected_itm.idx != None:
                # shift
                self.scene.pix_dict[self.scene.ctrl_selected_itm.idx].cx -= delta_x * M2PRATIO
                self.scene.pix_dict[self.scene.ctrl_selected_itm.idx].cy -= delta_y * M2PRATIO
                self.scene.pix_dict[self.scene.ctrl_selected_itm.idx].moveBy(-1*delta_x, -1*delta_y)
                self.main_widget.edit_data_dict[self.scene.ctrl_selected_itm.idx][0] -= delta_x * M2PRATIO
                self.main_widget.edit_data_dict[self.scene.ctrl_selected_itm.idx][1] -= delta_y * M2PRATIO

            elif self.scene.rotate_item_flag == True and self.scene.ctrl_selected_itm.idx != None:
                # totation
                self.scene.pix_dict[self.scene.ctrl_selected_itm.idx].ct += (delta_x * M2PRATIO / 5.)
                self.main_widget.edit_data_dict[self.scene.ctrl_selected_itm.idx][2] -= (delta_x * M2PRATIO / 5.)
                self.scene.pix_dict[self.scene.ctrl_selected_itm.idx].setRotation(self.scene.pix_dict[self.scene.ctrl_selected_itm.idx].ct + self.scene.pix_rotate)
            self.lock_zooming = False

            self.prev_x = curr_x
            self.prev_y = curr_y
        except Exception as e:
            traceback.print_exc()

    def mouseReleaseEvent(self, QMouseEvent):
        try:
            view_pos = QMouseEvent.pos()
            scen_pos = self.mapToScene(view_pos)

            if self.drag_canvas_flag == True:
                self.drag_canvas_flag = False
            elif self.scene.drag_item_flag == True:
                self.scene.drag_item_flag = False
                self.scene.ctrl_selected_itm = None
                self.main_widget.update_selected_info(None, 0, 0, 0)
                self.main_widget.clear_edit_history()
                for k in self.main_widget.edit_data_dict:
                    v = self.main_widget.edit_data_dict[k]
                    row = self.main_widget.lst_edit_history.rowCount()
                    self.main_widget.lst_edit_history.setRowCount(row + 1)
                    self.main_widget.lst_edit_history.setItem(row, 0, QTableWidgetItem(str(k)))
                    self.main_widget.lst_edit_history.setItem(row, 1, QTableWidgetItem(str(round(v[0], 2))))
                    self.main_widget.lst_edit_history.setItem(row, 2, QTableWidgetItem(str(round(-1*v[1], 2))))
                    self.main_widget.lst_edit_history.setItem(row, 3, QTableWidgetItem(str(round(v[2], 2))))
            elif self.scene.rotate_item_flag == True:
                self.scene.rotate_item_flag = False
                self.scene.ctrl_selected_itm = None
                self.main_widget.update_selected_info(None, 0, 0, 0)
                self.main_widget.clear_edit_history()
                for k in self.main_widget.edit_data_dict:
                    v = self.main_widget.edit_data_dict[k]
                    row = self.main_widget.lst_edit_history.rowCount()
                    self.main_widget.lst_edit_history.setRowCount(row + 1)
                    self.main_widget.lst_edit_history.setItem(row, 0, QTableWidgetItem(str(k)))
                    self.main_widget.lst_edit_history.setItem(row, 1, QTableWidgetItem(str(round(v[0], 2))))
                    self.main_widget.lst_edit_history.setItem(row, 2, QTableWidgetItem(str(round(-1*v[1], 2))))
                    self.main_widget.lst_edit_history.setItem(row, 3, QTableWidgetItem(str(round(v[2], 2))))

        except Exception as e:
            traceback.print_exc()

    def fast_navigate_by_pos(self, cent_x, cent_y):
        try:
            self.centerOn(cent_x / M2PRATIO, -1 * cent_y / M2PRATIO)
        except Exception as e:
            traceback.print_exc()

class MvScene(QGraphicsScene):
    def __init__(self, parent):
        QGraphicsScene.__init__(self, parent)
        self.main_widget = parent
        self.drag_canvas_flag = False
        self.drag_item_flag = False
        self.rotate_item_flag = False
        self.show_grid_flag = True

        self.pix_dict = {}
        self.grid_horz = []
        self.grid_vert = []
        self.grid_list = []
        self.grid_pen = QPen()

        self.prev_x = 0
        self.prev_y = 0
        self.mouse_x = 0
        self.mouse_y = 0
        self.total_shift_x = 0
        self.total_shift_y = 0
        self.maxx = 0
        self.maxy = 0
        self.minx = 1e10
        self.miny = 1e10
        self.pix_rotate = 0.

        self.scale = 1.0
        self.scale_factor = 1.1
        self.m2p_ratio = 0.40625
        self.x_axis_gap = 1000
        self.y_axis_gap = 1000
        self.grid_width = 1

        self.ctrl_selected_itm = None
        self.dclick_selected_idx = None
        self.dclick_selected_item = None
        self.gv_image = None

    # def mousePressEvent(self, QGraphicsSceneMouseEvent):
    #     try:
    #         print('shift:(%s,%s)'%(self.total_shift_x, self.total_shift_y))
    #         print('scene:(%s,%s)'%(QGraphicsSceneMouseEvent.scenePos().x() * M2PRATIO, -1*QGraphicsSceneMouseEvent.scenePos().y() * M2PRATIO))
    #         modifier = QApplication.keyboardModifiers()
    #         if QGraphicsSceneMouseEvent.button() == 4:
    #             # dragging the whole scene
    #             self.drag_canvas_flag = True
    #         elif QGraphicsSceneMouseEvent.button() == 1:
    #             # dragging (shifting) single selected item
    #             if modifier == Qt.ControlModifier:
    #                 if self.itemAt(QGraphicsSceneMouseEvent.scenePos(), QTransform()) != None:
    #                     self.ctrl_selected_itm = self.itemAt(QGraphicsSceneMouseEvent.scenePos(), QTransform())
    #                     self.main_widget.update_selected_info(self.ctrl_selected_itm.idx, self.ctrl_selected_itm.cx,
    #                                                           self.ctrl_selected_itm.cy, self.ctrl_selected_itm.ct)
    #                     self.drag_item_flag = True
    #                     if self.ctrl_selected_itm.idx not in self.main_widget.edit_data_dict.keys():
    #                         self.main_widget.edit_data_dict[self.ctrl_selected_itm.idx] = [0, 0, 0]
    #         elif QGraphicsSceneMouseEvent.button() == 2:
    #             # rotating single selected item
    #             if modifier == Qt.ControlModifier:
    #                 if self.itemAt(QGraphicsSceneMouseEvent.scenePos(), QTransform()) != None:
    #                     self.ctrl_selected_itm = self.itemAt(QGraphicsSceneMouseEvent.scenePos(), QTransform())
    #                     self.main_widget.update_selected_info(self.ctrl_selected_itm.idx, self.ctrl_selected_itm.cx,
    #                                                           self.ctrl_selected_itm.cy, self.ctrl_selected_itm.ct)
    #                     self.rotate_item_flag = True
    #                     if self.ctrl_selected_itm.idx not in self.main_widget.edit_data_dict.keys():
    #                         self.main_widget.edit_data_dict[self.ctrl_selected_itm.idx] = [0, 0, 0]
    #         self.prev_x = QGraphicsSceneMouseEvent.scenePos().x()
    #         self.prev_y = QGraphicsSceneMouseEvent.scenePos().y()
    #     except Exception as e:
    #         traceback.print_exc()
    #
    # def mouseMoveEvent(self, QGraphicsSceneMouseEvent):
    #     try:
    #         self.main_widget.canvas_view.lock_zooming = True
    #         self.mouse_x = QGraphicsSceneMouseEvent.scenePos().x()
    #         self.mouse_y = QGraphicsSceneMouseEvent.scenePos().y()
    #         self.main_widget.val_mouse_pos = '鼠标位置：%s, %s' % (
    #         round((self.mouse_x - self.total_shift_x) * M2PRATIO, 2), -1 * round((self.mouse_y + self.total_shift_y) * M2PRATIO, 2))
    #         self.main_widget.lbl_mouse_pos.setText(self.main_widget.val_mouse_pos)
    #         delta_x = QGraphicsSceneMouseEvent.scenePos().x() - self.prev_x
    #         delta_y = QGraphicsSceneMouseEvent.scenePos().y() - self.prev_y
    #         self.prev_x = QGraphicsSceneMouseEvent.scenePos().x()
    #         self.prev_y = QGraphicsSceneMouseEvent.scenePos().y()
    #
    #         if self.drag_canvas_flag == True:
    #             # dragging the hole canvas, need to adjust the total shift, too.
    #             self.drag_canvas(delta_x, delta_y)
    #
    #         elif self.drag_item_flag == True and self.ctrl_selected_itm.idx != None:
    #             # shift
    #             self.pix_dict[self.ctrl_selected_itm.idx].cx += delta_x * M2PRATIO
    #             self.pix_dict[self.ctrl_selected_itm.idx].cy += delta_y * M2PRATIO
    #             self.pix_dict[self.ctrl_selected_itm.idx].moveBy(delta_x, delta_y)
    #             self.main_widget.edit_data_dict[self.ctrl_selected_itm.idx][0] += delta_x * M2PRATIO
    #             self.main_widget.edit_data_dict[self.ctrl_selected_itm.idx][1] += delta_y * M2PRATIO
    #
    #         elif self.rotate_item_flag == True and self.ctrl_selected_itm.idx != None:
    #             # totation
    #             self.pix_dict[self.ctrl_selected_itm.idx].ct += (delta_x * M2PRATIO / 5.)
    #             self.main_widget.edit_data_dict[self.ctrl_selected_itm.idx][2] += (delta_x * M2PRATIO / 5.)
    #             self.pix_dict[self.ctrl_selected_itm.idx].setRotation(self.pix_dict[self.ctrl_selected_itm.idx].ct + self.pix_rotate)
    #         self.main_widget.canvas_view.lock_zooming = False
    #     except Exception as e:
    #         traceback.print_exc()
    #
    # def mouseReleaseEvent(self, QGraphicsSceneMouseEvent):
    #     try:
    #         if self.drag_canvas_flag == True:
    #             self.drag_canvas_flag = False
    #         elif self.drag_item_flag == True:
    #             self.drag_item_flag = False
    #             self.ctrl_selected_itm = None
    #             self.main_widget.update_selected_info(None, 0, 0, 0)
    #             self.main_widget.clear_edit_history()
    #             for k in self.main_widget.edit_data_dict:
    #                 v = self.main_widget.edit_data_dict[k]
    #                 row = self.main_widget.lst_edit_history.rowCount()
    #                 self.main_widget.lst_edit_history.setRowCount(row + 1)
    #                 self.main_widget.lst_edit_history.setItem(row, 0, QTableWidgetItem(str(k)))
    #                 self.main_widget.lst_edit_history.setItem(row, 1, QTableWidgetItem(str(round(v[0], 2))))
    #                 self.main_widget.lst_edit_history.setItem(row, 2, QTableWidgetItem(str(round(-1*v[1], 2))))
    #                 self.main_widget.lst_edit_history.setItem(row, 3, QTableWidgetItem(str(round(v[2], 2))))
    #         elif self.rotate_item_flag == True:
    #             self.rotate_item_flag = False
    #             self.ctrl_selected_itm = None
    #             self.main_widget.update_selected_info(None, 0, 0, 0)
    #             self.main_widget.clear_edit_history()
    #             for k in self.main_widget.edit_data_dict:
    #                 v = self.main_widget.edit_data_dict[k]
    #                 row = self.main_widget.lst_edit_history.rowCount()
    #                 self.main_widget.lst_edit_history.setRowCount(row + 1)
    #                 self.main_widget.lst_edit_history.setItem(row, 0, QTableWidgetItem(str(k)))
    #                 self.main_widget.lst_edit_history.setItem(row, 1, QTableWidgetItem(str(round(v[0], 2))))
    #                 self.main_widget.lst_edit_history.setItem(row, 2, QTableWidgetItem(str(round(-1*v[1], 2))))
    #                 self.main_widget.lst_edit_history.setItem(row, 3, QTableWidgetItem(str(round(v[2], 2))))
    #     except Exception as e:
    #         traceback.print_exc()

    def mouseDoubleClickEvent(self, QGraphicsSceneMouseEvent):
        try:
            self.dclick_selected_item = self.itemAt(QGraphicsSceneMouseEvent.scenePos(), QTransform())
            if self.dclick_selected_item != None:
                self.dclick_selected_item.setZValue(1.0)
                self.dclick_selected_idx = self.dclick_selected_item.idx
                self.main_widget.val_selected_node_id = '选中节点ID：%s' % self.dclick_selected_item.idx
                self.main_widget.val_selected_node_pos = '坐标：%s, %s' % (
                round(self.dclick_selected_item.cx, 2), -1 * round(self.dclick_selected_item.cy, 2))
                self.main_widget.val_selected_node_angle = '选中节点角度：%s' % self.dclick_selected_item.ct
                self.main_widget.val_btn_delete_selected_node = '删除选中节点：%s'%self.dclick_selected_idx
            else:
                self.pix_dict[self.dclick_selected_idx].setZValue(0.)
                self.dclick_selected_idx = None
                self.main_widget.val_selected_node_id = '选中节点ID：-'
                self.main_widget.val_selected_node_pos = '选中节点位置：-'
                self.main_widget.val_selected_node_angle = '选中节点角度：-'
                self.main_widget.val_btn_delete_selected_node = '删除选中节点：暂无选中ID'
            self.main_widget.lbl_selected_node_id.setText(self.main_widget.val_selected_node_id)
            self.main_widget.lbl_selected_node_pos.setText(self.main_widget.val_selected_node_pos)
            self.main_widget.lbl_selected_node_angle.setText(self.main_widget.val_selected_node_angle)
            self.main_widget.btn_delete_selected_node.setText(self.main_widget.val_btn_delete_selected_node)
        except Exception as e:
            traceback.print_exc()

    def load_all_pixmaps_from_db(self, path):
        if not os.path.exists(path):
            err = QErrorMessage()
            err.showMessage('数据库文件"%s"不存在' % path)
            err.exec_()
            return
        try:
            conn = sqlite3.connect(path)
            curs = conn.cursor()
            cnt = curs.execute('select count(id) from zhdl_map').__next__()[0]
            print(cnt)
            res = curs.execute('select id, x, y, heading, raw_image from zhdl_map')
            img_cnt = 0
            self.clear()
            self.pix_dict = {}
            while True:
                try:
                    data = res.__next__()
                    idx = data[0]
                    x = data[1]
                    y = -1 * data[2]
                    t = data[3]
                    ttt = QImage(data[4], 320, 320, QImage.Format_Grayscale8)
                    pix = QPixmap.fromImage(ttt).scaled(130, 130, Qt.KeepAspectRatio, Qt.FastTransformation)
                    # pix = QPixmap('0.bmp').scaled(130, 130, Qt.KeepAspectRatio)
                    img = self.addPixmap(pix)
                    img.setTransformOriginPoint(pix.width() // 2, pix.height() // 2)
                    img.setRotation(t + self.pix_rotate)
                    img.setPos(x - pix.width() // 2, y - pix.height() // 2)
                    img.setFlag(QGraphicsItem.ItemIsMovable)
                    img.cx = x
                    img.cy = y
                    img.ct = t
                    img.ox = x
                    img.oy = y
                    img.ot = t
                    img.idx = idx
                    self.pix_dict[idx] = img
                    self.maxx = max(x, self.maxx)
                    self.maxy = max(abs(y), self.maxy)
                    self.minx = min(x, self.minx)
                    self.miny = min(abs(y), self.miny)
                except Exception as e:
                    traceback.print_exc()
                    break
        except Exception as e:
            traceback.print_exc()
            err = QErrorMessage()
            err.showMessage('读取数据库出错：%s' % e)
            err.exec_()

    def load_all_pixmaps_from_path(self):
        # path = 'D:/Data/jx/231/part2/calib_0/'
        path = 'D:/Data/jx/231/part2/node/'
        for _, _, fs in os.walk(path):
            for f in fs:
                file = path + f
                idx = int(f[:-4].split('_')[0])
                x = float(f[:-4].split('_')[1])
                y = -1 * float(f[:-4].split('_')[2])
                t = float(f[:-4].split('_')[3]) + 90
                if idx not in self.pix_dict.keys():
                    pix = QPixmap(file).scaled(130, 130, Qt.KeepAspectRatio)
                    img = self.addPixmap(pix)
                    img.setTransformOriginPoint(pix.width() // 2, pix.height() // 2)
                    img.setRotation(t)
                    img.setPos(x - pix.width() // 2, y - pix.height() // 2)
                    img.setFlag(QGraphicsItem.ItemIsMovable)
                    img.cx = x
                    img.cy = y
                    img.ct = t
                    img.ox = x
                    img.oy = y
                    img.ot = t
                    img.idx = idx
                    self.pix_dict[idx] = img
                    self.maxx = max(x, self.maxx)
                    self.maxy = max(abs(y), self.maxy)
                    self.minx = min(x, self.minx)
                    self.miny = min(abs(y), self.miny)

    def load_grid(self):
        print('%s,%s->%s,%s' % (self.minx // 1000, self.miny // 1000, self.maxx // 1000, self.maxy // 1000))
        self.grid_list = []
        self.grid_pen = QPen(QColor.fromRgb(195, 12, 255))
        self.grid_pen.setWidth(self.grid_width)
        for i in range(int(self.minx // self.x_axis_gap), int(self.maxx // self.x_axis_gap) + 1):
            self.grid_vert.append((
                i * self.x_axis_gap * self.scale / M2PRATIO,
                -1 * (self.miny//self.y_axis_gap) * self.y_axis_gap / M2PRATIO,
                i * self.x_axis_gap * self.scale / M2PRATIO,
                -1 * (self.maxy//self.y_axis_gap) * self.y_axis_gap / M2PRATIO
            ))
        for j in range(int(self.miny // self.y_axis_gap), int(self.maxy // self.y_axis_gap) + 1):
            self.grid_horz.append((
                (self.minx//self.x_axis_gap) * self.x_axis_gap / M2PRATIO,
                -1 * j * self.y_axis_gap * self.scale / M2PRATIO,
                (self.maxx//self.x_axis_gap) * self.x_axis_gap / M2PRATIO,
                -1 * j * self.y_axis_gap * self.scale / M2PRATIO
            ))

        for e in self.grid_vert:
            line_itm = QGraphicsLineItem(e[0], e[1], e[2], e[3])
            # line_itm.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            line_itm.setPen(self.grid_pen)
            self.addItem(line_itm)
            self.grid_list.append(line_itm)
        for e in self.grid_horz:
            line_itm = QGraphicsLineItem(e[0], e[1], e[2], e[3])
            # line_itm.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            line_itm.setPen(self.grid_pen)
            self.addItem(line_itm)
            self.grid_list.append(line_itm)

    def reload_pixmaps(self):
        for k in self.pix_dict:
            self.pix_dict[k].setRotation(self.pix_dict[k].ct + self.pix_rotate)
        # self.load_grid()
        self.grid_pen.setWidth(self.grid_width)
        for item in self.grid_list:
            item.setPen(self.grid_pen)

    def handle_load_pixmaps_finished(self):
        try:
            for k in self.pix_dict:
                self.addItem(self.pix_dict[k])
            self.load_grid()
            self.update()
            self.main_widget.canvas_view.lock_zooming = False

            self.main_widget.canvas_view.setSceneRect((self.main_widget.canvas_view.scene.minx-self.main_widget.canvas_padding)/M2PRATIO, -1*(self.main_widget.canvas_view.scene.maxy+self.main_widget.canvas_padding)/M2PRATIO, abs(self.main_widget.canvas_view.scene.maxx-self.main_widget.canvas_view.scene.minx+1000+self.main_widget.canvas_padding*2)/M2PRATIO, abs(self.main_widget.canvas_view.scene.maxy-self.main_widget.canvas_view.scene.miny+(self.main_widget.canvas_padding*2))/M2PRATIO)
            self.main_widget.canvas_view.centerOn(self.main_widget.canvas_view.scene.minx/M2PRATIO, -1*self.main_widget.canvas_view.scene.miny/M2PRATIO)
        except Exception as e:
            traceback.print_exc()

    def clear_canvas(self):
        try:
            self.drag_canvas_flag = False
            self.drag_item_flag = False
            self.rotate_item_flag = False

            self.prev_x = 0
            self.prev_y = 0
            self.mouse_x = 0
            self.mouse_y = 0
            self.total_shift_x = 0
            self.total_shift_y = 0
            self.maxx = 0
            self.maxy = 0
            self.minx = 1e10
            self.miny = 1e10
            self.pix_rotate = 0.

            self.scale = 1.0
            self.scale_factor = 1.1
            self.m2p_ratio = 0.40625
            self.x_axis_gap = 1000
            self.y_axis_gap = 1000
            self.grid_width = 1.

            self.ctrl_selected_itm = None
            self.dclick_selected_idx = None
            self.dclick_selected_item = None
            self.gv_image = None

            for k in self.pix_dict:
                self.removeItem(self.pix_dict[k])
            for e in self.grid_list:
                self.removeItem(e)
            self.pix_dict = {}
            self.grid_list = []
            self.main_widget.canvas_view.setTransform(QTransform.fromScale(1, 1), False)
        except Exception as e:
            traceback.print_exc()

    def drag_canvas(self, delta_x, delta_y):
        print('x:%s|y:%s'%(delta_x, delta_y))
        for k in self.pix_dict:
            self.pix_dict[k].moveBy(delta_x, delta_y)
            self.update()
        for i in range(len(self.grid_list)):
            self.grid_list[i].moveBy(delta_x, delta_y)
        self.total_shift_x += delta_x
        self.total_shift_y -= delta_y
        print('total shift:%s, %s' % ((-1 * self.total_shift_x * M2PRATIO),  self.total_shift_y * M2PRATIO))


class MvWidget(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.main_window = parent
        self.canvas_scene = MvScene(self)
        # print('aaa %s,%s,%s,%s'%(self.canvas_scene.maxx, self.canvas_scene.minx, self.canvas_scene.maxy, self.canvas_scene.miny))
        self.canvas_view = MvView(self.canvas_scene, self)
        self.control_vbox = QVBoxLayout()
        self.root_hbox = QHBoxLayout()

        self.mouse_pos = '-'
        self.selected_node_id = '-'
        self.selected_node_pos = '-'
        self.selected_node_angle = '-'
        self.m2p_ratio = 0.40625
        self.canvas_padding = 5000
        self.socket_save_path = os.path.realpath(os.path.curdir).replace('\\', '/') + '/' + 'socket_data'
        self.configfile = {}
        self.edit_data_dict = {}

        # ---------------- gen ----------------
        self.gen_raw_path = 'D:/'
        self.gen_key_path = 'D:/keys/'
        self.gen_nod_path = 'D:/nodes/'
        self.gen_db_path = 'D:/'
        self.gen_db_name = 'untitled'
        self.gen_x_rate = .25
        self.gen_y_rate = .25
        self.gen_t_rate = .25
        self.gen_epochs = 100


        self.val_mouse_pos = '鼠标位置：%s' % self.mouse_pos
        self.val_selected_node_id = '选中节点ID：%s' % self.selected_node_id
        self.val_selected_node_pos = '坐标：%s' % self.selected_node_pos
        self.val_selected_node_angle = '选中节点角度：%s' % self.selected_node_angle
        self.val_current_scale = '缩放系数：%s' % str(round(self.canvas_scene.scale, 5))
        self.val_btn_set_show_grid = '已打开网格显示'
        self.val_btn_enter_edit_mod = '进入编辑模式'
        self.val_btn_delete_selected_node = '删除选中节点：暂无选中ID'

        self.frm_control_fram = QFrame()
        self.btn_gen_global_view = QPushButton('生成全局地图')
        self.btn_gen_global_view.clicked.connect(self.gen_global_view_handler)
        self.lbl_mouse_pos = QLabel()

        self.lbl_mouse_pos.setText(self.val_mouse_pos)
        self.lbl_selected_node_id = QLabel()
        self.lbl_selected_node_id.setText(self.val_selected_node_id)
        self.lbl_selected_node_pos = QLabel()
        self.lbl_selected_node_pos.setText(self.val_selected_node_pos)
        self.lbl_selected_node_angle = QLabel()
        self.lbl_selected_node_angle.setText(self.val_selected_node_angle)
        self.box_m2p_ratio = QHBoxLayout()
        self.lbl_m2p_ratio = QLabel('毫米/像素')
        self.ent_m2p_ratio = QLineEdit()
        self.ent_m2p_ratio.setText(str(self.m2p_ratio))
        self.btn_m2p_ratio_set = QPushButton('设定新的毫米/像素')
        self.btn_m2p_ratio_set.clicked.connect(self.set_m2p_ratio_set_handler)
        self.lbl_current_scale = QLabel()
        self.lbl_current_scale.setText(self.val_current_scale)

        self.box_x_gap = QHBoxLayout()
        self.lbl_x_gap = QLabel('x轴网格间距(mm)')
        self.ent_x_gap = QLineEdit('1000')
        self.ent_x_gap.setValidator(QDoubleValidator())
        self.box_y_gap = QHBoxLayout()
        self.lbl_y_gap = QLabel('y轴网格间距(mm)')
        self.ent_y_gap = QLineEdit('1000')
        self.ent_y_gap.setValidator(QDoubleValidator())
        self.btn_set_new_gap = QPushButton('设定新网格间距')
        self.btn_set_show_grid = QPushButton()
        self.btn_set_show_grid.setText(self.val_btn_set_show_grid)
        self.btn_set_new_gap.clicked.connect(self.set_new_gap_handler)
        self.btn_set_show_grid.clicked.connect(self.set_show_grid_handler)

        self.box_x_cent = QHBoxLayout()
        self.lbl_x_cent = QLabel('视野中心x值(mm)')
        self.ent_x_cent = QLineEdit('0')
        self.ent_x_cent.setText('0')
        self.ent_x_cent.setValidator(QDoubleValidator())
        self.box_y_cent = QHBoxLayout()
        self.lbl_y_cent = QLabel('视野中心y值(mm)')
        self.ent_y_cent = QLineEdit('0')
        self.ent_y_cent.setText('0')
        self.ent_y_cent.setValidator(QDoubleValidator())
        self.btn_set_new_cent = QPushButton('设定新中心点')
        self.btn_set_new_cent.clicked.connect(self.set_new_cent_handler)

        self.btn_enter_edit_mod = QPushButton()
        self.btn_enter_edit_mod.setText(self.val_btn_enter_edit_mod)
        # self.lst_edit_history = QListWidget()
        self.lst_edit_history = QTableWidget(0, 4)
        self.clear_edit_history()
        self.btn_commit_edit = QPushButton('提交修改')
        self.btn_commit_edit.clicked.connect(self.edit_commit_handler)
        self.btn_abort_edit = QPushButton('放弃修改')
        self.btn_abort_edit.clicked.connect(self.edit_abort_handler)
        self.box_btn_edit = QHBoxLayout()

        self.btn_delete_selected_node = QPushButton()
        self.btn_delete_selected_node.clicked.connect(self.edit_delete_handler)
        self.btn_delete_selected_node.setText(self.val_btn_delete_selected_node)
        self.initUI()

    def initUI(self):
        self.frm_control_fram.setFixedWidth(180)
        self.frm_control_fram.setLayout(self.control_vbox)
        self.control_vbox.addWidget(self.btn_gen_global_view)
        self.control_vbox.addWidget(LineSeparator())
        self.control_vbox.addWidget(self.lbl_mouse_pos)
        self.control_vbox.addWidget(self.lbl_selected_node_id)
        self.control_vbox.addWidget(self.lbl_selected_node_pos)
        self.control_vbox.addWidget(self.lbl_selected_node_angle)
        self.control_vbox.addLayout(self.box_m2p_ratio)
        self.box_m2p_ratio.addWidget(self.lbl_m2p_ratio)
        self.box_m2p_ratio.addWidget(self.ent_m2p_ratio)
        self.control_vbox.addWidget(self.btn_m2p_ratio_set)
        self.control_vbox.addWidget(self.lbl_current_scale)
        self.control_vbox.addWidget(LineSeparator())
        self.box_x_gap.addWidget(self.lbl_x_gap)
        self.box_x_gap.addWidget(self.ent_x_gap)
        self.control_vbox.addLayout(self.box_x_gap)
        self.box_y_gap.addWidget(self.lbl_y_gap)
        self.box_y_gap.addWidget(self.ent_y_gap)
        self.control_vbox.addLayout(self.box_y_gap)
        self.control_vbox.addWidget(self.btn_set_new_gap)
        self.control_vbox.addWidget(self.btn_set_show_grid)
        self.control_vbox.addWidget(LineSeparator())
        self.control_vbox.addLayout(self.box_x_cent)
        self.box_x_cent.addWidget(self.lbl_x_cent)
        self.box_x_cent.addWidget(self.ent_x_cent)
        self.control_vbox.addLayout(self.box_y_cent)
        self.box_y_cent.addWidget(self.lbl_y_cent)
        self.box_y_cent.addWidget(self.ent_y_cent)
        self.control_vbox.addWidget(self.btn_set_new_cent)
        self.control_vbox.addWidget(LineSeparator())
        # self.control_vbox.addWidget(self.btn_enter_edit_mod)
        self.control_vbox.addWidget(self.lst_edit_history)
        self.control_vbox.addLayout(self.box_btn_edit)
        self.control_vbox.addStrut(1)
        self.box_btn_edit.addWidget(self.btn_commit_edit)
        self.box_btn_edit.addWidget(self.btn_abort_edit)
        self.control_vbox.addWidget(LineSeparator())
        self.control_vbox.addWidget(self.btn_delete_selected_node)
        self.root_hbox.addWidget(self.frm_control_fram)
        self.root_hbox.addWidget(self.canvas_view)
        self.setLayout(self.root_hbox)

    def wheelEvent(self, QWheelEvent):
        self.val_current_scale = '缩放系数：%s' % str(round(self.canvas_scene.scale, 5))
        self.lbl_current_scale.setText(self.val_current_scale)

    # -------------------------------- control frame handler --------------------------------

    def gen_global_view_handler(self):
        self.global_view = MvGlobalView(self)

    def clear_edit_history(self):
        while self.lst_edit_history.rowCount() != 0:
            self.lst_edit_history.removeRow(0)
        self.lst_edit_history.setHorizontalHeaderLabels(['id', 'x', 'y', 'θ'])
        self.lst_edit_history.setColumnWidth(0, 64)
        self.lst_edit_history.setColumnWidth(1, 48)
        self.lst_edit_history.setColumnWidth(2, 48)
        self.lst_edit_history.setColumnWidth(3, 48)

    def edit_commit_handler(self):
        try:
            if len(self.edit_data_dict) == 0:
                QMessageBox.information(self, '提示', '无可提交的修改历史')
                return
            if self.main_window.using_db:
                # update db
                reply = QMessageBox.question(self, '提示', '确认提交修改回数据库？', QMessageBox.Yes, QMessageBox.No)
                if reply == QMessageBox.No:
                    return
                try:
                    conn = sqlite3.connect(self.main_window.db_path)
                    curs = conn.cursor()
                except Exception as e:
                    QMessageBox.warning(self, '错误', '当前数据库路径无效')
                    traceback.print_exc()
                try:
                    for k in self.edit_data_dict:
                        print('x:%s->%s'%(self.canvas_scene.pix_dict[k].ox, self.edit_data_dict[k][0]))
                        print('y:%s->%s'%(self.canvas_scene.pix_dict[k].oy, self.edit_data_dict[k][1]))
                        self.canvas_scene.pix_dict[k].ox += self.edit_data_dict[k][0]
                        self.canvas_scene.pix_dict[k].oy += self.edit_data_dict[k][1]
                        self.canvas_scene.pix_dict[k].ot -= self.edit_data_dict[k][2]
                        curs.execute('update zhdl_map set x=%s, y=%s, heading=%s where id=%s' % (self.canvas_scene.pix_dict[k].ox, -1 * self.canvas_scene.pix_dict[k].oy, self.canvas_scene.pix_dict[k].ot, k))
                        conn.commit()
                    conn.close()
                    QMessageBox.information(self, '提示', '地图数据修改已保存回数据库')
                    self.edit_data_dict = {}
                    self.clear_edit_history()
                except Exception as e:
                    traceback.print_exc()
            else:
                # update file
                reply = QMessageBox.question(self, '提示', '确认提交修改回文件？', QMessageBox.Yes, QMessageBox.No)
                if reply == QMessageBox.No:
                    return
                key_dict = {}
                for _,_,fs in os.walk(self.main_window.raw_path):
                    for f in fs:
                        key_dict[f.split('_')[0]] = f
                for k in self.edit_data_dict:
                    try:
                        self.canvas_scene.pix_dict[k].ox += self.edit_data_dict[k][0]
                        self.canvas_scene.pix_dict[k].oy += self.edit_data_dict[k][1]
                        self.canvas_scene.pix_dict[k].ot -= self.edit_data_dict[k][2]
                        new_fname = '%s_%s_%s_%s.bmp' % (k, self.canvas_scene.pix_dict[k].ox, -1 * self.canvas_scene.pix_dict[k].oy, self.canvas_scene.pix_dict[k].ot)
                        os.rename(self.main_window.raw_path+'/'+key_dict[str(k)], self.main_window.raw_path+'/'+new_fname)
                        print('modify filename from %s -> %s'%(self.main_window.raw_path+'/'+key_dict[str(k)], self.main_window.raw_path+'/'+new_fname))
                    except Exception as e:
                        traceback.print_exc()
                QMessageBox.information(self, '提示', '地图数据修改已保存回文件')
                self.edit_data_dict = {}
                self.clear_edit_history()

        except Exception as e:
            traceback.print_exc()

    def edit_abort_handler(self):
        try:
            if len(self.edit_data_dict) == 0:
                QMessageBox.information(self, '提示', '当前无修改历史')
                return
            reply = QMessageBox.question(self, '提示', '确认放弃修改？当前修改将不被保存', QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.No:
                return
            self.canvas_scene.drag_item_flag = False
            self.canvas_scene.rotate_item_flag = False
            for k in self.edit_data_dict:
                dx, dy, dt = self.edit_data_dict[k]
                self.canvas_scene.pix_dict[k].cx -= dx
                self.canvas_scene.pix_dict[k].cy -= dy
                self.canvas_scene.pix_dict[k].ct += dt
                self.canvas_scene.pix_dict[k].moveBy(-dx / M2PRATIO, -dy / M2PRATIO)
                self.canvas_scene.pix_dict[k].setRotation(self.canvas_scene.pix_dict[k].ct)
            self.edit_data_dict = {}
            self.clear_edit_history()
        except Exception as e:
            traceback.print_exc()

    def edit_delete_handler(self):
        try:
            if self.canvas_scene.dclick_selected_idx == None:
                QMessageBox.information(self, '提示', '当前无选中节点')
                return
            self.canvas_view.centerOn(self.canvas_scene.pix_dict[self.canvas_scene.dclick_selected_idx])
            reply = QMessageBox.question(self, '提示', '确认删除当前节点？操作不可恢复', QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.No:
                return
            if self.main_window.using_db:
                conn = sqlite3.connect(self.main_window.db_path)
                curs = conn.cursor()
                curs.execute('delete from zhdl_map where id=%s' % self.canvas_scene.dclick_selected_idx)
                conn.commit()
            else:
                for _,_,fs in os.walk(self.main_window.raw_path):
                    for f in fs:
                        if f.split('_')[0] == str(self.canvas_scene.dclick_selected_idx):
                            os.remove(self.main_window.raw_path + '/' + f)
                            break
            self.canvas_scene.removeItem(self.canvas_scene.pix_dict[self.canvas_scene.dclick_selected_idx])
            self.canvas_scene.pix_dict.pop(self.canvas_scene.dclick_selected_idx)
            self.canvas_scene.dclick_selected_item = None
            self.canvas_scene.dclick_selected_idx = None
            self.val_selected_node_id = '选中节点ID：-'
            self.val_selected_node_pos = '选中节点位置：-'
            self.val_selected_node_angle = '选中节点角度：-'
            self.val_btn_delete_selected_node = '删除选中节点：暂无选中ID'
            self.lbl_selected_node_id.setText(self.val_selected_node_id)
            self.lbl_selected_node_pos.setText(self.val_selected_node_pos)
            self.lbl_selected_node_angle.setText(self.val_selected_node_angle)
            self.btn_delete_selected_node.setText(self.val_btn_delete_selected_node)
        except Exception as e:
            traceback.print_exc()

    def update_selected_info(self, idx, x, y, t):
        if idx != None:
            self.val_selected_node_id = '选中节点ID：%s' % idx
            self.val_selected_node_pos = '坐标：%s, %s' % (round(x, 2), -1 * round(y, 2))
            self.val_selected_node_angle = '选中节点角度：%s' % t
            self.lbl_selected_node_id.setText(self.val_selected_node_id)
            self.lbl_selected_node_pos.setText(self.val_selected_node_pos)
            self.lbl_selected_node_angle.setText(self.val_selected_node_angle)
        else:
            self.val_selected_node_id = '选中节点ID：-'
            self.val_selected_node_pos = '选中节点位置：-'
            self.val_selected_node_angle = '选中节点角度：-'
            self.lbl_selected_node_id.setText(self.val_selected_node_id)
            self.lbl_selected_node_pos.setText(self.val_selected_node_pos)
            self.lbl_selected_node_angle.setText(self.val_selected_node_angle)

    def set_new_cent_handler(self):
        try:
            cent_x = float(self.ent_x_cent.text())
            cent_y = float(self.ent_y_cent.text())
            self.canvas_view.fast_navigate_by_pos(cent_x, cent_y)
        except Exception as e:
            traceback.print_exc()

    def set_new_gap_handler(self):
        pass

    def set_m2p_ratio_set_handler(self):
        M2PRATIO = round(float(self.ent_m2p_ratio.text()), 5)
        try:
            self.load_db_thread = ThreadLoadPixDB(self, self.main_window.db_path)
            self.load_db_thread.start()
            self.load_db_thread.signal.connect(self.main_window.handle_progress_bar)
            self.load_db_thread.finished.connect(self.canvas_scene.handle_load_pixmaps_finished)
            self.main_window.using_db = True
        except Exception as e:
            traceback.print_exc()

    def set_show_grid_handler(self):
        if self.canvas_view.scene.show_grid_flag:
            self.canvas_view.scene.show_grid_flag = False
            self.val_btn_set_show_grid = '已关闭网格显示'
            self.btn_set_show_grid.setText(self.val_btn_set_show_grid)
            for itm in self.canvas_view.scene.grid_list:
                itm.setVisible(False)
        else:
            self.canvas_view.scene.show_grid_flag = True
            self.val_btn_set_show_grid = '已打开网格显示'
            self.btn_set_show_grid.setText(self.val_btn_set_show_grid)
            for itm in self.canvas_view.scene.grid_list:
                itm.setVisible(True)

class MvWindow(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.using_db = True
        self.raw_path = ''
        self.db_path = ''

        self.initUI()
        self.main_widget.canvas_view.setGeometry(120, 0, self.width(), self.height())
        self.main_widget.canvas_view.setMouseTracking(True)
        self.main_widget.canvas_view.setBackgroundBrush(QBrush(QColor.fromRgb(25, 25, 25)))
        if os.path.exists(os.path.dirname(os.path.realpath(__file__))+os.path.sep + '/'+'mapviewer.cfg'):
            cfg = open(os.path.dirname(os.path.realpath(__file__))+os.path.sep+'mapviewer.cfg', 'r')
            self.main_widget.configfile = dict([e.split('=') for e in cfg.readlines()])
            cfg.close()
            if 'DBPATH' in self.main_widget.configfile.keys():
                # self.main_widget.canvas_scene.load_all_pixmaps_from_path()
                self.db_path = self.main_widget.configfile['DBPATH']
                self.load_pixmaps_thread = ThreadLoadPixDB(self.main_widget, self.main_widget.configfile['DBPATH'])
                self.load_pixmaps_thread.start()
                self.load_pixmaps_thread.signal.connect(self.handle_progress_bar)
                self.load_pixmaps_thread.finished.connect(self.main_widget.canvas_scene.handle_load_pixmaps_finished)
                self.using_db = True
        else:
            QMessageBox.information(self, '提示', '暂无可展示的数据')

        # ------------------ preferent params ------------------
        self.transformation_mode = Qt.FastTransformation

    def initUI(self):
        self.main_widget = MvWidget(self)
        self.setCentralWidget(self.main_widget)

        self.act_param_config = QAction('参数设置', self)
        self.act_param_config.setStatusTip('对MapViewer的参数进行设置')
        self.act_gen_hd_global_map = QAction('生成高清全局地图', self)
        self.act_gen_hd_global_map.setStatusTip('生成的高清地图“hd_global_viewmap.png”尺寸为长轴=10240，后期加入可调参数功能，保存在当前工具根目录中')
        self.act_import_single_img = QAction('导入一张图像', self)
        self.act_import_single_img_commit = QAction('提交导入图像', self)
        self.act_import_labeled_set = QAction('导入标注集合', self)
        self.act_import_raw_set = QAction('导入未标注集合', self)
        self.act_fix_labeled_set = QAction('固定标注集', self)
        self.act_label_n_filter = QAction('× 标注去重', self)
        self.act_import_from_sqlite = QAction('从Sqlite导入', self)
        self.act_export_to_sqlite = QAction('往Sqlite导出', self)
        self.act_gen_config_gradient_param = QAction('配置地图生成参数', self)
        self.act_gen_basic_dataset = QAction('生成基础数据集(640×640)', self)
        self.act_gen_sqlite_db = QAction('生成数据库(320×320)', self)
        self.act_gen_gradient_update = QAction('梯度下降更新', self)
        self.act_socket_open_data_port = QAction('打开图像采集Socket', self)
        self.act_socket_export_to_sqlite = QAction('将采集图像导出为Sqlite', self)
        self.act_about_version = QAction('关于Quicktron Mapviewer', self)
        self.act_about_help = QAction('× 使用说明', self)

        self.act_param_config.triggered.connect(self.open_param_config)
        self.act_gen_hd_global_map.triggered.connect(self.gen_hd_global_map)
        self.act_import_single_img.triggered.connect(self.import_single_img)
        self.act_import_single_img_commit.triggered.connect(self.import_single_img_commit)
        self.act_import_labeled_set.triggered.connect(self.import_labeled_set)
        self.act_import_raw_set.triggered.connect(self.import_raw_set)
        self.act_fix_labeled_set.triggered.connect(self.fix_labeled_set)
        self.act_label_n_filter.triggered.connect(self.label_n_filter)
        self.act_import_from_sqlite.triggered.connect(self.import_from_sqlite)
        self.act_export_to_sqlite.triggered.connect(self.export_to_sqlite)
        self.act_gen_config_gradient_param.triggered.connect(self.gen_config_gradient_param)
        self.act_gen_basic_dataset.triggered.connect(self.gen_basic_dataset)
        self.act_gen_sqlite_db.triggered.connect(self.gen_sqlite_db)
        self.act_gen_gradient_update.triggered.connect(self.gen_gradient_update)
        self.act_socket_open_data_port.triggered.connect(self.socket_open_data_port)
        self.act_socket_export_to_sqlite.triggered.connect(self.socket_export_to_sqlite)
        self.act_about_version.triggered.connect(self.about_version)
        self.act_about_help.triggered.connect(self.about_help)

        self.menu = self.menuBar()
        self.menu_config = self.menu.addMenu('选项  ')
        self.menu_config.addAction(self.act_param_config)
        self.menu_config.addAction(self.act_gen_hd_global_map)
        self.menu_config.addSeparator()
        self.menu_config.addAction(self.act_import_single_img)
        self.menu_config.addAction(self.act_import_single_img_commit)
        self.menu_config.addSeparator()
        self.menu_config.addAction(self.act_import_labeled_set)
        self.menu_config.addAction(self.act_import_raw_set)
        self.menu_config.addAction(self.act_fix_labeled_set)
        self.menu_config.addAction(self.act_label_n_filter)
        self.menu_config.addSeparator()
        self.menu_config.addAction(self.act_import_from_sqlite)
        self.menu_config.addAction(self.act_export_to_sqlite)
        self.menu_config.addSeparator()
        self.menu_config.addAction(self.act_gen_config_gradient_param)
        self.menu_config.addAction(self.act_gen_basic_dataset)
        self.menu_config.addAction(self.act_gen_sqlite_db)
        self.menu_config.addAction(self.act_gen_gradient_update)
        self.menu_config.addSeparator()
        self.menu_config.addAction(self.act_socket_open_data_port)
        self.menu_config.addAction(self.act_socket_export_to_sqlite)

        self.menu_about = self.menu.addMenu('关于  ')
        self.menu_about.addAction(self.act_about_version)
        self.menu_about.addAction(self.act_about_help)
        self.status = QStatusBar()
        self.progress = QProgressBar()
        self.progress.setFixedWidth(160)
        self.progress.setFixedHeight(20)
        self.progress.setVisible(False)
        self.status_message = QLabel('')
        self.setStatusBar(self.status)
        self.setMenuBar(self.menu)
        self.status.addWidget(QLabel('  '))
        self.status.addWidget(self.progress)
        self.status.addWidget(self.status_message)
        self.status.show()
        self.setWindowTitle('Quicktron Map Viewer')
        self.setWindowIcon(QIcon(os.path.dirname(os.path.realpath(__file__))+os.path.sep+'ico.ico'))
        self.setGeometry(0, 0, 1080, 780)
        self.showMaximized()

    def do_nothing(self):
        # literally doing nothing
        pass

    # ------------------------------------- handler function -------------------------------------

    def handle_progress_bar(self, msg):
        try:
            k, v = msg.split(':', 1)
            if k == 'start':
                self.progress.setVisible(True)
                self.status_message.setText('正在载入...')
            elif k == 'max':
                self.progress.setMaximum(int(v))
            elif k == 'min':
                self.progress.setMinimum(int(v))
            elif k == 'current':
                self.progress.setValue(int(v))
            elif k == 'stop':
                self.progress.setVisible(False)
                self.status_message.setText('共 %s 个地图瓦片数据，坐标 (%s, %s) 到 (%s, %s)' % (
                    len(self.main_widget.canvas_scene.pix_dict),
                    round(self.main_widget.canvas_scene.minx, 2),
                    round(self.main_widget.canvas_scene.miny, 2),
                    round(self.main_widget.canvas_scene.maxx, 2),
                    round(self.main_widget.canvas_scene.maxy, 2)))
            elif k == 'error':
                self.progress.setVisible(False)
                self.status_message.setText('发生错误')
                self.main_widget.canvas_view.scene.clear_canvas()
                self.main_widget.canvas_view.scene.clear()
                QMessageBox.critical(self.main_widget, '错误', v)

        except Exception as e:
            traceback.print_exc()

    def handle_progress_bar_gen_global(self, msg):
        try:
            k, v = msg.split(':')
            if k == 'start':
                self.progress.setVisible(True)
                self.status_message.setText('正在生成HD全局地图...')
            elif k == 'max':
                self.progress.setMaximum(int(v))
            elif k == 'min':
                self.progress.setMinimum(int(v))
            elif k == 'current':
                self.progress.setValue(int(v))
            elif k == 'stop':
                self.progress.setVisible(False)
                self.status_message.setText('共 %s 个地图瓦片数据，坐标 (%s, %s) 到 (%s, %s)' % (
                    len(self.main_widget.canvas_scene.pix_dict),
                    round(self.main_widget.canvas_scene.minx, 2),
                    round(self.main_widget.canvas_scene.miny, 2),
                    round(self.main_widget.canvas_scene.maxx, 2),
                    round(self.main_widget.canvas_scene.maxy, 2)))
        except Exception as e:
            traceback.print_exc()

    def handle_progress_bar_gen_basedata(self, msg):
        try:
            k, v = msg.split(':')
            if k == 'start':
                self.progress.setVisible(True)
                self.act_gen_basic_dataset.setDisabled(True)
                self.status_message.setText('正在以行车采集数据生成标定-非标定基础数据...')
            elif k == 'max':
                self.progress.setMaximum(int(v))
            elif k == 'min':
                self.progress.setMinimum(int(v))
            elif k == 'current':
                self.progress.setValue(int(v))
            elif k == 'stop':
                self.progress.setVisible(False)
                self.status_message.setText('基础标定-非标定数据生成完成')
        except Exception as e:
            traceback.print_exc()

    def handle_progress_bar_gen_gradient_db(self, msg):
        pass

    def handle_progress_bar_gradient_update(self, msg):
        pass

    def handle_gen_basedata_finished(self):
        try:
            self.main_widget.canvas_view.scene.clear_canvas()
            self.raw_path = self.main_widget.gen_key_path
            self.load_path_thread = ThreadLoadPixPath(self.main_widget, self.raw_path, True)
            self.load_path_thread.start()
            self.load_path_thread.signal.connect(self.handle_progress_bar)
            self.load_path_thread.finished.connect(self.main_widget.canvas_scene.handle_load_pixmaps_finished)
            self.using_db = False
        except Exception as e:
            traceback.print_exc()

    def handle_gen_db_finished(self):
        pass

    # ------------------------------------- menubar function -------------------------------------

    def open_param_config(self):
        try:
            about = MvPreference(self.main_widget)
            about.show()
            about.exec_()
        except Exception as e:
            traceback.print_exc()

    def gen_hd_global_map(self):
        try:
            self.hd_global_thread = ThreadHDGlobalMap(self.main_widget)
            self.hd_global_thread.start()
            self.hd_global_thread.signal.connect(self.handle_progress_bar_gen_global)
            self.hd_global_thread.finished.connect(self.do_nothing)
            self.using_db = False
        except Exception as e:
            traceback.print_exc()

    def import_single_img(self):
        pass

    def import_single_img_commit(self):
        pass

    def import_labeled_set(self):
        try:
            self.main_widget.canvas_view.scene.clear_canvas()
            self.raw_path = os.path.normpath(QFileDialog.getExistingDirectory(self)).replace('\\', '/')
            self.load_path_thread = ThreadLoadPixPath(self.main_widget, self.raw_path, True)
            self.load_path_thread.start()
            self.load_path_thread.signal.connect(self.handle_progress_bar)
            self.load_path_thread.finished.connect(self.main_widget.canvas_scene.handle_load_pixmaps_finished)
            self.using_db = False
        except Exception as e:
            traceback.print_exc()

    def import_raw_set(self):
        try:
            self.main_widget.canvas_view.scene.clear_canvas()
            self.raw_path = os.path.normpath(QFileDialog.getExistingDirectory(self)).replace('\\', '/')
            self.load_path_thread = ThreadLoadPixPath(self.main_widget, self.raw_path, False)
            self.load_path_thread.start()
            self.load_path_thread.signal.connect(self.handle_progress_bar)
            self.load_path_thread.finished.connect(self.main_widget.canvas_scene.handle_load_pixmaps_finished)
            self.using_db = False
        except Exception as e:
            traceback.print_exc()

    def fix_labeled_set(self):
        for k in self.main_widget.canvas_view.scene.pix_dict:
            if self.main_widget.canvas_view.scene.pix_dict[k].kp_flag:
                self.main_widget.canvas_view.scene.pix_dict[k].setFlag(QGraphicsItem.ItemIsMovable, False)
                print(k)

    def label_n_filter(self):
        pass

    def import_from_sqlite(self):
        try:
            options = QFileDialog.Options()
            # options |= QFileDialog.DontUseNativeDialog
            filter = 'db(*.db)'
            self.db_path, _ = QFileDialog.getOpenFileName(self, '.db 数据库文件 (*.db)', options=options, filter=filter)
            if not self.db_path.endswith('.db'):
                return
            self.load_db_thread = ThreadLoadPixDB(self.main_widget, self.db_path)
            self.load_db_thread.start()
            self.load_db_thread.signal.connect(self.handle_progress_bar)
            self.load_db_thread.finished.connect(self.main_widget.canvas_scene.handle_load_pixmaps_finished)
            self.using_db = True
        except Exception as e:
            traceback.print_exc()

    def export_to_sqlite(self):
        try:
            options = QFileDialog.Options()
            options |= QFileDialog.DontConfirmOverwrite
            filter = 'db(*.db)'
            self.export_db_path, _ = QFileDialog.getSaveFileName(self, '.db 数据库文件 (*.db)', options=options, filter=filter)
            if not self.db_path.endswith('.db'):
                self.export_db_path += '.db'
            if os.path.exists(self.export_db_path):
                self.export_db_thread = ThreadExportPixDB(self.main_widget, self.export_db_path)
                self.export_db_thread.start()
                self.export_db_thread.signal.connect(self.handle_progress_bar)
            else:
                reply = QMessageBox.question(self, '提示', '当前选中数据库不存在，是否创建？', QMessageBox.Yes, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    try:
                        conn = sqlite3.connect(self.export_db_path)
                        create_raw_str = '''
                            create table if not exists zhdl_raw (
                                id integer primary key,
                                timestamp integer,
                                device_num integer,
                                speed real,
                                x real not null,
                                y real not null,
                                theta real not null,
                                image blob not null,
                                is_keypoint integer not null,
                                pairid integer
                            );
                        '''
                        create_map_str = '''
                            create table if not exists zhdl_map (
                                id integer primary key,
                                x real not null,
                                y real not null,
                                heading real not null,
                                processed_image blob,
                                raw_image blob
                            );
                        '''
                        create_link_str = '''
                            create table if not exists zhdl_link (
                                id integer primary key,
                                raw_id integer not null,
                                link_id integer not null,
                                x real not null,
                                y real not null,
                                theta real not null,
                                is_keypoint integer not null
                            );
                        '''
                        curs = conn.cursor()
                        curs.execute(create_raw_str)
                        curs.execute(create_map_str)
                        curs.execute(create_link_str)
                        conn.commit()
                        conn.close()
                        self.export_db_thread = ThreadExportPixDB(self.main_widget, self.export_db_path)
                        self.export_db_thread.start()
                        self.export_db_thread.signal.connect(self.handle_progress_bar)
                    except Exception as e:
                        traceback.print_exc()
                else:
                    return

        except Exception as e:
            traceback.print_exc()

    def gen_config_gradient_param(self):
        try:
            about = MvGenConfig(self.main_widget)
            about.show()
            about.exec_()
        except Exception as e:
            traceback.print_exc()

    def gen_basic_dataset(self):
        try:
            self.gen_basedata_thread = ThreadGenBaseData(self.main_widget)
            self.gen_basedata_thread.start()
            self.gen_basedata_thread.signal.connect(self.handle_progress_bar_gen_basedata)
            self.gen_basedata_thread.finished.connect(self.handle_gen_basedata_finished)
        except Exception as e:
            traceback.print_exc()

    def gen_sqlite_db(self):
        try:
            self.gen_db_thread = ThreadGenDB(self.main_widget)
            self.gen_db_thread.start()
            self.gen_db_thread.signal.connect(self.handle_progress_bar_gen_gradient_db)
            self.gen_db_thread.finished.connect(self.handle_gen_db_finished)
            self.using_db = False
        except Exception as e:
            traceback.print_exc()

    def gen_gradient_update(self):
        pass

    def socket_open_data_port(self):
        try:
            about = MvSocket(self.main_widget)
            about.show()
            about.exec_()
        except Exception as e:
            traceback.print_exc()

    def socket_export_to_sqlite(self):
        pass

    def about_version(self):
        try:
            about = MvAbout()
            about.show()
            about.exec_()
        except Exception as e:
            traceback.print_exc()

    def about_help(self):
        pass


if __name__ == '__main__':
    try:
        app = QApplication(sys.argv)
        app.setStyle('Fusion')
        map = MvWindow()
        sys.exit(app.exec_())
    except Exception as e:
        traceback.print_exc()
