import sys
ok = True
for fn in sys.argv[1:]:
    for line in open(fn):
        line = line.strip()
        if not line: continue
        tid, fin, n, cs, data = line.split('|')
        nums = [int(x) for x in data.split(',')]
        c = 0
        for i, v in enumerate(nums):
            c = (c + abs(v) * ((i % 7) + 1)) % 1000003
        good = (c == int(cs)) and (len(nums) == 3 * int(n))
        ok &= good
        print(fn, tid, 'n', n, len(nums)//3, 'cs', cs, c, 'OK' if good else 'MISMATCH')
print('ALL OK' if ok else 'ERRORS')
