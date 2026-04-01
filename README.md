# 企业资产管理系统

## 运行方法

### 1. 安装依赖
```bash
pip install PySide6
```

### 2. 运行程序
```bash
python asset_manager.py
```

## 功能列表

| 功能 | 说明 |
|------|------|
| 📥 入库 | 录入新资产（名称、类别、型号、序列号、采购日期、价格） |
| 📤 出库 | 资产分配给员工（部门 + 领用人） |
| 🔄 转移 | 资产在部门/员工之间调拨 |
| 🔧 维修 | 记录维修历史 |
| 🗑️ 报废 | 标记报废 + 填写原因 |
| ♻️ 回收 | 回收已报废资产 |
| 📊 统计 | 按状态/类别统计数量和总价 |
| 📋 日志 | 查看资产操作历史 |
| 📤 导出 | 导出 JSON / CSV 报表 |

## 打包成 .exe（Windows）

安装 PyInstaller：
```bash
pip install pyinstaller
```

打包：
```bash
pyinstaller --onefile --windowed asset_manager.py
```

打包完成后，`dist/asset_manager.exe` 就是可双击运行的独立文件。

## 界面预览

- 顶部：工具栏（入库/状态筛选/类别筛选/搜索/统计）
- 中部：资产列表表格（双击可编辑）
- 底部：操作按钮（出库/转移/维修/报废/回收/日志）
