# Written by S. Mevawala, modified by D. Gitzel

import logging

import channelsimulator
import utils
import sys
import socket
import hashlib
import binascii
import struct


class Receiver(object):

    def __init__(self, inbound_port=50005, outbound_port=50006, timeout=10, debug_level=logging.INFO):
        self.logger = utils.Logger(self.__class__.__name__, debug_level)

        self.inbound_port = inbound_port
        self.outbound_port = outbound_port
        self.simulator = channelsimulator.ChannelSimulator(inbound_port=inbound_port, outbound_port=outbound_port,
                                                           debug_level=debug_level)
        self.simulator.rcvr_setup(timeout)
        self.simulator.sndr_setup(timeout)

    def checksum(self, data): 
        return hashlib.md5(data).hexdigest().encode('ascii') # 32 bytes

    def decode(self, data):
        return data[:-34], int(binascii.hexlify(data[-34:-33]),16), data[-32:].decode('ascii')

    def make_receiver_packet(self, ack):
        data = bytearray(struct.pack('h', ack))
        data.extend(self.checksum(data))
        return data

    def receive(self):
        self.logger.info("Receiving on port: {} and replying with ACK on port: {}".format(
            self.inbound_port, self.outbound_port))
        
        init_sender_ack = 0
        most_recent_ack = 0
        receiver_ack = 0
        received_data = {}
        CHUNK_SIZE = 990
        finished = False
        while True:
            try:
                data = self.simulator.u_receive()  # receive data
                # kind of an abuse of the simulation but hehe 
                if len(data) == 34:
                    self.logger.info("in end cond")
                    to_print = bytearray((most_recent_ack - init_sender_ack)*CHUNK_SIZE)
                    for index, value in received_data.items():
                        to_print[(index-init_sender_ack)*CHUNK_SIZE: (index-init_sender_ack+1)*CHUNK_SIZE] = value
                    
                    self.simulator.u_send(bytearray(34))
                    sys.stdout.write(to_print.decode('ascii'))
                    self.logger.info("Finished")
                    sys.exit()
                    return
                try:
                    data_chunk, ack, checksum = self.decode(data)
                    if self.checksum(data[:-32]) == checksum:  
                        self.logger.info("in receiver ack = " + str(ack))
                        if ack < init_sender_ack:
                            init_sender_ack = ack
                        if ack > most_recent_ack:
                            most_recent_ack = ack
                        received_data.update({ack: data_chunk})
                        self.simulator.u_send(self.make_receiver_packet(ack))
                        self.logger.info("Got data from socket: {}".format(data_chunk.decode('ascii')))  # note that ASCII will only decode bytes in the range 0-127
                
                except:
                    pass
                #sys.exit()
                #self.simulator.u_send(BogoReceiver.ACK_DATA)  # send ACK
            except socket.timeout:
                sys.exit()


class BogoReceiver(Receiver):
    ACK_DATA = bytes(123)

    def __init__(self):
        super(BogoReceiver, self).__init__()

if __name__ == "__main__":
    # test out BogoReceiver
    rcvr = BogoReceiver()
    rcvr.receive()
