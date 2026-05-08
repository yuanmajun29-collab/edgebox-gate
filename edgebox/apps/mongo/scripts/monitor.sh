#!/bin/bash 

#检查监控脚本进程探测
function check_monitor()
{
	normal_num=0
	monitor_path=`pwd`
	
	monitor_id=`ps -ef|grep ^monitor.sh|grep -v grep|awk '{print $2}'`
	for pid in ${monitor_id[*]}
	do
		tmp=`ls -al /proc/$pid|grep $monitor_path|wc -l`
		if [ $tmp -ge 1 ]
		then
			let normal_num++
		fi
	done

	if [ $normal_num -ge 2 ]
	then
		echo `/bin/date +"%Y-%m-%d %H:%M:%S"`
		echo "monitor.sh have been started on other window"
		exit 0
	fi
}


# monitor main

cd `dirname $0`
path=`pwd`

check_monitor 

while :
do
	cd $path
	./server_start.sh
	sleep 5
done
