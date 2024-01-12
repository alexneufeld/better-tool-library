from PySide import QtCore
from PySide.QtCore import Qt
from .util import qpixmap_from_svg, qpixmap_from_png
from ..i18n import translate


class TableModel(QtCore.QAbstractTableModel):
    def __init__(self, data):
        super(TableModel, self).__init__()
        self._data = data

    def data(self, index, role):
        if role == Qt.DisplayRole:
            match index.column():
                case 0:
                    return index.row()
                case 1:
                    return
                case 2:
                    return self._data[index.row()].label
        if role == Qt.DecorationRole:
            match index.column():
                case 1:
                    icon_type, icon_bytes = self._data[index.row()].shape.get_icon()
                    if not icon_type:
                        return
                    icon_ba = QtCore.QByteArray(icon_bytes)
                    icon_size = QtCore.QSize(50, 60)
                    if icon_type == 'svg':
                        icon = qpixmap_from_svg(icon_ba, icon_size)
                    elif icon_type == 'png':
                        icon = qpixmap_from_png(icon_ba, icon_size)
                    return icon
                case _:
                    return

    def rowCount(self, index=None):
        return len(self._data)

    def columnCount(self, index=None):
        return 3

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role!=QtCore.Qt.DisplayRole:
            return
        if orientation==QtCore.Qt.Horizontal:
            match section:
                case 0:
                    return translate('btl', 'Number')
                case 1:
                    return ''  # no row name for the icon
                case 2:
                    return translate('btl', 'Description')

