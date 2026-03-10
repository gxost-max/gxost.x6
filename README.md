# GXOST X6

## Clone
```
git clone https://github.com/YOUR_USER/gxost.x6.git
cd gxost.x6
```

## Run
- Python:
```
python3 gxost.x6.py
# or
python gxost.x6.py
```

## Publish to GitHub
- Create an empty repository on GitHub (e.g., `gxost.x6`)
- Then run:
```
powershell -ExecutionPolicy Bypass -File .\publish.ps1 -User YOUR_USER -Repo gxost.x6
# or use SSH if you have keys configured:
powershell -ExecutionPolicy Bypass -File .\publish.ps1 -User YOUR_USER -Repo gxost.x6 -UseSSH
```
If prompted, sign in or paste a Personal Access Token when using HTTPS. If you see "repository not found", create the repo on GitHub and re-run the command.

## CLI Examples
```
python gxost.x6.py --help
python gxost.x6.py social octocat --json
python gxost.x6.py email test@example.com --json
python gxost.x6.py phone +905551234567 --json
python gxost.x6.py domain example.com --json
python gxost.x6.py meta https://example.com --json
python gxost.x6.py dark crash --json
```
