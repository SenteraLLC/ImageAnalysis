#!/usr/bin/python3

import argparse
import pickle
import numpy as np
import os.path
from tqdm import tqdm

from props import getNode

from . import camera
from .logger import log, qlog
from . import matcher
from . import project
from . import smart
from . import srtm

# Reset all match point locations to their original direct
# georeferenced locations based on estimated camera pose and
# projection onto DEM earth surface

m = matcher.Matcher()

def merge_duplicates(proj):
    # compute keypoint usage map
    proj.compute_kp_usage()

    # For some features detection algorithms we expect duplicated feature
    # uv coordinates.  These duplicates may have different scaling or
    # other attributes important during feature matching, yet ultimately
    # resolve to the same uv coordinate in an image.
    log("Indexing features by unique uv coordinates:")
    for image in tqdm(proj.image_list, smoothing=0.05):
        # pass one, build a tmp structure of unique keypoints (by uv) and
        # the index of the first instance.
        image.kp_remap = {}
        used = 0
        for i, kp in enumerate(image.kp_list):
            if image.kp_used[i]:
                used += 1
                key = "%.2f-%.2f" % (kp.pt[0], kp.pt[1])
                if not key in image.kp_remap:
                    image.kp_remap[key] = i
                else:
                    #print("%d -> %d" % (i, image.kp_remap[key]))
                    #print(" ", image.coord_list[i], image.coord_list[image.kp_remap[key]])
                    pass

        #print(" features used:", used)
        #print(" unique by uv and used:", len(image.kp_remap))

    # after feature matching we don't care about other attributes, just
    # the uv coordinate.
    #
    # notes: we do a first pass duplicate removal during the original
    # matching process.  This removes 1->many relationships, or duplicate
    # matches at different scales within a match pair.  However, different
    # pairs could reference the same keypoint at different scales, so
    # duplicates could still exist.  This finds all the duplicates within
    # the entire match set and collapses them down to eliminate any
    # redundancy.
    log("Merging keypoints with duplicate uv coordinates:")
    for i, i1 in enumerate(tqdm(proj.image_list, smoothing=0.05)):
        for key in i1.match_list:
            matches = i1.match_list[key]
            count = 0
            i2 = proj.findImageByName(key)
            if i2 is None:
                # ignore pairs outside our area set
                continue
            for k, pair in enumerate(matches):
                # print pair
                idx1 = pair[0]
                idx2 = pair[1]
                kp1 = i1.kp_list[idx1]
                kp2 = i2.kp_list[idx2]
                key1 = "%.2f-%.2f" % (kp1.pt[0], kp1.pt[1])
                key2 = "%.2f-%.2f" % (kp2.pt[0], kp2.pt[1])
                # print key1, key2
                new_idx1 = i1.kp_remap[key1]
                new_idx2 = i2.kp_remap[key2]
                # count the number of match rewrites
                if idx1 != new_idx1 or idx2 != new_idx2:
                    count += 1
                if idx1 != new_idx1:
                    # sanity check
                    uv1 = list(i1.kp_list[idx1].pt)
                    new_uv1 = list(i1.kp_list[new_idx1].pt)
                    if not np.allclose(uv1, new_uv1):
                        print("OOPS!!!")
                        print("  index 1: %d -> %d" % (idx1, new_idx1))
                        print("  [%.2f, %.2f] -> [%.2f, %.2f]" % (uv1[0], uv1[1],
                                                                  new_uv1[0],
                                                                  new_uv1[1]))
                if idx2 != new_idx2:
                    # sanity check
                    uv2 = list(i2.kp_list[idx2].pt)
                    new_uv2 = list(i2.kp_list[new_idx2].pt)
                    if not np.allclose(uv2, new_uv2):
                        print("OOPS!")
                        print("  index 2: %d -> %d" % (idx2, new_idx2))
                        print("  [%.2f, %.2f] -> [%.2f, %.2f]" % (uv2[0], uv2[1],
                                                                  new_uv2[0],
                                                                  new_uv2[1]))
                # rewrite matches
                matches[k] = [new_idx1, new_idx2]
            #if count > 0:
            #    print('Match:', i1.name, 'vs', i2.name, '%d/%d' % ( count, len(matches) ), 'rewrites')

# enable the following code to visualize the matches after collapsing
# identical uv coordinates
if False:
    for i, i1 in enumerate(proj.image_list):
        for j, i2 in enumerate(proj.image_list):
            if i >= j:
                # don't repeat reciprocal matches
                continue
            if len(i1.match_list[j]):
                print("Showing %s vs %s" % (i1.name, i2.name))
                status = m.showMatchOrient(i1, i2, i1.match_list[j])

def check_for_pair_dups(proj):
    # after collapsing by uv coordinate, we could be left with duplicate
    # matches (matched at different scales or other attributes, but same
    # exact point.)
    #
    # notes: this really shouldn't (!) (by my best current understanding)
    # be able to find any dups.  These should all get caught in the
    # original pair matching step.
    log("Checking for pair duplicates (there never should be any):")
    for i, i1 in enumerate(tqdm(proj.image_list)):
        for key in i1.match_list:
            matches = i1.match_list[key]
            i2 = proj.findImageByName(key)
            if i2 is None:
                # ignore pairs not in our area set
                continue
            count = 0
            pair_dict = {}
            new_matches = []
            for k, pair in enumerate(matches):
                pair_key = "%d-%d" % (pair[0], pair[1])
                if not pair_key in pair_dict:
                    pair_dict[pair_key] = True
                    new_matches.append(pair)
                else:
                    count += 1
            if count > 0:
                print('Match:', i1.name, 'vs', i2.name, 'matches:', len(matches), 'dups:', count)
            i1.match_list[key] = new_matches
        
# enable the following code to visualize the matches after eliminating
# duplicates (duplicates can happen after collapsing uv coordinates.)
if False:
    for i, i1 in enumerate(proj.image_list):
        for j, i2 in enumerate(proj.image_list):
            if i >= j:
                # don't repeat reciprocal matches
                continue
            if len(i1.match_list[j]):
                print("Showing %s vs %s" % (i1.name, i2.name))
                status = m.showMatchOrient(i1, i2, i1.match_list[j])

def check_for_1vn_dups(proj):
    # Do we have a keypoint in i1 matching multiple keypoints in i2?
    #
    # Notes: again these shouldn't exist here, but let's check anyway.  If
    # we start finding these here, I should hunt for the reason earlier in
    # the code that lets some through, or try to understand what larger
    # logic principle allows somne of these to still exist here.
    log("Testing for 1 vs. n keypoint duplicates (there never should be any):")
    for i, i1 in enumerate(tqdm(proj.image_list)):
        for key in i1.match_list:
            matches = i1.match_list[key]
            i2 = proj.findImageByName(key)
            if i2 is None:
                # skip pairs outside our area set
                continue
            count = 0
            kp_dict = {}
            for k, pair in enumerate(matches):
                if not pair[0] in kp_dict:
                    kp_dict[pair[0]] = pair[1]
                else:
                    log("Warning keypoint idx", pair[0], "already used in another match.")
                    uv2a = list(i2.kp_list[ kp_dict[pair[0]] ].pt)
                    uv2b = list(i2.kp_list[ pair[1] ].pt)
                    if not np.allclose(uv2a, uv2b):
                        qlog("  [%.2f, %.2f] -> [%.2f, %.2f]" % (uv2a[0], uv2a[1],
                                                                 uv2b[0], uv2b[1]))
                    count += 1
            if count > 0:
                qlog('Match:', i, 'vs', k, 'matches:', len(matches), 'dups:', count)

def make_match_structure(proj):
    log("Constructing unified match structure:")
    # create an initial pair-wise match list
    matches_direct = []
    for i, img in enumerate(tqdm(proj.image_list, smoothing=0.05)):
        # print img.name
        for key in img.match_list:
            j = proj.findIndexByName(key)
            if j is None:
                continue
            matches = img.match_list[key]
            # print proj.image_list[j].name
            if j > i:
                for pair in matches:
                    # ned place holder, in use flag
                    match = [None, -1]
                    # camera/feature references
                    match.append([i, pair[0]])
                    match.append([j, pair[1]])
                    matches_direct.append(match)
                    # print pair, match

    sum = 0.0
    for match in matches_direct:
        sum += len(match[2:])

    if len(matches_direct):
        log("Total feature pairs in image set:", len(matches_direct))
        log("Keypoint average instances = %.1f (should be 2.0 here)" % (sum / len(matches_direct)))

    return matches_direct

# collect/group match chains that refer to the same keypoint
def link_matches(proj, matches_direct):
    log("Linking common matches together into chains:")
    count = 0
    done = False
    while not done:
        log("Iteration %d (%d):" % (count, len(matches_direct)))
        count += 1
        matches_new = []
        matches_lookup = {}
        for i, match in enumerate(tqdm(matches_direct, smoothing=0.05)):
            # scan if any of these match points have been previously seen
            # and record the match index
            index = -1
            for p in match[2:]:
                key = "%d-%d" % (p[0], p[1])
                if key in matches_lookup:
                    index = matches_lookup[key]
                    break
            if index < 0:
                # not found, append to the new list
                for p in match[2:]:
                    key = "%d-%d" % (p[0], p[1])
                    matches_lookup[key] = len(matches_new)
                matches_new.append(list(match)) # shallow copy
            else:
                # found a previous reference, append these match items
                existing = matches_new[index]
                for p in match[2:]:
                    key = "%d-%d" % (p[0], p[1])
                    found = False
                    for e in existing[2:]:
                        if p[0] == e[0]:
                            found = True
                            break
                    if not found:
                        # add
                        existing.append(list(p)) # shallow copy
                        matches_lookup[key] = index
                # no 3d location estimation yet
                # # attempt to combine location equitably
                # size1 = len(match[2:])
                # size2 = len(existing[2:])
                # ned1 = np.array(match[0])
                # ned2 = np.array(existing[0])
                # avg = (ned1 * size1 + ned2 * size2) / (size1 + size2)
                # existing[0] = avg.tolist()
                # # print(ned1, ned2, existing[0])
                # # print "new:", existing
                # # print
        if len(matches_new) == len(matches_direct):
            done = True
        else:
            matches_direct = list(matches_new) # shallow copy

    # replace the keypoint index in the matches file with the actual kp
    # values.  This will save time later and avoid needing to load the
    # full original feature files which are quite large.  This also will
    # reduce the in-memory footprint for many steps.
    log('Replacing keypoint indices with uv coordinates:')
    for match in tqdm(matches_direct):
        for m in match[2:]:
            kp = proj.image_list[m[0]].kp_list[m[1]].pt
            m[1] = list(kp)
        # print(match)

    # sort by longest match chains first
    log("Sorting matches by longest chain first.")
    matches_direct.sort(key=len, reverse=True)

    sum = 0.0
    for i, match in enumerate(matches_direct):
        refs = len(match[2:])
        sum += refs

    if count >= 1:
        log("Total unique features in image set:", len(matches_direct))
        log("Keypoint average instances:", "%.2f" % (sum / len(matches_direct)))

    return matches_direct

def triangulate_smart(proj, matches):
    K = camera.get_K(optimized=False)
    IK = np.linalg.inv(K)
    
    # for each image lookup the SRTM elevation under the camera
    log("Looking up [smart] base elevation for each image location...")
    smart.load(proj.analysis_dir)
    for image in proj.image_list:
        image_node = smart.smart_node.getChild(image.name, True)
        ned, ypr, quat = image.get_camera_pose()
        if image_node.hasChild("tri_surface_m"):
            image.base_elev = image_node.getFloat("tri_surface_m")
        else:
            image.base_elev = srtm.ned_interp([ned[0], ned[1]])[0]
        if -ned[2] - 1 < image.base_elev:
            image.base_elev = -ned[2] - 1
        #print(image.name, image.base_elev, -ned[2])

    log("Estimating initial projection for each feature...")
    bad_count = 0
    bad_indices = []
    for i, match in enumerate(tqdm(matches, smoothing=0.02)):
        sum = np.zeros(3)
        array = []              # fixme: temp/debug
        for m in match[2:]:
            image = proj.image_list[m[0]]
            cam2body = image.get_cam2body()
            body2ned = image.get_body2ned()
            ned, ypr, quat = image.get_camera_pose()
            uv_list = [ m[1] ] # just one uv element
            vec_list = project.projectVectors(IK, body2ned, cam2body, uv_list)
            v = vec_list[0]
            if v[2] > 0.0:
                d_proj = -(ned[2] + image.base_elev)
                factor = d_proj / v[2]
                n_proj = v[0] * factor
                e_proj = v[1] * factor
                p = [ ned[0] + n_proj, ned[1] + e_proj, ned[2] + d_proj ]
                # print('  ', p)
                sum += np.array(p)
                array.append(p)
            else:
                log('vector projected above horizon.')
        match[0] = (sum/len(match[2:])).tolist()
        # print(match[0])
