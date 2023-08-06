import os
import FreeCAD
import FreeCADGui
from pathlib import Path
from PySide import QtGui, QtCore
from .util import load_ui
from .machineeditor import MachineEditor
from ..machine import Machine
from ..feeds import FeedCalc
from ..feeds.operation import operations
from ..feeds.material import materials

__dir__ = os.path.dirname(__file__)
ui_path = os.path.join(__dir__, "feedsandspeeds.ui")
pool = QtCore.QThreadPool()

class FeedCalculatorWorker(QtCore.QObject):
    finished = QtCore.Signal()
    progress = QtCore.Signal(int)

    def __init__(self, fc):
        super(FeedCalculatorWorker, self).__init__()
        self.fc = fc
        self.result = None

    def start(self):
        progress_cb = lambda x: self.progress.emit(x*100)
        self.result = self.fc.start(progress_cb=progress_cb)
        self.finished.emit()

class FeedCalculatorRunnable(QtCore.QRunnable):
    def __init__(self, fc):
        super(FeedCalculatorRunnable, self).__init__()
        self.setAutoDelete(True)
        self.worker = FeedCalculatorWorker(fc)

    def run(self):
        self.worker.start()

warning_dismissed = False

class FeedsAndSpeedsWidget(QtGui.QWidget):
    def __init__(self, db, serializer, tool, parent=None):
        super(FeedsAndSpeedsWidget, self).__init__(parent)
        self.db = db
        self.serializer = serializer
        self.tool = tool

        self.layout = QtGui.QVBoxLayout(self)
        self.setLayout(self.layout)
        self.form = load_ui(ui_path)
        self.layout.addWidget(self.form)

        header = self.form.tableWidget.horizontalHeader()
        header.setResizeMode(QtGui.QHeaderView.ResizeToContents)
        policy = self.form.resultWidget.sizePolicy()
        policy.setRetainSizeWhenHidden(True)
        self.form.resultWidget.setSizePolicy(policy)

        self.form.toolButtonAddMachine.clicked.connect(self._on_new_machine_clicked)
        self.form.toolButtonEditMachine.clicked.connect(self._on_edit_machine_clicked)
        self.form.comboBoxMachine.currentIndexChanged.connect(self._on_machine_selected)
        self.form.comboBoxMaterial.activated.connect(self._on_material_selected)
        self.form.comboBoxOperation.activated.connect(self._on_operation_selected)
        self.form.doubleSpinBoxStickout.valueChanged.connect(self._on_stickout_changed)
        self.form.toolButtonWarning.clicked.connect(self._on_warning_dismissed)
        self.form.toolButtonError.clicked.connect(self.form.errorBox.hide)

    def _on_warning_dismissed(self):
        self.form.warningBox.hide()
        global warning_dismissed
        warning_dismissed = True

    def _on_machine_selected(self, index):
        self.update_state()

    def _on_material_selected(self, index):
        self.update_state()

    def _on_operation_selected(self, index):
        self.update_state()

    def _on_stickout_changed(self, value):
        self.tool.set_stickout(value)
        self.update_state()

    def update(self):
        # Update the library dropdown menu.
        combo = self.form.comboBoxMachine
        index = combo.currentIndex()
        combo.clear()
        machines = sorted(self.db.get_machines(), key=lambda l: l.label)
        for machine in machines:
            combo.addItem(machine.label, machine.id)
        combo.setCurrentIndex(index)
        if combo.currentIndex() == -1:
            combo.setCurrentIndex(0)

        combo = self.form.comboBoxMaterial
        index = combo.currentIndex()
        combo.clear()
        material_list = sorted(materials, key=lambda m: m.name)
        for material in material_list:
            combo.addItem(material.name, material)
        combo.setCurrentIndex(index)
        if combo.currentIndex() == -1:
            combo.setCurrentIndex(0)

        combo = self.form.comboBoxOperation
        index = combo.currentIndex()
        combo.clear()
        operation_list = sorted(operations, key=lambda o: o.label)
        for operation in operation_list:
            combo.addItem(operation.label, operation)
        combo.setCurrentIndex(index)
        if combo.currentIndex() == -1:
            combo.setCurrentIndex(0)

        self.form.warningBox.setVisible(not warning_dismissed)
        # Updating the stickout also triggers .update_state()
        stickout = self.tool.get_stickout()
        self.form.doubleSpinBoxStickout.setValue(stickout or 10)

    def show_hint(self, hint):
        self.form.hintLabel.setText(f"<i>{hint}</i>")
        self.form.hintLabel.show()

    def update_state(self):
        self.form.errorBox.hide()
        self.form.shapePixmap.hide()
        self.form.resultWidget.hide()
        machine = self.get_selected_machine()
        self.form.toolButtonEditMachine.setEnabled(machine is not None)

        material = self.get_selected_material()
        stickout = self.form.doubleSpinBoxStickout.value()

        if not machine:
            return self.show_hint("Please select a machine.")
        elif not material:
            return self.show_hint("Please select a material.")
        elif not stickout:
            return self.show_hint("Please enter the stickout of the tool.")
        elif not self.tool.shape.get_flutes():
            return self.show_hint("Tool needs to have more than zero flutes.")
        self.form.hintLabel.hide()

        # Prepare the calculator.
        op = self.form.comboBoxOperation.currentData()
        try:
            fc = FeedCalc(machine, self.tool, material, op=op)
        except AttributeError as e:
            self.show_hint("Calculator error: {e}")
            return
        if not self.tool.supports_pixmap():
            self.show_hint("This tool shape is not supported by the calculator.")
            return

        # Calculate.
        pool.clear()
        runnable = FeedCalculatorRunnable(fc)
        runnable.worker.finished.connect(pool.releaseThread)
        runnable.worker.progress.connect(self._on_calculator_progress)
        runnable.worker.finished.connect(lambda: self._on_calculator_finished(runnable.worker))
        pool.start(runnable)

    def _on_calculator_progress(self, progress):
        self.form.progressBar.setValue(progress)
        self.form.progressBar.show()

    def _on_calculator_finished(self, worker):
        # Unfortunately QThreadPool.activeThreadCount() is currently broken,
        # see https://bugreports.qt.io/browse/QTBUG-21051
        # Leaving this disabled; the user may see multiple updates that way,
        # but not a big deal.
        #if pool.activeThreadCount() > 0:
        #    return
        self.form.progressBar.hide()
        error_distance, error, params = worker.result
        if error:
            self.form.labelError.setText(
                f"No valid result found. Best result has error: {error}"
            )
            self.form.errorBox.show()
        else:
            self.form.errorBox.hide()

        # Show the result.
        self.form.warningBox.setVisible(not warning_dismissed)
        self.form.resultWidget.show()
        rpm = params.get('rpm')
        self.form.rpmResultLabel.setText(rpm.format() if rpm else "<i>none</i>")
        feed = params.get('feed')
        self.form.feedResultLabel.setText(feed.format() if feed else "<i>none</i>")
        woc = params.get('woc')
        self.form.stepoverResultLabel.setText(woc.format() if woc else "<i>none</i>")
        doc = params.get('doc')
        self.form.stepdownResultLabel.setText(doc.format() if doc else "<i>none</i>")

        table = self.form.tableWidget
        table.clear()
        table.setRowCount(len(params))
        params = sorted(params.items(), key=lambda x: x[0].lower())
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        for row, (name, param) in enumerate(params):
            # First column: Name.
            item = QtGui.QTableWidgetItem(name)
            item.setFont(font)
            table.setItem(row, 0, item)

            # Second column: Values and limits, marked if near the limit.
            item = QtGui.QTableWidgetItem(param.to_string())
            percent = param.get_percent_of_limit()*100
            if not param.within_minmax():
                 item.setForeground(QtGui.QColor(255, 255, 255))
                 item.setBackground(QtGui.QColor(255, 0, 0, 255))
            elif percent >= 95:
                 item.setBackground(QtGui.QColor(255, 165, 0))
            table.setItem(row, 1, item)

        # Display the shape.
        self.form.shapePixmap.show()
        tool_pixmap = self.tool.get_pixmap()
        img_data = tool_pixmap.render_engagement(doc.v, woc.v)
        image = QtGui.QImage(img_data,
                             tool_pixmap.size,
                             tool_pixmap.size,
                             QtGui.QImage.Format_ARGB32)
        pixmap = QtGui.QPixmap.fromImage(image)
        self.form.shapePixmap.setPixmap(pixmap)

    def get_selected_machine(self):
        machine_id = self.form.comboBoxMachine.currentData()
        if not machine_id:
            return
        return self.db.get_machine_by_id(machine_id)

    def get_selected_material(self):
        return self.form.comboBoxMaterial.currentData()

    def _show_machine_editor(self, machine):
        editor = MachineEditor(self.db, self.serializer, machine, self)
        if not editor.exec():
            self.update()
            return
        self.db.add_machine(machine)
        self.db.serialize_machines(self.serializer)
        self.update()

    def _on_new_machine_clicked(self):
        self._show_machine_editor(Machine())

    def _on_edit_machine_clicked(self):
        machine = self.get_selected_machine()
        self._show_machine_editor(machine)