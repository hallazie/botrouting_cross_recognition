#coding:utf-8

import os
import sys
import logging
import traceback
import sqlite3
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QImage, QTransform, QBrush, QPen
from PyQt5.QtWidgets import QWidget, QApplication, QMainWindow, QGraphicsView, QGraphicsScene, \
    QGraphicsItem, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QLineEdit, QFrame, QStatusBar, \
    QAction, QListWidget, QListWidgetItem, QGraphicsLineItem, QErrorMessage, QProgressBar, QFileDialog, QDialog
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

class MvView(QGraphicsView):
    def __init__(self, scene, parent):
        QGraphicsView.__init__(self, scene, parent)
        self.setSceneRect(0, 0, scene.width(), scene.height())
        self.setViewport(QGLWidget())
        self.scene = scene
        self.drag_canvas_flag = False
        self.prev_x, self.prev_y = 0, 0

    def wheelEvent(self, QWheelEvent):
        try:
            if QWheelEvent.angleDelta().y() > 0:
                if self.scene.scale < 16:
                    self.scene.scale *= self.scene.scale_factor
                    print('zoom bigger: %f'%self.scene.scale)
            else:
                if self.scene.scale > 0.0625:
                    self.scene.scale /= self.scene.scale_factor
                    print('zoom small: %f'%self.scene.scale)
            self.setTransform(QTransform.fromScale(self.scene.scale, self.scene.scale), False)
        except Exception as e:
            traceback.print_exc()


class MvAbout(QDialog):
    def __init__(self):
        QDialog.__init__(self)
        self.setGeometry(320, 120, 480, 480)
        self.box = QVBoxLayout()
        self.lbl001 = QLabel('Quicktron')
        self.lbl002 = QLabel('Texture Localization')
        self.setLayout(self.box)
        self.box.addWidget(self.lbl001)
        self.box.addWidget(self.lbl002)


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

        self.scale = 1.0
        self.scale_factor = 1.1
        self.m2p_ratio = 0.40625
        self.x_axis_gap = 1000
        self.y_axis_gap = 1000

        self.ctrl_selected_idx = None
        self.dclick_selected_idx = None
        self.dclick_selected_item = None

    def mousePressEvent(self, QGraphicsSceneMouseEvent):
        try:
            modifier = QApplication.keyboardModifiers()
            if QGraphicsSceneMouseEvent.button() == 4:
                # dragging the whole scene
                self.drag_canvas_flag = True
            elif QGraphicsSceneMouseEvent.button() == 1:
                # dragging (shifting) single selected item
                self.drag_item_flag = True
                if modifier == Qt.ControlModifier:
                    self.ctrl_selected_idx = self.itemAt(QGraphicsSceneMouseEvent.scenePos(), QTransform()).idx
            elif QGraphicsSceneMouseEvent.button() == 2:
                # rotating single selected item
                self.rotate_item_flag = True
                if modifier == Qt.ControlModifier:
                    self.ctrl_selected_idx = self.itemAt(QGraphicsSceneMouseEvent.scenePos(), QTransform()).idx
            self.prev_x = QGraphicsSceneMouseEvent.scenePos().x()
            self.prev_y = QGraphicsSceneMouseEvent.scenePos().y()
        except Exception as e:
            traceback.print_exc()

    def mouseMoveEvent(self, QGraphicsSceneMouseEvent):
        try:
            self.mouse_x = QGraphicsSceneMouseEvent.scenePos().x()
            self.mouse_y = QGraphicsSceneMouseEvent.scenePos().y()
            self.main_widget.val_mouse_pos = '鼠标位置：%s, %s' % (round(self.mouse_x - self.total_shift_x, 2), -1 * round(self.mouse_y - self.total_shift_y, 2))
            self.main_widget.lbl_mouse_pos.setText(self.main_widget.val_mouse_pos)
            delta_x = QGraphicsSceneMouseEvent.scenePos().x() - self.prev_x
            delta_y = QGraphicsSceneMouseEvent.scenePos().y() - self.prev_y
            self.prev_x = QGraphicsSceneMouseEvent.scenePos().x()
            self.prev_y = QGraphicsSceneMouseEvent.scenePos().y()

            if self.drag_canvas_flag == True:
            # dragging the hole canvas, need to adjust the total shift, too.
                for k in self.pix_dict:
                    self.pix_dict[k].moveBy(delta_x, delta_y)
                for i in range(len(self.grid_list)):
                    self.grid_list[i].moveBy(delta_x, delta_y)
                self.total_shift_x += delta_x
                self.total_shift_y += delta_y

            elif self.drag_item_flag == True and self.ctrl_selected_idx != None:
                self.pix_dict[self.ctrl_selected_idx].cx += delta_x
                self.pix_dict[self.ctrl_selected_idx].cy += delta_y
                self.pix_dict[self.ctrl_selected_idx].moveBy(delta_x, delta_y)

            elif self.rotate_item_flag == True and self.ctrl_selected_idx != None:
            # totation
                self.pix_dict[self.ctrl_selected_idx].ct += delta_x / 5.
                self.pix_dict[self.ctrl_selected_idx].setRotation(self.pix_dict[self.ctrl_selected_idx].ct)

        except Exception as e:
            traceback.print_exc()

    def mouseReleaseEvent(self, QGraphicsSceneMouseEvent):
        try:
            if self.drag_canvas_flag == True:
                self.drag_canvas_flag = False
            elif self.drag_item_flag == True:
                self.drag_item_flag = False
                self.ctrl_selected_idx = None
            elif self.rotate_item_flag == True:
                self.rotate_item_flag = False
                self.ctrl_selected_idx = None
        except Exception as e:
            traceback.print_exc()

    def mouseDoubleClickEvent(self, QGraphicsSceneMouseEvent):
        try:
            self.dclick_selected_item = self.itemAt(QGraphicsSceneMouseEvent.scenePos(), QTransform())
            if self.dclick_selected_item != None:
                self.main_widget.val_selected_node_id = '选中节点ID：%s' % self.dclick_selected_item.idx
                self.main_widget.val_selected_node_pos = '选中节点位置：%s, %s' % (round(self.dclick_selected_item.cx, 2), -1*round(self.dclick_selected_item.cy, 2))
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
            err.showMessage('数据库文件"%s"不存在'%path)
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

                    pix = QPixmap.fromImage(ttt).scaled(130, 130, Qt.KeepAspectRatio)
                    # pix = QPixmap('0.bmp').scaled(130, 130, Qt.KeepAspectRatio)
                    img = self.addPixmap(pix)
                    img.setTransformOriginPoint(pix.width()//2, pix.height()//2)
                    img.setRotation(t)
                    img.setPos(x-pix.width()//2, y-pix.height()//2)
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
                    self.maxy = max(y, self.maxy)
                    self.minx = min(x, self.minx)
                    self.miny = min(y, self.miny)
                except Exception as e:
                    traceback.print_exc()
                    break
        except Exception as e:
            traceback.print_exc()
            err = QErrorMessage()
            err.showMessage('读取数据库出错：%s' % e)
            err.exec_()

    def load_all_pixmaps_from_path(self):
        path = 'D:/Data/jx/231/part2/calib_0/'
        path = 'D:/Data/sz/sz_calibs/'
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
                    img.setTransformOriginPoint(pix.width()//2, pix.height()//2)
                    img.setRotation(t)
                    img.setPos(x-pix.width()//2, y-pix.height()//2)
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
        print('%s,%s->%s,%s' % (self.minx//1000, self.miny//1000, self.maxx//1000, self.maxy//1000))
        self.grid_list = []
        grid_pen = QPen(Qt.darkRed)
        grid_pen.setWidth(3)
        for i in range(int(self.minx//self.x_axis_gap), int(self.maxx//self.x_axis_gap)+1):
            self.grid_vert.append((
                i * self.x_axis_gap * self.scale,
                -1 * self.miny,
                i * self.x_axis_gap * self.scale,
                -1 * self.maxy
            ))
        for j in range(int(self.miny//self.y_axis_gap), int(self.maxy//self.y_axis_gap)+1):
            self.grid_horz.append((
                self.minx,
                -1 * j * self.y_axis_gap * self.scale,
                self.maxx,
                -1 * j * self.y_axis_gap * self.scale
            ))

        for e in self.grid_vert:
            line_itm = QGraphicsLineItem(e[0], e[1], e[2], e[3])
            # line_itm.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            line_itm.setPen(grid_pen)
            self.addItem(line_itm)
            self.grid_list.append(line_itm)
        for e in self.grid_horz:
            line_itm = QGraphicsLineItem(e[0], e[1], e[2], e[3])
            # line_itm.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            line_itm.setPen(grid_pen)
            self.addItem(line_itm)
            self.grid_list.append(line_itm)

class LineSeparator(QFrame):
    def __init__(self):
        QFrame.__init__(self)
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)


class MvWidget(QWidget):
    def __init__(self):
        QWidget.__init__(self)
        self.canvas_scene = MvScene(self)
        self.canvas_view = MvView(self.canvas_scene, self)
        self.control_vbox = QVBoxLayout()
        self.root_hbox = QHBoxLayout()

        self.mouse_pos = '-'
        self.selected_node_id = '-'
        self.selected_node_pos = '-'
        self.selected_node_angle = '-'
        self.m2p_ratio = 0.40625

        self.val_mouse_pos = '鼠标位置：%s' % self.mouse_pos
        self.val_selected_node_id = '选中节点ID：%s' % self.selected_node_id
        self.val_selected_node_pos = '选中节点位置：%s' % self.selected_node_pos
        self.val_selected_node_angle = '选中节点角度：%s' % self.selected_node_angle
        self.val_current_scale = '缩放系数：%s' % str(round(self.canvas_scene.scale, 5))
        self.val_btn_set_show_grid = '已打开网格显示'
        self.val_btn_enter_edit_mod = '进入编辑模式'
        self.val_btn_delete_selected_node = '删除选中节点：暂无选中ID'

        self.frm_control_fram = QFrame()
        self.btn_gen_global_view = QPushButton('生成全局地图')
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
        self.box_y_gap = QHBoxLayout()
        self.lbl_y_gap = QLabel('y轴网格间距(mm)')
        self.ent_y_gap = QLineEdit('1000')
        self.btn_set_new_gap = QPushButton('设定新网格间距')
        self.btn_set_show_grid = QPushButton()
        self.btn_set_show_grid.setText(self.val_btn_enter_edit_mod)

        self.box_x_cent = QHBoxLayout()
        self.lbl_x_cent = QLabel('视野中心x值(mm)')
        self.ent_x_cent = QLineEdit('0')
        self.box_y_cent = QHBoxLayout()
        self.lbl_y_cent = QLabel('视野中心y值(mm)')
        self.ent_y_cent = QLineEdit('0')
        self.btn_set_new_cent = QPushButton('设定新中心点')

        self.btn_enter_edit_mod = QPushButton()
        self.btn_enter_edit_mod.setText(self.val_btn_enter_edit_mod)
        self.lst_edit_history = QListWidget()
        self.btn_commit_edit = QPushButton('提交修改')
        self.btn_abort_edit = QPushButton('放弃修改')
        self.box_btn_edit = QHBoxLayout()

        self.btn_delete_selected_node = QPushButton()
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
        self.control_vbox.addWidget(self.btn_enter_edit_mod)
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

    # def mouseMoveEvent(self, QMouseEvent):
    #     self.val_mouse_pos = '鼠标位置：%s, %s' % (self.canvas_scene.mouse_x, self.canvas_scene.mouse_y)
    #     self.lbl_mouse_pos.setText(self.val_mouse_pos)

class MvWindow(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.initUI()
        self.main_widget.canvas_view.setGeometry(120, 0, self.width(), self.height())
        self.main_widget.canvas_view.setMouseTracking(True)
        self.main_widget.canvas_scene.load_all_pixmaps_from_path()
        self.main_widget.canvas_scene.load_grid()

    def initUI(self):
        self.main_widget = MvWidget()
        self.setCentralWidget(self.main_widget)

        self.act_param_config = QAction('参数设置', self)
        self.act_param_config.setStatusTip('对MapViewer的参数进行设置')
        self.act_import_single_img = QAction('导入一张图像', self)
        self.act_import_single_img_commit = QAction('提交导入图像', self)
        self.act_import_labeled_set = QAction('导入标注集合', self)
        self.act_import_raw_set = QAction('导入未标注集合', self)
        self.act_fix_labeled_set = QAction('固定标注集', self)
        self.act_label_n_filter = QAction('标注去重', self)
        self.act_import_from_sqlite = QAction('从Sqlite导入', self)
        self.act_export_to_sqlite = QAction('往Sqlite导出', self)
        self.act_gen_config_gradient_param = QAction('配置地图生成参数', self)
        self.act_gen_basic_dataset = QAction('生成基础数据集(640×640)', self)
        self.act_gen_sqlite_db = QAction('生成数据库(320×320)', self)
        self.act_gen_gradient_update = QAction('梯度下降更新', self)
        self.act_socket_open_data_port = QAction('打开图像采集Socket', self)
        self.act_socket_export_to_sqlite = QAction('将采集图像到处为Sqlite', self)
        self.act_about_version = QAction('关于Quicktron Mapviewer', self)
        self.act_about_help = QAction('使用说明', self)

        self.act_param_config.triggered.connect(self.open_param_config)
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
        self.setStatusBar(self.status)
        self.setMenuBar(self.menu)
        self.setWindowTitle('Quicktron Map Viewer')
        self.setGeometry(0, 0, 1080, 780)
        self.show()

    # ------------------------------------- menubar function -------------------------------------

    def open_param_config(self):
        pass

    def import_single_img(self):
        pass

    def import_single_img_commit(self):
        pass

    def import_labeled_set(self):
        pass

    def import_raw_set(self):
        pass

    def fix_labeled_set(self):
        pass

    def label_n_filter(self):
        pass

    def import_from_sqlite(self):
        try:
            options = QFileDialog.Options()
            options |= QFileDialog.DontUseNativeDialog
            filter = 'db(*.db)'
            path, _ = QFileDialog.getOpenFileName(self, '.db 数据库文件 (*.db)', options=options, filter=filter)
            if not path.endswith('.db'):
                return
            self.main_widget.canvas_scene.load_all_pixmaps_from_db(path)
            self.main_widget.canvas_scene.load_grid()
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
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    map = MvWindow()
    sys.exit(app.exec_())
