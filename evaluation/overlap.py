"""Mix a caller into a quieter agent prompt 400 ms after playback begins."""
import sys
import wave
from array import array

def load(path):
    with wave.open(path,"rb") as f:
        return f.getparams(),array("h",f.readframes(f.getnframes()))
a,prompt=load(sys.argv[1]); b,caller=load(sys.argv[2])
assert (a.framerate,a.nchannels,a.sampwidth)==(b.framerate,b.nchannels,b.sampwidth)
offset=int(a.framerate*0.4)*a.nchannels
samples=array("h",[0])*max(len(prompt),offset+len(caller))
for i,v in enumerate(prompt):
    samples[i]=int(v*0.12)
for i,v in enumerate(caller,offset):
    samples[i]=max(-32768,min(32767,samples[i]+v))
with wave.open(sys.argv[3],"wb") as f:
    f.setparams(a); f.writeframes(samples.tobytes())
