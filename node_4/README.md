#MQTT Topic for Data --> OC7/data/N2
Example: mosquitto_sub -h localhost -p 1883 -t "OC7/data/N2"

#MQTT Topic to send "rebooot" and "calibrate" --> "remote_control"
Example: mosquitto_pub -h localhost -t "remote_control" -m "calibrate"
