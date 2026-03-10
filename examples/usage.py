import subprocess, sys

def run(cmd):
    p = subprocess.run(cmd, shell=True)
    return p.returncode

def main():
    run("python gxost.x6.py --help")
    run("python gxost.x6.py social octocat --json")
    run("python gxost.x6.py domain example.com --json")
    run("python gxost.x6.py meta https://example.com --json")

if __name__ == "__main__":
    main()
