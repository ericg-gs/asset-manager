#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
企业资产管理工具 - Asset Manager
入库/出库/转移/维修/报废/统计/报表
"""

import sys
import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
import json

# ─── 数据库模块 ────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets.db")


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            model TEXT,
            serial_number TEXT UNIQUE,
            purchase_date TEXT,
            purchase_price REAL DEFAULT 0,
            status TEXT DEFAULT '库存',
            department TEXT DEFAULT '',
            assignee TEXT DEFAULT '',
            checkout_date TEXT,
            remarks TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS asset_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER,
            action TEXT NOT NULL,
            detail TEXT DEFAULT '',
            operator TEXT DEFAULT 'system',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.commit()
    conn.close()


def log_action(asset_id: int, action: str, detail: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO asset_log (asset_id, action, detail) VALUES (?, ?, ?)",
        (asset_id, action, detail)
    )
    conn.commit()
    conn.close()


# ─── 资产操作 ────────────────────────────────────────────

def add_asset(name: str, category: str, model: str, serial: str,
              purchase_date: str, price: float, remarks: str = '') -> int:
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO assets (name, category, model, serial_number,
                            purchase_date, purchase_price, remarks, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, '库存')
    """, (name, category, model, serial, purchase_date, price, remarks))
    asset_id = c.lastrowid
    log_action(asset_id, '入库', f'新资产入库: {name}')
    conn.commit()
    conn.close()
    return asset_id


def checkout_asset(asset_id: int, department: str, assignee: str) -> bool:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT status FROM assets WHERE id = ?", (asset_id,))
    row = c.fetchone()
    if not row or row[0] not in ('库存', '已回收'):
        return False
    c.execute("""
        UPDATE assets SET status='已出库', department=?, assignee=?,
                          checkout_date=datetime('now','localtime'),
                          updated_at=datetime('now','localtime')
        WHERE id=?
    """, (department, assignee, asset_id))
    log_action(asset_id, '出库', f'分配给 {department} - {assignee}')
    conn.commit()
    conn.close()
    return True


def transfer_asset(asset_id: int, new_department: str, new_assignee: str) -> bool:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT status FROM assets WHERE id = ?", (asset_id,))
    row = c.fetchone()
    if not row or row[0] != '已出库':
        return False
    c.execute("""
        UPDATE assets SET department=?, assignee=?,
                          updated_at=datetime('now','localtime')
        WHERE id=?
    """, (new_department, new_assignee, asset_id))
    log_action(asset_id, '转移', f'转移至 {new_department} - {new_assignee}')
    conn.commit()
    conn.close()
    return True


def repair_asset(asset_id: int, remarks: str = '') -> bool:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT status FROM assets WHERE id = ?", (asset_id,))
    row = c.fetchone()
    if not row:
        return False
    status = '维修中' if row[0] == '已出库' else row[0]
    c.execute("""
        UPDATE assets SET status=?, remarks=remarks || ?,
                          updated_at=datetime('now','localtime')
        WHERE id=?
    """, (status, f'\n[维修 {datetime.now().strftime("%Y-%m-%d")}] {remarks}', asset_id))
    log_action(asset_id, '维修', remarks)
    conn.commit()
    conn.close()
    return True


def retire_asset(asset_id: int, reason: str) -> bool:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT status FROM assets WHERE id = ?", (asset_id,))
    row = c.fetchone()
    if not row or row[0] == '已报废':
        return False
    c.execute("""
        UPDATE assets SET status='已报废', remarks=remarks || ?,
                          updated_at=datetime('now','localtime')
        WHERE id=?
    """, (f'\n[报废 {datetime.now().strftime("%Y-%m-%d")}] 原因: {reason}', asset_id))
    log_action(asset_id, '报废', reason)
    conn.commit()
    conn.close()
    return True


def get_assets(status: Optional[str] = None,
               category: Optional[str] = None,
               keyword: str = '') -> List[Dict]:
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    query = "SELECT * FROM assets WHERE 1=1"
    params = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if category:
        query += " AND category = ?"
        params.append(category)
    if keyword:
        query += " AND (name LIKE ? OR serial_number LIKE ? OR model LIKE ?)"
        kw = f'%{keyword}%'
        params.extend([kw, kw, kw])
    query += " ORDER BY id DESC"
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_asset(asset_id: int) -> Optional[Dict]:
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_asset_logs(asset_id: int) -> List[Dict]:
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM asset_log WHERE asset_id = ? ORDER BY id DESC",
              (asset_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_categories() -> List[str]:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT DISTINCT category FROM assets ORDER BY category")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows if r[0]]


def get_stats() -> Dict[str, Any]:
    conn = get_conn()
    c = conn.cursor()
    stats = {}

    # 按状态统计
    c.execute("""
        SELECT status, COUNT(*), COALESCE(SUM(purchase_price), 0)
        FROM assets GROUP BY status
    """)
    stats['by_status'] = [{'status': r[0], 'count': r[1], 'total_price': r[2]}
                          for r in c.fetchall()]

    # 按类别统计
    c.execute("""
        SELECT category, COUNT(*), COALESCE(SUM(purchase_price), 0)
        FROM assets GROUP BY category ORDER BY count DESC
    """)
    stats['by_category'] = [{'category': r[0], 'count': r[1], 'total_price': r[2]}
                             for r in c.fetchall()]

    # 总计
    c.execute("""
        SELECT COUNT(*), COALESCE(SUM(purchase_price), 0)
        FROM assets
    """)
    row = c.fetchone()
    stats['total_count'] = row[0]
    stats['total_price'] = row[1]

    conn.close()
    return stats


def export_to_json() -> str:
    assets = get_assets()
    stats = get_stats()
    data = {'assets': assets, 'stats': stats,
            'export_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        f'资产导出_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def export_to_csv() -> str:
    assets = get_assets()
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        f'资产导出_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
    if not assets:
        return ''
    headers = ['ID', '名称', '类别', '型号', '序列号', '采购日期',
               '采购价格', '状态', '部门', '领用人', '出库日期', '备注']
    with open(path, 'w', encoding='utf-8-sig') as f:
        f.write(','.join(headers) + '\n')
        for a in assets:
            row = [str(a.get(h, '')) for h in
                   ['id', 'name', 'category', 'model', 'serial_number',
                    'purchase_date', 'purchase_price', 'status',
                    'department', 'assignee', 'checkout_date', 'remarks']]
            f.write(','.join(row) + '\n')
    return path


# ─── GUI 模块 ────────────────────────────────────────────

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTableWidget, QTableWidgetItem, QPushButton, QLineEdit, QLabel,
        QComboBox, QDialog, QFormLayout, QDialogButtonBox, QMessageBox,
        QTextEdit, QTabWidget, QGroupBox, QGridLayout, QHeaderView,
        QAbstractItemView, QSplitter, QStatusBar, QMenuBar, QMenu
    )
    from PySide6.QtCore import Qt, QSize
    from PySide6.QtGui import QIcon, QAction, QFont
    USE_PYSIDE = True
except ImportError:
    USE_PYSIDE = False
    print("PySide6 not installed. Running in CLI mode.")
    print("Install with: pip install PySide6")


class AssetFormDialog(QDialog):
    """资产录入表单"""

    def __init__(self, parent=None, asset=None):
        super().__init__(parent)
        self.asset = asset
        self.setWindowTitle('编辑资产' if asset else '资产入库')
        self.setMinimumWidth(450)
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.addItems(
            ['台式机', '笔记本', '显示器', '打印机', '网络设备',
             '移动硬盘', '键盘鼠标', '其他'])
        self.model_edit = QLineEdit()
        self.serial_edit = QLineEdit()
        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText('YYYY-MM-DD')
        self.price_edit = QLineEdit()
        self.remarks_edit = QTextEdit()

        layout.addRow('资产名称 *:', self.name_edit)
        layout.addRow('类别 *:', self.category_combo)
        layout.addRow('型号:', self.model_edit)
        layout.addRow('序列号:', self.serial_edit)
        layout.addRow('采购日期:', self.date_edit)
        layout.addRow('采购价格:', self.price_edit)
        layout.addRow('备注:', self.remarks_edit)

        if self.asset:
            self.name_edit.setText(self.asset.get('name', ''))
            self.category_combo.setCurrentText(self.asset.get('category', ''))
            self.model_edit.setText(self.asset.get('model', ''))
            self.serial_edit.setText(self.asset.get('serial_number', ''))
            self.date_edit.setText(self.asset.get('purchase_date', ''))
            self.price_edit.setText(str(self.asset.get('purchase_price', 0)))
            self.remarks_edit.setText(self.asset.get('remarks', ''))

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_data(self):
        return {
            'name': self.name_edit.text().strip(),
            'category': self.category_combo.currentText().strip(),
            'model': self.model_edit.text().strip(),
            'serial': self.serial_edit.text().strip(),
            'purchase_date': self.date_edit.text().strip(),
            'price': float(self.price_edit.text() or 0),
            'remarks': self.remarks_edit.toPlainText().strip(),
        }


class CheckoutDialog(QDialog):
    """出库/分配对话框"""

    def __init__(self, parent=None, asset=None):
        super().__init__(parent)
        self.asset = asset
        self.setWindowTitle('资产出库')
        self.setMinimumWidth(350)
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)
        self.dept_edit = QLineEdit()
        self.assignee_edit = QLineEdit()
        layout.addRow('使用部门 *:', self.dept_edit)
        layout.addRow('领用人 *:', self.assignee_edit)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_data(self):
        return {
            'department': self.dept_edit.text().strip(),
            'assignee': self.assignee_edit.text().strip(),
        }


class TransferDialog(QDialog):
    """资产转移对话框"""

    def __init__(self, parent=None, asset=None):
        super().__init__(parent)
        self.asset = asset
        self.setWindowTitle('资产转移')
        self.setMinimumWidth(350)
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)
        self.dept_edit = QLineEdit()
        self.assignee_edit = QLineEdit()
        if self.asset:
            self.dept_edit.setPlaceholderText(f"当前: {self.asset.get('department','')}")
            self.assignee_edit.setPlaceholderText(f"当前: {self.asset.get('assignee','')}")
        layout.addRow('新部门 *:', self.dept_edit)
        layout.addRow('新领用人 *:', self.assignee_edit)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_data(self):
        return {
            'department': self.dept_edit.text().strip(),
            'assignee': self.assignee_edit.text().strip(),
        }


class RepairDialog(QDialog):
    """维修对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('资产维修')
        self.setMinimumWidth(350)
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)
        self.remarks_edit = QTextEdit()
        layout.addRow('维修说明:', self.remarks_edit)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_data(self):
        return {'remarks': self.remarks_edit.toPlainText().strip()}


class RetireDialog(QDialog):
    """报废对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('资产报废')
        self.setMinimumWidth(350)
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)
        self.reason_edit = QTextEdit()
        layout.addRow('报废原因 *:', self.reason_edit)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_data(self):
        return {'reason': self.reason_edit.toPlainText().strip()}


class StatsWindow(QDialog):
    """统计窗口"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('资产统计')
        self.setMinimumSize(600, 400)
        self.setup_ui()
        self.load_stats()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.stats_label = QLabel()
        self.stats_label.setWordWrap(True)
        self.stats_label.setStyleSheet("font-size: 14px; padding: 10px;")
        layout.addWidget(self.stats_label)

    def load_stats(self):
        stats = get_stats()
        lines = [
            f"<b>资产总数量:</b> {stats['total_count']} 件",
            f"<b>资产总价值:</b> ¥{stats['total_price']:,.2f}",
            "",
            "<b>按状态分布:</b>",
        ]
        for s in stats.get('by_status', []):
            lines.append(
                f"  {s['status']}: {s['count']} 件 "
                f"(价值 ¥{s['total_price']:,.2f})"
            )
        lines.append("")
        lines.append("<b>按类别分布:</b>")
        for s in stats.get('by_category', []):
            lines.append(
                f"  {s['category']}: {s['count']} 件 "
                f"(价值 ¥{s['total_price']:,.2f})"
            )
        self.stats_label.setText("<br>".join(lines))


class LogWindow(QDialog):
    """操作日志窗口"""

    def __init__(self, parent=None, asset_id=None):
        super().__init__(parent)
        self.asset_id = asset_id
        self.setWindowTitle('操作日志')
        self.setMinimumSize(600, 350)
        self.setup_ui()
        self.load_logs()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['时间', '操作', '详情', '操作人'])
        self.table.horizontalHeader().setStretchToContents(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.table)

    def load_logs(self):
        logs = get_asset_logs(self.asset_id) if self.asset_id else []
        self.table.setRowCount(len(logs))
        for i, log in enumerate(logs):
            self.table.setItem(i, 0, QTableWidgetItem(log.get('created_at', '')))
            self.table.setItem(i, 1, QTableWidgetItem(log.get('action', '')))
            self.table.setItem(i, 2, QTableWidgetItem(log.get('detail', '')))
            self.table.setItem(i, 3, QTableWidgetItem(log.get('operator', '')))


class AssetManagerWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle('企业资产管理系统')
        self.setMinimumSize(1100, 600)
        self.setup_ui()
        self.status_filter = None
        self.category_filter = None
        self.load_assets()

    def setup_ui(self):
        # ── 菜单栏 ──
        menubar = self.menuBar()
        file_menu = menubar.addMenu('文件')

        export_json_action = QAction('导出 JSON', self)
        export_json_action.triggered.connect(self.do_export_json)
        file_menu.addAction(export_json_action)

        export_csv_action = QAction('导出 CSV', self)
        export_csv_action.triggered.connect(self.do_export_csv)
        file_menu.addAction(export_csv_action)

        file_menu.addSeparator()
        refresh_action = QAction('刷新', self)
        refresh_action.triggered.connect(self.load_assets)
        file_menu.addAction(refresh_action)

        help_menu = menubar.addMenu('帮助')
        about_action = QAction('关于', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        # ── 主布局 ──
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 工具栏
        toolbar = QHBoxLayout()

        self.add_btn = QPushButton('入库')
        self.add_btn.clicked.connect(self.on_add)
        toolbar.addWidget(self.add_btn)

        toolbar.addWidget(QLabel('  状态:'))
        self.status_combo = QComboBox()
        self.status_combo.addItems(['全部', '库存', '已出库', '维修中', '已报废', '已回收'])
        self.status_combo.currentTextChanged.connect(self.on_filter_change)
        toolbar.addWidget(self.status_combo)

        toolbar.addWidget(QLabel('  类别:'))
        self.cat_combo = QComboBox()
        self.cat_combo.addItems(['全部'])
        self.cat_combo.currentTextChanged.connect(self.on_filter_change)
        toolbar.addWidget(self.cat_combo)

        toolbar.addWidget(QLabel('  搜索:'))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText('名称/序列号/型号')
        self.search_edit.textChanged.connect(self.on_filter_change)
        self.search_edit.setMinimumWidth(200)
        toolbar.addWidget(self.search_edit)

        self.stats_btn = QPushButton('📊 统计')
        self.stats_btn.clicked.connect(self.show_stats)
        toolbar.addWidget(self.stats_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 资产表格
        self.table = QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            'ID', '名称', '类别', '型号', '序列号', '采购日期',
            '价格', '状态', '部门', '领用人', '备注'
        ])
        self.table.horizontalHeader().setStretchToContents(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self.on_doubleclick)
        layout.addWidget(self.table)

        # 操作按钮栏
        btn_bar = QHBoxLayout()
        self.checkout_btn = QPushButton('出库')
        self.checkout_btn.clicked.connect(self.on_checkout)
        btn_bar.addWidget(self.checkout_btn)

        self.transfer_btn = QPushButton('转移')
        self.transfer_btn.clicked.connect(self.on_transfer)
        btn_bar.addWidget(self.transfer_btn)

        self.repair_btn = QPushButton('维修')
        self.repair_btn.clicked.connect(self.on_repair)
        btn_bar.addWidget(self.repair_btn)

        self.retire_btn = QPushButton('报废')
        self.retire_btn.clicked.connect(self.on_retire)
        btn_bar.addWidget(self.retire_btn)

        self.recycle_btn = QPushButton('回收')
        self.recycle_btn.clicked.connect(self.on_recycle)
        btn_bar.addWidget(self.recycle_btn)

        self.log_btn = QPushButton('日志')
        self.log_btn.clicked.connect(self.on_show_log)
        btn_bar.addWidget(self.log_btn)

        btn_bar.addStretch()
        layout.addLayout(btn_bar)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def load_assets(self):
        status = None if self.status_combo.currentText() == '全部' \
            else self.status_combo.currentText()
        category = None if self.cat_combo.currentText() == '全部' \
            else self.cat_combo.currentText()
        keyword = self.search_edit.text().strip()

        assets = get_assets(status=status, category=category, keyword=keyword)
        self.table.setRowCount(len(assets))

        for i, a in enumerate(assets):
            self.table.setItem(i, 0, QTableWidgetItem(str(a['id'])))
            self.table.setItem(i, 1, QTableWidgetItem(a['name']))
            self.table.setItem(i, 2, QTableWidgetItem(a['category']))
            self.table.setItem(i, 3, QTableWidgetItem(a['model'] or ''))
            self.table.setItem(i, 4, QTableWidgetItem(a['serial_number'] or ''))
            self.table.setItem(i, 5, QTableWidgetItem(a['purchase_date'] or ''))
            self.table.setItem(i, 6, QTableWidgetItem(f"¥{a['purchase_price']:,.2f}"))
            status_item = QTableWidgetItem(a['status'])
            # 状态颜色
            status_colors = {
                '库存': '#4CAF50',
                '已出库': '#2196F3',
                '维修中': '#FF9800',
                '已报废': '#9E9E9E',
                '已回收': '#9C27B0',
            }
            status_item.setBackground(
                QColor(status_colors.get(a['status'], '#FFF')))
            self.table.setItem(i, 7, status_item)
            self.table.setItem(i, 8, QTableWidgetItem(a['department'] or ''))
            self.table.setItem(i, 9, QTableWidgetItem(a['assignee'] or ''))
            self.table.setItem(i, 10, QTableWidgetItem(a['remarks'] or ''))

        self.status_bar.showMessage(f'共 {len(assets)} 条资产记录')

        # 更新类别下拉
        cats = get_categories()
        current = self.cat_combo.currentText()
        self.cat_combo.blockSignals(True)
        self.cat_combo.clear()
        self.cat_combo.addItems(['全部'] + cats)
        if current in cats:
            self.cat_combo.setCurrentText(current)
        self.cat_combo.blockSignals(False)

    def on_filter_change(self):
        self.load_assets()

    def on_doubleclick(self):
        self.on_edit()

    def get_selected_asset_id(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, '提示', '请先选择一条资产记录')
            return None
        return int(self.table.item(row, 0).text())

    def on_add(self):
        dlg = AssetFormDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            if not data['name']:
                QMessageBox.warning(self, '错误', '资产名称不能为空')
                return
            try:
                add_asset(**data)
                QMessageBox.information(self, '成功', '资产入库成功')
                self.load_assets()
            except sqlite3.IntegrityError:
                QMessageBox.warning(self, '错误', '序列号已存在，请勿重复')

    def on_edit(self):
        asset_id = self.get_selected_asset_id()
        if not asset_id:
            return
        asset = get_asset(asset_id)
        dlg = AssetFormDialog(self, asset)
        if dlg.exec():
            data = dlg.get_data()
            conn = get_conn()
            c = conn.cursor()
            c.execute("""
                UPDATE assets SET name=?, category=?, model=?,
                                  serial_number=?, purchase_date=?,
                                  purchase_price=?, remarks=?,
                                  updated_at=datetime('now','localtime')
                WHERE id=?
            """, (data['name'], data['category'], data['model'],
                  data['serial'], data['purchase_date'],
                  data['price'], data['remarks'], asset_id))
            conn.commit()
            conn.close()
            QMessageBox.information(self, '成功', '资产更新成功')
            self.load_assets()

    def on_checkout(self):
        asset_id = self.get_selected_asset_id()
        if not asset_id:
            return
        asset = get_asset(asset_id)
        dlg = CheckoutDialog(self, asset)
        if dlg.exec():
            data = dlg.get_data()
            if not data['department'] or not data['assignee']:
                QMessageBox.warning(self, '错误', '部门和领用人不能为空')
                return
            if checkout_asset(asset_id, data['department'], data['assignee']):
                QMessageBox.information(self, '成功', '资产出库成功')
                self.load_assets()
            else:
                QMessageBox.warning(self, '错误', '当前状态不允许出库')

    def on_transfer(self):
        asset_id = self.get_selected_asset_id()
        if not asset_id:
            return
        asset = get_asset(asset_id)
        dlg = TransferDialog(self, asset)
        if dlg.exec():
            data = dlg.get_data()
            if not data['department'] or not data['assignee']:
                QMessageBox.warning(self, '错误', '部门和领用人不能为空')
                return
            if transfer_asset(asset_id, data['department'], data['assignee']):
                QMessageBox.information(self, '成功', '资产转移成功')
                self.load_assets()
            else:
                QMessageBox.warning(self, '错误', '当前状态不允许转移')

    def on_repair(self):
        asset_id = self.get_selected_asset_id()
        if not asset_id:
            return
        dlg = RepairDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            repair_asset(asset_id, data['remarks'])
            QMessageBox.information(self, '成功', '维修记录已添加')
            self.load_assets()

    def on_retire(self):
        asset_id = self.get_selected_asset_id()
        if not asset_id:
            return
        dlg = RetireDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            if not data['reason']:
                QMessageBox.warning(self, '错误', '请填写报废原因')
                return
            if retire_asset(asset_id, data['reason']):
                QMessageBox.information(self, '成功', '资产已报废')
                self.load_assets()
            else:
                QMessageBox.warning(self, '错误', '当前状态不允许报废')

    def on_recycle(self):
        asset_id = self.get_selected_asset_id()
        if not asset_id:
            return
        asset = get_asset(asset_id)
        if asset['status'] == '已报废':
            conn = get_conn()
            c = conn.cursor()
            c.execute("""
                UPDATE assets SET status='已回收',
                                  updated_at=datetime('now','localtime')
                WHERE id=?
            """, (asset_id,))
            log_action(asset_id, '回收', '资产回收')
            conn.commit()
            conn.close()
            QMessageBox.information(self, '成功', '资产已回收')
            self.load_assets()
        else:
            QMessageBox.warning(self, '错误', '只有已报废的资产才能回收')

    def on_show_log(self):
        asset_id = self.get_selected_asset_id()
        dlg = LogWindow(self, asset_id)
        dlg.exec()

    def show_stats(self):
        dlg = StatsWindow(self)
        dlg.exec()

    def do_export_json(self):
        try:
            path = export_to_json()
            QMessageBox.information(self, '导出成功', f'已导出:\n{path}')
        except Exception as e:
            QMessageBox.warning(self, '导出失败', str(e))

    def do_export_csv(self):
        try:
            path = export_to_csv()
            if path:
                QMessageBox.information(self, '导出成功', f'已导出:\n{path}')
            else:
                QMessageBox.warning(self, '导出失败', '没有数据可导出')
        except Exception as e:
            QMessageBox.warning(self, '导出失败', str(e))

    def show_about(self):
        QMessageBox.about(self, '关于',
                          '<b>企业资产管理系统</b><br>'
                          'Version 1.0<br>'
                          '入库/出库/转移/维修/报废/统计/报表<br><br>'
                          '双击记录可编辑')


# ─── 入口 ────────────────────────────────────────────

def main():
    init_db()
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = AssetManagerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    if USE_PYSIDE:
        main()
    else:
        print("请先安装 PySide6: pip install PySide6")
        print("安装后运行: python asset_manager.py")
