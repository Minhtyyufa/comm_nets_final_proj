# Written by S. Mevawala, modified by D. Gitzel

import logging
import socket

import channelsimulator
import utils
import sys
import hashlib
import struct
import binascii
import Queue
import threading

# size of data chunks to send per packet
CHUNK_SIZE = 988
# number of threads, just increase to increase speed but queueing becomes more of an issue
NUM_SENDERS = 256


class Sender(object):
    class ThreadObject(threading.Thread):
        def __init__(self, sender, data):
            threading.Thread.__init__(self)
            self.sender = sender
            self.data= data
        def run(self):
            self.sender.thread_action(self.data)

    def __init__(self, inbound_port=50006, outbound_port=50005, timeout=1, debug_level=logging.INFO):
        self.logger = utils.Logger(self.__class__.__name__, debug_level)

        self.inbound_port = inbound_port
        self.outbound_port = outbound_port
        self.simulator = channelsimulator.ChannelSimulator(inbound_port=inbound_port, outbound_port=outbound_port,
                                                           debug_level=debug_level)
        self.simulator.sndr_setup(timeout)
        self.simulator.rcvr_setup(timeout)

        # multithreading reference: https://www.tutorialspoint.com/python/python_multithreading.htm
        self.queue_lock = threading.Lock()
        self.index_queue = Queue.Queue()
        self.threads = []
        self.finished = False
        self.received_acks = {}

    def checksum(self, data): 
        return hashlib.md5(data).hexdigest().encode('ascii') # 32 bytes

    # to decode our packet structure
    def decode(self, data):
        return int(binascii.hexlify(data[-36:-32]),16), data[-32:]
    
    # send a packet
    # ack can be identified by starting index
    def send_data(self, data_chunk, ack):
        packet_sent = False 
        # create packet
        data_chunk.extend(struct.pack('>i', ack))
        data_chunk.extend(self.checksum(data_chunk))

        while not packet_sent:
            try: 
                self.simulator.u_send(data_chunk)
                ack_back, checksum = self.decode(self.simulator.u_receive())
                if self.checksum(struct.pack('>i',ack_back)) == checksum:
                    self.received_acks.update({ack_back: True})
                
                if (self.received_acks.has_key(ack)):
                    packet_sent = True
            except:
                #socket timeouts, corrupted ack_backs, and also there is an error with multithreaded queueing in channelsimulator but cant handle so catch exception here
                pass

    # determine data portion to send 
    def thread_action(self, data):
        while not self.finished:
            index = 0
            # get data index from thread safe queue
            self.queue_lock.acquire()
            if not self.index_queue.empty():
                index = self.index_queue.get()
            self.queue_lock.release()
            self.send_data(data[index*CHUNK_SIZE: (index+1)*CHUNK_SIZE if len(data) > (index+1)*CHUNK_SIZE else None], index)        
                    

    def send(self, data):
        # [data_chunk ack checksum] packet organization
        self.logger.info("Sending on port: {} and waiting for ACK on port: {}".format(self.outbound_port, self.inbound_port))
        
        # indices to split data into chunks so the whole packet is 1024, (gets chunked to 1024 in channel simulator)
        split_indices = range(len(data)/CHUNK_SIZE + 1)

        # put indices in a queue that threads pull from
        for index in split_indices:
            self.index_queue.put(index)

        # create threads and send data
        for i in range(NUM_SENDERS):
            thread = Sender.ThreadObject(self, data)
            thread.start()
            self.threads.append(thread)
        
        # wait until no packets left to send
        while not self.index_queue.empty():
            pass
        
        # initiate ending
        self.finished = True
        for t in self.threads:
            t.join()

        packet_sent = False
        while not packet_sent:
            try: 
                # the terminating packet is just a packet with no data, kind of abusing the channel simulator because then we dont have to worry about data corruption
                self.simulator.u_send(bytearray(34))
                self.simulator.u_send(bytearray(34))
                self.simulator.u_send(bytearray(34))
                if (34 == len(self.simulator.u_receive())):
                    packet_sent = True
            except socket.timeout:
                pass
        self.logger.info("Finished")

class BogoSender(Sender):

    def __init__(self):
        super(BogoSender, self).__init__()

if __name__ == "__main__":
    # test out BogoSender
    DATA = bytearray(sys.stdin.read())
    sndr = BogoSender()
    sndr.send(DATA)
