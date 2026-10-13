import sys,json,soundfile as sf,subprocess,os,numpy as np
from kokoro_onnx import Kokoro
k=Kokoro("kokoro-v1.0.int8.onnx","voices-v1.0.bin")
SP=float(os.environ.get("SPEED","0.85"));SH=1.18
jobs=json.load(open(sys.argv[1]));tmp=f"/tmp/k{os.getpid()}.wav"
for t,o in jobs:
    a,sr=k.create(t,voice="af_heart",speed=SP,lang="en-us")
    sf.write(tmp,a,sr)
    subprocess.run(["ffmpeg","-loglevel","error","-y","-i",tmp,"-af",f"asetrate={sr}*{SH},aresample=24000,atempo={1/SH:.4f},silenceremove=start_periods=1:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse,apad=pad_dur=0.15","-ac","1","-b:a","32k",o],check=True)
