import sqlite3
import os
import platform
from PyQt5 import QtWidgets, QtGui, QtCore

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, QLineEdit, QVBoxLayout,
    QWidget, QTableWidget, QTableWidgetItem, QHBoxLayout, QMessageBox
)
import sys
import subprocess
import serial
import serial.tools.list_ports


from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QMessageBox
)

class LoginWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("تسجيل الدخول")
        self.setFixedSize(300, 150)

        layout = QFormLayout()

        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)

        layout.addRow("اسم المستخدم:", self.username_input)
        layout.addRow("كلمة المرور:", self.password_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.check_login)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)
        self.setLayout(layout)

    def check_login(self):
        username = self.username_input.text()
        password = self.password_input.text()

        if username == "admin" and password == "1234":
            self.accept()
        else:
            QMessageBox.warning(self, "خطأ", "اسم المستخدم أو كلمة المرور غير صحيحة")



# --- دالة لتحديد مسار قاعدة البيانات في مجلد آمن ---
def get_database_path():
    if platform.system() == "Windows":
        base_path = os.environ.get('APPDATA', 'C:/ProgramData')
    else:
        base_path = os.path.expanduser('~/.local/share')

    app_folder = os.path.join(base_path, "CashierApp")
    os.makedirs(app_folder, exist_ok=True)

    return os.path.join(app_folder, "products.db")

# --- نافذة تعديل قاعدة البيانات (إضافة، حذف، تعديل) ---
class DatabaseEditor(QtWidgets.QDialog):
    def __init__(self, cursor, connection):
        super().__init__()
        self.setWindowTitle("Stock")
        self.setMinimumWidth(450)
        self.cursor = cursor
        self.connection = connection

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.table = QTableWidget()
        self.layout.addWidget(self.table)

        self.load_data()

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("➕ إضافة")
        self.del_btn = QPushButton("🗑️ حذف")
        self.save_btn = QPushButton("💾 حفظ")
        self.cancel_btn = QPushButton("❌ إلغاء")

        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.del_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)

        self.layout.addLayout(btn_layout)

        self.add_btn.clicked.connect(self.add_row)
        self.del_btn.clicked.connect(self.delete_row)
        self.save_btn.clicked.connect(self.save_changes)
        self.cancel_btn.clicked.connect(self.reject)

    def load_data(self):
        self.cursor.execute("SELECT barcode, name, price FROM products")
        rows = self.cursor.fetchall()
        self.table.setRowCount(len(rows))
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["باركود", "الاسم", "السعر"])
        for row_idx, row_data in enumerate(rows):
            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.table.setItem(row_idx, col_idx, item)

    def add_row(self):
        row_position = self.table.rowCount()
        self.table.insertRow(row_position)
        for col in range(3):
            item = QTableWidgetItem("")
            item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.table.setItem(row_position, col, item)

    def delete_row(self):
        selected = self.table.selectionModel().selectedRows()
        for index in sorted(selected, reverse=True):
            self.table.removeRow(index.row())

    def save_changes(self):
        try:
            self.cursor.execute("DELETE FROM products")
            for row in range(self.table.rowCount()):
                barcode = self.table.item(row, 0)
                name = self.table.item(row, 1)
                price = self.table.item(row, 2)

                if not barcode or not name or not price:
                    continue

                barcode_text = barcode.text().strip()
                name_text = name.text().strip()
                price_text = price.text().strip()

                if not barcode_text or not name_text or not price_text:
                    continue

                price_val = float(price_text)

                self.cursor.execute(
                    "INSERT INTO products (barcode, name, price) VALUES (?, ?, ?)",
                    (barcode_text, name_text, price_val)
                )
            self.connection.commit()
            QMessageBox.information(self, "تم", "تم حفظ التغييرات.")
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"حدث خطأ أثناء الحفظ:\n{str(e)}")

# --- برنامج قارئ الباركود عبر منفذ تسلسلي ---
class BarcodeReader(QtCore.QObject):
    barcode_scanned = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.serial_port = None
        self.running = False

    def find_serial_ports(self):
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def open_port(self, port=None, baudrate=9600):
        if port is None:
            ports = self.find_serial_ports()
            if ports:
                port = ports[0]  # نأخذ أول منفذ متاح
            else:
                return False

        try:
            self.serial_port = serial.Serial(port, baudrate, timeout=1)
            self.running = True
            QtCore.QTimer.singleShot(100, self.read_data)
            return True
        except Exception as e:
            return False

    def read_data(self):
        if not self.running or not self.serial_port:
            return
        try:
            if self.serial_port.in_waiting > 0:
                data = self.serial_port.readline().decode('utf-8').strip()
                if data:
                    self.barcode_scanned.emit(data)
        except Exception as e:
            pass
        QtCore.QTimer.singleShot(100, self.read_data)

    def close_port(self):
        self.running = False
        if self.serial_port:
            try:
                self.serial_port.close()
            except:
                pass
            self.serial_port = None

# --- البرنامج الرئيسي للكاشير ---
class CashierApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("iPay")
        self.setGeometry(100, 100, 1000, 600)
        self.setStyleSheet("""
            QWidget {
                background-color: #f2f2f2;
                font-family: 'Segoe UI';
                font-size: 14px;
            }
            QLineEdit {
                padding: 10px;
                border: 1px solid #aaa;
                border-radius: 6px;
                text-align: right;
            }
            QPushButton {
                padding: 10px;
                background-color: #007acc;
                color: white;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #005f99;
            }
            QLabel#TotalLabel {
                color: #333;
                font-size: 36px;
                font-weight: bold;
            }
            QTableWidget {
                background-color: white;
                border-radius: 6px;
            }
            QHeaderView::section {
                background-color: #007acc;
                color: white;
                font-weight: bold;
                padding: 6px;
                border: none;
            }
        """)

        self.db_path = get_database_path()
        self.conn = sqlite3.connect(self.db_path)
        self.c = self.conn.cursor()
        self.c.execute('''CREATE TABLE IF NOT EXISTS products
                          (barcode TEXT PRIMARY KEY, name TEXT, price REAL)''')
        self.conn.commit()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.barcode_input = QLineEdit()
        self.barcode_input.setPlaceholderText("📷 امسح الباركود هنا...")
        self.barcode_input.returnPressed.connect(self.handle_barcode_scan)
        self.layout.addWidget(self.barcode_input)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["📦 الاسم", "🔢 الكمية", "💵 السعر", "💰 الإجمالي"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setLayoutDirection(QtCore.Qt.RightToLeft)  # اتجاه الجدول من اليمين لليسار
        self.layout.addWidget(self.table)

        total_layout = QHBoxLayout()
        self.total_label = QLabel("الإجمالي: 0.00")
        self.total_label.setObjectName("TotalLabel")
        total_layout.addWidget(self.total_label)
        total_layout.addStretch()
        self.layout.addLayout(total_layout)

        btn_layout = QHBoxLayout()

        self.add_btn = QPushButton("➕ إضافة منتج يدويًا")
        self.add_btn.clicked.connect(self.add_product_manually)
        btn_layout.addWidget(self.add_btn)

        self.delete_btn = QPushButton("❌ حذف منتج من الفاتورة")
        self.delete_btn.clicked.connect(self.delete_selected_product)
        btn_layout.addWidget(self.delete_btn)

        self.clear_btn = QPushButton("🧹 مسح الفاتورة")
        self.clear_btn.clicked.connect(self.clear_table)
        btn_layout.addWidget(self.clear_btn)

        self.edit_db_btn = QPushButton("🛠️ الموارد")
        self.edit_db_btn.clicked.connect(self.edit_database)
        btn_layout.addWidget(self.edit_db_btn)

        self.calc_btn = QPushButton("🧮 الآلة الحاسبة")
        self.calc_btn.clicked.connect(self.open_calculator)
        btn_layout.addWidget(self.calc_btn)

        self.about_btn = QPushButton("ℹ️ حول البرنامج")
        self.about_btn.clicked.connect(self.show_about)
        btn_layout.addWidget(self.about_btn)

        self.layout.addLayout(btn_layout)

        # قارئ الباركود
        self.barcode_reader = BarcodeReader()
        ports = self.barcode_reader.find_serial_ports()
        if ports:
            if not self.barcode_reader.open_port(ports[0]):
                # فشل في الفتح، اسأل المستخدم يدوياً
                port, ok = QtWidgets.QInputDialog.getText(self, "اختيار منفذ الباركود",
                                                          "لم يتم التعرف على قارئ الباركود تلقائيًا.\n"
                                                          "يرجى إدخال منفذ الباركود (مثال: COM3 أو /dev/ttyUSB0):")
                if ok and port.strip():
                    self.barcode_reader.open_port(port.strip())
        else:
            port, ok = QtWidgets.QInputDialog.getText(self, "اختيار منفذ الباركود",
                                                      "لم يتم العثور على أي منافذ تسلسلية.\n"
                                                      "يرجى إدخال منفذ الباركود يدوياً:")
            if ok and port.strip():
                self.barcode_reader.open_port(port.strip())

        self.barcode_reader.barcode_scanned.connect(self.on_barcode_scanned)

    def on_barcode_scanned(self, barcode):
        self.barcode_input.setText(barcode)
        self.handle_barcode_scan()

    def handle_barcode_scan(self):
        barcode = self.barcode_input.text().strip()
        if not barcode:
            return

        self.c.execute("SELECT name, price FROM products WHERE barcode = ?", (barcode,))
        result = self.c.fetchone()
        if result:
            name, price = result
            self.add_or_update_product_in_table(name, price)
            self.update_total()
            self.barcode_input.clear()
        else:
            # المنتج غير موجود - عرض نافذة إضافة منتج جديد
            add_new = QMessageBox.question(self, "منتج جديد",
                                           f"المنتج برمز {barcode} غير موجود.\nهل تريد إضافته كمنتج جديد؟",
                                           QMessageBox.Yes | QMessageBox.No)
            if add_new == QMessageBox.Yes:
                self.add_new_product(barcode)
            else:
                self.barcode_input.clear()

    def add_new_product(self, barcode):
        dialog = QDialog(self)
        dialog.setWindowTitle("إضافة منتج جديد")

        layout = QFormLayout(dialog)

        name_input = QLineEdit()
        price_input = QLineEdit()

        layout.addRow("اسم المنتج:", name_input)
        layout.addRow("السعر:", price_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)

        def on_accept():
            name = name_input.text().strip()
            price_text = price_input.text().strip()
            if not name or not price_text:
                QMessageBox.warning(dialog, "خطأ", "يرجى إدخال الاسم والسعر.")
                return
            try:
                price = float(price_text)
            except ValueError:
                QMessageBox.warning(dialog, "خطأ", "السعر غير صحيح.")
                return
            # إضافة المنتج إلى قاعدة البيانات
            try:
                self.c.execute("INSERT INTO products (barcode, name, price) VALUES (?, ?, ?)",
                               (barcode, name, price))
                self.conn.commit()
            except Exception as e:
                QMessageBox.warning(dialog, "خطأ", f"حدث خطأ أثناء الإضافة:\n{str(e)}")
                return

            self.add_or_update_product_in_table(name, price)
            self.update_total()
            dialog.accept()
            self.barcode_input.clear()

        buttons.accepted.connect(on_accept)
        buttons.rejected.connect(dialog.reject)

        dialog.exec_()

    def add_or_update_product_in_table(self, name, price):
        for row in range(self.table.rowCount()):
            item_name = self.table.item(row, 0)
            if item_name and item_name.text() == name:
                qty_item = self.table.item(row, 1)
                qty = int(qty_item.text())
                qty += 1
                qty_item.setText(str(qty))
                total_item = self.table.item(row, 3)
                total_item.setText(f"{qty * price:.2f}")
                return

        row_position = self.table.rowCount()
        self.table.insertRow(row_position)

        name_item = QTableWidgetItem(name)
        name_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        qty_item = QTableWidgetItem("1")
        qty_item.setTextAlignment(QtCore.Qt.AlignCenter)
        price_item = QTableWidgetItem(f"{price:.2f}")
        price_item.setTextAlignment(QtCore.Qt.AlignCenter)
        total_item = QTableWidgetItem(f"{price:.2f}")
        total_item.setTextAlignment(QtCore.Qt.AlignCenter)

        self.table.setItem(row_position, 0, name_item)
        self.table.setItem(row_position, 1, qty_item)
        self.table.setItem(row_position, 2, price_item)
        self.table.setItem(row_position, 3, total_item)

    def update_total(self):
        total = 0.0
        for row in range(self.table.rowCount()):
            total_item = self.table.item(row, 3)
            if total_item:
                try:
                    total += float(total_item.text())
                except ValueError:
                    pass
        self.total_label.setText(f"الإجمالي: {total:.2f}")

    def clear_table(self):
        self.table.setRowCount(0)
        self.update_total()

    def edit_database(self):
        editor = DatabaseEditor(self.c, self.conn)
        editor.exec_()

    def open_calculator(self):
        try:
            if platform.system() == "Windows":
                subprocess.Popen("calc.exe")
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", "-a", "Calculator"])
            else:
                subprocess.Popen(["gnome-calculator"])
        except Exception:
            pass

    def show_about(self):
        QMessageBox.information(self, "حول البرنامج", "Made with LOVE @izemh")

    def add_product_manually(self):
        barcode, ok = QtWidgets.QInputDialog.getText(self, "إضافة منتج عبر الباركود", "امسح باركود المنتج أو أدخله يدوياً:")

        if not ok or not barcode.strip():
            return

        barcode = barcode.strip()

        self.c.execute("SELECT name, price FROM products WHERE barcode = ?", (barcode,))
        result = self.c.fetchone()
        if result:
            name, price = result
            self.add_or_update_product_in_table(name, price)
            self.update_total()
        else:
            # المنتج غير موجود - عرض نافذة إضافة منتج جديد
            add_new = QMessageBox.question(self, "منتج جديد",
                                           f"المنتج برمز {barcode} غير موجود.\nهل تريد إضافته كمنتج جديد؟",
                                           QMessageBox.Yes | QMessageBox.No)
            if add_new == QMessageBox.Yes:
                self.add_new_product(barcode)

    def delete_selected_product(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "تنبيه", "يرجى اختيار المنتج الذي تريد حذفه من الفاتورة.")
            return

        for selected in sorted(selected_rows, key=lambda x: x.row(), reverse=True):
            self.table.removeRow(selected.row())
        self.update_total()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    login = LoginWindow()
    if login.exec_() == QDialog.Accepted:
        window = CashierApp()
        window.show()
        sys.exit(app.exec_())

