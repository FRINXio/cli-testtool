python ../mockdevice.py 0.0.0.0 10000 1 ssh ../devices/cisco_IOS.json &
python ../mockdevice.py 0.0.0.0 10001 1 ssh ../devices/cisco_XR.json &
python ../mockdevice.py 0.0.0.0 10002 1 ssh ../devices/huawei_VRP.json &

wait
