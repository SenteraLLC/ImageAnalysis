#!/usr/bin/python

import sys
sys.path.insert(0, "/usr/local/opencv-2.4.11/lib/python2.7/site-packages/")

import argparse
import commands
import cv2
import cv
import fnmatch
import numpy as np
import os.path
import random

sys.path.append('../lib')
import Image
import Pose
import ProjectMgr

# generate a list of random pixels, undistort them, then distort them to
# test our un/distortion code.

parser = argparse.ArgumentParser(description='Set the initial camera poses.')
parser.add_argument('--project', required=True, help='project directory')

args = parser.parse_args()

proj = ProjectMgr.ProjectMgr(args.project)

# setup the camera with sentera 3 Mpx params
width_px = 3808
height_px = 2754
fx = fy = 4662.25 # [pixels] - where 1 pixel = 1.67 micrometer
horiz_mm = width_px * 1.67 * 0.001
vert_mm = height_px * 1.67 * 0.001
focal_len_mm = (fx * horiz_mm) / width_px
proj.cam.set_lens_params(horiz_mm, vert_mm, focal_len_mm)
proj.cam.set_calibration_params(fx, fy, width_px/2, height_px/2,
                                [0.0, 0.0, 0.0, 0.0, 0.0], 0.0)
proj.cam.set_calibration_std(0.0, 0.0, 0.0, 0.0,
                             [0.0, 0.0, 0.0, 0.0, 0.0], 0.0)
proj.cam.set_image_params(width_px, height_px)
proj.cam.set_mount_params(0.0, -90.0, 0.0)

#image = proj.image_list[1]
image = Image.Image()
image.set_camera_pose([0.0, 0.0, 0.0], 0.0, -90.0, 0.0)
image.width = width_px
image.height = height_px

# k1, k2, p1, p2, k3

# from example online:
# http://stackoverflow.com/questions/11017984/how-to-format-xy-points-for-undistortpoints-with-the-python-cv2-api
#dist_coeffs = np.array([-0.24, 0.095, -0.0004, 0.000089, 0.], dtype=np.float32)

# from laura's camera:
dist_coeffs = np.array([-0.12474347, 0.82940434, -0.01625672, -0.00958748, -1.20843989], dtype=np.float32)

# no distortion?
#dist_coeffs = None

num_points = 20

# generate num points random points
points_orig = np.zeros((num_points,1,2), dtype=np.float32)
for i in range(0, num_points):
    x = random.randrange(image.width)
    y = random.randrange(image.height)
    points_orig[i][0] = [y,x]
#print points_orig

# undistort the points
points_undistort = cv2.undistortPoints(np.array(points_orig, dtype=np.float32), proj.cam.K, dist_coeffs, P=proj.cam.K)

for i in range(0, num_points):
    ud = points_undistort[i][0]
    print "orig = %s  undist = %s" % (points_orig[i], ud)
