"""
与具体产品线解耦、可共用的实现：

- ``algorith_server``：Redis 与二进制协议等（各 app 下同名薄重导出）
- ``mongo_line``：``apps/mongo`` 与 ``apps/ai_spirit`` 共用的日志映射与 JWT 工具函数
- ``repo_path`` / ``edgebox_repo_entry``：仓库根 ``sys.path`` 引导（各 app ``Utils/edgebox_repo`` 符号链接至此）
"""
