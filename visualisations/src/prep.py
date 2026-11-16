"""Compute every number for the 20 charts into <build>/data.json.

    python prep.py <build-dir>

Reads, from <build> (written by make.py): log.tsv (the history, one line per commit), texts.jsonl (the texts of the
laws, codes and the Constitution, one JSON line per file), const.tsv (the files each commit of the Constitution changed)
and repo/data/held.json, repo/data/laws.csv. Every rule that reads a category out of a title or a text is in this file.
Nothing is loaded whole except the history: the texts are streamed act by act.
"""
import collections, csv, json, os, re, statistics, sys
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
B = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '.build')
R = os.path.join(B, 'repo')
csv.field_size_limit(10 ** 9)
D = date.fromisoformat
OUT, PROFILE = {}, {}
KINDS = ('zakon', 'kodeks', 'postanovlenie', 'naredba', 'pravilnik', 'instruktsiya')
LAST_YEAR = 2026


def ntitle(t):
    """A title reduced for matching the same act across the history, laws.csv and held.json."""
    t = t.lower().replace('ё', 'е')
    t = re.sub(r'\(дв,? бр\.[^)]*\)', '', t)
    return re.sub(r'[^0-9а-яa-z]+', '', t)[:70]


# ------------------------------------------------------------------ 1. the acts, from the history
ACTS, OTHER_AUTHORS, N_COMMITS = [], collections.Counter(), 0
with open(os.path.join(B, 'log.tsv'), encoding='utf-8') as fh:
    for r in csv.DictReader(fh, delimiter='\t', quoting=csv.QUOTE_NONE):
        N_COMMITS += 1
        email = r['email']
        slug, _, dom = email.partition('@')
        k = slug.split('-')[0]
        if k not in KINDS or dom != 'parliament.invalid':
            OTHER_AUTHORS[slug.split('-')[0] + '@' + dom] += 1
            continue
        m = re.match(r'^[a-z]+-(\d{4})-dv(\d+)-(\d+)$', slug)
        if m:
            y, iss, mat = int(m.group(1)), int(m.group(2)), int(m.group(3))
        else:
            m = re.match(r'^[a-z]+/(\d{4})/dv(\d+)-(\d+)/', r['Files'])
            if not m:
                OTHER_AUTHORS['unplaced'] += 1
                continue
            y, iss, mat = int(m.group(1)), int(m.group(2)), int(m.group(3))
        title = r['Act'] or r['author']
        title = re.sub(r'\s+as enacted \(.*$', '', title)
        title = re.sub(r'\s*\(ДВ, бр\. \d+ от \d{4} г\.\)\s*$', '', title).strip()
        ACTS.append({'slug': slug, 'k': k, 'y': y, 'iss': iss, 'mat': mat, 'pub': r['Published'], 'en': r['Enacted'],
                     'inf': r['In-force'], 'prov': int(r['Provisions']) if r['Provisions'].isdigit() else None, 'title': title,
                     'folder': f'{k}/{y}/dv{iss:03d}-{mat}'})
print('acts', len(ACTS), collections.Counter(a['k'] for a in ACTS), 'other authors', dict(OTHER_AUTHORS))

# the day of each Gazette issue, from the acts printed in it
ISSUE_DAY = {}
for a in ACTS:
    if a['pub']:
        ISSUE_DAY.setdefault((a['y'], a['iss']), a['pub'])


def issue_day(y, n):
    """The day of issue n of year y; an issue no act gives a day for takes the day of the nearest earlier issue."""
    if (y, n) in ISSUE_DAY:
        return ISSUE_DAY[(y, n)]
    lo = [k for k in ISSUE_DAY if k[0] == y and k[1] < n]
    if lo:
        return ISSUE_DAY[max(lo)]
    hi = [k for k in ISSUE_DAY if k[0] == y and k[1] > n]
    return ISSUE_DAY[min(hi)] if hi else f'{y}-06-30'


# ------------------------------------------------------------------ 2. acts held back (in scope, not in the history)
HELD_ALL = json.load(open(os.path.join(R, 'data', 'held.json'), encoding='utf-8'))['acts']
# held.json ids are State Gazette material ids; laws in the history are named by the National Assembly's own ids,
# so laws are matched by issue and title only
built_ids = {(a['k'], a['mat']) for a in ACTS if a['k'] not in ('zakon', 'kodeks')}
built_keys = {(a['k'], a['y'], a['iss'], ntitle(a['title'])) for a in ACTS}
HELD, HELD_OUTSIDE = [], []
for h in HELD_ALL:
    n, y = h['gazette'].split('/')
    y, n = int(y), int(n)
    if (h['kind'], h['id']) in built_ids or (h['kind'], y, n, ntitle(h['title'])) in built_keys:
        continue  # appended to the history since held.json was written
    if h['reason'] == 'kind_outside_its_section':
        HELD_OUTSIDE.append(h)
        continue  # printed outside the section of its kind: the IMO maritime codes listed as "kodeks", for example; not acts of that kind
    HELD.append({'k': h['kind'], 'y': y, 'iss': n, 'title': h['title'].strip(), 'reason': h['reason']})
print('held', len(HELD_ALL), 'still held', len(HELD), collections.Counter(h['k'] for h in HELD))

# ------------------------------------------------------------------ 3. every law the record knows (history + laws.csv + held)
LAWS = {}  # (y, iss, ntitle) -> law
for a in ACTS:
    if a['k'] in ('zakon', 'kodeks'):
        LAWS[(a['y'], a['iss'], ntitle(a['title']))] = {'title': a['title'], 'y': a['y'], 'iss': a['iss'], 'pub': a['pub'], 'en': a['en'],
                                                         'inf': a['inf'], 'src': 'text', 'folder': a['folder']}
n_csv = 0
with open(os.path.join(R, 'data', 'laws.csv'), encoding='utf-8') as fh:
    for r in csv.DictReader(fh):
        m = re.match(r'^(zakon|kodeks)-(\d{4})-dv(\d+)-\d+$', r['key'])
        if not m:
            continue
        n_csv += 1
        y, n = int(m.group(2)), int(m.group(3))
        key = (y, n, ntitle(r['title']))
        if key in LAWS:
            L0 = LAWS[key]
            L0['en'] = L0['en'] or r['enacted']
            L0['inf'] = L0['inf'] or r['in_force_days']
            continue
        LAWS[key] = {'title': r['title'].strip(), 'y': y, 'iss': n, 'pub': r['published'], 'en': r['enacted'], 'inf': r['in_force_days'], 'src': 'record'}
for h in HELD:
    if h['k'] in ('zakon', 'kodeks'):
        key = (h['y'], h['iss'], ntitle(h['title']))
        if key not in LAWS:
            LAWS[key] = {'title': h['title'], 'y': h['y'], 'iss': h['iss'], 'pub': issue_day(h['y'], h['iss']), 'en': '', 'inf': '', 'src': 'held'}
for L0 in LAWS.values():
    if not L0['pub']:
        L0['pub'] = issue_day(L0['y'], L0['iss'])
print('laws in the record', len(LAWS), collections.Counter(L0['src'] for L0 in LAWS.values()), 'laws.csv rows', n_csv)
PROFILE['laws_record'] = len(LAWS)
PROFILE['laws_text'] = sum(1 for L0 in LAWS.values() if L0['src'] == 'text')


def law_type(t):
    t = t.strip()
    if re.match(r'^Закон\w*\s+за\s+(ратифициране|денонсиране|присъединяване|приемане на (?:декларация|Декларация)|оттегляне)', t):
        return 'treaty'
    if re.match(r'^(Закон|Кодекс)\w*\s+за\s+(изм|им|доп)\w*', t) or re.match(r'^Законопроект за (изм|доп)', t):
        return 'amend'
    if re.match(r'^Закон за (държавния бюджет|бюджета на|събирането на приходи и извършването на разходи)', t):
        return 'budget'
    return 'new'


for L0 in LAWS.values():
    L0['type'] = law_type(L0['title'])
    L0['adopt'] = L0['en'] or (D(L0['pub']) - timedelta(days=12)).isoformat()  # held laws: no adoption day; the median lag is 12 days
print('law types', collections.Counter(L0['type'] for L0 in LAWS.values()))

# ------------------------------------------------------------------ I. The National Assembly
# first sittings of the National Assemblies (the 52nd: the day it elected its chairman, reshenie/2026/dv041-243227)
ASSEMBLIES = [(39, '2001-07-05'), (40, '2005-07-11'), (41, '2009-07-14'), (42, '2013-05-21'), (43, '2014-10-27'), (44, '2017-04-19'),
              (45, '2021-04-15'), (46, '2021-07-21'), (47, '2021-12-03'), (48, '2022-10-19'), (49, '2023-04-12'), (50, '2024-06-19'),
              (51, '2024-11-11'), (52, '2026-04-30')]
BUILT = os.environ.get('BUILT_DAY') or max(a['pub'] for a in ACTS if a['pub'])  # the newest Gazette day in the record


def assembly_of(day):
    n = None
    for no, start in ASSEMBLIES:
        if start <= day:
            n = no
    return n


c01 = []
law_list = sorted(LAWS.values(), key=lambda L0: L0['adopt'])
for i, (no, start) in enumerate(ASSEMBLIES):
    end = ASSEMBLIES[i + 1][1] if i + 1 < len(ASSEMBLIES) else BUILT
    ls = [L0 for L0 in law_list if start <= L0['adopt'] < end]
    if no == 39:
        ls = [L0 for L0 in ls if L0['y'] >= 2003]
    tc = collections.Counter(L0['type'] for L0 in ls)
    c01.append({'n': no, 'start': start, 'end': end, 'laws': len(ls), 'first': ls[0]['adopt'] if ls else None, 'last': ls[-1]['adopt'] if ls else None,
                'types': dict(tc), 'dated': sum(1 for L0 in ls if L0['en']), 'partial': no in (39, 52)})
    # the boundary falls in a gap: no law adopted between the last law of this assembly and the first sitting of the next
    print('assembly', no, start, end, len(ls), ls[0]['adopt'] if ls else '', ls[-1]['adopt'] if ls else '', dict(tc))
OUT['c01'] = {'rows': c01, 'record_start': '2003-01-01', 'built': BUILT}

# c02: the calendar of adoption: laws adopted each month (adoption day from the history or laws.csv)
cal = collections.Counter()
for L0 in LAWS.values():
    if L0['en'] and 2004 <= int(L0['en'][:4]) <= LAST_YEAR:
        cal[(int(L0['en'][:4]), int(L0['en'][5:7]))] += 1
n_cal = sum(cal.values())
OUT['c02'] = {'cells': [[y, m, n] for (y, m), n in sorted(cal.items())], 'n': n_cal, 'built': BUILT,
              'undated': sum(1 for L0 in LAWS.values() if not L0['en'] and L0['y'] >= 2004)}
print('c02', n_cal, 'dec', sum(n for (y, m), n in cal.items() if m == 12), 'aug', sum(n for (y, m), n in cal.items() if m == 8))

# c03: what the laws of each assembly do (types), from c01
# c04: the State Budget Act of each year: when it was promulgated and took effect; extension laws
c04 = {}
for L0 in LAWS.values():
    m = re.match(r'^Закон за държавния бюджет на Република България за (\d{4}) г\.?$', L0['title'].strip())
    if m:
        by = int(m.group(1))
        c04.setdefault(by, {}).update({'y': by, 'pub': L0['pub'], 'en': L0['en'], 'inf': L0['inf'] or None, 'src': L0['src'], 'iss': L0['iss'], 'iy': L0['y']})
    m = re.match(r'^Закон за събирането на приходи и извършването на разходи през (\d{4}) г\.', L0['title'].strip())
    if m:
        by = int(m.group(1))
        c04.setdefault(by, {'y': by}).update({'ext_pub': L0['pub'], 'ext_inf': L0['inf'] or None, 'ext_en': L0['en']})
OUT['c04'] = [c04[y] for y in sorted(c04) if y >= 2004]
for r in OUT['c04']:
    print('c04', r)

# ------------------------------------------------------------------ II. How laws are amended: the texts of the laws
# An amending clause opens a provision with "В <закона> (обн., ДВ, бр. ...; изм., ...)" or "<Законът> (...) се отменя";
# the bracket lists the issue of the State Gazette that first published the law and every issue that amended it since.
TARGET_START = re.compile(r'^(?:В|Във)\s+(?=(?:Закона|Кодекса|Указ|[А-Я][а-я-]+(?:ия|ния)\s+(?:[а-я-]+\s+)?(?:кодекс|закон))\b)')
REPEAL_START = re.compile(r'^(?:Законът|Кодексът)\s+')
TITLE_T = re.compile(r'^(?:Закон|Кодекс)\w*\s+за\s+(?:изменение\s+и\s+допълнение|изменения\s+и\s+допълнения|изменение|допълнение|допълнения|изменения)\s+на\s+(?P<t>.+)$')
SEC_RX = re.compile(r'(преходн|заключителн|допълнителн)', re.I)


def norm_target(s):
    s = s.replace('„', '"').replace('“', '"').replace('”', '"').replace(' ', ' ')
    s = re.sub(r'\s+', ' ', s).strip().rstrip(',').strip()
    w = s.split(' ')
    w[0] = {'Законът': 'Закона', 'Кодексът': 'Кодекса'}.get(w[0], w[0])
    s = ' '.join(w).lower()
    s = re.sub(r'(\w)ият\b', r'\1ия', s)
    return s.replace('"', '').replace('вът-решните', 'вътрешните')


def balanced(s, i):
    d = 0
    for j in range(i, min(len(s), i + 30000)):
        if s[j] == '(':
            d += 1
        elif s[j] == ')':
            d -= 1
            if d == 0:
                return j + 1
    return -1


def parse_clause(body):
    """The first words of a provision -> (amend | repeal | cite, target, citation) or None."""
    t = body.lstrip().replace('(oбн', '(обн')
    m = TARGET_START.match(t)
    kind = 'amend'
    if not m:
        m = REPEAL_START.match(t)
        kind = 'repeal'
        if not m:
            return None
    i = t.find('(', m.end())
    if i < 0 or i - m.end() > 400:
        return None
    j = balanced(t, i)
    if j < 0:
        return None
    cit = t[i + 1:j - 1]
    if not re.match(r'^\s*(обн|ДВ|Изв)', cit):
        return None
    target = t[m.end():i] if kind == 'amend' else t[:i]
    if kind == 'repeal' and 'се отменя' not in t[j:j + 80]:
        kind = 'cite'
    return kind, norm_target(target), cit


ISS = re.compile(r'бр\.\s*((?:\d+\s*(?:,|и)\s*)*\d+)\s*от\s*(\d{4})\s*г')


def parse_cit(cit):
    """'обн., ДВ, бр. 26 от 1968 г.; попр., ...; изм., бр. 92 от 1969 г., бр. 26 и 27 от 1973 г.; Решение № 19 на
    Конституционния съд от 1995 г. - бр. 97 от 1995 г.; ...' -> first issue, amending issues, corrections, Court decisions."""
    out = {'orig': None, 'gaz': None, 'amend': set(), 'corr': set(), 'ks': set()}
    cur = 'amend'
    for seg in cit.split(';'):
        s = seg.strip()
        if not s:
            continue
        low = s.lower()
        if 'конституционния съд' in low:
            for m in re.finditer(r'Решение\s*№\s*(\d+)', s):
                yy = re.search(r'от\s*(\d{4})\s*г', s[m.end():m.end() + 60])
                bb = list(ISS.finditer(s))
                iy = int(bb[-1].group(2)) if bb else None
                out['ks'].add((int(m.group(1)), int(yy.group(1)) if yy else iy))
            # some citations write "бр. 98 от 2000 г. - Решение № 14 ... от 2000 г., бр. 41 и 101 от 2001 г., ..."
            rest = re.split(r'Конституционния съд от \d{4} г\.', s)[-1]
            rest = re.sub(r'^\s*-\s*бр\.\s*\d+\s*от\s*\d{4}\s*г\.?', '', rest)
            for m in ISS.finditer(rest):
                for n in re.findall(r'\d+', m.group(1)):
                    out['amend'].add((int(m.group(2)), int(n)))
            continue
        if low.startswith('обн') or (out['orig'] is None and re.match(r'^(дв|изв)', low)):
            m = ISS.search(s)
            if m:
                out['orig'] = (int(m.group(2)), int(re.findall(r'\d+', m.group(1))[0]))
                out['gaz'] = 'Изв' if re.search(r'\bизв', low[:14]) else 'ДВ'
            cur = 'amend'
            continue
        if low.startswith('попр'):
            cur = 'corr'
        elif re.match(r'^(изм|доп|отм)', low):
            cur = 'amend'
        for m in ISS.finditer(s):
            for n in re.findall(r'\d+', m.group(1)):
                out[cur].add((int(m.group(2)), int(n)))
    return out


def iter_acts(path):
    """(folder, {file: text}) for each act folder of texts.jsonl; the files of one folder are contiguous (git ls-tree order)."""
    cur, files = None, {}
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            d = json.loads(line)
            parts = d['p'].split('/')
            law = parts[0] in ('zakon', 'kodeks')
            folder = '/'.join(parts[:3]) if law else parts[0]
            if folder != cur:
                if cur:
                    yield cur, files
                cur, files = folder, {}
            files['/'.join(parts[3:]) if law else '/'.join(parts[1:])] = d['t']
    if cur:
        yield cur, files


def provisions(files):
    """[(label, section, text)] in the order of the act's README; headings set the section."""
    rd = files.get('README.md', '')
    out, sec = [], 'main'
    for m in re.finditer(r'^\| ([^|]+?) \| \[([^\]]+)\]', rd, re.M):
        lab, f = m.group(1).strip(), m.group(2)
        if 'heading' in f:
            if SEC_RX.search(lab):
                sec = lab
            continue
        out.append((lab, sec, re.sub(r'^#.*\n', '', files.get(f, ''), count=1)))
    return out


def split_fulltext(t):
    """Acts kept as one full text (as printed in the Gazette): split at '§ N.' and 'Чл. N.' and at section headings."""
    out, sec, cur, buf = [], 'main', None, []
    for ln in t.split('\n'):
        s = ln.strip()
        if re.match(r'^(ПРЕХОДНИ|ЗАКЛЮЧИТЕЛН|ДОПЪЛНИТЕЛН)', s) or re.match(r'^(Преходн|Заключителн|Допълнителн)\w* разпоредб', s):
            if cur:
                out.append((cur, sec, '\n'.join(buf)))
            cur, buf, sec = None, [], s
            continue
        m = re.match(r'^(§|Чл\.)\s*(\d+[а-я]?)\.\s*(.*)$', s)
        if m:
            if cur:
                out.append((cur, sec, '\n'.join(buf)))
            cur, buf = f'{m.group(1)} {m.group(2)}', [m.group(3)] if m.group(3) else []
            continue
        if cur is not None:
            buf.append(s)
    if cur:
        out.append((cur, sec, '\n'.join(buf)))
    return out


# EU acts: directives (year/number) and regulations (number/year before 2015 with "№", year/number after)
DIR = re.compile(r'Директив[аи]\s+(?:\((?:ЕС|ЕО)\)\s*)?(?:№\s*)?((?:19|20)?\d{2})/(\d+)')
REG_OLD = re.compile(r'Регламент(?:а|и)?\s+(?:за изпълнение\s+|делегиран\s+)?(?:\((?:ЕС|ЕО|ЕИО|Евратом)(?:,\s*Евратом)?\)\s*)?№\s*(\d+)/((?:19|20)?\d{2})\b')
REG_NEW = re.compile(r'Регламент(?:а|и)?\s+(?:за изпълнение\s+|делегиран\s+)?\((?:ЕС|ЕС,\s*Евратом)\)\s*(20\d{2})/(\d+)')
TRANS = re.compile(r'въвежда|въвеждат|транспонира', re.I)
IMPL = re.compile(r'мерки по прилагането на', re.I)
LEV = re.compile(r'\d[\d\s .,]*\s*(?:хил\.\s*|млн\.\s*|млрд\.\s*)?(?:лв\b|лева\b|лев\b)')
EUR = re.compile(r'\d[\d\s .,]*\s*(?:хил\.\s*|млн\.\s*|млрд\.\s*)?(?:евро\b|EUR\b)')


def yr(s):
    y = int(s)
    return y + 1900 if 50 <= y < 100 else (y + 2000 if y < 50 else y)


ACT_BY_FOLDER = {a['folder']: a for a in ACTS}
CITS = collections.defaultdict(list)        # target -> [(published, citation)]
AMEND_BY = collections.defaultdict(set)     # target -> {(year, issue)} of the acts in the history that amend it
VEHICLES, EU_ROWS, MONEY = [], [], collections.defaultdict(collections.Counter)
EU_COUNT = collections.Counter()
OTHER_SEC = collections.Counter()           # where a clause amending another law stands: transitional/final/supplementary provisions or the body
REPEALED = {}                               # law -> (the law in the history that repeals it, its year)
CONST_FILES = {}
n_text_laws = 0
for folder, files in iter_acts(os.path.join(B, 'texts.jsonl')):
    if folder == 'konstitutsiya':
        CONST_FILES = files
        continue
    a = ACT_BY_FOLDER.get(folder)
    if not a:
        print('no act for', folder)
        continue
    n_text_laws += 1
    pub = a['pub'] or issue_day(a['y'], a['iss'])
    tt = TITLE_T.match(a['title'])
    own = norm_target(re.sub(r'\s*\(.*$', '', tt.group('t'))) if tt else None
    if own:
        AMEND_BY[own].add((a['y'], a['iss']))
        uv = files.get('uvod.md', '')
        i = uv.find('(')
        if i >= 0:
            j = balanced(uv, i)
            if j > 0 and re.match(r'^\s*[оo]бн', uv[i + 1:i + 6]):
                CITS[own].append((pub, uv[i + 1:j - 1].replace('oбн', 'обн')))
    if 'README.md' in files and any(f.startswith(('par-', 'art-')) for f in files):
        provs = provisions(files)
    else:
        provs = split_fulltext(next((t for f, t in files.items() if f.startswith('full-text')), ''))
    others = set()
    for lab, sec, txt in provs:
        c = parse_clause(txt)
        if not c:
            continue
        kind, T, cit = c
        CITS[T].append((pub, cit))
        if kind == 'repeal':
            REPEALED.setdefault(T, (a['title'], a['y']))
        if kind in ('amend', 'repeal'):
            AMEND_BY[T].add((a['y'], a['iss']))
            if T != own and not re.match(r'^закона за (изменение|допълнение)', T):
                others.add(T)  # another law (amendments to an earlier amending act's own provisions are left out)
                OTHER_SEC['pzr' if sec != 'main' else 'main'] += 1
    VEHICLES.append({'title': a['title'], 'y': a['y'], 'pub': pub, 'n': len(others), 'own': own, 'targets': sorted(others)})
    if law_type(a['title']) == 'treaty':
        continue
    body = '\n'.join(t for f, t in files.items() if f != 'README.md')
    eu = set()
    for m in DIR.finditer(body):
        eu.add(('D', yr(m.group(1)), int(m.group(2))))
    for m in REG_OLD.finditer(body):
        eu.add(('R', yr(m.group(2)), int(m.group(1))))
    for m in REG_NEW.finditer(body):
        eu.add(('R', int(m.group(1)), int(m.group(2))))
    paras = body.split('\n')
    trans = any(TRANS.search(p) and DIR.search(p) for p in paras)
    impl = any(IMPL.search(p) and (REG_OLD.search(p) or REG_NEW.search(p)) for p in paras)
    EU_ROWS.append({'y': a['y'], 'cat': 'trans' if trans else 'impl' if impl else 'mention' if eu else 'none'})
    for e in eu:
        EU_COUNT[e] += 1
    MONEY[a['y']]['lev'] += len(LEV.findall(body))
    MONEY[a['y']]['eur'] += len(EUR.findall(body))
    MONEY[a['y']]['laws'] += 1
print('law texts', n_text_laws, 'targets', len(CITS), 'amended targets', len(AMEND_BY))


# ------------------------------------------------------------------ the amendment record of every law amended in the texts
def stems(s):
    return {w[:5] for w in re.findall(r'[а-яa-z]+', s) if len(w) > 3} - {'закон', 'кодек'}


def jacc(a, b):
    a, b = stems(a), stems(b)
    return len(a & b) / max(1, len(a | b))


REC = {}
for T in set(CITS) | set(AMEND_BY):
    if re.match(r'^закона за (изменение|допълнение)', T) or ':' in T or len(T) < 12:
        continue  # amendments to an earlier amending act's own provisions, and parse leftovers
    cs = sorted(CITS.get(T, []), key=lambda x: (x[0], len(x[1])))
    p = parse_cit(cs[-1][1]) if cs else parse_cit('')
    REC[T] = {'names': {T: len(cs)}, 'orig': p['orig'], 'gaz': p['gaz'], 'cit_amend': p['amend'], 'ks': p['ks'],
              'built': set(AMEND_BY.get(T, ())), 'last_cit': cs[-1][0] if cs else None, 'n_cit': len(cs)}
# one law under several names (renamed, or spelled differently): the same first issue and similar names
groups = collections.defaultdict(list)
for T, r in REC.items():
    groups[r['orig']].append(T)
LAWREC = []
for o, ts in groups.items():
    ts = sorted(ts, key=lambda t: -REC[t]['n_cit'])
    clusters = []
    for t in ts:
        for c in clusters:
            a_, b_ = stems(t), stems(c[0])
            if o is not None and (jacc(t, c[0]) >= 0.5 or (a_ and (a_ <= b_ or b_ <= a_))):
                c.append(t)
                break
        else:
            clusters.append([t])
    for c in clusters:
        rs = [REC[t] for t in c]
        best = max(rs, key=lambda r: (r['last_cit'] or '', r['n_cit']))
        amend = set(best['cit_amend'])
        for r in rs:
            amend |= r['built']
        names = collections.Counter()
        for r in rs:
            names.update(r['names'])
        LAWREC.append({'name': names.most_common(1)[0][0], 'names': list(names), 'orig': o, 'gaz': best['gaz'],
                       'amend': sorted(x for x in amend if o is None or x > o), 'ks': sorted(set().union(*[r['ks'] for r in rs])),
                       'last_cit': best['last_cit']})
print('laws with an amendment record', len(LAWREC), 'merged from', len(REC))

# the laws whose title says they amend a given law, by issue (the record of every law, with or without text)
TITLE_TARGETS = collections.defaultdict(list)
for L0 in LAWS.values():
    m = TITLE_T.match(L0['title'].strip())
    if m:
        TITLE_TARGETS[(L0['y'], L0['iss'])].append(norm_target(re.sub(r'\s*\(.*$', '', m.group('t'))))


def own_in_issue(rec, y, n):
    """Did issue n of year y print a law titled as amending this law?"""
    for tt in TITLE_TARGETS.get((y, n), ()):
        if tt in rec['names'] or any(jacc(tt, nm) >= 0.75 for nm in rec['names']):
            return True
    return False

# policy area of an amended law, read from its name (first rule that matches; "other" otherwise)
AREAS = [
    ('tax', r'данъ|акциз|митни|бюджет|публичните финанси|счетоводств|одит|кредитните институции|банк|застрахов|ценни книжа|финансови инструменти|финансов надзор|финансовия надзор|хазарт|валут|платежн|държавния дълг|приватизац|концеси|обществените поръчки|такси|облагане|пазарите на|колективн\w* инвестиц|пенсионноосигурител|осигурителни дружества|кредит'),
    ('social', r'осигуряв|здрав|лечебн|лекарств|медицин|социалн|труд|заетост|семейни помощи|увреждания|закрила на детето|пенси|кръвта|трансплант|аптеки|потребителите на|хората с'),
    ('justice', r'наказател|съдебн|процесуал|адвокат|нотари|съдебните изпълнители|частните съдебни|изпълнение на наказанията|вътрешните работи|полиц|чужденците|убежище|административните нарушения|корупц|отнемане|изпиране|арбитраж|отговорността на държавата|задълженията и договорите|собствеността|наследств|семейни|семейния|търговския регистър|лицата и семейството|юридическите лица|гражданск|особените залози|несъстоятелност|българските лични документи|документи за самоличност|гражданската регистрация|хулиганство|малолетните'),
    ('economy', r'енерг|търгов|конкуренц|инвестиц|туризм|защита на потребителите|съобщения|пощ|стандарт|измерван|промишлен|занаят|кооперац|движението по пътищата|движение по пътищата|автомобилн|железопът|въздухоплаване|корабоплаване|морск|пътищата|превоз|транспорт|електронн|нефт|природния газ|ядрена|подземните богатства|храни|тютюн|вино|спиртни|оръжия|техническите изисквания|малките и средните|насърчаване|счетоводството|регистрация|рекламата|киберсигурност|интернет|туризма'),
    ('land', r'устройство на територията|устройството на територията|кадастър|водите|горите|околната среда|отпадъц|земедел|ветеринар|растения|рибарство|защитените|почва|биологичното|черноморското|лова|пасищ|селскостопан|климат|атмосферния въздух|шума|химичн|генетично|животн|аквакулт|подпомагане на земеделските|собствеността и ползването на земеделските|зърно|посевния|фуражите|пчел'),
    ('state', r'изборн|избор|държавния служител|администрация|местното самоуправление|отбраната|въоръжен|национална сигурност|разузнаване|сметната палата|омбудсман|нормативните актове|държавната собственост|общинската собственост|министерския|президент|народното събрание|референдум|допитване|статистик|архив|класифицираната информация|достъп до обществена|държавна агенция|защита при бедствия|военн|резерв|охрана|защита на личните данни|конфликт на интереси|сигурност|кризи|административно-териториалното|областите|столичната община|гражданската защита|държавния вестник|държавен вестник|президента'),
    ('education', r'образование|училищ|висшето|наук|култур|радио|телевиз|спорт|вероизповедания|авторско|паметници|музеи|библиотек|младежта|читалищ|медии|книжовн|академи'),
]


def area_of(name):
    return next((k for k, rx in AREAS if re.search(rx, name)), 'other')


Y0, Y1 = 2004, LAST_YEAR
for r in LAWREC:
    r['area'] = area_of(r['name'])
    r['ev'] = [(y, n) for (y, n) in r['amend'] if Y0 <= y <= Y1]
    r['own_ev'] = {(y, n) for (y, n) in r['ev'] if own_in_issue(r, y, n)}
print('areas', collections.Counter(r['area'] for r in LAWREC))
print('other-area laws', [r['name'] for r in sorted(LAWREC, key=lambda r: -len(r['ev'])) if r['area'] == 'other'][:40])

# c05: every amendment of a law, by year: made by a law titled as amending it, or inside another law
c05y = collections.defaultdict(collections.Counter)
c05a = collections.defaultdict(collections.Counter)
for r in LAWREC:
    for (y, n) in r['ev']:
        k = 'own' if (y, n) in r['own_ev'] else 'other'
        c05y[y][k] += 1
        c05a[r['area']][k] += 1
OUT['c05'] = {'years': [{'y': y, 'own': c05y[y]['own'], 'other': c05y[y]['other']} for y in range(Y0, Y1 + 1)],
              'areas': [{'k': k, 'own': c05a[k]['own'], 'other': c05a[k]['other'], 'laws': sum(1 for r in LAWREC if r['area'] == k and r['ev'])}
                        for k in [a[0] for a in AREAS] + ['other']],
              'laws': sum(1 for r in LAWREC if r['ev']), 'sec': dict(OTHER_SEC)}
T5 = sum(c05y[y]['own'] + c05y[y]['other'] for y in c05y)
print('c05', T5, 'other share %.1f' % (100 * sum(c05y[y]['other'] for y in c05y) / T5), [(y, c05y[y]['own'], c05y[y]['other']) for y in range(Y0, Y1 + 1)])
print('c05 areas', OUT['c05']['areas'])

# c06: the laws (in the texts) whose provisions amended the most other laws
VEHICLES.sort(key=lambda v: (-v['n'], v['pub']))
OUT['c06'] = {'top': [{'title': v['title'], 'y': v['y'], 'pub': v['pub'], 'n': v['n'], 'amending': bool(v['own'])} for v in VEHICLES[:16]],
              'hist': collections.Counter(min(v['n'], 20) for v in VEHICLES if v['n']), 'laws': len(VEHICLES),
              'with': sum(1 for v in VEHICLES if v['n']), 'total': sum(v['n'] for v in VEHICLES)}
OUT['c06']['hist'] = sorted(OUT['c06']['hist'].items())
for v in VEHICLES[:16]:
    print('c06', v['n'], v['y'], v['title'][:100])

# c07: the most-amended laws, 2004-2026, by year
top = sorted([r for r in LAWREC if r['ev']], key=lambda r: (-len(r['ev']), r['name']))[:25]
OUT['c07'] = [{'name': r['name'], 'orig': r['orig'], 'n': len(r['ev']), 'all': len(r['amend']),
               'by': dict(collections.Counter(y for y, n in r['ev'])), 'own': len(r['own_ev'])} for r in top]
for r in OUT['c07']:
    print('c07', r['n'], r['all'], r['orig'], r['name'])

# c08: how many times a year each law was amended
c08 = collections.defaultdict(collections.Counter)
for r in LAWREC:
    for y, k in collections.Counter(y for y, n in r['ev']).items():
        c08[y]['1' if k == 1 else '2' if k == 2 else '3-4' if k <= 4 else '5+'] += 1
OUT['c08'] = [{'y': y, **c08[y]} for y in range(Y0, Y1 + 1)]
print('c08', OUT['c08'])

# c09: the codes, from their first publication: every issue that amended them
CODES = ['наказателния кодекс', 'кодекса на труда', 'кодекса за социално осигуряване', 'данъчно-осигурителния процесуален кодекс',
         'наказателно-процесуалния кодекс', 'гражданския процесуален кодекс', 'административнопроцесуалния кодекс', 'изборния кодекс']
c09 = []
for nm in CODES:
    r = next((r for r in LAWREC if nm in r['names']), None)
    if not r:
        print('c09 missing', nm)
        continue
    c09.append({'name': nm, 'orig': r['orig'], 'orig_day': issue_day(*r['orig']) if r['orig'] and r['orig'][0] >= 2003 else None,
                'amend': [[y, n, issue_day(y, n) if y >= 2003 else None] for (y, n) in r['amend']], 'ks': r['ks']})
    print('c09', nm, r['orig'], len(r['amend']), r['amend'][:3], r['amend'][-3:])
OUT['c09'] = c09

# c10: laws first published before 1990 and amended since 2004
old = [r for r in LAWREC if r['orig'] and r['orig'][0] < 1990 and r['ev']]
OUT['c10'] = sorted([{'name': r['name'], 'orig': r['orig'], 'gaz': r['gaz'],
                      'p1': sum(1 for y, n in r['amend'] if y < 1990), 'p2': sum(1 for y, n in r['amend'] if 1990 <= y < Y0),
                      'p3': len(r['ev']), 'last': max(y for y, n in r['amend']),
                      'rep': next((REPEALED[n] for n in r['names'] if n in REPEALED), None)} for r in old], key=lambda r: (r['orig'][0], r['name']))
for r in OUT['c10']:
    print('c10', r)
era = collections.defaultdict(collections.Counter)
for r in LAWREC:
    if not r['orig']:
        continue
    e = 'pre90' if r['orig'][0] < 1990 else 'p90s' if r['orig'][0] < 2000 else 'p00s' if r['orig'][0] < 2007 else 'eu'
    for y, n in r['ev']:
        era[y][e] += 1
OUT['c10_era'] = [{'y': y, **era[y]} for y in range(Y0, Y1 + 1)]

# c12: Constitutional Court decisions recorded in the amendment records of the laws
ks = collections.defaultdict(set)
for r in LAWREC:
    for no, y in r['ks']:
        if y:
            ks[(no, y)].add(r['name'])
OUT['c12'] = {'years': [[y, sum(1 for (no, yy) in ks if yy == y)] for y in range(1991, LAST_YEAR + 1)],
              'n': len(ks), 'laws': len({n for s in ks.values() for n in s}),
              'top': sorted([[r['name'], len({k for k in r['ks'] if k[1]})] for r in LAWREC if r['ks']], key=lambda x: -x[1])[:12]}
print('c12', OUT['c12']['n'], OUT['c12']['laws'], OUT['c12']['years'], OUT['c12']['top'])

# ------------------------------------------------------------------ III. The Constitution
CH_START = []
for f, t in CONST_FILES.items():
    m = re.match(r'^art-(\d{3})-0-heading-1\.md$', f)
    if m:
        CH_START.append((int(m.group(1)), t.split('\n')[0].lstrip('# ').strip(), (t.split('\n') + [''])[1].strip()))
CH_START.sort()
print('chapters', CH_START)


def chapter_of(f):
    m = re.match(r'^art-(\d{3})', f)
    if not m:
        return len(CH_START)  # the transitional and final provisions
    n = int(m.group(1))
    return max(i for i, (s, _, _) in enumerate(CH_START) if s <= n)


units = collections.Counter()
for f in CONST_FILES:
    if f.endswith('.md') and f != 'README.md' and 'heading' not in f:
        units[chapter_of(f)] += 1
EVENTS = {'2015-12-21': 'v2015', '2023-12-25': 'v2023', '2024-08-09': 'v2024'}
chg = collections.defaultdict(collections.Counter)
with open(os.path.join(B, 'const.tsv'), encoding='utf-8') as fh:
    for line in fh:
        sha, email, day, inf, st, f = line.rstrip('\n').split('\t')
        f = f.split('/')[-1]
        if day in EVENTS and f != 'README.md' and 'heading' not in f:
            chg[EVENTS[day]][chapter_of(f)] += 1
OUT['c11'] = {'chapters': [{'i': i, 'name': nm, 'title': ti, 'units': units[i], **{k: chg[k][i] for k in EVENTS.values()}} for i, (s, nm, ti) in enumerate(CH_START)] +
              [{'i': len(CH_START), 'name': 'ПЗР', 'title': 'ПРЕХОДНИ И ЗАКЛЮЧИТЕЛНИ РАЗПОРЕДБИ', 'units': units[len(CH_START)], **{k: chg[k][len(CH_START)] for k in EVENTS.values()}}],
              'placeholder_2023': sum(1 for f in CONST_FILES if f.endswith('.md') and False)}
print('c11', OUT['c11'])

# ------------------------------------------------------------------ IV. The executive and the State Gazette
KIND5 = {'zakon': 'law', 'kodeks': 'law', 'postanovlenie': 'decree', 'naredba': 'ordinance', 'pravilnik': 'rules', 'instruktsiya': 'instruction'}
# c13: acts of the official section per year, by kind: in the history, and held back
c13 = collections.defaultdict(collections.Counter)
for L0 in LAWS.values():  # the laws: the same record as section I (with text, held back, or only in laws.csv)
    c13[L0['y']]['law'] += 1
    if L0['src'] != 'text':
        c13[L0['y']]['notext'] += 1
for a in ACTS:
    if a['k'] not in ('zakon', 'kodeks'):
        c13[a['y']][KIND5[a['k']]] += 1
for h in HELD:
    if h['k'] not in ('zakon', 'kodeks'):
        c13[h['y']][KIND5[h['k']]] += 1
        c13[h['y']]['notext'] += 1
OUT['c13'] = [{'y': y, **c13[y]} for y in range(2003, LAST_YEAR + 1)]
PROFILE['acts'] = len(ACTS)
PROFILE['held'] = len(HELD)
print('c13', OUT['c13'][:3], OUT['c13'][-2:])

# c14: the issues of the State Gazette by weekday (issues that carry at least one act of the history)
c14 = collections.defaultdict(collections.Counter)
for (y, n), d in ISSUE_DAY.items():
    c14[y][D(d).weekday()] += 1
OUT['c14'] = [{'y': y, 'wd': [c14[y][i] for i in range(7)], 'max_no': max(n for (yy, n) in ISSUE_DAY if yy == y)} for y in range(2003, LAST_YEAR + 1)]
PROFILE['issues'] = len(ISSUE_DAY)
print('c14', sum(sum(r['wd']) for r in OUT['c14']), sum(r['wd'][1] + r['wd'][4] for r in OUT['c14']))


# c15: what the Council of Ministers' decrees do, read from their titles
def decree_kind(title):
    t = re.sub(r'^Постановление\s*№\s*\S+\s+от\s+\d+\s+\S+\s+\d{4}\s*г\.\s*', '', title.strip()).lower()
    if (re.match(r'^за (одобряване|предоставяне|осигуряване|разрешаване|възстановяване|извършване|отпускане|увеличаване|финансиране)\b.*\b(разход|трансфер|средства|бюджет|промени|финансов|кредит)', t)
            or re.match(r'^за одобряване на (вътрешнокомпенсирани|допълнителн|промени в|целев)', t)):
        return 'spend'
    if re.match(r'^за (изменение|допълнение|изменения|отменяне|отмяна)\b', t):
        return 'amend'
    if re.match(r'^за (приемане|одобряване|утвърждаване) на (наредба|правилник|устройствен|тарифа|методика|инструкция|правила|списък|норми|класификатор|стандарт|изисквания|номенклатура)', t):
        return 'rules'
    return 'other'


c15 = collections.defaultdict(collections.Counter)
for a in ACTS:
    if a['k'] == 'postanovlenie':
        c15[a['y']][decree_kind(a['title'])] += 1
for h in HELD:
    if h['k'] == 'postanovlenie':
        c15[h['y']][decree_kind(h['title'])] += 1
OUT['c15'] = [{'y': y, **c15[y]} for y in range(2003, LAST_YEAR + 1)]
print('c15', [(r['y'], r.get('spend', 0), sum(v for k, v in r.items() if k != 'y')) for r in OUT['c15']])

# c16: the day an act takes effect, against the day the Gazette published it
c16 = collections.defaultdict(collections.Counter)
adopt_day = collections.Counter()
for a in ACTS:
    if not (a['pub'] and a['inf']):
        continue
    d = (D(a['inf']) - D(a['pub'])).days
    b = 'before' if d < 0 else 'same' if d == 0 else 'd12' if d < 3 else 'd3' if d == 3 else 'm1' if d <= 31 else 'later'
    c16[KIND5[a['k']]][b] += 1
    if d < 0 and a['k'] == 'postanovlenie' and a['en'] and a['inf'] == a['en']:
        adopt_day['decree'] += 1
    if d < 0 and a['inf'][5:] == '01-01':
        adopt_day[KIND5[a['k']] + '_jan1'] += 1
OUT['c16'] = {'rows': [{'k': k, **c16[k]} for k in ('law', 'decree', 'ordinance', 'rules', 'instruction')], 'adopt_day': dict(adopt_day)}
print('c16', OUT['c16'])

# c17: what the ministers' ordinances are about, read from their titles (first rule that matches)
ORD_TOPIC = [
    ('qual', r'квалификация по професи'),
    ('health', r'здрав|медицин|лечеб|лечени|болнич|лекарств|аптек|фармак|терапевт|клиничн|заболяв|имуниз|кръв|трансплант|психиатр|дентал|стоматолог|епидем|заразн|'
               r'пациент|хоспис|лаборатор|санитарн|радиац|йонизиращ|диагност|тъкани|клетки|кърмачет|наркоти|стерилиз|дезинф|козмет|профилакти|диспансер'),
    ('food', r'ветеринар|животн|храни|храна|фураж|растени|семена|посевен|посадъч|зърн|земедел|горск|гори\b|горите|\bлов\b|дивеч|риб|пчел|тютюн|вино|лоз|'
             r'млечн|мляко|месо|пестицид|торове|агро|селскостопан|почв|аквакулт|картоф|сортове|породи|разсад|овощ|зеленчу|кланиц|болест|вредител|въшка|'
             r'карантин|пасищ|дървесин|подпомагане на площ|схеми и мерки за подпомагане|телета|хуманно отношение|неместни'),
    ('transport', r'превоз|автомобил|пътн|моторни|водач|железопът|въздух|летищ|кораб|морск|пристан|ремарке|трактор|типа на нов|въздухоплаване|пътищ|'
                  r'тахограф|шофьор|пилот|авиац|навигац|плавател|речн|дунав|транспорт|съобщени|пощенск|радиочестот|далекосъобщ|гуми|мотопед|мотоцикл|колесни'),
    ('social', r'социалн|помощ|закрила|детето|деца|увреждан|пенси|осигурителн\w* стаж|труд|работн\w* време|работодател|заетост|безработ|обезщет|майчинств|'
               r'семейни|стипенди|бежан|инвалид|ветеран|възрастни|отрезвяване|временно настаняване'),
    ('money', r'данъ|такс|мит|акциз|бюджет|счетовод|фискалн|касов|плащан|банк|застрах|осигур|възнагражд|заплат|командиров|финансов|кредит|разход|'
              r'държавни помощи|облаг|ценни книжа|цени\b|ценообраз|приход|лихв|валут|одит|гаранц|концеси|обществени поръчки|сметк|паричн|евро\b|еврото|'
              r'инвестиционни посредници|управляващите дружества|капиталов|ликвидност|игрално|хазарт|платежн'),
    ('build', r'строител|сград|проектиран|устройств|кадастр|геодез|картограф|нивелач|енерг|газ\b|газопр|природния газ|електр|топлин|отоплен|вод[аиоуне]|'
              r'канализ|околна|отпадъ|емиси|шум|химич|опасни|пожар|безопасност|технически|съоръжения|асансьор|котли|минни|подземни|ядрен|нефт|горива|'
              r'конструкци|бетон|стомана|благоустрой|климат|въздуха|озон|атмосфер|защитени|територи|инвестиционните проекти|курорт|възстановената собственост'),
    ('education', r'образован|училищ|учебн|ученици|студент|висше|детск|предучилищ|изпит|оценяване|възпитател|научн|докторант|учител|треньор|спорт|'
                  r'култур|музе|библиотек|читалищ|театр|филм|паметни|академи|младеж|туризъм|туристическ|език'),
    ('security', r'отбран|военн|въоръжен|вътрешните работи|полиц|класифицирана|охрана|оръжи|взрив|граничн|затвор|задържане|наказания|бедстви|'
                 r'гражданска защита|сигурност|миграц|чужденц|лични документи|документи за самоличност|8121'),
    ('admin', r'регистър|регистри|документ|удостоверен|печат|архив|служител|администрац|статистик|избор|адрес|гражданска регистрация|нотари|съдебн|съдии|'
              r'прокур|вещи лица|синдици|медиатор|търг|конкурс|достъп до|наград|отличи|знак|почетн|информационна система|електронн|служб|стаж|кадри|длъжност|'
              r'организацията и дейността|устройството и дейността|етичен|контрол|инспекц|проверк|санкци|стандартизац|акредитац|метролог|измерван|качеств|'
              r'сертифик|лиценз|разрешени|правоспособност|съдимост|гражданство|заповед за изпълнение|населените места'),
]


def ord_topic(title):
    t = title.lower()
    return next((k for k, rx in ORD_TOPIC if re.search(rx, t)), 'other')


PER = [(2003, 2006), (2007, 2010), (2011, 2014), (2015, 2018), (2019, 2022), (2023, LAST_YEAR)]
c17 = collections.defaultdict(lambda: {'new': 0, 'amend': 0, 'by': collections.Counter()})
ord_all = [(a['y'], a['title']) for a in ACTS if a['k'] == 'naredba'] + [(h['y'], h['title']) for h in HELD if h['k'] == 'naredba']
for y, t in ord_all:
    k = ord_topic(t)
    am = bool(re.search(r'^Наредба\w*\s+(?:№\s*\S+\s+)?(?:от\s+\d+\s+\S+\s+\d{4}\s*г\.\s*)?за\s+(изменение|допълнение|отменяне|отмяна)', t.strip(), re.I))
    c17[k]['amend' if am else 'new'] += 1
    c17[k]['by'][next(i for i, (p0, p1) in enumerate(PER) if p0 <= y <= p1)] += 1
OUT['c17'] = {'rows': sorted([{'k': k, 'new': v['new'], 'amend': v['amend'], 'by': [v['by'][i] for i in range(len(PER))]} for k, v in c17.items()],
                             key=lambda r: (r['k'] == 'other', -(r['new'] + r['amend']))),
              'periods': [f'{p0}–{p1}' for p0, p1 in PER], 'n': len(ord_all)}
print('c17', [(r['k'], r['new'], r['amend']) for r in OUT['c17']['rows']])
print('c17 other sample', [t[:90] for y, t in ord_all if ord_topic(t) == 'other'][:30])

# ------------------------------------------------------------------ V. The European Union, treaties and the euro
c18 = collections.defaultdict(collections.Counter)
for r in EU_ROWS:
    c18[r['y']][r['cat']] += 1
OUT['c18'] = {'years': [{'y': y, **c18[y]} for y in range(2004, LAST_YEAR + 1)],
              'top': [[k[0], k[1], k[2], n] for k, n in EU_COUNT.most_common(12)], 'acts': len(EU_COUNT)}
print('c18', [(r['y'], dict((k, v) for k, v in r.items() if k != 'y')) for r in OUT['c18']['years']], OUT['c18']['top'])

CTRY = [('US', r'съединените американски щати|сащ'), ('DE', r'германи'), ('AT', r'австри'), ('CH', r'швейцари'), ('NO', r'норвеги'),
        ('GR', r'гърци|елинск'), ('TR', r'турци|турск'), ('RU', r'руската федерация|руска федерация|русия|руск'), ('MK', r'македони'),
        ('RS', r'сърби|сръбск'), ('RO', r'румъни'), ('ME', r'черна гора|черногорск'), ('AL', r'албани'), ('HR', r'хървати'), ('SI', r'словени'),
        ('BA', r'босна'), ('XK', r'косово'), ('MD', r'молдов'), ('UA', r'украйн'), ('BY', r'беларус'), ('GE', r'грузи'), ('AM', r'армени'),
        ('AZ', r'азербайджан'), ('KZ', r'казахстан'), ('UZ', r'узбекистан'), ('TM', r'туркменистан'), ('KG', r'киргиз'), ('TJ', r'таджикистан'),
        ('MN', r'монголи'), ('CN', r'китай|китайск'), ('JP', r'япони'), ('KR', r'корея'), ('KP', r'корейската народнодемократична'), ('VN', r'виетнам'),
        ('IN', r'инди[яи]\b|индийск'), ('PK', r'пакистан'), ('ID', r'индонези'), ('TH', r'тайланд|таиланд'), ('SG', r'сингапур'), ('MY', r'малайзи'),
        ('PH', r'филипин'), ('AU', r'австрали'), ('NZ', r'нова зеландия'), ('CA', r'канада'), ('MX', r'мексик'), ('BR', r'бразили'), ('AR', r'аржентин'),
        ('CL', r'чили\b|чилийск'), ('CU', r'куба\b|кубинск'), ('EG', r'египет'), ('MA', r'мароко'), ('TN', r'тунис'), ('DZ', r'алжир'), ('LY', r'либи[яйи]'),
        ('IL', r'израел'), ('PS', r'палестин'), ('JO', r'йордани'), ('LB', r'ливан'), ('SY', r'сири[яи]\b|сирийск'), ('IQ', r'ирак'), ('IR', r'иран'),
        ('KW', r'кувейт'), ('QA', r'катар'), ('BH', r'бахрейн'), ('OM', r'оман\b'), ('AE', r'обединените арабски емирства'), ('SA', r'саудитска арабия'),
        ('YE', r'йемен'), ('AF', r'афганистан'), ('ZA', r'южна африка|южноафриканск'), ('NG', r'нигери'), ('FR', r'франци|френск'), ('IT', r'итали'),
        ('ES', r'испани'), ('PT', r'португали'), ('BE', r'белги'), ('NL', r'нидерланд|холанд'), ('LU', r'херцогство люксембург'), ('DK', r'дани[яи]\b|датск'),
        ('SE', r'швеци'), ('FI', r'финланди'), ('EE', r'естони'), ('LV', r'латви'), ('LT', r'литв'), ('PL', r'полша|полск'), ('CZ', r'чешк|чехи'),
        ('SK', r'словаш|словаки'), ('HU', r'унгари'), ('CY', r'кипър'), ('MT', r'малта'), ('IE', r'ирланди'), ('GB', r'обединеното кралство|великобритани'),
        ('IS', r'исланди'), ('LI', r'лихтенщайн'), ('MC', r'монако'), ('SM', r'сан марино'), ('AD', r'андора'), ('VA', r'светия престол|ватикан'),
        ('ET', r'етиопи'), ('KE', r'кения'), ('AO', r'ангола'), ('MZ', r'мозамбик'), ('LK', r'шри ланка'), ('BD', r'бангладеш'), ('BT', r'бутан'),
        ('NP', r'непал'), ('CO', r'колумби'), ('VE', r'венецуел'), ('PE', r'перу\b'), ('EC', r'еквадор'), ('UY', r'уругвай'), ('SN', r'сенегал'),
        ('TZ', r'танзани'), ('LA', r'лаос'), ('KH', r'камбоджа'), ('CR', r'коста рика'), ('PA', r'панама'), ('SD', r'судан'), ('MU', r'мавриций'),
        ('CV', r'кабо верде'), ('ZW', r'зимбабве'), ('ZM', r'замбия'), ('NA', r'намиби'), ('CM', r'камерун'), ('GN', r'гвинея'), ('CG', r'конго'),
        ('TW', r'тайван'), ('HK', r'хонконг')]
RAT_PER = [(2003, 2006), (2007, 2013), (2014, 2020), (2021, LAST_YEAR)]
c19 = collections.defaultdict(collections.Counter)
c19n = collections.Counter()
rat = [L0 for L0 in LAWS.values() if re.match(r'^Закон за ратифициране', L0['title'].strip())]
for L0 in rat:
    t = L0['title'].lower()
    t = re.sub(r'(народна )?република българия|българия|българск\w*', ' ', t)
    # the place a treaty was signed is not a party: "подписан(а) на 9 декември 2009 г. в Букурещ, Румъния"
    t = re.sub(r'(подписан|сключен|съставен|приет)\w*\s+(?:на\s+\d{1,2}\s+\S+\s+\d{4}\s*г\.?\s*)?(?:в|във)\s+[^,;()]+(?:,\s*[^,;()]+)?', ' ', t)
    hits = sorted({k for k, rx in CTRY if re.search(r'\b(?:' + rx + ')', t)})
    if 'KP' in hits and 'KR' in hits:
        hits.remove('KR')
    if 'AT' in hits and 'AU' in hits and 'австрали' not in t:
        hits.remove('AU')
    if not hits or len(hits) > 3:
        hits = ['multi']
    p = next(i for i, (p0, p1) in enumerate(RAT_PER) if p0 <= L0['y'] <= p1)
    for k in hits:
        c19[k][p] += 1
        c19n[k] += 1
OUT['c19'] = {'rows': [{'k': k, 'n': n, 'by': [c19[k][i] for i in range(len(RAT_PER))]} for k, n in c19n.most_common()],
              'laws': len(rat), 'periods': [f'{p0}–{p1}' for p0, p1 in RAT_PER]}
print('c19', len(rat), c19n.most_common(40))

# c20: money in the texts of laws: amounts written in leva and in euro
OUT['c20'] = [{'y': y, 'lev': MONEY[y]['lev'], 'eur': MONEY[y]['eur'], 'laws': MONEY[y]['laws']} for y in range(2004, LAST_YEAR + 1)]
print('c20', OUT['c20'])

# ------------------------------------------------------------------ profile
PROFILE.update({
    'commits': N_COMMITS, 'head': os.environ.get('HEAD_SHA', ''), 'built': BUILT, 'made': date.today().isoformat(),
    'kinds': dict(collections.Counter(KIND5[a['k']] for a in ACTS)), 'laws_with_record': sum(1 for r in LAWREC if r['ev']),
    'amend_events': T5, 'first_pub': min(a['pub'] for a in ACTS if a['pub']), 'held_reasons': dict(collections.Counter(h['reason'] for h in HELD).most_common(6)),
    'other_authors': dict(OTHER_AUTHORS), 'laws_csv': n_csv, 'held_outside': len(HELD_OUTSIDE),
})
json.dump({'charts': OUT, 'profile': PROFILE}, open(os.path.join(B, 'data.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'), default=list)
print('profile', PROFILE)
