#!/usr/bin/env python

import numpy as np

def findnearest(arr,value):
  """
  Find an entry in an array closest to some value
  Inputs:
    arr:   array
    value: value
  Outputs:
    ind:   index in array corresponding to closest entry
    val:   value in array corresponding to closest entry
  i.e., val=arr[ind] is closest entry to value
  """
  constarr=np.zeros(len(arr))
  constarr.fill(value)
  ind=np.argmin(abs(arr-constarr))
  val=arr[ind]
  return ind,val

