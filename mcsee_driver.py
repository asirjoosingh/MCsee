#!/usr/bin/env python

import os
from copy import deepcopy
from mcsee import readparams,runmccycle,ElScattCrossSec,InelScattCrossSec,Electron

currdir=os.getcwd()

# Read system parameters
Efermi,workfn,en0,coords0,theta0,phi0,nprimary,nelecperrun,fdiffinelcs,felf,decs,fimfp=readparams("params.in")
stopen=Efermi+workfn # elecs with less than this energy cannot be transmitted

# Get elastic cross section data
os.chdir(decs)
contents=os.listdir(".")
ecsdata=[]
for item in contents:
  cs=ElScattCrossSec(item)
  ecsdata.append(cs)

# Get inelastic cross section data
os.chdir(currdir)
ics=InelScattCrossSec(fimfp)
ics.readicsdata(fdiffinelcs,felf,Efermi)

# Initialize electron array
elecs0=[]
for i in range(nelecperrun):
  elecs0.append(Electron(0,en0,coords0,theta0,phi0,ecsdata,ics))

# Iterate over number of cycles based on user-input total number of primary elecs vs elecs per cycle
ncycles=nprimary/nelecperrun

avgstr=""
enstr=""
nelectot=0
nstoppedtot=0
ntransmittedtot=0
nsectransmittedtot=0
for i in range(ncycles):
  elecs=deepcopy(elecs0)
  nstopped,ntransmitted,nsectransmitted,emitteden=runmccycle(elecs,ecsdata,ics,Efermi,workfn,stopen)
  nelectot+=nelecperrun
  nstoppedtot+=nstopped
  ntransmittedtot+=ntransmitted
  nsectransmittedtot+=nsectransmitted
  for en in emitteden:
    enstr+="%10.6f\n"%(en)
  avgstr+="%15d%15d%15d%15d\n"%(nelecperrun,nstopped,ntransmitted,nsectransmitted)
  if i%10 == 0:
   avgout=open("running_avg.out","a")
   enout=open("running_en.out","a")
   avgout.write(avgstr)
   enout.write(enstr)
   enout.close()
   avgout.close()
   avgstr=""
   enstr=""
avgout=open("running_avg.out","a")
avgout.write(avgstr)
avgout.write("Totals:%15d%15d%15d%15d\n"%(nelectot,nstoppedtot,ntransmittedtot,nsectransmittedtot))
avgout.close()
enout=open("running_en.out","a")
enout.write(enstr)
enout.close()

# Re-read output energy file and sort after finished to save memory
os.system("sleep 5")
enin=open("running_en.out","r")
lines=enin.readlines()
enin.close()
emittedenergies=[float(line.strip()) for line in lines]
emittedenergies.sort()

# Output summary
outp=open("emitted_energies.out","w")
outp.write(str(nelectot) + " # Number of primary electrons\n")
outp.write(str(nstoppedtot) + " # Number of stopped electrons\n")
outp.write(str(ntransmittedtot) + " # Number of transmitted electrons\n")
outp.write(str(nsectransmittedtot) + " # Number of transmitted true secondary electrons\n")
for i in range(len(emittedenergies)):
  outp.write("%10.6f\n"%(emittedenergies[i]))
outp.close()

