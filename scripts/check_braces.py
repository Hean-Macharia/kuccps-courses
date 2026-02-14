from pathlib import Path
s=Path('app.py').read_text()
bal=0
for i,line in enumerate(s.splitlines(),1):
    for ch in line:
        if ch=='{': bal+=1
        elif ch=='}': bal-=1
        if bal<0:
            print('Negative balance at line',i)
            raise SystemExit
print('Final balance:',bal)
print('Scan complete')
