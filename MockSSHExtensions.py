import os
import shlex
import MockSSH
import sys, traceback
import time
from threading import Thread

from twisted.conch import avatar, interfaces as conchinterfaces, recvline
from twisted.conch import manhole
from twisted.conch.insults import insults
from twisted.internet.protocol import ClientFactory, ServerFactory
from twisted.conch.telnet import TelnetTransport, TelnetProtocol, AuthenticatingTelnetProtocol, ITelnetProtocol, TelnetBootstrapProtocol, StatefulTelnetProtocol
from twisted.conch.openssh_compat import primes
from twisted.conch.ssh import (connection, factory, keys, session, transport,
                               userauth)
from twisted.cred import checkers, portal
from twisted.internet import reactor
from zope.interface import implements
from twisted.cred import credentials

class ShowCommand(MockSSH.SSHCommand):

    def __init__(self, name, data, cmd_delay, *args):
        self.name = name
        self.data = data
        self.cmd_delay = cmd_delay
        self.required_arguments = [name] + list(args)
        print("DEBUG ShowCommand __init__ %s " % (self.required_arguments))
        self.protocol = None  # set in __call__

    def __call__(self, protocol, *args):
        if self.cmd_delay is not 0:
            print "Sleeping for %f seconds" % (self.cmd_delay / 1000.0)
            time.sleep(self.cmd_delay / 1000.0)

        MockSSH.SSHCommand.__init__(self, protocol, self.name, *args)
        return self

    def start(self):
        reqArgsEscaped = map(lambda x: x.replace('"', ''), self.required_arguments[1:])
        noArgs = (len(self.args[1:]) == 0) and (len(reqArgsEscaped) == 0)
        if (noArgs or " ".join(self.args[1:]) in set(reqArgsEscaped)):
            for k in self.data.keys():
                if (k == " ".join(self.args) or k.replace('"', '') == " ".join(self.args)):
                    self.writeln(self.data[k])
                    break
        elif isChangingCommand(self):
            command = " ".join(self.args[:])
            self.writeln(self.data[command]["actual"])
            self.data[command]["actual"], self.data[command)]["new"] = self.data[command]["new"], self.data[command)]["actual"]        
        else:
            # Try to get arg from data if cannot return '% Invalid input'
            self.writeln(self.data.get(" ".join(self.args), "% Invalid input"))

        self.exit()

class CommandChangingCommand(MockSSH.SSHCommand):

    def __init__(self, name, value, cmd_delay):
        self.name = name
        self.value = value
        self.cmd_delay = cmd_delay
        self.protocol = None  # set in __call__
        print("DEBUG CommandChangingCommand __init__ %s" % (self.name))

    def __call__(self, protocol, *args):
        if self.cmd_delay is not 0:
            print "Sleeping for %f seconds" % (self.cmd_delay / 1000.0)
            time.sleep(self.cmd_delay / 1000.0)

        print("DEBUG CommandChangingCommand __call__ %s %s" % (self.name, self.value))
        MockSSH.SSHCommand.__init__(self, protocol, self.name, *args)
        return self

    def start(self):
        all_members = self.__dict__.keys()
        print("DEBUG CommandChangingCommand before %s" % (all_members))
        self.writeln(self.value["actual"])
        temp = self
        self.value["actual"], self.value["new"] = self.value["new"], self.value["actual"]
        all_members = self.__dict__.keys()
        print("DEBUG CommandChangingCommand after %s" % (all_members))
        self.exit()


class PromptChangingCommand(MockSSH.SSHCommand):

    def __init__(self, name, newprompt, cmd_delay):
        self.name = name
        self.newprompt = newprompt
        self.cmd_delay = cmd_delay
        self.protocol = None  # protocol is set by __call__

    def __call__(self, protocol, *args):
        if self.cmd_delay is not 0:
            print "Sleeping for %f seconds" % (self.cmd_delay / 1000.0)
            time.sleep(self.cmd_delay / 1000.0)

        MockSSH.SSHCommand.__init__(self, protocol, self.name, *args)
        return self

    def start(self):
        self.protocol.prompt = self.newprompt
        self.exit()

class SimplePromptingCommand(MockSSH.SSHCommand):

    def __init__(self,
                 name,
                 password,
                 prompt,
                 newprompt,
                 error_msg,
                 cmd_delay):
        self.name = name
        self.valid_password = password
        self.prompt = prompt
        self.newprompt = newprompt
        self.error_msg = error_msg
        self.cmd_delay = cmd_delay

        self.protocol = None  # protocol is set by __call__

    def __call__(self, protocol, *args):
        MockSSH.SSHCommand.__init__(self, protocol, self.name, *args)
        return self

    def start(self):
        if self.cmd_delay is not 0:
            print "Sleeping for %f seconds" % (self.cmd_delay / 1000.0)
            time.sleep(self.cmd_delay / 1000.0)

        self.write(self.prompt)
        self.protocol.password_input = True

    def lineReceived(self, line):
        self.validate_password(line.strip())

    def validate_password(self, password):
        if password == self.valid_password:
            self.protocol.prompt = self.newprompt
        else:
            self.writeln(self.error_msg)

        self.protocol.password_input = False
        self.exit()


def isChangingCommand(object) :
    command = " ".join(object.args[:])
    return (command in set(object.data.keys())) and (object.data[command]["change_commands"] == True)

def getTelnetFactory(commands, prompt, **users):
    if not users:
        raise SSHServerError("You must provide at least one "
                             "username/password combination "
                             "to run this Telnet server.")
    cmds = {}
    for command in commands:
        cmds[command.name] = command
    commands = cmds

    for exit_cmd in ['_exit', 'exit']:
        if exit_cmd not in commands:
            commands[exit_cmd] = MockSSH.command_exit

    telnetRealm = TelnetRealm(prompt, commands)
 
    telnetPortal = portal.Portal(telnetRealm, (checkers.InMemoryUsernamePasswordDatabaseDontUse(**users),))
    telnetPortal.registerChecker(checkers.InMemoryUsernamePasswordDatabaseDontUse(**users))
    
    telnetFactory = ServerFactory()
    telnetFactory.protocol = makeTelnetProtocol(telnetPortal, telnetRealm, users)

    return telnetFactory
    
class TelnetRealm:
 
    def __init__(self, prompt, commands):
        self.prompt = prompt
        self.commands = commands
 
    def requestAvatar(self, avatarId, *interfaces):
        if ITelnetProtocol in interfaces:
            try:
                args = (avatarId, self.prompt, self.commands,)
                server = TelnetBootstrapProtocol(insults.ServerProtocol, TelnetProtocol, *args)
                return ITelnetProtocol, server, lambda: None
            except Exception as e:
                print >> sys.stderr, traceback.format_exc()
                print "Unable to open session for %s, due to: %s" % (avatarId, e)
        raise NotImplementedError()

class makeTelnetProtocol:
    def __init__(self, portal, telnetRealm, users):
        self.telnetRealm = telnetRealm
        self.users = users
        self.portal = portal
 
    def __call__(self):
        auth = CustomAuthenticatingTelnetProtocol
        #auth = StatefulTelnetProtocol
        args = (self.portal,)
        return TelnetTransport(auth, *args)


# This is a copy paste of MockSSH.SSHProtocol changed to work on top of Manhole
class TelnetProtocol(manhole.Manhole):

    def __init__(self, user, prompt, commands):
        self.user = user
        self.prompt = prompt
        self.commands = commands
        self.password_input = False
        self.cmdstack = []

    def connectionMade(self):
        manhole.Manhole.connectionMade(self)
        self.cmdstack = [MockSSH.SSHShell(self, self.prompt)]

    def lineReceived(self, line):
        if len(self.cmdstack):
            self.cmdstack[-1].lineReceived(line)
        else:
            manhole.Manhole.lineReceived(self, line)

    def connectionLost(self, reason):
        manhole.Manhole.connectionLost(self, reason)
        del self.commands

    # Overriding to prevent terminal.reset() and setInsertMode()
    def initializeScreen(self):
        pass

    def getCommand(self, name):
        if name in self.commands:
            return self.commands[name]

    def keystrokeReceived(self, keyID, modifier):
        manhole.Manhole.keystrokeReceived(self, keyID, modifier)

    # Easier way to implement password input?
    def characterReceived(self, ch, moreCharactersComing):
        # manhole.Manhole.characterReceived(self, ch, moreCharactersComing)
        self.lineBuffer[self.lineBufferIndex:self.lineBufferIndex + 1] = [ch]
        self.lineBufferIndex += 1

        if not self.password_input:
            self.terminal.write(ch)

    def writeln(self, data):
        self.terminal.write(data)
        self.terminal.nextLine()

    def call_command(self, cmd, *args):
        obj = cmd(self, cmd.name, *args)
        self.cmdstack.append(obj)
        obj.start()

    def handle_RETURN(self):
        if len(self.cmdstack) == 1:
            if self.lineBuffer:
                self.historyLines.append(''.join(self.lineBuffer))
            self.historyPosition = len(self.historyLines)
        return manhole.Manhole.handle_RETURN(self)

# Extends the class from twisted to remove sending do and don't ECHO options during authentication
class CustomAuthenticatingTelnetProtocol(AuthenticatingTelnetProtocol):

    state = "User"
    protocol = None

    def __init__(self, portal):
        self.portal = portal

    def telnet_User(self, line):
        self.username = line
        self.transport.write(b"Password: ")
        return 'Password'

    def telnet_Password(self, line):
        username, password = self.username, line
        del self.username
        creds = credentials.UsernamePassword(username, password)
        d = self.portal.login(creds, None, ITelnetProtocol)
        d.addCallback(self._cbLogin)
        d.addErrback(self._ebLogin)
        return 'Discard'
