## Quick Start: Use Repo Control Center

1. Download and start MongoDB Daemon. You can download it [here](https://www.mongodb.com/download-center/community)

```bash
Ubuntu:bin yufengzh$ sudo ./mongod
```

2. Start repo-daemon, which will automatically start Repo

```bash
Ubuntu:dev yufengzh$ cd NDN-Repo/
Ubuntu:NDN-Repo yufengzh$ source venv/bin/activate
(venv) Ubuntu:NDN-Repo yufengzh$ python repo_daemon.py

```

3. Start control-center

```bash
(venv) Ubuntu:NDN-Repo yufengzh$ python control_center.py
```

4. Go to control center http://localhost:1234 on your Web browser, where you can add dummy Data, see what Data is in the Repo, delete Data, start/stop/restart Repo, test Repo, etc.