"""
Mongo 网关类产品线（``apps/mongo``、``apps/ai_spirit``）共用实现。

含：日志与 JWT（``logcfg``/``utils``）、入口与配置（``app_main``/``product_config``）、
第三方开放接口（``thirdpaty``）、阿里云短信（``alibabasms``）、部分路由与算法侧工具等。
运行期仍依赖各 app 目录在 ``sys.path`` 上以便解析 ``Utils``、``system``、``config`` 等包名。

能耗站 ``apps/energy`` 不使用此子包。
"""
