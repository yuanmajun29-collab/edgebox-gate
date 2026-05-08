#!/bin/bash

#main entrance
cd /data/ebox
base_path=`pwd`

#预处理
PATH="/usr/bin:/bin:$base_path"
export PATH

#停止算法服务
cd $base_path
MONITOR_PID=$(ps -ef | grep "$base_path/alg/monitor.sh" | grep -v grep | wc -l)
if [ $MONITOR_PID -gt 0 ];then
        echo "alg监控服务停止中......"
        ps -ef | grep "$base_path/alg/monitor.sh" | grep -v grep | awk '{print $2}' | xargs kill -9
        echo "alg监控服务停止成功"
fi