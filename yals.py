#!/usr/bin/env python3

# Yet Another Linux Sandbox
# Copyright © 2015 - Dario Ostuni < another.code.996@gmail.com >
# License: Apache License Version 2.0 ( https://www.apache.org/licenses/LICENSE-2.0.html )

import os
import lxc
import sys
import json
import shutil
import base64

autodev_config = """#!/bin/bash
cd ${LXC_ROOTFS_MOUNT}/dev
mkdir net
mknod net/tun c 10 200
chmod 0666 net/tun
"""
def check_field(field, dic):
    if field not in dic:
        print("Missing \"", field, "\" from \"", sys.argv[1], "\"", sep="")
        sys.exit(1)
if os.getuid() != 0:
    print("You must be root")
    sys.exit(1)
if len(sys.argv) != 2:
    print("Usage:", sys.argv[0], "<config>.json")
    sys.exit(1)
try:
    config_file = open(sys.argv[1], "r")
except FileNotFoundError:
    print("Error opening \"", sys.argv[1], "\"", sep="")
    sys.exit(1)
config_file_content = config_file.read()
config_file.close()
try:
    config = json.loads(config_file_content)
except:
    print("\"", sys.argv[1], "\" contains invalid JSON", sep="")
    sys.exit(1)
check_field("action", config)
check_field("id", config)
os.makedirs("/root/yals/", exist_ok = True, mode = 0o700)
sandbox = lxc.Container(str(config["id"]), config_path = "/root/yals/")
if config["action"] == "create":
    if sandbox.defined:
        print("Sandbox already exists")
        sys.exit(1)
    if not isinstance(config["id"], int):
        print("ID must be an integer associated with a CPU Core")
        print("(From 0 to # of cores - 1)")
        sys.exit(1)
    shutil.copy("lxc-yals", "/usr/share/lxc/templates/lxc-yals")
    os.chmod("/usr/share/lxc/templates/lxc-yals", 0o755)
    sandbox.create(template = "yals")
    autodev_file = open("/root/yals/" + str(config["id"]) + "/autodev", "w")
    print(autodev_config, file=autodev_file)
    autodev_file.close()
    os.chmod("/root/yals/" + str(config["id"]) + "/autodev", 0o755)
    sandbox.append_config_item("lxc.autodev", "1")
    sandbox.append_config_item("lxc.pts", "1024")
    sandbox.append_config_item("lxc.kmsg", "0")
    sandbox.append_config_item("lxc.hook.autodev", "/root/yals/" + str(config["id"]) + "/autodev")
    sandbox.append_config_item("lxc.cgroup.memory.limit_in_bytes", "1G")
    sandbox.append_config_item("lxc.cgroup.memory.swappiness", "0")
    sandbox.append_config_item("lxc.cgroup.cpuset.cpus", str(config["id"]))
    sandbox.append_config_item("lxc.cgroup.cpu.shares", "1024")
    sandbox.save_config()
elif config["action"] == "destroy":
    if not sandbox.defined:
        print("Sandbox doesn't exist")
        sys.exit(1)
    sandbox.destroy()
elif config["action"] == "execute":
    check_field("command", config)
    check_field("input", config)
    check_field("output", config)
    check_field("time", config)
    check_field("memory", config)
    sandbox.append_config_item("lxc.cgroup.memory.limit_in_bytes", str(config["memory"]) + "M")
    sandbox.save_config()
    sandbox.start()
    sandbox.attach_wait(lxc.attach_run_command, ["yals_clean"])
    for key in config["input"]:
        f = open("/root/yals/" + str(config["id"]) + "/rootfs/yals/" + key, "wb")
        f.write(base64.b64decode(config["input"][key].encode()))
        f.close()
        os.chmod("/root/yals/" + str(config["id"]) + "/rootfs/yals/" + key, 0o777)
    f = open("/root/yals/" + str(config["id"]) + "/rootfs/yals/__execute.sh", "w")
    f.write("#!/bin/bash\n")
    f.write(config["command"])
    f.close()
    os.chmod("/root/yals/" + str(config["id"]) + "/rootfs/yals/__execute.sh", 0o777)
    for key in config["output"]:
        open("/root/yals/" + str(config["id"]) + "/rootfs/yals/" + key, "w")
        os.chmod("/root/yals/" + str(config["id"]) + "/rootfs/yals/" + key, 0o777)
    sandbox.attach_wait(lxc.attach_run_command, ["yals_execute", str(config["time"])])
    response = {}
    output_json = json.loads(open("/root/yals/" + str(config["id"]) + "/rootfs/root/info.json", "r").read())
    for i in ("time", "memory", "return"):
        response[i] = output_json[i]
    response["memory"] = response["memory"] / 1024
    response["output"] = {}
    for key in config["output"]:
        try:
            f = open("/root/yals/" + str(config["id"]) + "/rootfs/yals/" + key, "rb")
        except FileNotFoundError:
            response["output"][key] = ""
            continue
        response["output"][key] = base64.b64encode(f.read()).decode()
        f.close()
    output_result = open("yals_output_" + str(config["id"]) + ".json", "w")
    output_result.write(json.dumps(response))
    output_result.close()
    os.chmod("yals_output_" + str(config["id"]) + ".json", 0o777)
    sandbox.attach_wait(lxc.attach_run_command, ["yals_clean"])
    sandbox.stop()
else:
    print("Action not valid")
    sys.exit(1)
