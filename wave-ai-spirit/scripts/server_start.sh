#!/bin/bash

#main entrance
cd /data/ebox 
base_path=`pwd`

#预处理
PATH="/usr/bin:/bin:$base_path"
export PATH

#启动emqx
cd $base_path
EMQX_PID=$(ps -ef | grep emqx | grep -v grep | wc -l)
if [ $EMQX_PID -le 0 ];then
	echo "emqx服务启动中......."
	nohup $base_path/emqx/bin/emqx start >/dev/null 2>&1  &
	sleep 5
fi
echo "emqx服务启动成功"

#启动redis服务
cd $base_path
REDIS_PID=$(ps -ef | grep redis-server | grep -v grep | wc -l)
if [ $REDIS_PID -le 0 ];then
	echo "redis服务启动中......."
	chmod 777 $base_path/redis-5.0.12/src/redis-server
	nohup $base_path/redis-5.0.12/src/redis-server $base_path/redis-5.0.12/redis.conf >/dev/null 2>&1  &
	sleep 5
fi
echo "redis服务启动成功"

#启动nginx服务
cd $base_path
NGINX_PID=$(ps -ef | grep "/usr/sbin/nginx -c /etc/nginx/nginx.conf" | grep -v grep | wc -l)
if [ $NGINX_PID -le 0 ];then
	echo "nginx服务启动中......."
	killall nginx >/dev/null 2>&1
#	cp -rf $base_path/nginx/cfg/nginx/nginx.conf /etc/nginx/nginx.conf
	/usr/sbin/nginx -c /etc/nginx/nginx.conf
	sleep 5
fi
echo "nginx服务启动成功"

MONGO_PID=$(ps -ef | grep mongod | grep -v grep | wc -l)
if [ $MONGO_PID -le 0 ];then
    echo "mongo服务启动中......."
	rm -rf /data/python-web/fzdn-python/mongodb/log/*
    /usr/bin/mongod --dbpath /data/python-web/fzdn-python/mongodb/data/db --logpath /data/python-web/fzdn-python/mongodb/log/mongodb.log --fork >/dev/null 2>&1
	echo "mongo服务启动成功"
fi

PYTHON_PID=$(ps -ef | grep WaveGateMongo | grep -v grep | wc -l)
if [ $PYTHON_PID -le 0 ];then
	while [ $MONGO_PID -le 0 -o $EMQX_PID -le 0 ]
	do
		sleep 5
	done
    echo "python后台服务启动中......."
    export PYTHONPATH=$PYTHONPATH:/system/lib:/usr/local/lib
    export HOMEPATH=$HOMEPATH:/root
    export OPENCV_FFMPEG_CAPTURE_OPTIONS="gb28181_transport_rtp;tcp|rtsp_transport;tcp|buffer_size;1024000|max_delay;500000|stimeout;20000000|analyzeduration;100|probesize;5000"
    nohup python3 -u /data/python-web/fzdn-python/WaveGateMongo/app.py  >/data/python-web/fzdn-python/nohup.out 2>&1 &
    echo "--python后台服务启动成功"    
fi

#启动算法服务
cd $base_path
MONITOR_PID=$(ps -ef | grep "$base_path/alg/monitor.sh" | grep -v grep | wc -l)
if [ $MONITOR_PID -le 0 ];then
	echo "alg监控服务启动中......"
	nohup $base_path/alg/monitor.sh EcalculateBox backgroud >/dev/null 2>&1  &
fi
echo "alg监控服务启动成功"
