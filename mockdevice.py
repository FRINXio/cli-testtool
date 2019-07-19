#!/usr/bin/python

import os
import sys
import time
import argparse
# import psutil
import MockSSH
import MockSSHExtensions
import traceback
from random import randint
from time import sleep

import json
from collections import defaultdict

from twisted.python import log
from threading import Thread
from twisted.internet import reactor

from twisted.internet import reactor
from twisted.internet.protocol import ClientFactory, ServerFactory
from twisted.conch.telnet import TelnetTransport, TelnetProtocol, AuthenticatingTelnetProtocol, ITelnetProtocol, TelnetBootstrapProtocol, StatefulTelnetProtocol
from twisted.cred import checkers, portal
from twisted.conch import avatar, interfaces as conchinterfaces, recvline
from twisted.conch import manhole
from twisted.conch.insults import insults
from twisted.conch.ssh import session
import multiprocessing
import subprocess

pool = None
batch_size = 100  # ports to handle per process


def get_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('interface')
    parser.add_argument('first_port')
    parser.add_argument('devices_number')
    parser.add_argument('protocol_type')
    parser.add_argument('device_file')
    return parser.parse_args(argv)


def main(args):

    protocol_type = args.protocol_type
    device_file = args.device_file
    interface = args.interface

    port_low = int(args.first_port)
    port_high = port_low + int(args.devices_number)
    all_ports = port_high - port_low
    last_batch = all_ports % batch_size
    processes = all_ports / batch_size

    log.startLogging(sys.stdout)

    with open(device_file) as f:
        data = json.load(f)

    global pool
    process_pool_size = processes if last_batch <= 0 else (processes + 1)

    if process_pool_size == 1:
        print("Running in a single process")
        spawn_server(port_low, port_high, interface, protocol_type, data)
    else:
        print("Spawning pool with %s processes" % process_pool_size)
        pool = multiprocessing.Pool(processes if last_batch <= 0 else (processes + 1))

        args = []
        for i in range(0, processes):

            starting_port = port_low + i*batch_size
            ending_port = port_low + batch_size + i*batch_size
            print("Spawning process for ports: %s - %s" % (starting_port, ending_port))
            if i == processes - 1:
                ending_port = ending_port + 1

            args.append((i, starting_port, ending_port, interface, protocol_type, data))

        r = pool.map_async(spawn_server_wrapper, args)

        if last_batch > 0:
            starting_port = port_low + processes*batch_size + 1
            ending_port = port_high + 1
            print("Spawning process for ports: %s - %s" % (starting_port, ending_port))
            r2 = pool.map_async(spawn_server_wrapper, [(processes, starting_port, ending_port, interface, protocol_type, data)])
            try:
                r2.wait()
            except KeyboardInterrupt:
                r.wait()

        r.wait()


def spawn_server_wrapper(args):
    # Wait N * 500 milliseconds to prevent all sub processes to start at once (e.g. batch 7 would wait 3.5 seconds before starting)
    # If processes start at once, this error might occur: https://twistedmatrix.com/trac/ticket/4759
    sleep((500.0 * args[0]) / 1000)
    spawn_server(*args[1:])


def spawn_server(port_low, port_high, interface, protocol_type, data):
    # p = psutil.Process(os.getpid())
    try:
        os.nice(-1)
    except Exception as e:
        print("Unable to lower niceness(priority), RUN AS SUDO, running with normal priority")

    for i in range(port_low, port_high):
        try:
            print("Spawning")
            show_commands, prompt_change_commands, usr, passwd, cmd_delay, default_prompt = parse_commands(data)

            users = {usr: passwd}

            local_commands = []

            for cmd in show_commands:
                command = getShowCommand(cmd, data, show_commands[cmd], cmd_delay)
                local_commands.append(command)

            for cmd in prompt_change_commands:
                if ("password" in prompt_change_commands[cmd]):
                    command = getPasswordPromptCommand(cmd, prompt_change_commands[cmd], cmd_delay)
                else:
                    command = getPromptChangingCommand(cmd, prompt_change_commands[cmd], cmd_delay)
                local_commands.append(command)

            factory = None
            if (protocol_type == "ssh"):
                factory = MockSSH.getSSHFactory(local_commands, default_prompt, ".", **users)
            elif (protocol_type == "telnet"):
                factory = MockSSHExtensions.getTelnetFactory(local_commands, default_prompt, **users)

            reactor.listenTCP(i, factory, interface=interface)

        except Exception as e:
            print >> sys.stderr, traceback.format_exc()
            print("Unable to open port at %s, due to: %s" % (i, e))

    reactor.run()


def parse_commands(data):
    show_commands = defaultdict(list)
    prompt_change_commands = {}

    default_prompt = data["setting_default_prompt"]
    cmd_delay = data["setting_cmd_delay"]

    usr = data["setting_default_user"]
    passwd = data["setting_default_passwd"]

    print("Using username: %s and password: %s" % (usr, passwd))

    for cmd in data:
        if isinstance(data[cmd], dict):
            prompt_change_commands[cmd] = data[cmd]
            # print "Adding prompt changing command: %s" % cmd
        else:
            cmd_split = cmd.split(" ", 1)
            if (len(cmd_split) == 1):
                show_commands[cmd_split[0]]
            else:
                show_commands[cmd_split[0]].append(cmd_split[1])
            # print("Adding show command: %s, with arguments: %s" % (cmd, show_commands[cmd]))

    return (show_commands, prompt_change_commands, usr, passwd, cmd_delay, default_prompt)


def getPasswordPromptCommand(cmd, values, cmd_delay):
    return MockSSHExtensions.SimplePromptingCommand(values["name"], values["password"], values["prompt"], values["newprompt"], values["error_message"], cmd_delay)


def getPromptChangingCommand(cmd, values, cmd_delay):
    return MockSSHExtensions.PromptChangingCommand(cmd, values["newprompt"], cmd_delay)


def getShowCommand(cmd, data, arguments, cmd_delay):
    return MockSSHExtensions.ShowCommand(cmd, data, cmd_delay, *arguments)


if __name__ == "__main__":
    args = get_args()
    try:
        main(args)
    except KeyboardInterrupt:
        print("User interrupted")
        global pool
        pool.close()
        pool.terminate()
        pool.join()
        sys.exit(1)
