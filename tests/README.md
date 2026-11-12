# Offline sandbox regression

Run target-controlled tests only in a real OS sandbox. This Linux recipe uses
existing bwrap, Python and Git; it does not install or fetch anything. Run from
the repository root. If namespace setup fails, stop; never fall back to host
execution. The scratch tmpfs has an explicit 64 MiB limit. Limits are applied
inside namespaces before the test process, avoiding pre-namespace process-limit
bootstrap failures. The outer timeout enforces wall time.

```sh
/usr/bin/timeout 30 /usr/bin/bwrap --unshare-all --die-with-parent --new-session \
  --ro-bind /usr /usr --ro-bind /bin /bin --ro-bind /lib /lib --ro-bind /lib64 /lib64 \
  --ro-bind "$PWD" /src --proc /proc --dev /dev --size 67108864 --tmpfs /scratch \
  --chdir /src --clearenv --setenv HOME /scratch --setenv TMPDIR /scratch \
  --setenv XDG_CACHE_HOME /scratch --setenv PATH /usr/bin:/bin \
  --setenv PYTHONDONTWRITEBYTECODE 1 /usr/bin/python3 -c \
  'import os,resource; resource.setrlimit(resource.RLIMIT_CPU,(20,20)); resource.setrlimit(resource.RLIMIT_AS,(536870912,536870912)); resource.setrlimit(resource.RLIMIT_NPROC,(32,32)); resource.setrlimit(resource.RLIMIT_FSIZE,(10485760,10485760)); os.execv("/usr/bin/python3",["python3","-m","unittest","discover","-s","tests","-v"])'
```

This is a local fixture regression, not an OpenSpec compatibility or real-agent
integration test. tmpfs is discarded on sandbox exit; no host credentials or
network are intentionally made available.
