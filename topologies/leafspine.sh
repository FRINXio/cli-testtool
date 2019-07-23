python ../mockdevice.py 0.0.0.0 11000 1 ssh ../devices/leafspine/leaf1.json &
python ../mockdevice.py 0.0.0.0 11001 1 ssh ../devices/leafspine/leaf2.json &
python ../mockdevice.py 0.0.0.0 11002 1 ssh ../devices/leafspine/leaf3.json &
python ../mockdevice.py 0.0.0.0 11003 1 ssh ../devices/leafspine/leaf4.json &
python ../mockdevice.py 0.0.0.0 11004 1 ssh ../devices/leafspine/leaf5.json &
python ../mockdevice.py 0.0.0.0 12000 1 ssh ../devices/leafspine/spine1.json &
python ../mockdevice.py 0.0.0.0 12001 1 ssh ../devices/leafspine/spine2.json &

wait
