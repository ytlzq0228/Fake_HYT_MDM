import sys
import os
import time
import re
import configparser
import aprs
from datetime import datetime

CALLSIGN="BI1FQO"
SSID="BI1FQO-H"
SSID_ICON="Q"
APRS_PASSWORD="20898"
APRS_Server=""

def aprs_report(lat_input, lon_input, device_name):

	try:
		decimal_lat = float(lat_input)
		lat_dir = "N" if decimal_lat >= 0 else "S"
		lat_degrees = int(abs(decimal_lat))
		lat_minutes = (abs(decimal_lat) - lat_degrees) * 60
	
		# 经度转换
		decimal_lon = float(lon_input)
		lon_dir = "E" if decimal_lon >= 0 else "W"
		lon_degrees = int(abs(decimal_lon))
		lon_minutes = (abs(decimal_lon) - lon_degrees) * 60

		# 格式化为 APRS 格式
		lat = f"{lat_degrees:02d}{lat_minutes:05.2f}"
		lon = f"{lon_degrees:03d}{lon_minutes:05.2f}"


		frame_text=(f'{SSID}>PYTHON,TCPIP*,qAC,{SSID}:!{lat}{lat_dir}/{lon}{lon_dir}{SSID_ICON}APRS by Hytera MDM from {device_name} report').encode()
		callsign = CALLSIGN.encode('utf-8')
		password = APRS_PASSWORD.encode('utf-8')
		
		# 定义 APRS 服务器地址和端口（字节形式）
		#server_host = APRS_Server.encode('utf-8')  # 使用 rotate.aprs2.net 服务器和端口 14580
		
		# 创建 TCP 对象并传入服务器信息
		#a = aprs.TCP(callsign, password, servers=[server_host])
		a = aprs.TCP(callsign, password)
		a.start()
		aprs_return=a.send(frame_text)
		if aprs_return==len(frame_text)+2:
			print('APRS Report Good Length:%s'%aprs_return)
		else:
			print('APRS Report Return:%s Frame Length: %s Retrying..'%(aprs_return,frame_text))
	except Exception as err:
		print(f"APRS Report Error: {err}")

if __name__ == "__main__":
	aprs_report("-23.56729", "-46.65940", "device_name")