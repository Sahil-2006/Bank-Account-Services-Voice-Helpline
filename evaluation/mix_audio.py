"""Add seeded noise at zero dB signal-to-noise ratio to a mono PCM fixture."""
import math
import random
import sys
import wave
from array import array

with wave.open(sys.argv[1],"rb") as wav:
    params=wav.getparams()
    if params.sampwidth != 2:
        raise ValueError("16-bit PCM required")
    samples=array("h",wav.readframes(wav.getnframes()))
rms=math.sqrt(sum(float(v)*v for v in samples)/len(samples))
rng=random.Random(10)
mixed=array("h",(max(-32768,min(32767,int(v+rng.gauss(0,rms)))) for v in samples))
with wave.open(sys.argv[2],"wb") as wav:
    wav.setparams(params)
    wav.writeframes(mixed.tobytes())
