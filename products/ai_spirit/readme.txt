1、flask-mongoengine 这个库的依赖很多，有些库要注意对应Python版本
					 如Flask-wtf和mongoengine这两个库，这两个库最
					 新版只能在Python>=3.8下运行，盒子的Python为3.5，
					 这两个库只能装旧版本；


2、盒子reboot或刚开机需要启动mqtt服务、启动mongodb服务,启动nginx服务
2.1、启动mqtt方法:
	cd 	/home/lishen/Toolkit/emqx/
	./bin/emqx start
	./bin/emqx_ctl status
	关闭mqtt服务：
	./bin/emqx stop

2.2、启动mongodb服务：
	cd /usr/bin
	mongod --dbpath /data/mongodb/db --logpath /data/mongodb/log/mongodb.log --fork

	// mongod --dbpath /data/ymj/fzdn-python/mongodb/data/db --logpath /data/ymj/fzdn-python/mongodb/log/mongodb.log --fork

2.3、启动nginx服务：
	/usr/sbin/nginx -c /etc/nginx/nginx.conf

    // /usr/sbin/nginx -c /data/ymj/fzdn-python/nginx.conf
	
	tip:盒子复位后或者刚拿到盒子时，需将/etc/nginx/conf.d/下的两个文件删掉或者改成nginx.box.conf.bak和nginx.gate.conf.bak；	