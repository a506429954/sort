"""
    SORT: A Simple, Online and Realtime Tracker
    Copyright (C) 2016-2020 Alex Bewley alex@bewley.ai

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
'''
__future__将新的python版本的特性引入到当前版本中
python 2.x : print "Hello World"
python 3.x : print("Hello World")
如果你想用python2.x体验python3.x的写法，就可以使用 from __future__ import print_function实现
'''
from __future__ import print_function

import os
import numpy as np
import matplotlib

'''
Reference: https://matplotlib.org/faq/usage_faq.html
If your script depends on a specific backend you can use the use() function
import matplotlib
matplotlib.use('PS')

If you use the use() function, this must be done before importing matplotlib.pyplot
Calling use() after pyplot has been imported will have no effect.
Using use() will require changes in your code if users want to use a different backend.
Therefore, you should avoid explicitly calling use() unless absolutely necessary

Backend name specifications are not case-sensitive; e.g. "TkAgg" and "tkagg" are equivalent.

If you want to write graphical user interfaces, or a web application server (Matplotlib in a
web application server), or need a better understanding of what is going on, read on. To make
things a little more customizable for graphical user interfaces, matplotlib seperates the concept
of the renderer (the thing that actually does the drawing) from the canvas (the place where the drawing
goes). The canonical renderer for user interfaces is Agg which uses the Anti-Grain Geometry C++ library
to make a raster (pixel) image of the figure. All of the uuser interfaces except macosx can be used with
agg rendering, e.g. WXAgg, GTKAgg, QT4Agg, QT5Agg, TkAgg. 

TkAgg: Agg rendering to a Tk canvas (resuqire TkInter)

Tk: 
Tk is a graphical user interface for Tcl and many other dynamic languages. It can produce rich, native 
applications that run unchanged across Windows, Mac OS X, Linux and more.

TkInter:Tkinter is Python's de-facto standard GUI (Graphical User Interface) package. It is a thin 
object-oriented layer on top of Tcl/Tk. Tkinter is not the only GuiProgramming toolkit for Python. 
It is however the most commonly used one.
'''
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches

from skimage import io

import glob  # Reference: https://docs.python.org/3/library/glob.html
import time  # Reference: https://www.programiz.com/python-programming/time
import argparse  # Reference: https://docs.python.org/3/library/argparse.html

'''
FilterPy is a Python library that implements a number of Bayesian filter, most notably Kalman filters.
1. KalmanFilter
2. Extended Kalman Filter
3. Unscented Kalman Filter
4. Ensemble Kalman Filter
5. ...
'''
from filterpy.kalman import KalmanFilter  # References: https://filterpy.readthedocs.io/en/latest/

np.random.seed(0)


def linear_assignment(cost_matrix):
  try:
    # lap is a linear assignment problem solver using Jonker-Volgenant algorithm for dense (LAPJV) or sparse (LAPMOD) matrices.
    import lap
    # The Jonker-Volgenant algorithm is much faster than the famous Hungarian algorithm for the Linear Assignment Problem (LAP)
    _, x, y = lap.lapjv(cost_matrix, extend_cost=True)
    return np.array([[y[i],i] for i in x if i >= 0]) #
  except ImportError:
    # The method used is the Hungarian algorithm, also known as the Munkres or Kuhn-Munkres algorithm.
    from scipy.optimize import linear_sum_assignment
    x, y = linear_sum_assignment(cost_matrix) # row_ind, col_ind : array
    return np.array(list(zip(x, y)))

'''
The Jonker-Volgenant algorithm References:
[1] https://github.com/gatagat/lap
[2] R. Jonker and A. Volgenant, "A Shortest Augmenting Path Algorithm for Dense and Sparse Linear Assignment Problems", Computing 38, 325-340 (1987)
[3] A. Volgenant, "Linear and Semi-Assignment Problems: A Core Oriented Approach", Computer Ops Res. 23, 917-932 (1996)
[4] http://www.assignmentproblems.com/LAPJV.htm

Hungarian Method References:
[1] Harold W. Kuhn. The Hungarian Method for the assignment problem. Naval Research Logistics Quarterly, 2:83-97, 1955.
[2] Harold W. Kuhn. Variants of the Hungarian method for assignment problems. Naval Research Logistics Quarterly, 3: 253-258, 1956.
[3] Munkres, J. Algorithms for the Assignment and Transportation Problems. J. SIAM, 5(1):32-38, March, 1957.
[4] https://en.wikipedia.org/wiki/Hungarian_algorithm
[5] http://csclab.murraystate.edu/bob.pilgrim/445/munkres.html
'''

def iou_batch(bb_test, bb_gt):
  """
  From SORT: Computes IUO between two bboxes in the form [x1,y1,x2,y2]
  """
  bb_gt = np.expand_dims(bb_gt, 0)
  bb_test = np.expand_dims(bb_test, 1)
  
  xx1 = np.maximum(bb_test[..., 0], bb_gt[..., 0])
  yy1 = np.maximum(bb_test[..., 1], bb_gt[..., 1])
  xx2 = np.minimum(bb_test[..., 2], bb_gt[..., 2])
  yy2 = np.minimum(bb_test[..., 3], bb_gt[..., 3])
  w = np.maximum(0., xx2 - xx1)
  h = np.maximum(0., yy2 - yy1)
  wh = w * h
  o = wh / ((bb_test[..., 2] - bb_test[..., 0]) * (bb_test[..., 3] - bb_test[..., 1])                                      
    + (bb_gt[..., 2] - bb_gt[..., 0]) * (bb_gt[..., 3] - bb_gt[..., 1]) - wh)                                              
  return(o)  


def convert_bbox_to_z(bbox):
  """
  Takes a bounding box in the form [x1,y1,x2,y2] and returns z in the form
    [x,y,s,r] where x,y is the centre of the box and s is the scale/area and r is
    the aspect ratio
  """
  w = bbox[2] - bbox[0]
  h = bbox[3] - bbox[1]
  x = bbox[0] + w/2.
  y = bbox[1] + h/2.
  s = w * h    # scale is just area
  r = w / float(h)
  return np.array([x, y, s, r]).reshape((4, 1))


def convert_x_to_bbox(x,score=None):
  """
  Takes a bounding box in the centre form [x,y,s,r] and returns it in the form
    [x1,y1,x2,y2] where x1,y1 is the top left and x2,y2 is the bottom right
  """
  w = np.sqrt(x[2] * x[3])
  h = x[2] / w
  if(score==None):
    return np.array([x[0]-w/2.,x[1]-h/2.,x[0]+w/2.,x[1]+h/2.]).reshape((1,4))
  else:
    return np.array([x[0]-w/2.,x[1]-h/2.,x[0]+w/2.,x[1]+h/2.,score]).reshape((1,5))


class KalmanBoxTracker(object):
  """
  This class represents the internal state of individual tracked objects observed as bbox.
  """
  count = 0
  def __init__(self,bbox):
    """
    Initialises a tracker using initial bounding box.
    """
    #define constant velocity model
    self.kf = KalmanFilter(dim_x=7, dim_z=4) 
    self.kf.F = np.array([[1,0,0,0,1,0,0],[0,1,0,0,0,1,0],[0,0,1,0,0,0,1],[0,0,0,1,0,0,0],  [0,0,0,0,1,0,0],[0,0,0,0,0,1,0],[0,0,0,0,0,0,1]])
    self.kf.H = np.array([[1,0,0,0,0,0,0],[0,1,0,0,0,0,0],[0,0,1,0,0,0,0],[0,0,0,1,0,0,0]])

    self.kf.R[2:,2:] *= 10.
    self.kf.P[4:,4:] *= 1000. #give high uncertainty to the unobservable initial velocities
    self.kf.P *= 10.
    self.kf.Q[-1,-1] *= 0.01
    self.kf.Q[4:,4:] *= 0.01

    self.kf.x[:4] = convert_bbox_to_z(bbox)  # [x1,y1,x2,y2] to [x,y,s,r] (shape: (4,1))
    self.time_since_update = 0
    self.id = KalmanBoxTracker.count
    KalmanBoxTracker.count += 1
    self.history = []
    self.hits = 0 
    self.hit_streak = 0
    self.age = 0

  def update(self,bbox):
    """
    Updates the state vector with observed bbox.
    """
    self.time_since_update = 0
    self.history = []
    self.hits += 1
    self.hit_streak += 1
    self.kf.update(convert_bbox_to_z(bbox))

  def predict(self):
    """
    Advances the state vector and returns the predicted bounding box estimate.
    """
    
    # self.kf.x = [x,y,s,r,x_dot,y_dot,s_dot]
    # s_dot + s <= 0, then s_dot = 0
    if((self.kf.x[6]+self.kf.x[2])<=0):
      self.kf.x[6] *= 0.0
    self.kf.predict()
    self.age += 1
    if(self.time_since_update>0):
      self.hit_streak = 0
    self.time_since_update += 1
    self.history.append(convert_x_to_bbox(self.kf.x))  # [x,y,s,r] => [x1,y1,x2,y2]
    return self.history[-1]  # newest predicted bounding box coordinates

  def get_state(self):
    """
    Returns the current bounding box estimate.
    """
    return convert_x_to_bbox(self.kf.x)  # [x,y,s,r] => [x1,y1,x2,y2]


def associate_detections_to_trackers(detections,trackers,iou_threshold = 0.3):
  """
  Assigns detections to tracked object (both represented as bounding boxes)

  Returns 3 lists of matches, unmatched_detections and unmatched_trackers
  """
  if(len(trackers)==0):
    return np.empty((0,2),dtype=int), np.arange(len(detections)), np.empty((0,5),dtype=int)
    # return matches, unmatched_detections, unmatched_trackers

  # Computes IOU between two bboxes in the form [x1,y1,x2,y2]
  # Assignment cost matrix
  iou_matrix = iou_batch(detections, trackers)
    
  if min(iou_matrix.shape) > 0:
    a = (iou_matrix > iou_threshold).astype(np.int32)
    if a.sum(1).max() == 1 and a.sum(0).max() == 1:
        matched_indices = np.stack(np.where(a), axis=1)
    else:
        '''
        In assigning detections to existing targets, each target’s
        bounding box geometry is estimated by predicting its new
        location in the current frame. 
        
        The assignment cost matrix is
        then computed as the intersection-over-union (IOU) distance
        between each detection and all predicted bounding boxes
        from the existing targets.
        '''
        matched_indices = linear_assignment(-iou_matrix)
  else:
    matched_indices = np.empty(shape=(0,2))

  unmatched_detections = []
  for d, det in enumerate(detections):
    if(d not in matched_indices[:,0]):
      unmatched_detections.append(d)
    
  unmatched_trackers = []
  for t, trk in enumerate(trackers):
    if(t not in matched_indices[:,1]):
      unmatched_trackers.append(t)

  #filter out matched with low IOU
  matches = []
  for m in matched_indices:
    if(iou_matrix[m[0], m[1]]<iou_threshold):
      unmatched_detections.append(m[0])
      unmatched_trackers.append(m[1])
    else:
      matches.append(m.reshape(1,2))
  if(len(matches)==0):
    matches = np.empty((0,2),dtype=int)
  else:
    matches = np.concatenate(matches,axis=0)

  return matches, np.array(unmatched_detections), np.array(unmatched_trackers)


class Sort(object):
  def __init__(self, max_age=1, min_hits=3, iou_threshold=0.3):
    """
    Sets key parameters for SORT
    """
    self.max_age = max_age
    self.min_hits = min_hits
    self.iou_threshold = iou_threshold
    self.trackers = []
    self.frame_count = 0

  def update(self, dets=np.empty((0, 5))):
    """
    Params:
    dets: a numpy array of dettections in the format [[x1,y1,x2,y2,score], [x1,y1,x2,y2,score],...]
    Requires: this method must be called once for each frame even with empty detections (use np.empty((0,5)) for frames without detections).
    Returns a similar array, where the last column is the object ID.
    
    NOTE: 'The number of objects returned' may differ from 'the number of detections' provided.
    """
    self.frame_count += 1
    
    # get predicted locations from existing trackers.
    trks = np.zeros((len(self.trackers), 5))
    to_del = []
    ret = []
    for t, trk in enumerate(trks):
      pos = self.trackers[t].predict()[0]  # ???
      trk[:] = [pos[0], pos[1], pos[2], pos[3], 0]
      if np.any(np.isnan(pos)):  # To check if there is nan in pos, as when np.isnan(pos) has True, then np.any(np.isnan(pos)) is True
        to_del.append(t)
    trks = np.ma.compress_rows(np.ma.masked_invalid(trks))
    for t in reversed(to_del):  # list_reverseiterator
      self.trackers.pop(t)
    matched, unmatched_dets, unmatched_trks = associate_detections_to_trackers(dets,trks, self.iou_threshold)

    # update matched trackers with assigned detections
    for m in matched:
      self.trackers[m[1]].update(dets[m[0], :])

    # create and initialise new trackers for unmatched detections
    for i in unmatched_dets:
        trk = KalmanBoxTracker(dets[i,:])
        self.trackers.append(trk)
    i = len(self.trackers)
    for trk in reversed(self.trackers):
        d = trk.get_state()[0]
        if (trk.time_since_update < 1) and (trk.hit_streak >= self.min_hits or self.frame_count <= self.min_hits):
          ret.append(np.concatenate((d,[trk.id+1])).reshape(1,-1)) # +1 as MOT benchmark requires positive
        i -= 1
        # remove dead tracklet
        if(trk.time_since_update > self.max_age):
          self.trackers.pop(i)
    if(len(ret)>0):
      return np.concatenate(ret)
    return np.empty((0,5))

def parse_args():
    """Parse input arguments."""
    parser = argparse.ArgumentParser(description='SORT demo')
    parser.add_argument('--display', dest='display', help='Display online tracker output (slow) [False]',action='store_true')
    parser.add_argument("--seq_path", help="Path to detections.", type=str, default='data')
    parser.add_argument("--phase", help="Subdirectory in seq_path.", type=str, default='train')
    parser.add_argument("--max_age", 
                        help="Maximum number of frames to keep alive a track without associated detections.", 
                        type=int, default=1)
    parser.add_argument("--min_hits", 
                        help="Minimum number of associated detections before track is initialised.", 
                        type=int, default=3)
    parser.add_argument("--iou_threshold", help="Minimum IOU for match.", type=float, default=0.3)
    args = parser.parse_args()
    return args

if __name__ == '__main__':
  # all train
  args = parse_args()
  display = args.display
  phase = args.phase
  total_time = 0.0
  total_frames = 0
  colours = np.random.rand(32, 3)  # used only for display
  if(display):
    if not os.path.exists('mot_benchmark'):
      print('\n\tERROR: mot_benchmark link not found!\n\n    Create a symbolic link to the MOT benchmark\n    (https://motchallenge.net/data/2D_MOT_2015/#download). E.g.:\n\n    $ ln -s /path/to/MOT2015_challenge/2DMOT2015 mot_benchmark\n\n')
      exit()
    plt.ion()  # turn the interactive mode on.
    fig = plt.figure()
    ax1 = fig.add_subplot(111, aspect='equal')

  if not os.path.exists('output'):
    os.makedirs('output')
  pattern = os.path.join(args.seq_path, phase, '*', 'det', 'det.txt')  # glob.glob("*/...")中的*代表下一层文件夹
  for seq_dets_fn in glob.glob(pattern):  # glob.glob(path) : 匹配所有的符合条件的文件，并将其以list的形式返回
    # create instance of the SORT tracker
    mot_tracker = Sort(max_age=args.max_age,  # Maximum number of frames to keep alive a track without associated detections
                       min_hits=args.min_hits,  # Minimum number of associated detections before track is initialised
                       iou_threshold=args.iou_threshold) 
    seq_dets = np.loadtxt(seq_dets_fn, delimiter=',')  # Load data from a text file. Each row in the text file must have the same number of values.
    seq = seq_dets_fn[pattern.find('*'):].split('/')[0] # ???
    
    with open('output/%s.txt'%(seq),'w') as out_file: 
      print("Processing %s."%(seq))
      for frame in range(int(seq_dets[:,0].max())):
        frame += 1 #detection and frame numbers begin at 1
        dets = seq_dets[seq_dets[:, 0]==frame, 2:7]
        dets[:, 2:4] += dets[:, 0:2] #convert to [x1,y1,w,h] to [x1,y1,x2,y2]
        total_frames += 1

        if(display):
          fn = 'mot_benchmark/%s/%s/img1/%06d.jpg'%(phase, seq, frame)
          im =io.imread(fn)
          ax1.imshow(im)
          plt.title(seq + ' Tracked Targets')

        start_time = time.time()
        trackers = mot_tracker.update(dets)
        cycle_time = time.time() - start_time
        total_time += cycle_time

        for d in trackers:
          print('%d,%d,%.2f,%.2f,%.2f,%.2f,1,-1,-1,-1'%(frame,d[4],d[0],d[1],d[2]-d[0],d[3]-d[1]),file=out_file)
          if(display):
            d = d.astype(np.int32)
            ax1.add_patch(patches.Rectangle((d[0],d[1]),d[2]-d[0],d[3]-d[1],fill=False,lw=3,ec=colours[d[4]%32,:]))

        if(display):
          fig.canvas.flush_events()
          plt.draw()
          ax1.cla()

  print("Total Tracking took: %.3f seconds for %d frames or %.1f FPS" % (total_time, total_frames, total_frames / total_time))

  if(display):
    print("Note: to get real runtime results run without the option: --display")
