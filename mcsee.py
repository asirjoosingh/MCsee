#!/usr/bin/env python

import os
from random import Random
from numpy import *
from subprocess import *
from convfactors import *


def plotdata(data,filestring):
  contents=os.listdir(".")
  if filestring in contents:
   raise IOError("File " + filestring + " already in cwd")
  outp=open(filestring,"w")
  npts=len(data)
  for i in range(npts):
    outp.write("%20.10f%20.10f\n"%(data[i][0],data[i][1]))
  outp.close()
  return

def findnearest(arr,value):
  constarr=zeros(len(arr))
  constarr.fill(value)
  ind=argmin(abs(arr-constarr))
  val=arr[ind]
  return ind,val

def readparams(filestring):
  try:
    inp=open(filestring,"r")
    lines=inp.readlines()
    inp.close()
  except:
    raise IOError("File " + filestring + " not found")
  Efermi=float(lines[0].strip().split()[0])
  del lines[0]
  workfn=float(lines[0].strip().split()[0])
  del lines[0]
  en0=float(lines[0].strip().split()[0])
  del lines[0]
  coords0=[float(lines[0].strip().split()[0]),float(lines[0].strip().split()[1]),float(lines[0].strip().split()[2])]
  del lines[0]
  theta0=float(lines[0].strip().split()[0])
  del lines[0]
  phi0=float(lines[0].strip().split()[0])
  del lines[0]
  nprimaryelecs=int(lines[0].strip().split()[0])
  del lines[0]
  fdiffinelcs=lines[0].strip().split()[0]
  del lines[0]
  felf=lines[0].strip().split()[0]
  del lines[0]
  return Efermi,workfn,en0,coords0,theta0,phi0,nprimaryelecs,fdiffinelcs,felf

def runmccycle(elecs,ecsdata,ics,Efermi,workfn,stopen):
# Set up random number generators
  randarr=[]
  randarr.append(Random())
  randarr[0].seed()
  initstate=randarr[0].getstate()
  for i in range(1,8):
    randarr.append(Random())
    randarr[i].setstate(initstate)
    randarr[i].jumpahead(i*1000000001)

# Tabulate EMFP and IMFP energies
  ecsenergies=zeros(len(ecsdata))
  for i in range(len(ecsdata)):
    ecsenergies[i]=ecsdata[i].energy
  icsenergies=ics.getEcoords()

# Run MC cycle on elecs
  alldone=False
  ntransmitted=0
  nstopped=0
  emitteden=[]
  nsectransmitted=0
  while not alldone:
    secelecs=[]
#    eleccount=0

    for el in elecs:
#      eleccount+=1
#      print "Trajectory for electron: ",eleccount

# Determine length before scattering event
      rand1=randarr[0].random()
      s=-el.mfp*log(rand1)
      el.updatecoords(s)
#      print "Moving by: ",s
#      print el

# Check if transmitted if surface crossed (z<0)
      if el.coords[2] < 0:
       rand8=randarr[7].random()
       el.checktransmit(Efermi,workfn,rand8)
       if el.transmitted:
        ntransmitted+=1
        emitteden.append(el.energy)
        if el.energy <= 50:
         nsectransmitted+=1
        continue

# Determine type of scattering event
      rand2=randarr[1].random()
      if rand2 < el.mfp/el.emfp:
       elastic=True
      else:
       elastic=False

      if elastic:
# Elastic scattering: determine angles after scattering
       rand3=randarr[2].random()
       ecsintind,ecsintval=findnearest(ecsdata[el.ecsind].cumintdata,rand3*ecsdata[el.ecsind].totcrosssec/(2.*pi))
       dtheta=ecsdata[el.ecsind].data[ecsintind][0]

       rand4=randarr[3].random()
       dphi=2*pi*rand4

#       print "Elastic (dtheta,dphi):",dtheta*180/pi,dphi*180/pi
       el.updatevdirecpolar(dtheta,dphi)
#       print el

      else:
# Inelastic scattering: determine energy loss and angles after scattering
       icsind,icsval=findnearest(icsenergies,el.energy*ev2au)
       delEcoords=ics.getdelEcoords(icsval)
       rand5=randarr[4].random()
       icsintind,icsintval=findnearest(ics.cumintdata[icsind,:],rand5*ics.totcrosssec[icsind])
       delE=delEcoords[icsintind]

# Given E, delE, form probability distribution for double differential cross section
       rand6=randarr[5].random()
       wcoords=ics.getwcoords()
       icsind,icsval=findnearest(wcoords,delE)
       dtheta=ics.finddcsangle(el.energy*ev2au,delE,icsind,rand6)

       rand7=randarr[6].random()
       dphi=2*pi*rand7

#       print "Inelastic (delE,dtheta,dphi)",delE*au2ev,dtheta*180/pi,dphi*180/pi

       newen=delE*au2ev+Efermi
       if newen > stopen: # Only generate secondary electron if energy greater than stopped energy cutoff
        newel=Electron(el.order+1,delE*au2ev+Efermi,el.coords,el.vtheta,el.vphi,ecsdata,ics)
        newel.updatevdirecpolar(arcsin(cos(dtheta)),dphi+pi)
        secelecs.append(newel)

       el.updatevdirecpolar(dtheta,dphi)
       el.updateenergy(-delE*au2ev,stopen,ecsdata,ics)
       if el.stopped:
        nstopped+=1
#       print el
#       print newel

    elecs[:]=filter(Electron.prune,elecs) # This syntax will ensure elecs is modified in place (affects calling routines referencing elecs as well!)
    elecs.extend(secelecs)
#    print "Number of electrons, Number of stopped electrons, Number of transmitted electrons:",len(elecs),nstopped,ntransmitted
    alldone=elecs==[]

  return nstopped,ntransmitted,nsectransmitted,emitteden


class ElScattCrossSec:

  def __init__(self,filestring):
    try:
      inp=open(filestring,"r")
      lines=inp.readlines()
      inp.close()
    except:
      raise IOError("File " + filestring + " not found")
    self.atnum=int(Popen("grep 'Atomic number' " + filestring,stdout=PIPE,shell=True).communicate()[0].strip().split()[-1])
    self.energy=int(Popen("grep 'Energy' " + filestring,stdout=PIPE,shell=True).communicate()[0].strip().split()[-2])
    self.totcrosssec=float(Popen("grep 'Total cross section' " + filestring,stdout=PIPE,shell=True).communicate()[0].strip().split()[-2])
    self.data=[]
    self.cumintdata=[] # stores cumulative integral from 0->theta cross_section(theta) * sin(theta) * dtheta (corresponding angle indexed in same order in self.data)
    done=False
    while not done:
      linesplit=lines[0].strip().split()
      del lines[0]
      if len(linesplit) >= 2 and linesplit[0] == "Angle" and linesplit[1] == "theta":
       done=True
      if lines == []:
       done=True
       raise IOError("Could not process data in " + filestring)
    del lines[0]
    del lines[0]
    cumint=0.
    done=False
    while not done:
      linesplit=lines[0].strip().split()
      del lines[0]
      ang=float(linesplit[0])*pi/180.
      val=float(linesplit[1])
      self.data.append((ang,val))
      if len(self.cumintdata) > 0:
       cumint+=0.5*(ang-ang0)*(sin(ang)*val+sin(ang0)*val0)
      self.cumintdata.append(cumint)
      ang0=ang
      val0=val
      if lines == []:
       done=True
    self.npts=len(self.data)
    if self.atnum == 28: # Nickel
     mass=58.6934 # amu=g/mol
     dens=8.908 # g/cm3
    self.emfp=1.0/(self.totcrosssec*dens/mass*0.602214*(bohr2ang)**3)
    return

  def nintegrate(self,a,b):
    intsum=0.
    for i in range(self.npts-1):
      if self.data[i+1][0] > b:
       break
      else:
       if self.data[i][0] >= a:
        intsum+=0.5*(self.data[i+1][0]-self.data[i][0])*(sin(self.data[i+1][0])*self.data[i+1][1]+sin(self.data[i][0])*self.data[i][1])
    return intsum

  @staticmethod
  def findemfp(ecsarr,en):
    enarr=zeros(len(ecsarr))
    for i in range(len(ecsarr)):
      enarr[i]=ecsarr[i].energy
    ecsind,enfound=findnearest(enarr,en)
    return ecsind,ecsarr[ecsind].emfp


class InelScattCrossSec:

  def __init__(self,filestring):
    try:
      inp=open(filestring,"r")
      lines=inp.readlines()
      inp.close()
    except:
      raise IOError("File " + filestring + " not found")
    elem=Popen("grep -A 1 'ELEMENT' " + filestring,stdout=PIPE,shell=True).communicate()[0].strip().split("\n")[1].strip()
    if elem == "Ni":
     self.atnum=28
    self.atweight=float(Popen("grep 'ATOMIC WEIGHT' " + filestring,stdout=PIPE,shell=True).communicate()[0].strip().split()[-1])
    self.density=float(Popen("grep 'DENSITY' " + filestring,stdout=PIPE,shell=True).communicate()[0].strip().split()[-2])
    self.imfpdata=[]
    self.energies=[]
    done=False
    while not done:
      linesplit=lines[0].strip().split()
      del lines[0]
      if len(linesplit) >= 2 and linesplit[0] == "Energy" and linesplit[1] == "IMFP":
       done=True
      if lines == []:
       done=True
       raise IOError("Could not process data in " + filestring)
    del lines[0]
    del lines[0]
    done=False
    while not done:
      linesplit=lines[0].strip().split()
      del lines[0]
      en=float(linesplit[0]) # Read in as eV
      val=float(linesplit[1])*ang2bohr # Read in as A, store as au
      self.imfpdata.append((en,val))
      self.energies.append(en)
      if lines == []:
       done=True
    self.nimfppts=len(self.imfpdata)
    return

  def findimfp(self,en):
    icsind,enfound=findnearest(self.energies,en)
    return self.imfpdata[icsind][1]

  def readicsdata(self,filestring1,filestring2,Efermi):
    try:
      inp1=open(filestring1,"r")
      lines1=inp1.readlines()
      inp1.close()
    except:
      raise IOError("File " + filestring1 + " not found")
    try:
      inp2=open(filestring2,"r")
      lines2=inp2.readlines()
      inp2.close()
    except:
      raise IOError("File " + filestring2 + " not found")
# Get differential data
    self.Emin=float(lines1[0].strip())*ev2au
    del lines1[0]
    self.Emax=float(lines1[0].strip())*ev2au
    del lines1[0]
    self.NE=int(len(lines1))
    self.NdelE=int(len(lines1[0].strip().split()))
    self.icsdata=zeros((self.NE,self.NdelE))
    self.cumintdata=zeros((self.NE,self.NdelE)) # stores for each E the cumulative integral from 0->delE cross_section(delE) * delE (corresponding delE indexed in same order in self.icsdata[E,:])
    self.totcrosssec=zeros(self.NE)
    Ecoords=self.getEcoords()
    for i in range(self.NE):
      delEcoords=self.getdelEcoords(Ecoords[i])
      linesplit=lines1[0].strip().split()
      del lines1[0]
      cumint=0.
      for j in range(self.NdelE):
        val=float(linesplit[j])
        self.icsdata[i,j]=val
        if j > 0:
         cumint+=0.5*(delEcoords[j]-delEcoords[j-1])*(val+val0)
        self.cumintdata[i,j]=cumint
        val0=val
        if delEcoords[j] <= (Ecoords[i]-Efermi*ev2au):
         self.totcrosssec[i]=cumint
# Get ELF(q,w) data
    wmin=float(lines2[0].strip())*ev2au # Read in eV, convert to Eh
    del lines2[0]
    wmax=float(lines2[0].strip())*ev2au # Read in eV, convert to Eh
    del lines2[0]
    qmin=float(lines2[0].strip())*bohr2ang # Read in A^-1, convert to a0^-1
    del lines2[0]
    qmax=float(lines2[0].strip())*bohr2ang # Read in A^-1, convert to a0^-1
    del lines2[0]
    self.wmin=wmin
    self.wmax=wmax # Temp
    self.qmin=qmin
    self.qmax=qmax # Temp
    self.Nw=int(len(lines2)) # Temp
    self.Nq=int(len(lines2[0].strip().split())) # Temp
    self.wcoords=self.getwcoords() # Temp
    self.qcoords=self.getqcoords() # Temp
    wind,wval=findnearest(self.wcoords,self.Emax) # Find last index of input table needed
    if (self.Emax > wval) and (wind < self.Nw): # Round up to ensure table is complete for all transitions
     wind+=1
     wval=self.wcoords[wind]
    self.wmax=wval
    self.Nw=wind+1
    self.wcoords=self.getwcoords()
    qind,qval=findnearest(self.qcoords,sqrt(2.*self.wmax)) # Find last index of input table needed
    if qind < self.Nq: # Round up to ensure table is complete for all transitions
     qind+=1
     qval=self.qcoords[qind]
    self.qmax=qval
    self.Nq=qind+1
    self.qcoords=self.getqcoords()
    self.elfqw=zeros((self.Nw,self.Nq))
    for i in range(self.Nw):
      linesplit=lines2[0].strip().split()
      del lines2[0]
      for j in range(self.Nq):
        val=float(linesplit[j])
        self.elfqw[i,j]=val
# Find maximum inelastic scattering angle to save loop iterations later
    a=sqrt(self.Emax*(self.Emax-self.wmin))
    b=4.*self.Emax-2.*self.wmin
    c=-4.*a
    maxang=-1 # degrees (int)
    done=False
    while not done:
      maxang+=1
      ang=maxang*pi/180.
      q=sqrt(b+c*cos(ang))
      if (q > self.qmax) or (maxang == 180):
       done=True
    self.maxang=maxang
    return

  def finddcsangle(self,E,delE,wind,rand):
    deltheta=1.*pi/180. # grid in increments of 1 deg (consistent with elastic scattering)
    a=sqrt(E*(E-delE))
    b=4.*E-2.*delE
    c=-4.*a
    d=1./(pi*pi*E)
    ang0=0.
    val0=0.
    cumint=0.
    cumintarr=zeros((self.maxang+1))
    for i in range(1,self.maxang+1):
      ang=i*deltheta
      q=sqrt(b+c*cos(ang))
      qind,qval=findnearest(self.qcoords,q)
      val=d*self.elfqw[wind,qind]*a/(q*q)
      cumint+=0.5*deltheta*(val*sin(ang)+val0*sin(ang0))
      cumintarr[i]=cumint
    ind,val=findnearest(cumintarr,rand*cumintarr[-1])
    theta=ind*deltheta
#    print cumintarr[-1],rand*cumintarr[-1],ind,val,theta*180/pi
    return theta

  def getEcoords(self):
    Estep=(self.Emax-self.Emin)/(self.NE-1)
    coords=[]
    for i in range(self.NE):
      coords.append(self.Emin+i*Estep)
    return coords

  def getdelEcoords(self,en):
    delEmax=en
    delEstep=delEmax/(self.NdelE-1)
    coords=[]
    for i in range(self.NdelE):
      coords.append(i*delEstep)
    return coords

  def getwcoords(self):
    wstep=(self.wmax-self.wmin)/(self.Nw-1)
    coords=[]
    for i in range(self.Nw):
      coords.append(self.wmin+i*wstep)
    return coords

  def getqcoords(self):
    qstep=(self.qmax-self.qmin)/(self.Nq-1)
    coords=[]
    for i in range(self.Nq):
      coords.append(self.qmin+i*qstep)
    return coords


class Electron:

  def __init__(self,order,energy,coords,vtheta,vphi,ecsdata,icsinst):
    self.order=order       # intr describing order in generation by collision (0=primary, 1=initial secondary, ...)
    self.energy=energy     # energy in eV
    self.coords=coords     # coordinates (Cartesian)
    self.vtheta=0.         # angle from positive z-axis in direction of velocity relative to current coordinates
    self.vphi=0.           # angle from positive x-axis in direction of velocity relative to current coordinates
    self.vdirec=zeros((3)) # unit vector in direction of velocity (Cartesian) relative to current coordinates
    self.updatevdirecpolar(vtheta,vphi)
    self.transmitted=False
    self.stopped=False
    self.getmfpdata(ecsdata,icsinst)
    return

  def __str__(self):
    infostr="""
    Instance of Electron class:
    -------------------------------------------
      Order          = %4d
      Energy (eV)    = %8.2f
      Coords (a0)    = (%6.2f,%6.2f,%6.2f)
      Velocity Direc = (%6.2f,%6.2f,%6.2f)
      EMFP (A)       = %8.2f
      IMFP (A)       = %8.2f
    -------------------------------------------
    """%(self.order,self.energy,self.coords[0],self.coords[1],self.coords[2],self.vdirec[0],self.vdirec[1],self.vdirec[2],self.emfp,self.imfp)
    return infostr

  def getmfpdata(self,ecs,ics):
    self.ecsind,self.emfp=ElScattCrossSec.findemfp(ecs,self.energy)
    self.imfp=ics.findimfp(self.energy)
    self.mfp=1./(1./self.emfp+1./self.imfp)
    return

  def updatecoords(self,dr):
    self.coords[0]=self.coords[0]+dr*self.vdirec[0]
    self.coords[1]=self.coords[1]+dr*self.vdirec[1]
    self.coords[2]=self.coords[2]+dr*self.vdirec[2]
    return

  def updatevdirecpolar(self,dtheta,dphi):
    self.vtheta=(self.vtheta+dtheta)%(2*pi)
    self.vphi=(self.vphi+dphi)%(2*pi)
    dx=sin(self.vtheta)*cos(self.vphi)
    dy=sin(self.vtheta)*sin(self.vphi)
    dz=cos(self.vtheta)
    self.vdirec[0]=dx
    self.vdirec[1]=dy
    self.vdirec[2]=dz
    return

  def updateenergy(self,denergy,stopenergy,ecsdata,icsinst):
    self.energy=self.energy+denergy
    self.getmfpdata(ecsdata,icsinst)
    self.stopped=self.energy<stopenergy
    return

  def checktransmit(self,Efermi,workfn,rand):
    U0=(Efermi+workfn)*ev2au
    vx=self.vdirec[0]
    vy=self.vdirec[1]
    vz=self.vdirec[2]
    beta=pi-self.vtheta
    Ecos2beta=self.energy*ev2au*cos(beta)*cos(beta)
    if Ecos2beta > U0:
     T=4.*sqrt(1.-U0/Ecos2beta)/(1.+sqrt(1.-U0/Ecos2beta))**2
    else:
     T=0.
    if rand < T: # transmit
     self.vtheta=arcsin(sqrt(self.energy/(self.energy-U0*au2ev))*sin(beta)) # self.vtheta is now angle from normal to -z axis
     self.energy=self.energy-U0*au2ev # no need to use updateenergy which looks up new MFP data
     self.transmitted=True
    else: # reflect
     delr=self.coords[2]/vz
     self.updatecoords(-delr) # move back to z=0 (negative displacement along same velocity)
     self.updatevdirecpolar(pi-2*self.vtheta,0.)
     self.updatecoords(delr) # move along new direction by remaining displacement
    return

  @staticmethod
  def prune(inst): # returns true if neither stopped nor transmitted (use with filter to prune lists of electrons)
    return not(inst.transmitted or inst.stopped)

if __name__ == "__main__":
 currdir=os.getcwd()

# Read system parameters
 Efermi,workfn,en0,coords0,theta0,phi0,nprimaryelecs,fdiffinelcs,felf=readparams("params.in")
 stopen=Efermi+workfn # elecs with less than this energy cannot be transmitted

 os.chdir("/home/ars217/Ni_NIST_data/elastic")
 contents=os.listdir(".")
 ecsdata=[]
 for item in contents:
   cs=ElScattCrossSec(item)
#   print cs.atnum,cs.energy,cs.totcrosssec,2.*pi*cs.nintegrate(0,pi),2.*pi*cs.cumintdata[-1],cs.emfp
   ecsdata.append(cs)

 os.chdir(currdir)
 ics=InelScattCrossSec("/home/ars217/Ni_NIST_data/imfpdata/imfp_Ni.dat")
# print ics.atnum,ics.atweight,ics.density
# plotdata(ics.imfpdata,"imfp_vs_E.dat")
 ics.readicsdata(fdiffinelcs,felf,Efermi)
# print ics.Emin,ics.Emax,ics.NE,ics.NdelE
# print ics.Emin*au2ev,ics.Emax*au2ev,ics.Nw,ics.wmin*au2ev,ics.wmax*au2ev,ics.Nq,ics.qmin*ang2bohr,ics.qmax*ang2bohr,ics.maxang

 elecs=[]
 for i in range(nprimaryelecs):
   elecs.append(Electron(0,en0,coords0,theta0,phi0,ecsdata,ics))
 nstopped,ntransmitted,nsectransmitted,emitteden=runmccycle(elecs,ecsdata,ics,Efermi,workfn,stopen)
 emitteden.sort()

 outp=open("emitted_energies.dat","w")
 outp.write(str(nprimaryelecs) + " # Number of primary electrons\n")
 outp.write(str(nstopped) + " # Number of stopped electrons\n")
 outp.write(str(ntransmitted) + " # Number of transmitted electrons\n")
 outp.write(str(nsectransmitted) + " # Number of transmitted true secondary electrons\n")
 for i in range(len(emitteden)):
   outp.write("%10.6f\n"%(emitteden[i]))
 outp.close()

