"""Rebuild visualisations/balgarskoto-pravo-v-20-grafiki.html from this repository.

    python visualisations/src/make.py [--repo PATH] [--ref REF]

Steps (all read-only on the repository; scratch output goes to visualisations/src/.build/):
  1. the blobs the charts read are listed from the tree of REF: the texts of the laws, codes and the Constitution
     (zakon/, kodeks/, konstitutsiya/) and two tables under data/. In a partial (blobless) clone the missing ones
     are fetched in one batch; then they are read with git cat-file, one at a time:
       the tables                                   -> .build/repo/data/...
       the law texts, one JSON line per file        -> .build/texts.jsonl
  2. git log of REF, streamed: one line per commit with its author, dates, subject and the trailers the charts use
                                                    -> .build/log.tsv
  3. the files each commit of the Constitution changed (git log --name-status -- konstitutsiya)
                                                    -> .build/const.tsv
  4. prep.py turns those into .build/data.json; build.py fills page.tpl.html with it.
Works in a blobless or --no-checkout clone, because everything is read from git objects. Nothing is held in memory
at once: the history and the texts are streamed line by line.
"""
import argparse, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument('--repo', default=os.path.abspath(os.path.join(HERE, '..', '..')))
ap.add_argument('--ref', default=None, help='default: origin/main if present, else HEAD')
ap.add_argument('--out', default=os.path.join(HERE, '..', 'balgarskoto-pravo-v-20-grafiki.html'))
ap.add_argument('--skip-extract', action='store_true', help='reuse .build/ from a previous run (prep and build only)')
a = ap.parse_args()
B = os.path.join(HERE, '.build')
os.makedirs(B, exist_ok=True)


def git(*args, **kw):
    return subprocess.run(['git', '-C', a.repo, *args], check=True, capture_output=True, **kw).stdout


ref = a.ref
if not ref:
    ref = 'origin/main' if subprocess.run(['git', '-C', a.repo, 'rev-parse', '--verify', '-q', 'origin/main'], capture_output=True).returncode == 0 else 'HEAD'
sha = git('rev-parse', ref).decode().strip()
print('ref', ref, sha)

TABLES = {'data/held.json', 'data/laws.csv'}
TEXT_DIRS = ('zakon/', 'kodeks/', 'konstitutsiya/')

if not a.skip_extract:
    # 1. the blobs the charts read
    items = []
    for e in git('ls-tree', '-r', '-z', ref, '--', 'data', 'zakon', 'kodeks', 'konstitutsiya').split(b'\0'):
        if not e:
            continue
        meta, path = e.split(b'\t', 1)
        _, typ, oid = meta.split()
        path = path.decode('utf-8')
        if typ == b'blob' and (path in TABLES or path.startswith(TEXT_DIRS)):
            items.append((oid.decode(), path))
    print('blobs', len(items))
    env_nolazy = dict(os.environ, GIT_NO_LAZY_FETCH='1')
    chk = subprocess.run(['git', '-C', a.repo, 'cat-file', '--batch-check'], input=''.join(o + '\n' for o, _ in items).encode(),
                         capture_output=True, env=env_nolazy).stdout.decode().split('\n')
    missing = [l.split()[0] for l in chk if l.endswith(' missing')]
    if missing:  # partial clone: one batched fetch instead of one lazy fetch per blob
        print('fetching', len(missing), 'blobs')
        subprocess.run(['git', '-C', a.repo, '-c', 'fetch.negotiationAlgorithm=noop', 'fetch', 'origin', '--no-tags', '--no-write-fetch-head',
                        '--recurse-submodules=no', '--filter=blob:none', '--stdin'], input=''.join(m + '\n' for m in missing).encode(), check=False)
    R = os.path.join(B, 'repo')
    p = subprocess.Popen(['git', '-C', a.repo, 'cat-file', '--batch'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env_nolazy)
    n_txt = 0
    with open(os.path.join(B, 'texts.jsonl'), 'w', encoding='utf-8', newline='\n') as tx:
        for oid, path in items:
            p.stdin.write((oid + '\n').encode()); p.stdin.flush()
            head = p.stdout.readline().split()
            if len(head) < 3:
                sys.exit('cannot read ' + path)
            data = p.stdout.read(int(head[2])); p.stdout.read(1)
            if path in TABLES:
                dst = os.path.join(R, *path.split('/'))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(dst, 'wb') as fh:
                    fh.write(data)
            else:
                tx.write(json.dumps({'p': path, 't': data.decode('utf-8', 'replace')}, ensure_ascii=False) + '\n')
                n_txt += 1
    p.stdin.close(); p.wait()
    print('texts', n_txt)

    # 2. the history, streamed: sha, author, author email, author date, subject, then the trailers the charts use
    KEYS = ['Kind', 'In-force', 'Published', 'Enacted', 'Provisions', 'Law-kind', 'Files', 'In-force-basis', 'Act']
    fmt = '%x1e%H%x1f%an%x1f%ae%x1f%ad%x1f%s%x1f%(trailers:unfold,separator=%x1d)'
    lg = subprocess.Popen(['git', '-C', a.repo, 'log', ref, '--date=short', '--format=' + fmt], stdout=subprocess.PIPE)
    n, buf = 0, b''
    with open(os.path.join(B, 'log.tsv'), 'w', encoding='utf-8', newline='\n') as out:
        out.write('\t'.join(['sha', 'author', 'email', 'date', 'subject'] + KEYS) + '\n')

        def emit(rec):
            global n
            rec = rec.decode('utf-8', 'replace').strip('\n')
            if not rec:
                return
            parts = rec.split('\x1f')
            tr = {}
            for t in (parts[5] if len(parts) > 5 else '').split('\x1d'):
                k, _, v = t.partition(': ')
                k = k.strip()
                if k and k not in tr:
                    tr[k] = v.strip()
            if 'Files' in tr:
                tr['Files'] = tr['Files'].split(',')[0].strip()
            row = parts[:5] + [tr.get(k, '') for k in KEYS]
            out.write('\t'.join(x.replace('\t', ' ').replace('\n', ' ') for x in row) + '\n')
            n += 1
        for chunk in iter(lambda: lg.stdout.read(1 << 16), b''):
            buf += chunk
            *recs, buf = buf.split(b'\x1e')
            for r in recs:
                emit(r)
        emit(buf)
    lg.wait()
    print('commits', n)

    # 3. the Constitution: the files each of its commits changed
    with open(os.path.join(B, 'const.tsv'), 'w', encoding='utf-8', newline='\n') as out:
        cur = None
        for l in git('log', ref, '--format=@@C %H%x1f%ae%x1f%ad%x1f%(trailers:key=In-force,valueonly,separator=)', '--date=short',
                     '--name-status', '--no-renames', '--', 'konstitutsiya').decode('utf-8', 'replace').split('\n'):
            if l.startswith('@@C '):
                cur = l[4:].split('\x1f')
                continue
            if l and cur:
                st, _, f = l.partition('\t')
                out.write('\t'.join(cur + [st, f]) + '\n')

# 4. prep + build
env = dict(os.environ, HEAD_SHA=sha)
subprocess.run([sys.executable, '-X', 'utf8', os.path.join(HERE, 'prep.py'), B], check=True, env=env)
subprocess.run([sys.executable, '-X', 'utf8', os.path.join(HERE, 'build.py'), os.path.join(B, 'data.json'), os.path.abspath(a.out)], check=True)
