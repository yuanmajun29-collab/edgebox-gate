"""
与具体产品线解耦、可共用的实现：

- ``flask_bootstrap``：各产品线共用的 ``create_configured_app()``
- ``algorith_server``（本目录下子包）：Redis 与二进制协议等（各 app 薄重导出）
- ``mongo_line``：``apps/mongo`` 与 ``apps/ai_spirit`` 共用的日志映射与 JWT 工具函数
- ``energy_line``：``apps/energy`` 共用的 Blueprint 注册
- ``wave_blueprint_segments``：mongo / energy 等共用的连续 Blueprint 注册小段
- ``wave_app_common``：mongo / ai_spirit（及与之一致的 energy 文件）共用的同名模块；各 app 内为指向此目录的符号链接（Windows 需启用 git symlink 支持）
- ``repo_path`` / ``edgebox_repo_entry``：仓库根 ``sys.path`` 引导（各 app ``Utils/edgebox_repo`` 符号链接至此）
"""
