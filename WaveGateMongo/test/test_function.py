def bytesToHexString(bs):
    # hex_str = ''
    # for item in bs:
    #     hex_str += str(hex(item))[2:].zfill(2).upper() + " "
    # return hex_str
    return ''.join(['%02X' % b for b in bs])


# s = b'\x00\x01\x00\x00\x00\x06\xff\x05\x00d\x00\x00'
# print(bytesToHexString(s))

import subprocess
import os

def execShell(cmd):
    err,result = subprocess.getstatusoutput(cmd)
    return err,result

def transfer_img_url(ipaddr,imgurl):
    url  = 'http://10.0.192.105:8088/net-web/control/event_images/079b3898d9484b62b55ca9e84f131a5e?date=20230424'
    imgend = url.split('/',3)[-1]
    imgstart = 'http://%s:8088/'%ipaddr
    url_img = imgstart + imgend
    return url_img

def get_eth0_ip():
    '''
    说明:从eth0文件获取ip地址和网关等
    '''
    eth0_path = "/etc/network/interfaces.d/eth0"
    if not os.path.exists(eth0_path):
        return
    fp = open(eth0_path,'r')
    content = fp.readlines()
    ip = content[2].lstrip().split()[1]
    netmask = content[3].lstrip().split()[1]
    gateway = content[4].lstrip().split()[1]
    dns = content[5].lstrip().split()[1]
    return (ip,netmask,gateway,dns)


def get_ip():
    err0,result0 = execShell("sudo ifconfig eth0")
    print(result0.split())
    return

def get_nginx_port():
    cmd = 'cat /etc/nginx/nginx.conf|grep listen'
    error,result = execShell(cmd)
    print(result.split()[1][:-1])
    return


def getPid(command,Toflag):
    try:
        cmd = "ps -ef|grep -v grep|grep " + command + "|grep " + Toflag
        error,resp = execShell(cmd)
        if not resp:
            return None
        else:
            pid = resp.split()[1]
        return pid
    except Exception as e:
        print('error : %s'%e)
        return

getPid()    