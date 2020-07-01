import uuid
from threading import Thread
import copy
import logging
from datetime import datetime
import time
from math import sin
import sys
import socket
import os
import platform 

from opcua.ua import NodeId, NodeIdType
from opcua import ua, uamethod, Server

# Inserts current folder to sys path at index 0
sys.path.insert(0, "..")

# Interactive IDE
try:
    from IPython import embed
except ImportError:
    import code

    def embed():
        myvars = globals()
        myvars.update(locals())
        shell = code.InteractiveConsole(myvars)
        shell.interact()


class SubHandler(object):
    """
    Subscription Handler. To receive events from server for a subscription
    """

    def datachange_notification(self, node, val, data):
        print("Python: New data change event", node, val)

    def event_notification(self, event):
        print("Python: New event", event)


# method to be exposed through server

def func(parent, variant):
    ret = False
    if variant.Value % 2 == 0:
        ret = True
    return [ua.Variant(ret, ua.VariantType.Boolean)]


# method to be exposed through server
# uses a decorator to automatically convert to and from variants

@uamethod
def open_cmd(parent):
    os.system("start cmd")

class CyclicValueUpdater(Thread):
    def __init__(self, interval):
        """
        Parameters:
        interval (int): interval in seconds [s]
        """
        Thread.__init__(self)
        super().setDaemon(True)
        self.interval = interval
        self.stopthread = False
        self.varlist = []
        

    def stop(self):
        self.stopthread = True

    def insert_variable(self, var, getterfunc):
        self.varlist.append((var, getterfunc))

    def run(self):
        while not self.stopthread:
            for e in self.varlist:
                e[0].set_value(e[1]())

            time.sleep(self.interval)


if __name__ == "__main__":
    # optional: setup logging
    logging.basicConfig(level=logging.WARN)

    # now setup our server
    server = Server()
    #server.disable_clock()
    server.set_endpoint("opc.tcp://localhost:5020")
    server.set_server_name("Example OPC UA Python Server")
    
    # set all possible endpoint policies for clients to connect through
    server.set_security_policy([
                ua.SecurityPolicyType.NoSecurity,
                ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt,
                ua.SecurityPolicyType.Basic256Sha256_Sign])

    # setup our own namespace
    uri = "http://masam.io/opcua"
    idx = server.register_namespace(uri)

    # create a new node type we can instantiate in our address space
    sys_data = server.nodes.base_object_type.add_object_type(idx, "SystemData")
    sys_data.add_variable(idx, "time", "invalid").set_modelling_rule(True)
    sys_data.add_variable(idx, "os", "").set_modelling_rule(True)
    sys_data.add_variable(idx, "platform", "").set_modelling_rule(True)
    sys_data.add_variable(idx, "release", "").set_modelling_rule(True)
    sys_data.add_variable(idx, "hostname", "").set_modelling_rule(True)
    sys_data.add_variable(idx, "ip", "").set_modelling_rule(True)


    # instanciate one instance of our system data
    server_system = server.nodes.objects.add_object(idx, "ServerSystem", sys_data)
    server_time = server_system.get_child(["{}:time".format(idx)]) 
    server_os = server_system.get_child(["{}:os".format(idx)]) 
    server_hostname = server_system.get_child(["{}:hostname".format(idx)]) 
    server_ip = server_system.get_child(["{}:ip".format(idx)]) 
    server_platform = server_system.get_child(["{}:platform".format(idx)]) 
    server_release = server_system.get_child(["{}:release".format(idx)]) 
    server_system.add_method(idx, "open_cmd", open_cmd)

    # starting!
    server.start()
    print("Available loggers are: ", logging.Logger.manager.loggerDict.keys())

    # Static variables
    #-----------------------------------------------------
    server_os.set_value(os.name)
    server_hostname.set_value(socket.gethostname())
    server_ip.set_value(socket.gethostbyname(server_hostname.get_value()))
    server_platform.set_value(platform.system())
    server_release.set_value(platform.release())

    # Dynamic variables
    # -----------------------------------------------------
    # Create cyclic variable updater (Inteval in seconds)
    cvu = CyclicValueUpdater(1)
    # record variables for cyclic update (opc variable to be updated, function to be called to get value)
    cvu.insert_variable(server_time, lambda: datetime.now())
    cvu.insert_variable(server_ip, lambda: socket.gethostbyname(server_hostname.get_value()))
    # start updater
    cvu.start()

    try:
        embed()
    finally:
        cvu.stop()
        server.stop()

