#!/usr/bin/python3
from flask import Flask, abort
import tinytuya
from clientlib import RestApiClient
from config import CONFIG
from core.log import create_logger
from core.appinfo import AppInfo


AppInfo.init(__name__, CONFIG['default'])
app = AppInfo.get_app()


tinytuya.set_debug(False)

logger=create_logger(__name__)

class DeviceRoutingNotFound(Exception):
    pass

class DeviceNotFound(Exception):
    pass

class DeviceAttributeKeyNotFound(Exception):
    pass

@app.route("/<external_device_id>/<attribute>/<value>", methods=['POST','GET'])
def send_command(external_device_id, attribute, value):
    try:
        client=__create_client()

        rs=__retrive_device(client, external_device_id)
        device_attribute_key=__get_device_attribute_key(client, attribute, rs['class_id'])

        if rs!=None and (rs['vendor_id']).upper()=='TUYA' and (rs['class_id']).upper()=='BULB':
            d = tinytuya.BulbDevice(rs['id'], rs['address'], rs['local_key'], dev_type='default')
            d.set_version(float(rs['version']))

            key_value=False
            if value=='on':
                key_value=True

            d.set_value(device_attribute_key,key_value)

        elif rs!=None and (rs['vendor_id']).upper()=='TUYA' and (rs['class_id']).upper()=='OUTLET':
            d = tinytuya.OutletDevice(rs['id'], rs['address'], rs['local_key'], dev_type='default')
            d.set_version(float(rs['version']))

            key_value=False
            if value=='on':
                key_value=True
            print(device_attribute_key)
            d.set_value(device_attribute_key,key_value)

        else:
            print("No device found")

        __logoff_client(client)

        return f"OK"

    except (DeviceRoutingNotFound,DeviceNotFound,DeviceAttributeKeyNotFound) as err:
        logger.exception(f"{err}")
        abort(404,f"{err}")
    except exception as err:
        logger.exception(f"{err}")
        abort(500,f"{err}")


def __retrive_device(client, device_alias):
    rs=client.read_multible("iot_device_routing", {"internal_device_id": f"{device_alias}" }, json_out=True, none_if_eof=True)
    if rs == None:
        raise DeviceRoutingNotFound(f"{device_alias}")

    rs=client.read_multible("iot_device", {"id": f"{rs[0]['external_device_id']}"}, json_out=True, none_if_eof=True)

    if rs==None:
        raise DeviceNotFound(f"{rs[0]['external_device_id']}")

    return rs[0]


def __get_device_attribute_key(client, attribute, class_id):
    rs=client.read_multible("iot_device_attribute",{"name":f"{attribute}", "class_id": f"{class_id}"}, json_out=True, none_if_eof=True)

    if rs==None:
        raise DeviceAttributeKeyNotFound(f"attribute:{attribute} class_id:{class_id}")

    return rs[0]['device_attribute_key']

def __create_client():
    client=AppInfo.create_restapi_client()
    return client

def __logoff_client(client):
    client.logoff()


@app.before_first_request
def start_monitor():
    from threading import Thread
    from plugins.tuya_device_monitor import TuyaDeviceMonitor
    from plugins.tuya_device_scanner import TuyaDeviceScanner

    def run_monitor():
        client=AppInfo.create_restapi_client()

        tuya_mon=TuyaDeviceMonitor()
        tuya_mon.execute(client)

    def run_scanner():
        client=AppInfo.create_restapi_client()

        tuya_scan=TuyaDeviceScanner()
        tuya_scan.execute(client)

    print("starting the main threads")
    t_mon = Thread(target=run_monitor)
    t_mon.setDaemon(True)
    t_mon.start()

    t_scan = Thread(target=run_scanner)
    t_scan.setDaemon(True)
    t_scan.start()
    print("main threads running")


if __name__ == '__main__':
    app.run(debug=True, host=AppInfo.get_server_host(), port=AppInfo.get_server_port())
