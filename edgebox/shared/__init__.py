"""
与具体产品线解耦、可共用的实现（当前主要为 ``algorith_server`` 侧无应用上下文的模块）。

各 app 在 ``algorith_server`` 下保留与原模块同名的薄重导出文件，避免批量修改业务 import 路径。
"""
