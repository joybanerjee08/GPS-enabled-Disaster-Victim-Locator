from __future__ import division
import time
import torch 
import torch.nn as nn
from torch.autograd import Variable
import numpy as np
import cv2 
from util import *
from darknet import Darknet
from preprocess import prep_image, inp_to_image
import urllib.request
import pandas as pd
import random 
import argparse
import zmq
import pickle as pkl
import sqlite3


def recv_array_and_str(socket, flags=0, copy=True, track=False):
    string = socket.recv_string(flags=flags)
    msg = socket.recv(flags=flags, copy=copy, track=track)
    return string, msg

conn = sqlite3.connect('objects.db')

context = zmq.Context()
footage_socket = context.socket(zmq.SUB)
footage_socket.setsockopt(zmq.LINGER, 0)
footage_socket.bind('tcp://*:5555')
try:
    footage_socket.setsockopt(zmq.SUBSCRIBE, b'')
except TypeError:
    footage_socket.setsockopt_string(zmq.SUBSCRIBE, b'')

def prep_image(img, inp_dim):
    """
    Prepare image for inputting to the neural network. 
    
    Returns a Variable 
    """

    orig_im = img
    dim = orig_im.shape[1], orig_im.shape[0]
    img = cv2.resize(orig_im, (inp_dim, inp_dim))
    img_ = img[:,:,::-1].transpose((2,0,1)).copy()
    img_ = torch.from_numpy(img_).float().div(255.0).unsqueeze(0)
    return img_, orig_im, dim

def write(x, img):
    global objectlist
    c1 = tuple(x[1:3].int())
    c2 = tuple(x[3:5].int())
    cls = int(x[-1])
    label = "{0}".format(classes[cls])
    color = random.choice(colors)
    objectlist.append(label)
    cv2.rectangle(img, c1, c2,color, 1)
    t_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_PLAIN, 1 , 1)[0]
    c2 = c1[0] + t_size[0] + 3, c1[1] + t_size[1] + 4
    cv2.rectangle(img, c1, c2,color, -1)
    cv2.putText(img, label, (c1[0], c1[1] + t_size[1] + 4), cv2.FONT_HERSHEY_PLAIN, 1, [225,255,255], 1)
    return img

def arg_parse():
    """
    Parse arguements to the detect module
    
    """
    
    
    parser = argparse.ArgumentParser(description='YOLO v3 Cam Demo')
    parser.add_argument("--confidence", dest = "confidence", help = "Object Confidence to filter predictions", default = 0.25)
    parser.add_argument("--nms_thresh", dest = "nms_thresh", help = "NMS Threshhold", default = 0.4)
    parser.add_argument("--reso", dest = 'reso', help = 
                        "Input resolution of the network. Increase to increase accuracy. Decrease to increase speed",
                        default = "160", type = str)
    return parser.parse_args()



if __name__ == '__main__':
    cfgfile = "config/yolov3.cfg"
    weightsfile = "config/yolov3.weights"
    num_classes = 80

    args = arg_parse()
    confidence = float(args.confidence)
    nms_thesh = float(args.nms_thresh)
    start = 0
    CUDA = torch.cuda.is_available()

    num_classes = 80
    bbox_attrs = 5 + num_classes
    
    model = Darknet(cfgfile)
    model.load_weights(weightsfile)
    
    model.net_info["height"] = args.reso
    inp_dim = int(model.net_info["height"])
    
    assert inp_dim % 32 == 0 
    assert inp_dim > 32

    if CUDA:
        model.cuda()
            
    model.eval()
    
    videofile = 'video.avi'
    frames = 0
    start = time.time() 

    while True:
        string,msg = recv_array_and_str(footage_socket)

        a = msg.find(b'\xff\xd8')
        b = msg.find(b'\xff\xd9')

        if a != -1 and b != -1:
            jpg = msg[a:b+2]
            msg = msg[b+2:]
            frame = cv2.imdecode(np.fromstring(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
            #frame = cv2.imdecode(img, 1)
            #frame = np.flipud(frame)
            #frame = np.fliplr(frame)
            print(string)
            if frame.any():
                
                img, orig_im, dim = prep_image(frame, inp_dim)
                
                im_dim = torch.FloatTensor(dim).repeat(1,2)                        
                
                
                if CUDA:
                    im_dim = im_dim.cuda()
                    img = img.cuda()
                
                
                output = model(Variable(img), CUDA)
                output = write_results(output, confidence, num_classes, nms = True, nms_conf = nms_thesh)

                if type(output) == int:
                    frames += 1
                    print("FPS of the video is {:5.2f}".format( frames / (time.time() - start)))
                    cv2.imshow("frame", orig_im)
                    key = cv2.waitKey(1)
                    if key & 0xFF == ord('q'):
                        break
                    continue
                

            
                output[:,1:5] = torch.clamp(output[:,1:5], 0.0, float(inp_dim))/inp_dim
                
    #            im_dim = im_dim.repeat(output.size(0), 1)
                output[:,[1,3]] *= frame.shape[1]
                output[:,[2,4]] *= frame.shape[0]

                
                classes = load_classes('config/coco.names')
                colors = pkl.load(open("pallete", "rb"))
                
                objectlist = []
                list(map(lambda x: write(x, orig_im), output))
                
                if len(objectlist) > 0:
                    for i in set(objectlist):
                        occurence = objectlist.count(i)
                        conn.execute("INSERT INTO OBJECT (lat,lon,mag,alti,total,label) VALUES ("+string+","+str(occurence)+","+str(i)+")")
                        conn.commit()
                cv2.imshow("frame", orig_im)
                key = cv2.waitKey(1)
                if key & 0xFF == ord('q'):
                    break
                frames += 1
                print("FPS of the video is {:5.2f}".format( frames / (time.time() - start)))
conn.close()
footage_socket.close()