# python version: python3
import socket
from threading import Thread, Lock
import sys
import time
import os
import random
import math
import uuid

# Global variable define here
PORT_BASE = 50000                        # base port
IP_address = "127.0.0.1"                 # localhost
ping_timeout = 5.0                       # time out for ping ops
timeout_interval = 1                     # time out for send packet
ping_sleep = 6.0                         # sleep time between every ping finished
BUFF_SIZE = 1024                         # buffer size
TTL = 10                                 # Time to live
                                         # message form
msg_form = {0:"ping request", 1:"ping response", 2:"Request NextSucc", 3:"Response NextSucc", \
            4:"Depature request", 5:"file location request", 6:"file location response", 7: "file packet send", \
            8:"file packet ACK", 9:"file Fin/PSH", 10:"file Fin/PSH ACK", 11:"Departure response"}
'''
number                       function                                              msg format
0                   ping request                                        "ping request" + '\r\n' + Peer ID
1                   ping response                                       "ping response" + '\r\n' + Peer ID
2                   request next successor                              "Request NextSucc" + '\r\n' + successor seq(1 or 2) + '\r\n' + crash successor ID
3                   response next successor                             "Response NextSucc" + '\r\n' + next succssor ID
4                   departure request                                   "Departure request" + '\r\n' + own Peer ID
5                   file exist location request                         "file location request" + '\r\n' + request Peer ID + '\r\n' + filename + '\r\n' + TTL + '\r\n' + uuid
6                   file exist location response                        "file location response" + '\r\n' + own Peer ID + '\r\n' + filename
7                   contain file packet                                 "file packet send" + '\r\n' + packet seq + '\r\n' + data
8                   file packet ACK                                     "file packet ACK" + '\r\n' + ACK
9                   all file packet sent, push buffer                   "file Fin/PSH"
10                  file finshed msg ACK                                "file Fin/PSH ACK"
11                  departure response                                  "Departure response"
'''

event = ['snd', 'rcv', 'drop', 'RTX', 'RTX/drop']   # Snd = send, rcv= receive, drop= packet dropped, and RTX= retransmission.

class Peer:

    # initial method, open threads in it
    def __init__(self, id, firSucc, secSucc, MSS, dropProb):
        # private variable define here
        self.__id = int(id)                                          # Peer id
        self.__firSucc = int(firSucc)                                # first Successor
        self.__secSucc = int(secSucc)                                # second Successor
        self.__MSS = int(MSS)                                        # Maximum Segment Size
        self.__dropProb = float(dropProb)                            # drop probability
        self.__firAlive = 0                                          # when XXXAlive > 2,
        self.__secAlive = 0                                          # means that fir or sec successor has crashed
        self.__predLs = list()                                       # predecessor which only have two elements
        self.__cache = ''.encode()                                   # used for store file temporarily
        self.__recv_seq = 1                                          # initial file sequence number
        self.__lock = Lock()                                         # threading lock
        self.__accLock = Lock()
        self.__wfLock = Lock()
        self.__SdgFLs = list()                                       # sending file List, stored uuid here

        # threads start here for supporting class Peer
        Thread(target=self.scr_input, daemon=False).start()            # thread 1 for screen input
        Thread(target=self.UDP_listener, daemon=True).start()          # thread 2 for listening to UDP message
        Thread(target=self.TCP_listener, daemon=True).start()          # thread 3 for listening to TCP message
        Thread(target=self.ping, args=(1,), daemon=True).start()       # thread 4 for ping firSucc
        Thread(target=self.ping, args=(2,) , daemon=True).start()      # thread 5 for ping secSucc

    # accept screen input cmd
    def scr_input(self):
        while True:
            cmd = input("")
            #print("cmd is:"+cmd)
            if cmd == "quit":                          # quit cmd
                t = Thread(target=self.departure, args=())
                t.start()
                t.join()
                sys.exit(0)                                      # exit directly

            elif cmd[0:7] == "request":                # request X cmd (TCP protocol)
                cmd_part = cmd.split(' ')
                try:
                    if self.Is_filename_vaild(cmd_part[1]):      # request file number valid
                        SendAddrLs = [(IP_address, PORT_BASE + self.__firSucc)]

                        for SendAddr in SendAddrLs:
                            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            s.connect(SendAddr)
                            msg = msg_form[5] + '\r\n' + str(self.__id) + '\r\n' + cmd_part[1] + '\r\n' + str(TTL)

                            s.send(msg.encode())                 # send msg5 here
                            print(f"File request message for {cmd_part[1]} has been sent to my successor.")
                            s.close()
                    else:
                        raise TypeError
                except:
                    print("Incorrect parameter, plz retry.")
            else:
                print("Not found this command.")

    # ping two successors (UDP protocol)
    def ping(self, fir_or_sec):                                       # peer's ping module
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(ping_timeout)

        while True:
            port = PORT_BASE
            if fir_or_sec == 1:                         # first successor
                port += self.__firSucc
            else:                                       # second successor
                port += self.__secSucc

            sendAddr = (IP_address, port)                       # send Ping request msg
            msg = msg_form[0] + "\r\n"+ str(self.__id)          #
            s.sendto(msg.encode(), sendAddr)                    #

            try:                                                    # successor still alive
                data, addr = s.recvfrom(BUFF_SIZE)

                msg_list = data.decode().split('\r\n')              # deal with data here
                if fir_or_sec == 1:
                    self.__firAlive = 0
                else:
                    self.__secAlive = 0
                print(f"A ping response message was received from Peer {msg_list[1]}.");

            except socket.timeout:                                  # timeout
                if fir_or_sec == 1:
                    self.__firAlive += 1
                    if self.__firAlive > 3:
                        print(f"Peer {port - PORT_BASE} is no longer alive.")
                        self.get_succ(1)
                        self.__firAlive = 0
                else:
                    self.__secAlive += 1
                    if self.__secAlive > 3:
                        print(f"Peer {port - PORT_BASE} is no longer alive.")
                        self.get_succ(2)
                        self.__secAlive = 0
            except ConnectionResetError:
                continue

            time.sleep(ping_sleep)                                  # thread Sleep

        s.close()

    # UDP listener (UDP protocol)
    def UDP_listener(self):                                           # listen Ping and transfered file
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)               # UDP server initial
        port = PORT_BASE + self.__id
        s.bind((IP_address, port))

        while True:
            try:
                data, addr = s.recvfrom(BUFF_SIZE)
                Thread(target=self.UDP_link, args=(data, addr, s)).start()
            except:
                pass

        s.close()

    # Thread function for UDP_listener
    def UDP_link(self, data, addr, s):
        try:
            un_data = data.decode()
            msg_list = un_data.split('\r\n')
        except UnicodeDecodeError:                                                 # data contain data
            pos = self.pos_splite(data) + 1
            msg_list = (data[0: pos].decode()).split('\r\n')            

        try:
            msg_sort = list(msg_form.keys())[list(msg_form.values()).index(msg_list[0])]

            if msg_sort == 0:                               # msg is Ping request, response
                print(f"A ping request message was received from Peer {msg_list[1]}.")

                # store predecessor into List
                if len(self.__predLs) < 2:
                    self.__predLs.append(int(msg_list[1]))
                else:
                    if int(msg_list[1]) not in self.__predLs:
                        self.__predLs.append(int(msg_list[1]))
                        self.__predLs.pop(0)

                msg = msg_form[1] + '\r\n' + str(self.__id)
                s.sendto(msg.encode(), addr)

            elif msg_sort == 7:                             # file packet get, recv
                pos = self.pos_splite(data) + 1
                msg_list = (data[0: pos].decode()).split('\r\n')
                
                if self.__recv_seq == 1:
                    print("We now start receiving the file ………")
                    f = open("requesting_log.txt",'w')
                    f.close()

                if self.__recv_seq == int(msg_list[1]):                      # received correct packet
                    with self.__lock:
                        self.__recv_seq += len(data[pos::])
                        self.__cache += data[pos::]
                    with self.__wfLock:
                        f = open("requesting_log.txt", 'a')
                        f.write(event[1].ljust(20) + str(round(time.time(), 2)).ljust(20) + str(msg_list[1]).ljust(11) + str(len(data[pos::])).ljust(11) + str(0).ljust(11) + '\n')
                        f.write(event[0].ljust(20) + str(round(time.time(), 2)).ljust(20) + str(0).ljust(11) +str(len(data[pos::])).ljust(11) + str(self.__recv_seq).ljust(11) + '\n')
                    msg = msg_form[8] + '\r\n' + str(self.__recv_seq)
                    s.sendto(msg.encode(), addr)
                else:                                                        # Redundant file packet, just drop it then let sender timeout
                    with self.__wfLock:
                        f = open("requesting_log.txt", 'a')
                        f.write(event[1].ljust(20) + str(round(time.time(), 2)).ljust(20) + str(msg_list[1]).ljust(11) + str(len(data[pos::])).ljust(11) + str(0).ljust(11) + '\n')

            elif msg_sort == 9:                             # receive all packet && push immediately
                if len(self.__cache) > 0:
                    fp = open("received_file.pdf", 'wb')
                    fp.write(self.__cache)
                    fp.close()

                    self.__cache = ''.encode()              # reset val
                    self.__recv_seq = 1

                msg = msg_form[10]
                print("The file is received.")
                s.sendto(msg.encode(), addr)                # reply Fin ACK

        except IndexError:
            pass

    # TCP listener (TCP protocol)
    def TCP_listener(self):                                           # listen file request message and response message
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)                   # TCP server initial
        s.bind((IP_address, PORT_BASE + self.__id))
        s.listen(5)

        while True:
            sock, addr = s.accept()
            Thread(target=self.TCP_link, args=(sock,)).start()

    # Thread function for TCP_listener
    def TCP_link(self, sock):                                         # thread for TCP listener 
        data = sock.recv(BUFF_SIZE)
        data = data.decode()

        data_list = data.split('\r\n')

        data_sort = list(msg_form.keys())[list(msg_form.values()).index(data_list[0])]
        msgs = msg_form[3] + "\r\n"

        if data_sort == 2:                                               # response for searching successor
            if int(data_list[2]) != self.__firSucc:
                msgs += str(self.__firSucc)
            else:
                msgs += str(self.__secSucc)
            sock.send(msgs.encode())

        elif data_sort == 4:                                             # get departure request
            if self.__firSucc == int(data_list[1]):
                print(f"Peer {data_list[1]} will depart from the network.")
                self.get_succ(1)
            elif self.__secSucc == int(data_list[1]):
                print(f"Peer {data_list[1]} will depart from the network.")
                self.get_succ(2)
            else:
                pass
            msg = msg_form[11]
            sock.send(msg.encode())

        elif data_sort == 5:                                             # get file location request
            local_file = os.listdir()

            same_file = [x for x in local_file if os.path.splitext(x)[0] == data_list[2]]        # determine if required file exist

            if len(same_file) > 0 and self.hash_jug(int(data_list[2])):                                                     # request file exist in local (TCP protocol)
                print(f"File {data_list[2]} is here.")
                sr = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                SendAddr = (IP_address, PORT_BASE + int(data_list[1]))

                msg = msg_form[6] + '\r\n' + str(self.__id) + '\r\n' + data_list[2]
                sr.connect(SendAddr)
                sr.send(msg.encode())
                print(f"A response message, destined for peer {data_list[1]}, has been sent.")
                sr.close()

                time.sleep(1)   
                self.file_transfer(int(data_list[1]), same_file[0])         # starting transfer file here 
                
            else:                                                                      # request file doesn't exist (TCP protocol) then forwarding to successors
                print(f"File {data_list[2]} is not stored here.")

                if int(data_list[3]) > 0:                                 # TTL still large than zero, means that can be forwarding
                    if self.__firSucc == int(data_list[1]):                                                     # last node of circle, don' t need to forwarding to its successor
                        AddrSuccLs = []
                    else:                                                                                       # else
                        AddrSuccLs = [(IP_address, PORT_BASE + self.__firSucc)]

                    for addr in AddrSuccLs:
                        sr = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sr.connect(addr)
                        msg = msg_form[5] + '\r\n' + data_list[1] + '\r\n' + data_list[2] + '\r\n' + str(int(data_list[3]) - 1)

                        sr.send(msg.encode())
                        sr.close()

                    if self.__firSucc != int(data_list[1]):
                        print("File request message has been forwarded to my successor.")

        elif data_sort == 6:                                              # get file location response
            print(f"Received a response message from peer {data_list[1]}, which has the file {data_list[2]}.")
        sock.close()

    # a peer departure (TCP protocol)
    def departure(self):                                              # peer departure from this p2p network, should notice other peers

        for item in self.__predLs:              # send departure information
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            SendAddr = (IP_address, PORT_BASE + item)
            s.connect(SendAddr)

            msg = msg_form[4] + '\r\n' + str(self.__id)

            s.send(msg.encode())
            data = s.recv(1024).decode()
            s.close()

    # find successor when one of current successor crash suddenly (TCP protocol)
    # fir_or_sec = 1 means that detect second Successor crash, else first Successor
    def get_succ(self, fir_or_sec):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        if fir_or_sec == 1:
            SendAddr = (IP_address, PORT_BASE + self.__secSucc)
        else:
            SendAddr = (IP_address, PORT_BASE + self.__firSucc)

        s.connect(SendAddr)

        if fir_or_sec == 1:
            msg = msg_form[2] + '\r\n' + str(2) + '\r\n' + str(self.__firSucc)
        else:
            msg = msg_form[2] + '\r\n' + str(1) + '\r\n' + str(self.__secSucc)
        s.send(msg.encode())                       # send query msg to request next successor

        data = s.recv(BUFF_SIZE)
        data = data.decode().split('\r\n')

        if fir_or_sec == 1:
            self.__firSucc = self.__secSucc
            print(f"My first successor is now peer {self.__secSucc}.")
        else:
            print(f"My first successor is now peer {self.__firSucc}.")

        self.__secSucc = int(data[1])
        print(f"My second successor is now peer {data[1]}.")

        s.close()
        # receive data from TCP server and do something here

    # file transfer between file requester and file owner (reliable UDP protocol)
    def file_transfer(self, dest_port, filename):
        print("We now start sending the file ………")
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)               # UDP server initial
        s.settimeout(timeout_interval)
        SendAddr = (IP_address, PORT_BASE + dest_port)                     # udp send address

        f = open(filename, 'rb')
        f_log = open('responding_log.txt', 'w')                     # may change open mode to a+

        while len(f.read(self.__MSS)) != 0:
            pass
        f_maxseq = f.tell() + 1                                     # record max seqence number
        f.seek(0, 0)                                                # move file pointer to head
        seq = 1                                                     # sequence number
        RTX_flag = 0                                                # flag for determine if RTX(timeout or drop) 0 is work normally, else 1
        pkt_seg = f.read(self.__MSS)                                # first segment of file which contain MSS bytes data

        while True:
            try:
                if not self.Is_response(self.__dropProb):                         # drop (RTX/drop drop)
                    if RTX_flag == 0:                 # drop
                        f_log.write(event[2].ljust(20) + str(round(time.time(), 2)).ljust(20) + str(seq).ljust(11) + str(len(pkt_seg)).ljust(11) + str(0).ljust(11) + '\n')
                        raise socket.timeout
                    else:                             # RTX/drop
                        f_log.write(event[4].ljust(20) + str(round(time.time(), 2)).ljust(20) + str(seq).ljust(11) + str(len(pkt_seg)).ljust(11) + str(0).ljust(11) + '\n')
                        raise socket.timeout
                else:                                                             # not drop (snd RTX)
                    if RTX_flag ==  0:                # snd
                        f_log.write(event[0].ljust(20) + str(round(time.time(), 2)).ljust(20) + str(seq).ljust(11) + str(len(pkt_seg)).ljust(11) + str(0).ljust(11) + '\n')
                    else:                             # RTX
                        f_log.write(event[3].ljust(20) + str(round(time.time(), 2)).ljust(20) + str(seq).ljust(11) + str(len(pkt_seg)).ljust(11) + str(0).ljust(11) + '\n')

                    msg_head = msg_form[7] + '\r\n' + str(seq) + '\r\n'
                    s.sendto((msg_head).encode() + pkt_seg, SendAddr)                  # send UDP packet

                # received data here
                data, addr = s.recvfrom(BUFF_SIZE)
                recv_msgLs = data.decode().split('\r\n')
                
                f_log.write(event[1].ljust(20) + str(round(time.time(), 2)).ljust(20) + str(0).ljust(11) + str(len(pkt_seg)).ljust(11) + str(int(recv_msgLs[1])).ljust(11) + '\n')
                if seq + len(pkt_seg) == int(recv_msgLs[1]):                              # ACK
                    seq = int(recv_msgLs[1])
                    pkt_seg = f.read(self.__MSS)
                    RTX_flag = 0
                else:                                                                # NAK
                    pass
            except socket.timeout:
                RTX_flag += 1
                continue
            
            if seq == f_maxseq:
                while True:
                    try:
                        msg = msg_form[9]
                        s.sendto(msg.encode(), SendAddr)
                    except socket.timeout:
                        continue

                    # receive Fin ack here
                    Fin, addr = s.recvfrom(BUFF_SIZE)
                    FinLs = Fin.decode().split('\r\n')

                    if list(msg_form.keys())[list(msg_form.values()).index(FinLs[0])] == 10:
                        break
                break # send psh msg

        print("The file is sent.")
        f_log.close()                    # opened file && socket close
        f.close()
        s.close()

    # Support function: determine if filename is valid
    def Is_filename_vaild(self, filename):
        if len(filename) != 4 or not filename.isdigit():
            return False
        return  True

    # Support function for file transfering
    # retval True means send packet, else False
    def Is_response(self, dropProb):
        if random.random() >= dropProb:
            return True
        return False

    # Support function for find position to splite
    # return index pos
    def pos_splite(self, byte_str):
        flag = 0
        for i in range(0, len(byte_str)):
            if byte_str[i] == 10 or byte_str[i] == 13:
                flag += 1
            if flag == 4:
                return i
        return -1

    # Support function for determining the required file whether in this peer
    # parameter filename is a integer
    def hash_jug(self, filename):
        hash_val = filename % 256
        with self.__accLock:
            while True:
                if len(self.__predLs) == 2:
                    break

            if max(self.__predLs) > self.__id and min(self.__predLs) < self.__id:
                last = min(self.__predLs)
            else:
                last = max(self.__predLs)

            if last < self.__id:
                if hash_val > last and hash_val <= self.__id:
                    return True
            else:
                if (hash_val > last and self.__id + 255 >= hash_val) or (hash_val <= self.__id):
                    return True
        return False

# function entry here
if __name__ == "__main__":
    try:                                                     # Value determining
        if len(sys.argv) != 6:
            raise TypeError
        if int(sys.argv[1]) < 0 or int(sys.argv[2]) < 0 or int(sys.argv[3]) < 0 \
                or int(sys.argv[1]) > 255 or int(sys.argv[2]) > 255 or int(sys.argv[3]) > 255\
                or float(sys.argv[5]) > 1 or float(sys.argv[5]) < 0:
            raise ValueError
    except ValueError:                                       # value is non-satisfied
        print("ValueError: Value is not meet the requirement...")
        sys.exit(-1)
    except TypeError:                                        # lack parameters
        print("TypeError: missing required positional argument...")
        sys.exit(-1)

    asst = Peer(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])