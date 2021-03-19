python ../mockdevice.py 0.0.0.0 10000 1 ssh ../devices/cisco_IOS.json &
python ../mockdevice.py 0.0.0.0 10001 1 ssh ../devices/cisco_XR.json &
python ../mockdevice.py 0.0.0.0 10002 1 ssh ../devices/huawei_VRP.json &
python ../mockdevice.py 0.0.0.0 10003 1 ssh ../devices/cisco_XR5.json &
python ../mockdevice.py 0.0.0.0 10004 1 ssh ../devices/cisco_XR623.json &
python ../mockdevice.py 0.0.0.0 10005 1 ssh ../devices/cisco_XR661.json &
python ../mockdevice.py 0.0.0.0 10006 1 ssh ../devices/cisco_XR701.json &
python ../mockdevice.py 0.0.0.0 10007 1 ssh ../devices/junos_14.json &

wait
