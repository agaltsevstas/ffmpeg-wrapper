import sys

if sys.version_info[0] < 3:
    sys.stderr.write("You need Python 3 or later to run this script!\n")
    sys.exit(1)

import subprocess as sp
from PIL import Image
from pathlib import Path
from PyQt5 import QtCore, QtWidgets, QtGui
from functools import partial
from natsort import natsorted
from collections import namedtuple

VideoInfo = namedtuple('VideoInfo', ('STATUS', 'CODEC', 'WIDTH', 'HEIGHT', 'FPS', 'DURATION', 'FRAMES_QUANTITY'))
ImageInfo = namedtuple('ImageInfo', ('STATUS', 'TYPE', "MODE", 'WIDTH', 'HEIGHT'))
PYTHON = 'python3'
FFMPEG = 'ffmpeg'
FFPROBE = 'ffprobe'
WRAPPER = "wrapper.py"
RENAMER = 'rebase_frames.py'

def deleteItemsOfLayout(layout):
    if layout is not None:
        item = layout.takeAt(7)
        widget = item.widget()
        widget.setParent(None)

def get_video_info(video_file):
    # Соблюдать этот порядок полей при обработки вывода ffprobe
    fields = (
        'codec_long_name',
        'width',
        'height',
        'r_frame_rate',
        'duration',
        'nb_frames',
    )

    sep = ','
    on_error = VideoInfo(False, 'Unknown', 0, 0, 0.0, 0.0, 0)
    # on_error = 'Unknown', 0, 0, 0.0, 0.0, 0

    ff_cmd = [str(FFPROBE), '-v', '0', '-of', 'csv=p=0', '-select_streams', 'v:0',
              '-show_entries', 'stream={}'.format(sep.join(fields)), str(Path(video_file))]

    try:
        return VideoInfo(
            True,
            *(action(item) for item, action in zip(
                sp.check_output(ff_cmd).decode(sys.stdout.encoding).rstrip('\n').split(sep),
                (str, int, int, eval, float, int)
            ))
        )
    except (sp.CalledProcessError, AttributeError, ValueError, TypeError) as e:
        return on_error
    except FileNotFoundError as os_err:
        print(os_err)
        sys.exit(1)

def get_image_info(image_file):
    image = Image.open(image_file)
    width, height = image.size
    return image.format, image.mode, width, height

class BlockWindow(QtWidgets.QWidget):

    def __init__(self, message="", parent=None):
        super().__init__()
        self.setWindowTitle('Обработка')
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
        self.resize(200, 50)

        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)

        vbox.addWidget(QtWidgets.QLabel(message))


class TableView(QtWidgets.QTableView):

    SUPPORTED_MEDIA_FORMAT = (".avi", ".mp4")

    def __init__(self, parent=None):
        super(TableView, self).__init__(parent=None)

        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.setSortingEnabled(True)

        self.mode = None
        self.names_sti = []
        self.table_sti = QtGui.QStandardItemModel()
        self.setModel(self.table_sti)

    def append_to_table(self, path):
        self.table_sti.setHorizontalHeaderLabels(self.names_sti)
        if self.mode == 1:
            video_info = get_video_info(path)
            if video_info.STATUS:
                pathItem = QtGui.QStandardItem()
                pathItem.setData(str(path))
                pathItem.setText(path.name)
                self.table_sti.appendRow([pathItem] + [QtGui.QStandardItem(str(v)) for v in video_info[1:]])
        elif self.mode == 2:
            image_info = get_image_info(path)
            pathItem = QtGui.QStandardItem()
            pathItem.setData(str(path))
            pathItem.setText(path.name)
            self.table_sti.appendRow([pathItem] + [QtGui.QStandardItem(str(v)) for v in image_info])

class Window(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__()

        self.setWindowTitle("FFMPEG wrapper")

        self.output = None
        self.last_pwd = QtCore.QDir.homePath()

        vbox = QtWidgets.QVBoxLayout()

        tablebox = QtWidgets.QHBoxLayout()
        controlbox = QtWidgets.QVBoxLayout()
        vbox.addLayout(tablebox)
        vbox.addLayout(controlbox)
        self.setLayout(vbox)

        buttonbox = QtWidgets.QHBoxLayout()
        self.buttonbox_media = QtWidgets.QHBoxLayout()
        buttonbox_frames = QtWidgets.QHBoxLayout()

        controlbox.addLayout(buttonbox)
        controlbox.addLayout(self.buttonbox_media)
        controlbox.addLayout(buttonbox_frames)

        self.tv = TableView(parent=self)
        tablebox.addWidget(self.tv)

        clear_table_btn = QtWidgets.QPushButton('Очистить')
        clear_table_btn.clicked.connect(self.on_clear_table)

        grouping_btn = QtWidgets.QPushButton('Группировать')
        grouping_btn.clicked.connect(self.grouping_start)

        load_media_btn = QtWidgets.QPushButton("Добавить видео ")
        load_media_btn.clicked.connect(self.on_load_media)

        execute_media_btn = QtWidgets.QPushButton('Извлечь кадры')
        execute_media_btn.clicked.connect(self.on_execute)

        load_frames_btn = QtWidgets.QPushButton("Добавить кадры")
        load_frames_btn.clicked.connect(self.on_load_frames)

        execute_frames_btn = QtWidgets.QPushButton("Извлечь кадры")
        execute_frames_btn.clicked.connect(self.on_load_frames)

        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.activated.connect(self.on_change_combobox)
        self.mode_combo.addItem('Извлечь все')
        self.mode_combo.addItem('Интервал в кадрах')
        self.mode_combo.addItem('Интервал в секундах')

        self.step_field = QtWidgets.QSpinBox()
        self.step_field.hide()

        self.frames_field = QtWidgets.QSpinBox()
        self.frames_field.setAlignment(QtCore.Qt.AlignRight)
        self.frames_field.setRange(1, 10**6)

        buttonbox.addWidget(clear_table_btn)
        buttonbox.addWidget(grouping_btn)
        buttonbox.addStretch(0)
        self.buttonbox_media.addWidget(QtWidgets.QLabel('Работа с видеофайлами  '))
        self.buttonbox_media.addWidget(load_media_btn)
        self.buttonbox_media.addWidget(execute_media_btn)
        self.buttonbox_media.addWidget(QtWidgets.QLabel('Режим работы:  '))
        self.buttonbox_media.addWidget(self.mode_combo)
        self.buttonbox_media.addWidget(self.step_field)
        self.buttonbox_media.addStretch(0)
        buttonbox_frames.addWidget(QtWidgets.QLabel('Работа с изображениями'))
        buttonbox_frames.addWidget(load_frames_btn)
        buttonbox_frames.addWidget(execute_frames_btn)
        buttonbox_frames.addWidget(QtWidgets.QLabel('Удалять каждый'))
        buttonbox_frames.addWidget(self.frames_field)
        buttonbox_frames.addWidget(QtWidgets.QLabel('кадр'))
        buttonbox_frames.addStretch(0)

        self.modal_extracting = BlockWindow(
            message='Внимание! Идет извлечение кадров.\nПожалуйста, не закрывайте программу.',
            parent=self
        )
        self.modal_grouping = BlockWindow(
            message='Внимание! Идет обработка\nПожалуйста, не закрывайте программу.',
            parent=self
        )

        self.extraction_process = QtCore.QProcess()
        self.extraction_process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.extraction_process.finished.connect(self.on_extraction_finished)

        self.groping_process = QtCore.QProcess()
        self.groping_process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.groping_process.finished.connect(self.on_grouping_finished)

    @QtCore.pyqtSlot()
    def grouping_start(self):
        dialog = QtWidgets.QFileDialog()
        dialog.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
        dialog.setOption(QtWidgets.QFileDialog.ShowDirsOnly)
        _dir = dialog.getExistingDirectory(
            self, directory=str(self.last_pwd), caption="Выберите директорию:"
        )
        if _dir:
            self.modal_grouping.show()
            self.groping_process.start(str(PYTHON), [str(RENAMER), _dir])


    @QtCore.pyqtSlot()
    def on_extraction_finished(self):
        self.modal_extracting.close()

    @QtCore.pyqtSlot()
    def on_grouping_finished(self):
        self.modal_grouping.close()
        QtWidgets.QMessageBox.information(self, 'Готово!', "Групировка завершена.", QtWidgets.QMessageBox.Ok)

    @QtCore.pyqtSlot()
    def on_change_combobox(self):
        if self.buttonbox_media.count() >= 8:
            deleteItemsOfLayout(self.buttonbox_media)
        i = self.mode_combo.currentIndex()

        if i > 0:
            if i == 1:
                self.step_field = QtWidgets.QSpinBox()
                self.step_field.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
                self.step_field.setAlignment(QtCore.Qt.AlignRight)
                self.step_field.setRange(1, 10**6)
            elif i == 2:
                self.step_field = QtWidgets.QDoubleSpinBox()
                self.step_field.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
                self.step_field.setAlignment(QtCore.Qt.AlignRight)
                self.step_field.setRange(0.1, 24*60*60)

            self.buttonbox_media.addWidget(self.step_field)
            # self.buttonbox_media.addStretch(1)

    @QtCore.pyqtSlot()
    def on_clear_table(self):
        selected_rows = self.tv.selectedIndexes()[::self.tv.table_sti.columnCount()]
        if len(selected_rows):
            for QModelIndex in reversed(selected_rows):
                self.tv.table_sti.removeRow(QModelIndex.row())
        else:
            self.tv.table_sti.removeRows(0, self.tv.table_sti.rowCount())

    def get_output(self, message):
        dialog = QtWidgets.QFileDialog()
        dialog.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
        dialog.setOption(QtWidgets.QFileDialog.ShowDirsOnly)
        _dir = dialog.getExistingDirectory(
            self, directory=str(self.last_pwd), caption=message
        )
        if _dir:
            self.output = Path(_dir)

    @QtCore.pyqtSlot()
    def on_execute(self):
        if self.tv.table_sti.rowCount() > 0:
            self.get_output("Выберите директорию для извлеченных кадров:")

            if not self.output.is_dir():
                QtWidgets.QMessageBox.critical(
                    self, 'Ошибка', "Директория назначения не выбрана", QtWidgets.QMessageBox.Ok
                )
            else:
                files = [self.tv.table_sti.item(i, 0).data() for i in range(self.tv.table_sti.rowCount())]

                if len(files) > 0:
                    args = [
                        str(WRAPPER),
                        '--input', *files,
                        '--output', str(self.output),
                        'extract',
                    ]
                    params = self.get_parameters()
                    if params is not None:
                        args.extend(params)
                    self.modal_extracting.show()

                    # sp.run(cmd)
                    self.extraction_process.start(str(PYTHON), args)

        else:
            QtWidgets.QMessageBox.critical(
                self, 'Список файлов пуст!',
                "Не указаны видеофайлы для извлечения кадров. Добавьте видеофайлы!",
                QtWidgets.QMessageBox.Ok
            )

    @QtCore.pyqtSlot()
    def on_load_media(self):
        dialog = QtWidgets.QFileDialog()
        dialog.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
        files, st = dialog.getOpenFileNames(self, caption="Выберите видеофайлы:", directory=str(self.last_pwd),
                                            filter="Видеофайлы({})".format(
                                                ' '.join('*.' + ext for ext in ('avi', 'mp4', 'mpg', 'mov', 'mkv'))))

        if files:
            if self.tv.mode == 2:
                self.tv.table_sti.clear()
            self.tv.mode = 1
            self.tv.names_sti = ["Media", 'CODEC', 'WIDTH', 'HEIGHT', 'FPS', 'DURATION', 'FRAMES_QUANTITY']
            files = list(map(Path, files))
            _f = files[-1]
            if _f.is_file():
                self.last_pwd = _f.parent

        for f in natsorted(set(files) - set(self.tv.table_sti.item(i, 0).data() for i in range(self.tv.table_sti.rowCount()))):
            self.tv.append_to_table(f)

    @QtCore.pyqtSlot()
    def on_load_frames(self):
        dialog = QtWidgets.QFileDialog()
        dialog.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
        files, st = dialog.getOpenFileNames(self, caption="Выберите изображения:", directory=str(self.last_pwd),
                                            filter="Изображения({})".format(
                                                ' '.join('*.' + ext for ext in ('png', 'jpg', 'jpeg', 'bmp', 'gif'))))

        if files:
            if self.tv.mode == 1:
                self.tv.table_sti.clear()
            self.tv.mode = 2
            self.tv.names_sti = ["Frames", 'TYPE', "MODE", 'WIDTH', 'HEIGHT']
            files = list(map(Path, files))
            _f = files[-1]
            if _f.is_file():
                self.last_pwd = _f.parent

        for f in natsorted(set(files) - set(self.tv.table_sti.item(i, 0).data() for i in range(self.tv.table_sti.rowCount()))):
            self.tv.append_to_table(f)

    def keyPressEvent(self, QKeyEvent):
        actions = {
            QtCore.Qt.Key_Escape: self.close
        }
        key = QKeyEvent.key()
        actions.get(key, partial(print, key))()

    def get_parameters(self):
        args = {
            0: '--extract_all',
            1: '--frame_interval',
            2: '--time_interval',
        }
        arg = [args.get(self.mode_combo.currentIndex()), ]
        if arg[0] is not None:
            if arg[0] != '--extract_all':
                arg.append(str(self.step_field.value()))
            return arg


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    desktop = app.desktop()
    window = Window()
    window.resize(1000, 350)
    window.move(desktop.availableGeometry().center() - window.rect().center())
    window.show()
    sys.exit(app.exec_())
