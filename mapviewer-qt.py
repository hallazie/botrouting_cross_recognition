# coding:utf-8

import os
import sys
import logging
import traceback
import sqlite3
import numpy as np
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


class LineSeparator(QFrame):
    def __init__(self):
        QFrame.__init__(self)
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)


class ThreadLoadPixPath(QThread):
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
            # self.main_widget.canvas_scene.clear()
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
        err = QErrorMessage()
        try:
            self.main_widget.canvas_view.setInteractive(False)
            self.main_widget.canvas_view.lock_zooming = True
            # QApplication.setOverrideCursor(Qt.WaitCursor)
            self.signal.emit('start:0')
            print('disabling canvas view interaction due to data loading...')
            if not os.path.exists(self.path):
                err.showMessage('数据库文件"%s"不存在' % path)
                err.exec_()
                return
            while self.isrunning:
                try:
                    conn = sqlite3.connect(self.path)
                    curs = conn.cursor()
                    cnt = curs.execute('select count(id) from zhdl_map').__next__()[0]
                    if cnt == 0:
                        err.showMessage('当前数据库中无有效地图文件')
                        err.exec_()
                        return
                except Exception as e:
                    traceback.print_exc()
                    err.showMessage('读取数据库出错，请正确配置数据库文件\n错误信息：%s' % e)
                    err.exec_()
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


class ThreadHDGlobalMap(QThread):
    signal = pyqtSignal('PyQt_PyObject')
    def __init__(self, main_widget):
        QThread.__init__(self, main_widget)
        self.main_widget = main_widget
        self.isrunning = True

    def run(self):
        err = QErrorMessage()
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
            self.signal.emit('stop:0')
        except Exception as e:
            traceback.print_exc()

class MvAbout(QDialog):
    def __init__(self):
        QDialog.__init__(self)
        self.setGeometry(320, 120, 480, 480)
        self.box = QVBoxLayout()
        self.lbl001 = QLabel('Quicktron')
        self.lbl002 = QLabel('Texture Localization')
        self.box.addWidget(self.lbl001)
        self.box.addWidget(self.lbl002)
        self.setLayout(self.box)


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
            self.gen_global_view()
            self.gv_lbl_image.setPixmap(self.gv_pixmap)
            self.vbox.addWidget(self.gv_lbl_image)
            self.setWindowTitle('global view')
            self.setGeometry(320, 120, self.gv_width, self.gv_height)
            self.setLayout(self.vbox)
            self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowSystemMenuHint)
            self.setFixedSize(self.gv_width, self.gv_height)
            self.show()

        except Exception as e:
            traceback.print_exc()

    def gen_global_view(self):
        try:
            width_max = 960
            height_max = 640
            canvas_width_param = self.main_widget.canvas_scene.maxx - self.main_widget.canvas_scene.minx + 2000
            canvas_height_param = self.main_widget.canvas_scene.maxy - self.main_widget.canvas_scene.miny + 2000
            if canvas_width_param > canvas_height_param:
                self.gv_width = width_max
                self.zoom_scale = float(width_max) / canvas_width_param
                self.gv_height = int(width_max * canvas_width_param / canvas_height_param)
            else:
                self.gv_height = height_max
                self.zoom_scale = float(height_max) / canvas_height_param
                self.gv_width = int(height_max * canvas_height_param / canvas_width_param)
            img_scale = max(int(320 * self.zoom_scale * M2PRATIO), 1)
            self.gv_canvas = np.zeros((self.gv_width, self.gv_height))
            for k in self.main_widget.canvas_scene.pix_dict:
                itm = self.main_widget.canvas_scene.pix_dict[k]
                arr = np.array(imq.fromqpixmap(itm.pixmap()).convert('L').resize((img_scale, img_scale)))
                pos_x = int(self.gv_width * (itm.ox - self.main_widget.canvas_scene.minx + 1000) / canvas_width_param)
                pos_y = int(self.gv_height * (itm.oy - self.main_widget.canvas_scene.miny + 1000) / canvas_height_param)
                self.gv_canvas[pos_x-img_scale//2:pos_x-img_scale//2+img_scale, pos_y-img_scale//2:pos_y-img_scale//2+img_scale] = arr
            self.gv_image = im.fromarray(self.gv_canvas.astype('uint8'))
            self.gv_pixmap = imq.toqpixmap(self.gv_image)
            self.gv_image.save(os.path.dirname(os.path.realpath(__file__))+os.path.sep + '/'+'global_view.png')

        except Exception as e:
            traceback.print_exc()

class MvSocket(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.main_widget = parent


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

    def mousePressEvent(self, QGraphicsSceneMouseEvent):
        try:
            print('shift:(%s,%s)'%(self.total_shift_x, self.total_shift_y))
            print('scene:(%s,%s)'%(QGraphicsSceneMouseEvent.scenePos().x() * M2PRATIO, -1*QGraphicsSceneMouseEvent.scenePos().y() * M2PRATIO))
            modifier = QApplication.keyboardModifiers()
            if QGraphicsSceneMouseEvent.button() == 4:
                # dragging the whole scene
                self.drag_canvas_flag = True
            elif QGraphicsSceneMouseEvent.button() == 1:
                # dragging (shifting) single selected item
                if modifier == Qt.ControlModifier:
                    if self.itemAt(QGraphicsSceneMouseEvent.scenePos(), QTransform()) != None:
                        self.ctrl_selected_itm = self.itemAt(QGraphicsSceneMouseEvent.scenePos(), QTransform())
                        self.main_widget.update_selected_info(self.ctrl_selected_itm.idx, self.ctrl_selected_itm.cx,
                                                              self.ctrl_selected_itm.cy, self.ctrl_selected_itm.ct)
                        self.drag_item_flag = True
                        if self.ctrl_selected_itm.idx not in self.main_widget.edit_data_dict.keys():
                            self.main_widget.edit_data_dict[self.ctrl_selected_itm.idx] = [0, 0, 0]
            elif QGraphicsSceneMouseEvent.button() == 2:
                # rotating single selected item
                if modifier == Qt.ControlModifier:
                    if self.itemAt(QGraphicsSceneMouseEvent.scenePos(), QTransform()) != None:
                        self.ctrl_selected_itm = self.itemAt(QGraphicsSceneMouseEvent.scenePos(), QTransform())
                        self.main_widget.update_selected_info(self.ctrl_selected_itm.idx, self.ctrl_selected_itm.cx,
                                                              self.ctrl_selected_itm.cy, self.ctrl_selected_itm.ct)
                        self.rotate_item_flag = True
                        if self.ctrl_selected_itm.idx not in self.main_widget.edit_data_dict.keys():
                            self.main_widget.edit_data_dict[self.ctrl_selected_itm.idx] = [0, 0, 0]
            self.prev_x = QGraphicsSceneMouseEvent.scenePos().x()
            self.prev_y = QGraphicsSceneMouseEvent.scenePos().y()
        except Exception as e:
            traceback.print_exc()

    def mouseMoveEvent(self, QGraphicsSceneMouseEvent):
        try:
            self.main_widget.canvas_view.lock_zooming = True
            self.mouse_x = QGraphicsSceneMouseEvent.scenePos().x()
            self.mouse_y = QGraphicsSceneMouseEvent.scenePos().y()
            self.main_widget.val_mouse_pos = '鼠标位置：%s, %s' % (
            round((self.mouse_x - self.total_shift_x) * M2PRATIO, 2), -1 * round((self.mouse_y + self.total_shift_y) * M2PRATIO, 2))
            self.main_widget.lbl_mouse_pos.setText(self.main_widget.val_mouse_pos)
            delta_x = QGraphicsSceneMouseEvent.scenePos().x() - self.prev_x
            delta_y = QGraphicsSceneMouseEvent.scenePos().y() - self.prev_y
            self.prev_x = QGraphicsSceneMouseEvent.scenePos().x()
            self.prev_y = QGraphicsSceneMouseEvent.scenePos().y()

            if self.drag_canvas_flag == True:
                # dragging the hole canvas, need to adjust the total shift, too.
                self.drag_canvas(delta_x, delta_y)

            elif self.drag_item_flag == True and self.ctrl_selected_itm.idx != None:
                # shift
                self.pix_dict[self.ctrl_selected_itm.idx].cx += delta_x * M2PRATIO
                self.pix_dict[self.ctrl_selected_itm.idx].cy += delta_y * M2PRATIO
                self.pix_dict[self.ctrl_selected_itm.idx].moveBy(delta_x, delta_y)
                self.main_widget.edit_data_dict[self.ctrl_selected_itm.idx][0] += delta_x * M2PRATIO
                self.main_widget.edit_data_dict[self.ctrl_selected_itm.idx][1] += delta_y * M2PRATIO

            elif self.rotate_item_flag == True and self.ctrl_selected_itm.idx != None:
                # totation
                self.pix_dict[self.ctrl_selected_itm.idx].ct += (delta_x * M2PRATIO / 5.)
                self.main_widget.edit_data_dict[self.ctrl_selected_itm.idx][2] += (delta_x * M2PRATIO / 5.)
                self.pix_dict[self.ctrl_selected_itm.idx].setRotation(self.pix_dict[self.ctrl_selected_itm.idx].ct + self.pix_rotate)
            self.main_widget.canvas_view.lock_zooming = False
        except Exception as e:
            traceback.print_exc()

    def mouseReleaseEvent(self, QGraphicsSceneMouseEvent):
        try:
            if self.drag_canvas_flag == True:
                self.drag_canvas_flag = False
            elif self.drag_item_flag == True:
                self.drag_item_flag = False
                self.ctrl_selected_itm = None
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
            elif self.rotate_item_flag == True:
                self.rotate_item_flag = False
                self.ctrl_selected_itm = None
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

    def mouseDoubleClickEvent(self, QGraphicsSceneMouseEvent):
        try:
            self.dclick_selected_item = self.itemAt(QGraphicsSceneMouseEvent.scenePos(), QTransform())
            if self.dclick_selected_item != None:
                self.main_widget.val_selected_node_id = '选中节点ID：%s' % self.dclick_selected_item.idx
                self.main_widget.val_selected_node_pos = '坐标：%s, %s' % (
                round(self.dclick_selected_item.cx, 2), -1 * round(self.dclick_selected_item.cy, 2))
                self.main_widget.val_selected_node_angle = '选中节点角度：%s' % self.dclick_selected_item.ct
                self.main_widget.lbl_selected_node_id.setText(self.main_widget.val_selected_node_id)
                self.main_widget.lbl_selected_node_pos.setText(self.main_widget.val_selected_node_pos)
                self.main_widget.lbl_selected_node_angle.setText(self.main_widget.val_selected_node_angle)
            else:
                self.main_widget.val_selected_node_id = '选中节点ID：-'
                self.main_widget.val_selected_node_pos = '选中节点位置：-'
                self.main_widget.val_selected_node_angle = '选中节点角度：-'
                self.main_widget.lbl_selected_node_id.setText(self.main_widget.val_selected_node_id)
                self.main_widget.lbl_selected_node_pos.setText(self.main_widget.val_selected_node_pos)
                self.main_widget.lbl_selected_node_angle.setText(self.main_widget.val_selected_node_angle)
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
                -1 * self.miny / M2PRATIO,
                i * self.x_axis_gap * self.scale / M2PRATIO,
                -1 * self.maxy / M2PRATIO
            ))
        for j in range(int(self.miny // self.y_axis_gap), int(self.maxy // self.y_axis_gap) + 1):
            self.grid_horz.append((
                self.minx / M2PRATIO,
                -1 * j * self.y_axis_gap * self.scale / M2PRATIO,
                self.maxx / M2PRATIO,
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
            # midx = (self.main_widget.canvas_view.scene.maxx-self.main_widget.canvas_view.scene.minx)/M2PRATIO/2
            # midy = (self.main_widget.canvas_view.scene.maxy-self.main_widget.canvas_view.scene.miny)/M2PRATIO/2
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
            for k in self.pix_dict:
                self.removeItem(self.pix_dict[k])
            for e in self.grid_list:
                self.removeItem(e)
            self.pix_dict = {}
            self.grid_list = []
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

    # def fast_navigate_by_pos(self, x, y):
    #     # print(self.main_widget.canvas_view.size())
    #     # print(self.main_widget.canvas_view.width())
    #     # print(self.main_widget.canvas_view.height())
    #     dx = -1 * x / M2PRATIO - self.total_shift_x + self.main_widget.canvas_view.width()//2
    #     dy = 1 * y / M2PRATIO + self.total_shift_y - self.main_widget.canvas_view.height()//2
    #     self.drag_canvas(dx, dy)

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

        self.box_x_cent = QHBoxLayout()
        self.lbl_x_cent = QLabel('视野中心x值(mm)')
        self.ent_x_cent = QLineEdit('0')
        self.ent_x_cent.setText('18000')
        self.ent_x_cent.setValidator(QDoubleValidator())
        self.box_y_cent = QHBoxLayout()
        self.lbl_y_cent = QLabel('视野中心y值(mm)')
        self.ent_y_cent = QLineEdit('0')
        self.ent_y_cent.setText('20000')
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
                        self.canvas_scene.pix_dict[k].ot += self.edit_data_dict[k][2]
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
                        self.canvas_scene.pix_dict[k].ot += self.edit_data_dict[k][2]
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
                self.canvas_scene.pix_dict[k].ct -= dt
                self.canvas_scene.pix_dict[k].moveBy(-dx / M2PRATIO, -dy / M2PRATIO)
                self.canvas_scene.pix_dict[k].setRotation(self.canvas_scene.pix_dict[k].ct)
            self.edit_data_dict = {}
            self.clear_edit_history()
        except Exception as e:
            traceback.print_exc()

    def edit_delete_handler(self):
        pass

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
        self.act_import_single_img = QAction('× 导入一张图像', self)
        self.act_import_single_img_commit = QAction('× 提交导入图像', self)
        self.act_import_labeled_set = QAction('× 导入标注集合', self)
        self.act_import_raw_set = QAction('导入未标注集合', self)
        self.act_fix_labeled_set = QAction('× 固定标注集', self)
        self.act_label_n_filter = QAction('× 标注去重', self)
        self.act_import_from_sqlite = QAction('从Sqlite导入', self)
        self.act_export_to_sqlite = QAction('× 往Sqlite导出', self)
        self.act_gen_config_gradient_param = QAction('配置地图生成参数', self)
        self.act_gen_basic_dataset = QAction('生成基础数据集(640×640)', self)
        self.act_gen_sqlite_db = QAction('生成数据库(320×320)', self)
        self.act_gen_gradient_update = QAction('梯度下降更新', self)
        self.act_socket_open_data_port = QAction('× 打开图像采集Socket', self)
        self.act_socket_export_to_sqlite = QAction('× 将采集图像导出为Sqlite', self)
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
            k, v = msg.split(':')
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
        pass

    def import_raw_set(self):
        try:
            self.raw_path = os.path.normpath(QFileDialog.getExistingDirectory(self)).replace('\\', '/')
            self.load_path_thread = ThreadLoadPixPath(self.main_widget, self.raw_path)
            self.load_path_thread.start()
            self.load_path_thread.signal.connect(self.handle_progress_bar)
            self.load_path_thread.finished.connect(self.main_widget.canvas_scene.handle_load_pixmaps_finished)
            self.using_db = False
        except Exception as e:
            traceback.print_exc()

    def fix_labeled_set(self):
        pass

    def label_n_filter(self):
        pass

    def import_from_sqlite(self):
        try:
            options = QFileDialog.Options()
            options |= QFileDialog.DontUseNativeDialog
            filter = 'db(*.db)'
            self.db_path, _ = QFileDialog.getOpenFileName(self, '.db 数据库文件 (*.db)', options=options, filter=filter)
            if not self.db_path.endswith('.db'):
                return
            self.load_db_thread = ThreadLoadPixDB(self.main_widget, self.db_path)
            self.load_db_thread.start()
            self.load_db_thread.signal.connect(self.handle_progress_bar)
            self.using_db = True
        except Exception as e:
            traceback.print_exc()

    def export_to_sqlite(self):
        pass

    def gen_config_gradient_param(self):
        pass

    def gen_basic_dataset(self):
        pass

    def gen_sqlite_db(self):
        pass

    def gen_gradient_update(self):
        pass

    def socket_open_data_port(self):
        pass

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
