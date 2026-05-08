#一: 总体概述

算力盒子智慧感知平台 采用前后端分离的方案
前端使用vue 后端用flask 开发, 用nginx 来实现前后端分开部署

#二: flask 部分概述
## 1. 目录结构
### app.py -> 入口文件
### config.py -> 配置文件
### fakes.py -> 造假的數據
### extends.py -> 拓展库相关的
### 已经约定的目录   templates  static 
### 自定义的目录   
#### > user (xshx add 20220408)
##### 用户相关的


##2.数据库使用方法
### mysql
### 初始化db:  flask db init
### 更新db: flask db migrate -m "注释"
### 应用更新: flask db upgrade 
### mongo

##3.库的说明

##4.更多

#三:  安装部署
## 开发环境配置

## 生产环境配置
linux 环境
###1.导出开发环境的配置
        pip install pipreqs
        pipreqs . --encoding=utf8 --force
        生成 requirements.txt
###2.创建生成环境
        python -m venv env
        source env/bin/activate
        pip install -r requirements.txt
        python app.py   

#四: 参考文档:
《Flask Web开发实战：入门、进阶与原理解析》_李辉