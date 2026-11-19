import numpy as np, wave
SR=44100; T=105.0; N=int(SR*T); t=np.arange(N)/SR
rng=np.random.default_rng(7)
bpm=100; beat=60/bpm; bar=4*beat
out=np.zeros((N,2))
def env(n,a,r):
    e=np.ones(n); a=int(a*SR); r=int(r*SR)
    if a: e[:a]=np.linspace(0,1,a)
    if r: e[-r:]*=np.linspace(1,0,r)
    return e
def add(sig,start,gain=1.0,pan=0.0):
    i=int(start*SR); j=min(N,i+len(sig))
    if j<=i: return
    s=sig[:j-i]*gain
    out[i:j,0]+=s*(1-pan)/1.0*0.5+s*0.5*(1-max(pan,0))
    out[i:j,1]+=s*(1+pan)/1.0*0.5+s*0.5*(1+min(pan,0))
def smooth(x,k):
    return np.convolve(x,np.ones(k)/k,mode='same')
# intensity curve per section (0..1)
secs=[(0,9,.25),(9,18,.55),(18,30,.75),(30,42,.6),(42,54,.85),(54,66,.8),(66,76,1),(76,88,.9),(88,96,.3),(96,105,1)]
def level(x):
    for a,b,l in secs:
        if a<=x<b: return l
    return 1
# chords: Am F C G (A minor), voiced around 220Hz
f=lambda m:440*2**((m-69)/12)
prog=[[57,60,64,69],[53,57,60,65],[48,55,60,64],[55,59,62,67]]
bassn=[45,41,48,43]
k=0; s=0.0
while s<T:
    ch=prog[k%4]; dur=bar*2
    n=int(dur*SR); tt=np.arange(n)/SR
    pad=np.zeros(n)
    for m in ch:
        for h,a in [(1,1),(2,.35),(3,.12),(4,.05)]:
            det=1+0.002*rng.standard_normal()
            pad+=a*np.sin(2*np.pi*f(m)*h*det*tt+rng.uniform(0,6))
    pad*=env(n,0.8,1.0)*(0.85+0.15*np.sin(2*np.pi*0.25*tt))
    add(pad,s,0.035*(0.7+0.3*level(s)))
    # bass on beats 1 and 3 after intro
    if s>=9:
        for b in range(8):
            if b%2==0:
                bn=int(beat*1.8*SR); bt=np.arange(bn)/SR
                sig=np.sin(2*np.pi*f(bassn[k%4])*bt)*np.exp(-bt*2.2)
                add(sig,s+b*beat,0.16*level(s+b*beat))
    # arpeggio in high sections
    for i16 in range(32):
        ts=s+i16*beat/4
        if level(ts)>=0.75 and i16%2==0:
            m=ch[(i16//2)%4]+12
            an=int(0.22*SR); at=np.arange(an)/SR
            sig=(np.sin(2*np.pi*f(m)*at)+.3*np.sin(4*np.pi*f(m)*at))*np.exp(-at*14)
            add(sig,ts,0.05*level(ts),pan=0.4 if (i16//2)%2 else -0.4)
    k+=1; s+=dur
# drums
nb=int(T/beat)+1
for i in range(nb):
    ts=i*beat; L=level(ts)
    if ts<9 or (88<=ts<96): continue
    kn=int(0.35*SR); kt=np.arange(kn)/SR
    freq=50+90*np.exp(-kt*30)
    kick=np.sin(2*np.pi*np.cumsum(freq)/SR)*np.exp(-kt*9)
    add(kick,ts,0.45*L)
    if ts>=18:
        for off in (0.5,):
            hn=int(0.05*SR); noise=rng.standard_normal(hn); noise=noise-smooth(noise,6)
            add(noise*np.exp(-np.arange(hn)/SR*80),ts+off*beat,0.05*L,pan=0.3)
    if L>=0.85 and i%2==1:
        sn=int(0.18*SR); st=np.arange(sn)/SR; noise=rng.standard_normal(sn); noise=noise-smooth(noise,3)
        add(noise*np.exp(-st*22)*0.6+np.sin(2*np.pi*190*st)*np.exp(-st*30)*0.4,ts,0.12*L)
# risers into scene changes
for a,_,_ in secs[1:]:
    rn=int(1.2*SR); rt=np.arange(rn)/SR
    noise=smooth(rng.standard_normal(rn),8)
    add(noise*(rt/1.2)**2.5,a-1.2,0.06)
# master fades
out[:int(1.5*SR)]*=np.linspace(0,1,int(1.5*SR))[:,None]
fo=int(3*SR); out[-fo:]*=np.linspace(1,0,fo)[:,None]
out/=np.max(np.abs(out))*1.12
pcm=(out*32767).astype(np.int16)
with wave.open('music.wav','wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print("ok")
