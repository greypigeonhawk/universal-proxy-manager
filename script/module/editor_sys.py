import re,os,sqlite3
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor
from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QMessageBox,QFileDialog,QTableWidget,QTableWidgetItem,QComboBox

from script.utils.util_manager import utils

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from script.window.mainwindow import MainWindow

class MultiSyntaxHighlighter(QSyntaxHighlighter):

    def __init__(self, document, file_extension=""):
        super().__init__(document)
        self.file_extension = file_extension.lower()
        self.rules = []
        if self.file_extension == ".json":
            self.init_json_rules()
        elif self.file_extension in (".yaml", ".yml"):
            self.init_yaml_rules()
        elif self.file_extension in (".cmd", ".bat"):
            self.init_cmd_rules()

    def init_json_rules(self):
        key_fmt = QTextCharFormat()
        key_fmt.setForeground(QColor("blue"))
        self.rules.append((re.compile(r'".+?"(?=\s*:)'), key_fmt))
        string_fmt = QTextCharFormat()
        string_fmt.setForeground(QColor("darkgreen"))
        self.rules.append((re.compile(r'".*?"(?=\s*[,\}])'), string_fmt))
        number_fmt = QTextCharFormat()
        number_fmt.setForeground(QColor("darkmagenta"))
        self.rules.append((re.compile(r'\b-?\d+(\.\d+)?([eE][+-]?\d+)?\b'), number_fmt))
        bool_fmt = QTextCharFormat()
        bool_fmt.setForeground(QColor("darkred"))
        self.rules.append((re.compile(r'\b(true|false|null)\b'), bool_fmt))

    def init_yaml_rules(self):
        key_fmt = QTextCharFormat()
        key_fmt.setForeground(QColor("blue"))
        self.rules.append((re.compile(r'^\s*[\w\-]+(?=\s*:)'), key_fmt))
        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("darkgreen"))
        comment_fmt.setFontItalic(True)
        self.rules.append((re.compile(r'#.*$'), comment_fmt))
        bool_fmt = QTextCharFormat()
        bool_fmt.setForeground(QColor("darkred"))
        self.rules.append((re.compile(r'\b(true|false|null)\b'), bool_fmt))
        number_fmt = QTextCharFormat()
        number_fmt.setForeground(QColor("darkmagenta"))
        self.rules.append((re.compile(r'\b-?\d+(\.\d+)?\b'), number_fmt))

    def init_cmd_rules(self):
        keywords = [
            "echo", "set", "if", "else", "goto", "call", "exit", "for", "pause",
            "rem", "shift", "title", "cd", "cls", "copy", "del", "dir", "mkdir",
            "rmdir", "start", "assoc", "attrib", "break", "choice", "date", "time",
            "type", "ver", "xcopy", "taskkill", "tasklist"
        ]
        keyword_fmt = QTextCharFormat()
        keyword_fmt.setForeground(QColor("blue"))
        keyword_fmt.setFontWeight(QTextCharFormat.Bold)
        for kw in keywords:
            pattern = re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE)
            self.rules.append((pattern, keyword_fmt))
        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("darkgreen"))
        comment_fmt.setFontItalic(True)
        self.rules.append((re.compile(r'^\s*rem.*$', re.IGNORECASE), comment_fmt))
        self.rules.append((re.compile(r'^\s*::.*$', re.IGNORECASE), comment_fmt))
        string_fmt = QTextCharFormat()
        string_fmt.setForeground(QColor("darkred"))
        self.rules.append((re.compile(r'"[^"]*"'), string_fmt))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)

@utils.decorate_all_methods(utils.show_error_messagebox)
class editor_system(QObject):
    
    def __init__(self, parent, f=None):
        super().__init__()
        self.parent: MainWindow = parent
        self.file_path = ''
        self.load_default_table()

    def editor_ui_signals(self,f=None):
        self.parent.ui.editor_openfile.clicked.connect(self.open_file_editor)
        self.parent.ui.editor_minus.clicked.connect(lambda: self.editor_fontsize(0))
        self.parent.ui.editor_add.clicked.connect(lambda: self.editor_fontsize(1))
        self.parent.ui.editor_undo.clicked.connect(self.undo_editor)
        self.parent.ui.editor_redo.clicked.connect(self.redo_editor)
        self.parent.ui.editor_new.clicked.connect(self.new_file)
        self.parent.ui.editor_save.clicked.connect(self.save_file)

        self.parent.ui.table_open.clicked.connect(self.open_db)
        self.parent.ui.table_save.clicked.connect(self.save_changes)
        self.parent.ui.table_combo_list.currentTextChanged.connect(self.load_table_data)
        self.parent.ui.table_minus.clicked.connect(lambda: self.table_fontsize(0))
        self.parent.ui.table_plus.clicked.connect(lambda: self.table_fontsize(1))
        self.parent.ui.table_combo_file.currentTextChanged.connect(self.set_defualt_table)

# text file editor

    def open_file_editor(self, file_path=None,f=None):
        if file_path is None or file_path == False:
            file_path = utils.open_file(self.parent, self.tr('select file'), '', self.tr('All Files (*)'))
        if not file_path:
            return
        self.file_path = file_path
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
        except Exception as e:
            QMessageBox.critical(self.parent, self.tr("Error"), self.tr(f"Failed to open file:\n{e}"))
            return
        self.parent.ui.textEdit.setPlainText(content)
        self.parent.ui.label_editor_path.setText(os.path.basename(file_path))
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        if hasattr(self, 'highlighter') and self.highlighter:
            self.highlighter.setDocument(None)
            self.highlighter = None
        if ext in ['.json', '.yaml', '.yml', '.cmd', '.bat']:
            self.highlighter = MultiSyntaxHighlighter(self.parent.ui.textEdit.document(), file_extension=ext)
        else:
            self.highlighter = None

    def _adjust_fontsize(self, widget, index):
        font = widget.font()
        size = font.pointSize()
        if size <= 0:
            size = int(font.pointSizeF()) or int(font.pixelSize()) or 12
        size = max(6, size - 1) if index == 0 else min(72, size + 1)
        font.setPointSize(size)
        widget.setFont(font)

    def editor_fontsize(self, index, f=None):
        self._adjust_fontsize(self.parent.ui.textEdit, index)

    def undo_editor(self, f=None):
        self.parent.ui.textEdit.undo()

    def redo_editor(self, f=None):
        self.parent.ui.textEdit.redo()

    def new_file(self, f=None):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_path, _ = QFileDialog.getSaveFileName(
            self.parent,
            self.tr("Create New File"),
            "",
            self.tr("All Files (*)"),
            options=options
        )
        if not file_path:
            return
        else:self.file_path = file_path
        if not os.path.exists(file_path):
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    pass
            except Exception as e:
                QMessageBox.critical(self.parent, self.tr("Error"), self.tr(f"Cannot create file:\n{e}"))
                return
        self.open_file_editor(file_path)

    def save_file(self, f=None):
        if not self.file_path:
            QMessageBox.warning(self.parent, self.tr("Error"), self.tr("Please open or create a file first."))
            return
        try:
            text = self.parent.ui.textEdit.toPlainText()
            with open(self.file_path, 'w', encoding='utf-8') as file:
                file.write(text)
        except Exception as e:
            QMessageBox.critical(self.parent, self.tr("Error"), self.tr(f"Failed to save file:\n{e}"))
            return

# db file editor in table

    def open_db(self,path,f=None):
        if not path: 
            path = utils.open_file(self.parent,'','',self.tr('database file (*.db *.sqlite)'))
        if not path:
            return
        self.conn = sqlite3.connect(path)
        self.cursor = self.conn.cursor()
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        self.table_names = [row[0] for row in self.cursor.fetchall()]
        self.parent.ui.table_combo_list.clear()
        self.parent.ui.table_combo_list.addItems(self.table_names)
        if self.table_names:
            self.table_name = self.table_names[0]
            self.load_table_data(self.table_name)

    def load_table_data(self, table_name,f=None):
        if not hasattr(self, 'cursor') or not self.cursor:
            return
        if not table_name:
            return
        self.table_name = table_name
        self.cursor.execute(f"SELECT * FROM {self.table_name}")
        rows = self.cursor.fetchall()
        col_names = [desc[0] for desc in self.cursor.description]
        self.parent.ui.tableWidget.setColumnCount(len(col_names))
        self.parent.ui.tableWidget.setHorizontalHeaderLabels(col_names)
        self.parent.ui.tableWidget.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                self.parent.ui.tableWidget.setItem(r, c, item)

    def save_changes(self,f=None):
        if not hasattr(self, 'conn') or not self.conn or not self.table_name:
            return
        if not self.conn or not self.table_name:
            return
        col_names = [self.parent.ui.tableWidget.horizontalHeaderItem(i).text() for i in range(self.parent.ui.tableWidget.columnCount())]
        for r in range(self.parent.ui.tableWidget.rowCount()):
            values = [self.parent.ui.tableWidget.item(r, c).text() for c in range(self.parent.ui.tableWidget.columnCount())]
            pk_value = values[0]
            set_clause = ", ".join(f"{col} = ?" for col in col_names[1:])
            sql = f"UPDATE {self.table_name} SET {set_clause} WHERE {col_names[0]} = ?"
            self.cursor.execute(sql, values[1:] + [pk_value])
        self.conn.commit()

    def table_fontsize(self, index, f=None):
        self._adjust_fontsize(self.parent.ui.tableWidget, index)

    def load_default_table(self,f=None):
        db_list = ['data/app_launcher.db','data/fav_conn.db','data/tools.db',]
        for i in db_list:
            self.parent.ui.table_combo_file.addItem(i)

    def set_defualt_table(self,f=None):
        self.open_db(self.parent.ui.table_combo_file.currentText())
